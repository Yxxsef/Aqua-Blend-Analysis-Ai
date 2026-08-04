"""
Tests for the reporting layer.

What this layer guarantees: a number reaches the document without being
retyped, a failed run stays visible in the table, and a cluster profile
is expressed in the measured features rather than a reduced space.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from xxcluster.core.base import BaseClusterer
from xxcluster.core.mixins import NoiseAwareMixin
from xxcluster.core.registry import ComponentRegistry
from xxcluster.core.tags import Capabilities
from xxcluster.core.types import ComponentKind, Family, SubFamily
from xxcluster.evaluation import report as report_module
from xxcluster.evaluation.protocol import Protocol, RunResult
from xxcluster.evaluation.report import ComparisonRun, ComparisonTable, profile_clusters
from xxcluster.measures.validation.base import BaseValidityIndex


@pytest.fixture
def registry(monkeypatch) -> ComponentRegistry:
    registry = ComponentRegistry()

    @registry.register("kmeans", kind=ComponentKind.CLUSTERER)
    class KMeans:
        _capabilities = Capabilities(
            family=Family.PARTITIONAL,
            subfamily=SubFamily.SSE_BASED,
            requires_n_clusters=True,
        )

    @registry.register("dbscan", kind=ComponentKind.CLUSTERER)
    class DBSCAN:
        _capabilities = Capabilities(
            family=Family.PARTITIONAL,
            subfamily=SubFamily.DENSITY_BASED,
            handles_noise=True,
        )

    monkeypatch.setattr(report_module, "REGISTRY", registry)
    return registry


@pytest.fixture
def results() -> list[RunResult]:
    return [
        RunResult(
            "kmeans",
            scores={"silhouette": 0.55, "davies_bouldin": 0.66},
            n_clusters_found=3,
            fit_seconds=0.02,
        ),
        RunResult(
            "dbscan",
            scores={"silhouette": 0.41, "davies_bouldin": 0.90},
            n_clusters_found=2,
            n_noise=17,
            fit_seconds=0.11,
        ),
        RunResult("ward", error="backend unavailable"),
    ]


# --- ComparisonRun ---------------------------------------------------------


class _Alternating(BaseClusterer):
    """Deterministic clusterer, so a test asserts on the run, not on it."""

    def __init__(self, n_clusters=2, *, random_state=None, n_init=10):
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.n_init = n_init

    def _fit(self, X, y=None, **fit_params):
        self.seen_ = np.asarray(X)
        self.labels_ = np.arange(len(self.seen_)) % self.n_clusters
        self.n_clusters_ = self.n_clusters


class _Noisy(NoiseAwareMixin, BaseClusterer):
    _capabilities = Capabilities(handles_noise=True)

    def __init__(self, *, random_state=None):
        self.random_state = random_state

    def _fit(self, X, y=None, **fit_params):
        self.labels_ = np.array([-1] + [0] * (len(X) - 1))
        self.n_clusters_ = 1


class _Broken(BaseClusterer):
    def _fit(self, X, y=None, **fit_params):
        raise RuntimeError("no backend")


class _MeanLabel(BaseValidityIndex):
    name = "mean_label"
    higher_is_better = True

    def score(self, X=None, labels=None, *, labels_true=None, metric="euclidean", **kwargs):
        return float(np.mean(labels))


class _Fussy(BaseValidityIndex):
    """Stands for an index that declines a partition it cannot read."""

    name = "fussy"
    higher_is_better = False

    def score(self, X=None, labels=None, *, labels_true=None, metric="euclidean", **kwargs):
        if (np.asarray(labels) == -1).any():
            raise ValueError("undefined on noise")
        return float(np.max(labels))


class _External(BaseValidityIndex):
    name = "external"
    higher_is_better = True
    requires_labels_true = True

    def score(self, X=None, labels=None, *, labels_true=None, metric="euclidean", **kwargs):
        return float(np.mean(np.asarray(labels) == np.asarray(labels_true)))


@pytest.fixture
def live_registry(monkeypatch) -> ComponentRegistry:
    """A registry holding components that actually fit, unlike `registry`."""
    live = ComponentRegistry()
    live.register("alternating", kind=ComponentKind.CLUSTERER)(_Alternating)
    live.register("noisy", kind=ComponentKind.CLUSTERER)(_Noisy)
    live.register("broken", kind=ComponentKind.CLUSTERER)(_Broken)
    for index in (_MeanLabel, _Fussy, _External):
        live.register(index.name, kind=ComponentKind.VALIDITY_INDEX)(index)
    monkeypatch.setattr(report_module, "REGISTRY", live)
    return live


@pytest.fixture
def X() -> np.ndarray:
    return np.arange(24, dtype=float).reshape(12, 2)


def test_one_result_per_method_in_order(live_registry, X):
    run = ComparisonRun(["alternating", "noisy"], protocol=Protocol())
    results = run.run(X)
    assert [r.method for r in results] == ["alternating", "noisy"]
    assert run.results_ is results


def test_a_failing_method_is_recorded_and_the_others_still_run(live_registry, X):
    results = ComparisonRun(["broken", "alternating"], protocol=Protocol()).run(X)
    assert results[0].failed and "no backend" in results[0].error
    assert not results[1].failed


def test_a_component_is_named_by_its_registered_name(live_registry, X):
    results = ComparisonRun([_Alternating(n_clusters=3)], protocol=Protocol()).run(X)
    assert results[0].method == "alternating"
    assert results[0].n_clusters_found == 3


def test_seeds_are_derived_from_the_protocol_and_differ_per_method(live_registry, X):
    protocol = Protocol(random_state=7)
    results = ComparisonRun(["alternating", "noisy"], protocol=protocol).run(X)
    assert results[0].params["random_state"] == protocol.seed_for(
        "alternating:random_state"
    )
    assert results[0].params["random_state"] != results[1].params["random_state"]


def test_restarts_reach_the_methods_n_init(live_registry, X):
    protocol = Protocol(n_restarts=3)
    results = ComparisonRun(["alternating"], protocol=protocol).run(X)
    assert results[0].params["n_init"] == 3


def test_preprocessing_is_shared_and_the_protocols_own_copy_is_untouched(
    live_registry, X
):
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()
    method = _Alternating()
    ComparisonRun([method], protocol=Protocol(preprocessing=scaler)).run(X)

    # `clone` is what makes a protocol reusable across datasets.
    assert not hasattr(scaler, "n_features_in_")


def test_an_index_that_refuses_the_result_scores_nan_rather_than_failing_the_run(
    live_registry, X
):
    protocol = Protocol(indices=["fussy", "mean_label"])
    result = ComparisonRun(["noisy"], protocol=protocol).run(X)[0]
    assert not result.failed
    assert np.isnan(result.scores["fussy"])
    assert not np.isnan(result.scores["mean_label"])


def test_an_external_index_without_a_reference_scores_nan(live_registry, X):
    protocol = Protocol(indices=["external"])
    assert np.isnan(ComparisonRun(["alternating"], protocol=protocol).run(X)[0].scores["external"])
    scored = ComparisonRun(["alternating"], protocol=protocol).run(
        X, y=np.arange(12) % 2
    )
    assert scored[0].scores["external"] == 1.0


def test_an_unknown_index_is_refused_before_anything_is_fitted(live_registry, X):
    from xxcluster.core.exceptions import RegistryError

    with pytest.raises(RegistryError, match="no_such_index"):
        ComparisonRun(["alternating"], protocol=Protocol(indices=["no_such_index"])).run(X)


def test_noise_is_counted_only_where_the_method_declares_it(live_registry, X):
    results = ComparisonRun(["alternating", "noisy"], protocol=Protocol()).run(X)
    assert results[0].n_noise is None
    assert results[1].n_noise == 1


# --- best ------------------------------------------------------------------


def test_best_applies_the_indexs_direction(live_registry, X):
    run = ComparisonRun([_Alternating(n_clusters=2), _Alternating(n_clusters=4)])
    run.protocol = Protocol(indices=["mean_label", "fussy"])
    run.run(X)
    assert run.best("mean_label").n_clusters_found == 4   # higher is better
    assert run.best("fussy").n_clusters_found == 2        # lower is better


def test_best_refuses_when_no_run_scored(live_registry, X):
    run = ComparisonRun(["noisy"], protocol=Protocol(indices=["fussy"]))
    run.run(X)
    with pytest.raises(ValueError, match="no run produced a finite"):
        run.best("fussy")


def test_best_before_a_run_is_refused(live_registry):
    with pytest.raises(ValueError, match="call run\\(\\) first"):
        ComparisonRun(["alternating"]).best("mean_label")


# --- Quantitative ----------------------------------------------------------


def test_one_row_per_run_indexed_by_method(results):
    table = ComparisonTable(results).quantitative()
    assert list(table.index) == ["kmeans", "dbscan", "ward"]


def test_scores_become_columns(results):
    table = ComparisonTable(results).quantitative()
    assert table.loc["kmeans", "silhouette"] == 0.55


def test_a_failed_run_is_kept_with_its_error(results):
    """A comparison that drops what did not work reads as though it all worked."""
    table = ComparisonTable(results).quantitative()
    assert table.loc["ward", "error"] == "backend unavailable"
    assert np.isnan(table.loc["ward", "silhouette"])


def test_a_column_no_method_reported_is_dropped():
    table = ComparisonTable([RunResult("kmeans", scores={"silhouette": 0.5})]).quantitative()
    assert "n_noise" not in table.columns
    assert "error" not in table.columns


def test_no_results_yields_an_empty_table():
    assert ComparisonTable([]).quantitative().empty


# --- Qualitative -----------------------------------------------------------


def test_capabilities_come_from_the_registry(registry, results):
    table = ComparisonTable(results).qualitative()
    assert table.loc["kmeans", "subfamily"] == "sse_based"
    assert bool(table.loc["dbscan", "handles_noise"])


def test_an_unregistered_method_shows_as_a_gap(registry, results):
    """Visible in the table, which is the point."""
    table = ComparisonTable(results).qualitative()
    assert table.loc["ward"].isna().all()


# --- Export ----------------------------------------------------------------


def test_csv_round_trips(tmp_path, results):
    path = tmp_path / "results.csv"
    ComparisonTable(results).to_csv(path)
    assert pd.read_csv(path).loc[0, "silhouette"] == 0.55


def test_latex_emits_the_documents_tabularx_form(tmp_path, results):
    path = tmp_path / "results.tex"
    ComparisonTable(results).to_latex(path, label="tab:comparison:metrics")
    text = path.read_text()
    assert r"\begin{tabularx}{\textwidth}{@{}L" in text
    assert r"\toprule" in text and r"\bottomrule" in text
    assert r"\label{tab:comparison:metrics}" in text


def test_latex_omits_the_float_so_the_caption_stays_in_the_prose(tmp_path, results):
    path = tmp_path / "results.tex"
    ComparisonTable(results).to_latex(path)
    assert r"\begin{table}" not in path.read_text()


def test_underscores_in_names_are_escaped(tmp_path, results):
    """An unescaped one is a compile error rather than a wrong number."""
    path = tmp_path / "results.tex"
    ComparisonTable(results).to_latex(path)
    assert r"davies\_bouldin" in path.read_text()


def test_counts_render_as_integers_and_scores_as_decimals(tmp_path, results):
    path = tmp_path / "results.tex"
    ComparisonTable(results).to_latex(path)
    row = [line for line in path.read_text().splitlines() if "dbscan" in line][0]
    assert "& 2 &" in row
    assert "0.410" in row


def test_missing_values_render_as_the_documents_dash(tmp_path, results):
    path = tmp_path / "results.tex"
    ComparisonTable(results).to_latex(path)
    assert "--" in [line for line in path.read_text().splitlines() if "ward" in line][0]


def test_columns_can_be_selected_and_ordered(tmp_path, registry, results):
    """Capabilities has seventeen fields and no page fits them."""
    path = tmp_path / "q.tex"
    ComparisonTable(results).to_latex(
        path, which="qualitative", columns=["subfamily", "handles_noise"]
    )
    header = path.read_text().splitlines()[3]
    assert header.count("&") == 2


def test_an_unknown_table_is_refused(tmp_path, results):
    with pytest.raises(ValueError, match="quantitative"):
        ComparisonTable(results).to_csv(tmp_path / "x.csv", which="sideways")


# --- Cluster profiles ------------------------------------------------------


@pytest.fixture
def frame() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "ph": np.concatenate([rng.normal(7.0, 0.1, 20), rng.normal(8.5, 0.1, 20)]),
            "turbidity_ntu": np.concatenate(
                [rng.normal(1.0, 0.1, 20), rng.normal(1.1, 0.1, 20)]
            ),
        }
    )


@pytest.fixture
def labels() -> np.ndarray:
    return np.array([0] * 20 + [1] * 20)


def test_profile_is_indexed_by_cluster(frame, labels):
    profile = profile_clusters(frame, labels)
    assert list(profile.index) == [0, 1]


def test_profile_reports_size_and_share(frame, labels):
    profile = profile_clusters(frame, labels)
    assert profile.loc[0, ("", "size")] == 20
    assert profile.loc[0, ("", "share")] == pytest.approx(0.5)


def test_profile_reports_means_in_original_units(frame, labels):
    """Never a scaled or reduced representation -- that is the whole point."""
    profile = profile_clusters(frame, labels)
    assert profile.loc[1, ("ph", "mean")] == pytest.approx(8.5, abs=0.1)


def test_separation_identifies_the_distinguishing_feature(frame, labels):
    """pH separates the clusters; turbidity barely does."""
    profile = profile_clusters(frame, labels)
    assert abs(profile.loc[0, ("ph", "separation")]) > abs(
        profile.loc[0, ("turbidity_ntu", "separation")]
    )


def test_noise_is_profiled_rather_than_dropped(frame, labels):
    """How many a method declined to assign, and where they sit, is a result."""
    noisy = labels.copy()
    noisy[:3] = -1
    profile = profile_clusters(frame, noisy)
    assert -1 in profile.index
    assert profile.loc[-1, ("", "size")] == 3


def test_arrays_get_positional_feature_names(labels):
    profile = profile_clusters(np.random.default_rng(0).normal(size=(40, 2)), labels)
    assert ("x0", "mean") in profile.columns


def test_supplied_feature_names_are_used(labels):
    profile = profile_clusters(
        np.random.default_rng(0).normal(size=(40, 2)), labels, feature_names=["a", "b"]
    )
    assert ("a", "mean") in profile.columns


def test_length_mismatch_is_caught(frame):
    with pytest.raises(ValueError, match="observations but labels"):
        profile_clusters(frame, np.zeros(5, dtype=int))
