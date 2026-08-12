"""
Tests for the dataset layer.

What this layer guarantees: the columns a method sees are the ones declared
for it, the schema is checked against the source, and the window the data
covers travels with it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from xxcluster.io.datasets import (
    Dataset,
    FeatureSpec,
    features_from_names,
)
from xxcluster.io.loaders import BenchmarkLoader, CsvLoader, FrameLoader, ParquetLoader

FEATURES = [
    FeatureSpec("ph", unit="pH", role="cluster", valid_range=(0, 14)),
    FeatureSpec("turbidity_ntu", unit="NTU", role="cluster", valid_range=(0, None)),
    FeatureSpec("cost_per_ml", unit="$/ML", role="interpret"),
    FeatureSpec("source_id", dtype="str", role="identifier"),
]


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ph": [7.1, 7.4, 6.9, 7.0],
            "turbidity_ntu": [1.2, 0.8, 3.4, 1.1],
            "cost_per_ml": [120.0, 95.0, 140.0, 110.0],
            "source_id": ["A", "B", "C", "D"],
        }
    )


@pytest.fixture
def dataset(frame: pd.DataFrame) -> Dataset:
    return FrameLoader(frame, FEATURES, description="fixture", data_cutoff="2026-08-01").load()


# --- Roles -----------------------------------------------------------------


def test_cluster_matrix_holds_back_interpretation_columns(dataset):
    assert list(dataset.cluster_matrix().columns) == ["ph", "turbidity_ntu"]


def test_interpretation_frame_returns_the_held_out_columns(dataset):
    assert list(dataset.interpretation_frame().columns) == ["cost_per_ml"]


def test_identifier_is_not_clustered_on(dataset):
    """Clustering on a key would partition by row, not by behaviour."""
    assert "source_id" not in dataset.cluster_matrix().columns


def test_names_filters_by_role(dataset):
    assert dataset.names("cluster") == ["ph", "turbidity_ntu"]
    assert dataset.names() == [f.name for f in FEATURES]


def test_unknown_role_is_rejected():
    with pytest.raises(ValueError, match="unknown role"):
        FeatureSpec("ph", role="clusterr")


# --- Container handling ----------------------------------------------------


def test_array_input_selects_positionally():
    numeric = [f for f in FEATURES if f.name != "source_id"]
    data = np.array([[7.1, 1.2, 120.0], [7.4, 0.8, 95.0]])
    ds = FrameLoader(data, numeric).load()
    np.testing.assert_allclose(ds.cluster_matrix(), [[7.1, 1.2], [7.4, 0.8]])


def test_frame_in_frame_out(dataset):
    assert isinstance(dataset.cluster_matrix(), pd.DataFrame)


def test_mismatched_column_count_is_caught(frame):
    with pytest.raises(ValueError, match="feature specs describe a matrix"):
        Dataset(X=frame, features=FEATURES[:2])


# --- Schema validation -----------------------------------------------------


def test_missing_column_is_caught(frame):
    with pytest.raises(ValueError, match="missing turbidity_ntu"):
        FrameLoader(frame.drop(columns=["turbidity_ntu"]), FEATURES).load()


def test_undeclared_column_is_caught(frame):
    """A source that grew a column silently is a change nobody recorded."""
    with pytest.raises(ValueError, match="undeclared chlorine_mg_l"):
        FrameLoader(frame.assign(chlorine_mg_l=0.5), FEATURES).load()


def test_columns_are_reordered_to_the_declared_order(frame):
    shuffled = frame[["source_id", "cost_per_ml", "ph", "turbidity_ntu"]]
    ds = FrameLoader(shuffled, FEATURES).load()
    assert ds.names() == list(ds.X.columns)


def test_a_loader_without_a_schema_is_refused(frame):
    with pytest.raises(ValueError, match="role cannot be inferred"):
        FrameLoader(frame, [])


# --- Ranges ----------------------------------------------------------------


def test_in_range_data_reports_no_violations(dataset):
    assert dataset.check_ranges().empty


def test_out_of_range_value_is_reported(frame):
    bad = frame.copy()
    bad.loc[0, "ph"] = 15.2
    violations = FrameLoader(bad, FEATURES).load().check_ranges()
    assert violations.loc[0, "feature"] == "ph"
    assert violations.loc[0, "n_violations"] == 1


def test_one_sided_range_is_honoured(frame):
    bad = frame.copy()
    bad.loc[1, "turbidity_ntu"] = -0.5
    violations = FrameLoader(bad, FEATURES).load().check_ranges()
    assert list(violations["feature"]) == ["turbidity_ntu"]


# --- Summary ---------------------------------------------------------------


def test_summary_covers_every_declared_column(dataset):
    assert list(dataset.summary().index) == [f.name for f in FEATURES]


def test_summary_reports_missingness(frame):
    holed = frame.copy()
    holed.loc[0, "ph"] = np.nan
    summary = FrameLoader(holed, FEATURES).load().summary()
    assert summary.loc["ph", "missing"] == 1
    assert summary.loc["ph", "count"] == 3


def test_summary_tolerates_non_numeric_columns(dataset):
    """Statistics are left empty rather than the column being dropped.

    NaN, not None: the column is float dtype because the numeric features
    fill it, which is pandas doing the right thing.
    """
    summary = dataset.summary()
    assert pd.isna(summary.loc["source_id", "min"])
    assert summary.loc["source_id", "count"] == 4


# --- Provenance ------------------------------------------------------------


def test_cutoff_is_recorded(dataset):
    assert dataset.provenance["data_cutoff"] == "2026-08-01"


def test_provenance_statement_states_the_window(dataset):
    statement = dataset.provenance_statement()
    assert "used up until 2026-08-01" in statement
    assert "4 observations" in statement


def test_missing_cutoff_is_stated_not_hidden(frame):
    statement = FrameLoader(frame, FEATURES).load().provenance_statement()
    assert "no cutoff recorded" in statement


def test_describe_does_not_need_to_load(frame):
    loader = FrameLoader(frame, FEATURES, description="fixture", data_cutoff="2026-08-01")
    assert loader.describe()["data_cutoff"] == "2026-08-01"


def test_with_provenance_adds_without_mutating(dataset):
    extended = dataset.with_provenance(view="analysis.source_quality")
    assert extended.provenance["view"] == "analysis.source_quality"
    assert "view" not in dataset.provenance


def test_index_comes_from_the_identifier_column(dataset):
    np.testing.assert_array_equal(dataset.index, ["A", "B", "C", "D"])


# --- File loaders ----------------------------------------------------------


def test_csv_round_trip(tmp_path, frame):
    path = tmp_path / "extract.csv"
    frame.to_csv(path, index=False)
    ds = CsvLoader(path, FEATURES, data_cutoff="2026-08-01").load()
    assert ds.n_observations == 4
    assert ds.provenance["source"] == str(path)


def test_parquet_round_trip(tmp_path, frame):
    path = tmp_path / "extract.parquet"
    frame.to_parquet(path)
    assert ParquetLoader(path, FEATURES).load().n_observations == 4


def test_missing_file_is_reported_clearly(tmp_path):
    with pytest.raises(FileNotFoundError, match="no extract at"):
        CsvLoader(tmp_path / "absent.csv", FEATURES).load()


# --- Benchmarks ------------------------------------------------------------


def test_benchmark_loads_with_a_derived_schema():
    ds = BenchmarkLoader("iris").load()
    assert ds.n_observations == 150
    assert len(ds.names("cluster")) == 4


def test_published_labels_are_held_out_not_clustered_on():
    ds = BenchmarkLoader("iris").load()
    assert "target" not in ds.names("cluster")
    assert ds.names("interpret") == ["target"]


def test_true_labels_are_reachable_for_external_indices():
    loader = BenchmarkLoader("iris")
    assert len(np.unique(loader.true_labels(loader.load()))) == 3


def test_labels_can_be_excluded_entirely():
    ds = BenchmarkLoader("iris", include_labels=False).load()
    assert ds.names("interpret") == []


def test_unknown_benchmark_is_refused():
    with pytest.raises(ValueError, match="unknown benchmark"):
        BenchmarkLoader("aquablend")


# --- Helper ----------------------------------------------------------------


def test_features_from_names_builds_a_uniform_schema():
    specs = features_from_names(["a", "b"], unit="m")
    assert [s.name for s in specs] == ["a", "b"]
    assert all(s.role == "cluster" and s.unit == "m" for s in specs)
