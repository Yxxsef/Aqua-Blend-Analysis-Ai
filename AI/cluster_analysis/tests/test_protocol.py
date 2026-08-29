"""
Tests for the experimental protocol.

What App. A promises: a result can be traced back to the code, versions and
seed that produced it. These pin the parts of that promise the protocol is
responsible for.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from sklearn.preprocessing import StandardScaler

from xxcluster.evaluation.protocol import (
    Environment,
    Protocol,
    RunResult,
    _capture_environment,
)

ROOT = Path(__file__).resolve().parent.parent


# --- Environment -----------------------------------------------------------


def test_capture_records_the_running_python():
    import platform

    assert Environment.capture().python_version == platform.python_version()


def test_capture_records_the_core_package_versions():
    versions = Environment.capture().package_versions
    assert {"numpy", "scipy", "scikit-learn"} <= set(versions)
    import sklearn

    assert versions["scikit-learn"] == sklearn.__version__


def test_absent_optional_backends_are_skipped_not_reported_missing():
    versions = Environment.capture().package_versions
    pytest.importorskip  # noqa: B018 - documenting intent
    assert "hdbscan" not in versions or versions["hdbscan"]


def test_capture_is_cached():
    _capture_environment.cache_clear()
    assert Environment.capture() is Environment.capture()


def test_revision_is_a_commit_or_none():
    revision = Environment.capture().revision
    assert revision is None or revision.split("-")[0].isalnum()


def test_summary_names_the_versions():
    summary = Environment.capture().summary()
    assert "Python" in summary and "numpy" in summary


# --- Seed derivation -------------------------------------------------------


def test_seed_is_deterministic():
    protocol = Protocol(random_state=42)
    assert protocol.seed_for("kmeans") == protocol.seed_for("kmeans")


def test_different_keys_get_different_seeds():
    protocol = Protocol(random_state=42)
    assert protocol.seed_for("kmeans") != protocol.seed_for("hdbscan")


def test_root_seed_shifts_the_whole_family():
    assert Protocol(random_state=1).seed_for("kmeans") != Protocol(random_state=2).seed_for("kmeans")


def test_seed_fits_in_32_bits():
    protocol = Protocol(random_state=42)
    for key in ("kmeans", "ward", "hdbscan", "som"):
        assert 0 <= protocol.seed_for(key) < 2**32


def test_seed_survives_a_new_process_with_a_different_hash_seed():
    """The trap this derivation exists to avoid.

    Python's built-in `hash` is salted per process, so a seed built from it
    would differ between runs of the same script -- reproducible-looking
    code that is not reproducible.
    """
    script = (
        "from xxcluster.evaluation.protocol import Protocol;"
        "print(Protocol(random_state=42).seed_for('kmeans'))"
    )
    seeds = set()
    for hash_seed in ("0", "12345"):
        out = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={"PYTHONHASHSEED": hash_seed, "PATH": "/usr/bin:/bin"},
            check=True,
        )
        seeds.add(out.stdout.strip())
    assert len(seeds) == 1, f"seed changed with PYTHONHASHSEED: {seeds}"


def test_no_root_seed_still_derives_deterministically():
    assert Protocol().seed_for("kmeans") == Protocol().seed_for("kmeans")


# --- Serialisation ---------------------------------------------------------


def test_to_dict_is_json_serialisable():
    protocol = Protocol(
        indices=["silhouette", "davies_bouldin"],
        random_state=42,
        preprocessing=StandardScaler(),
        n_clusters_candidates=range(2, 6),
    )
    json.dumps(protocol.to_dict())  # must not raise


def test_preprocessing_is_stored_as_class_and_params_not_repr():
    stored = Protocol(preprocessing=StandardScaler(with_mean=False)).to_dict()["preprocessing"]
    assert stored["class"] == "StandardScaler"
    assert stored["params"]["with_mean"] is False


def test_to_dict_carries_the_environment():
    stored = Protocol(random_state=1).to_dict()
    assert stored["environment"]["package_versions"]["numpy"]


# --- Construction ----------------------------------------------------------


def test_environment_is_captured_at_construction():
    assert Protocol().environment is not None


def test_supplied_environment_is_kept():
    """A protocol read back from an artefact keeps the environment it ran under."""
    stored = Environment(python_version="3.9.0", platform="old")
    assert Protocol(environment=stored).environment is stored


def test_protocol_is_frozen():
    with pytest.raises(Exception):
        Protocol().n_restarts = 5


@pytest.mark.parametrize(
    "field, kwargs",
    [
        ("preprocessing", {"preprocessing": ...}),
        ("indices", {"indices": [...]}),
        ("n_clusters_candidates", {"n_clusters_candidates": ...}),
    ],
)
def test_an_unfilled_template_placeholder_is_refused_naming_the_field(field, kwargs):
    with pytest.raises(ValueError, match=field):
        Protocol(**kwargs)


def test_none_and_empty_are_answers_not_placeholders():
    protocol = Protocol(indices=["silhouette"], preprocessing=None, n_clusters_candidates=())
    assert protocol.preprocessing is None


# --- Prose -----------------------------------------------------------------


def test_describe_mentions_the_setup():
    prose = Protocol(
        indices=["silhouette", "calinski_harabasz"],
        n_restarts=25,
        random_state=42,
        n_clusters_candidates=range(2, 11),
    ).describe()
    assert "silhouette and calinski_harabasz" in prose
    assert "25 restarts" in prose
    assert "2--10" in prose
    assert "root random seed is 42" in prose


def test_describe_says_so_when_no_seed_is_set():
    assert "limits reproducibility" in Protocol().describe()


def test_describe_handles_a_single_index():
    assert "scored on silhouette," in Protocol(indices=["silhouette"]).describe()


# --- RunResult -------------------------------------------------------------


def test_run_result_failed_flag():
    assert not RunResult(method="kmeans").failed
    assert RunResult(method="kmeans", error="did not converge").failed
