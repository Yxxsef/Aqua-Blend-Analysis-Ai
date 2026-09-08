"""
Tests for the native DBSCAN in
``xxcluster/cluster/partitional/density_based/dbscan.py``.

Five groups. First, that the implementation reproduces the reference
one exactly -- labels and core points -- since a native method has to be
shown to behave as published before its results on project data are
trusted. Second, the family contract: noise is -1, ``n_clusters_`` and
``n_noise_`` are recounted from the labels on every fit, and the -1
convention is enforced by the base. Third, the properties the method is
chosen for: arbitrary cluster shape, and the refusal to assign a rare
state. Fourth, the declarations, which Sect. 8.2's table is generated
from. Fifth, that noise is traceable back to the period it came from,
which is what makes a rare state something the operations team can be
asked about.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.spatial.distance import pdist, squareform
from sklearn.cluster import DBSCAN as ReferenceDBSCAN
from sklearn.datasets import make_blobs, make_moons

from xxcluster.cluster.partitional.density_based.dbscan import DBSCAN
from xxcluster.core.exceptions import ContractViolationError
from xxcluster.core.registry import REGISTRY
from xxcluster.core.types import (
    NOISE_LABEL,
    Assignment,
    Backend,
    ComponentKind,
    Family,
    SubFamily,
)


# ---------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def moons() -> np.ndarray:
    """Two interleaving crescents: shape no centroid method can recover."""
    X, _ = make_moons(n_samples=200, noise=0.06, random_state=0)
    return X


@pytest.fixture(scope="module")
def blobs_with_rare_states() -> np.ndarray:
    """Three dense groups plus three isolated points.

    The isolated points stand for rare operating states: far from every
    dense region, so a method that assigns everything would have to fold
    them into a regime.
    """
    X, _ = make_blobs(n_samples=150, centers=3, cluster_std=0.5, random_state=1)
    rare = np.array([[12.0, 12.0], [-11.0, 9.0], [13.0, -10.0]])
    return np.vstack([X, rare])


# ---------------------------------------------------------------------
# Group 1: agreement with the reference implementation.
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "eps,min_samples",
    [(0.25, 5), (0.3, 3), (0.2, 10), (0.5, 5)],
)
def test_labels_match_the_reference_implementation(moons, eps, min_samples):
    """Same partition, cluster for cluster, not merely the same count.

    Label *values* are compared directly rather than up to a permutation:
    both implementations number clusters in order of first appearance
    scanning by index, so an exact match also pins the scan order, which
    is what makes a border point's assignment reproducible.
    """
    ours = DBSCAN(eps=eps, min_samples=min_samples).fit(moons)
    theirs = ReferenceDBSCAN(eps=eps, min_samples=min_samples).fit(moons)
    np.testing.assert_array_equal(ours.labels_, theirs.labels_)


def test_core_points_match_the_reference_implementation(blobs_with_rare_states):
    """The core/border/noise split, not just the final labels."""
    ours = DBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states)
    theirs = ReferenceDBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states)
    np.testing.assert_array_equal(
        ours.core_sample_indices_, theirs.core_sample_indices_
    )


def test_a_precomputed_matrix_gives_the_same_partition(blobs_with_rare_states):
    """The route a custom measure reaches this family by must not change the result."""
    dense = DBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states)
    D = squareform(pdist(blobs_with_rare_states, metric="euclidean"))
    precomputed = DBSCAN(eps=0.7, min_samples=5, metric="precomputed").fit(D)
    np.testing.assert_array_equal(precomputed.labels_, dense.labels_)


# ---------------------------------------------------------------------
# Group 2: the family contract.
# ---------------------------------------------------------------------
def test_noise_is_minus_one(blobs_with_rare_states):
    """ARCHITECTURE.md 7: noise is -1, everywhere."""
    model = DBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states)
    assert NOISE_LABEL in model.labels_
    assert model.labels_.min() == NOISE_LABEL
    # Clusters are numbered from zero with no gaps, so -1 is unambiguous.
    assigned = np.unique(model.labels_[model.labels_ != NOISE_LABEL])
    np.testing.assert_array_equal(assigned, np.arange(model.n_clusters_))


def test_counts_are_results_derived_from_the_labels(blobs_with_rare_states):
    """`n_clusters_` and `n_noise_` must agree with `labels_`, not be asserted."""
    model = DBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states)
    labels = model.labels_
    assert model.n_noise_ == int(np.sum(labels == NOISE_LABEL))
    assert model.n_clusters_ == int(
        np.unique(labels[labels != NOISE_LABEL]).size
    )


def test_counts_are_recounted_on_refit(moons, blobs_with_rare_states):
    """A refit must not report the previous fit's noise against new labels.

    The failure the family base recounts to prevent: fit once on data with
    no noise, then on data with some, and read a stale zero.
    """
    model = DBSCAN(eps=0.25, min_samples=5).fit(moons)
    assert model.n_noise_ == 0

    model.fit(blobs_with_rare_states)
    assert model.n_noise_ == int(np.sum(model.labels_ == NOISE_LABEL))
    assert model.n_noise_ > 0


def test_noise_mask_selects_exactly_the_unassigned(blobs_with_rare_states):
    """`noise_mask` is what every consumer selects noise with."""
    model = DBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states)
    np.testing.assert_array_equal(
        model.noise_mask(), model.labels_ == NOISE_LABEL
    )
    assert int(model.noise_mask().sum()) == model.n_noise_


def test_the_density_estimate_is_kept(blobs_with_rare_states):
    """The quantity the clusters were formed from is the one a diagnostic plots."""
    model = DBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states)
    counts = np.asarray(model.n_neighbours_)
    assert counts.shape == (blobs_with_rare_states.shape[0],)
    # Every point is its own neighbour, and core points are exactly the
    # points whose count reached the threshold.
    assert counts.min() >= 1
    np.testing.assert_array_equal(
        np.flatnonzero(counts >= model.min_samples), model.core_sample_indices_
    )


# ---------------------------------------------------------------------
# Group 3: what the method is chosen for.
# ---------------------------------------------------------------------
def test_it_recovers_a_shape_no_centroid_method_could(moons):
    """Two crescents, recovered as two clusters with no noise.

    This is the property that puts a density method on the list: the
    clusters are not convex, so a Voronoi partition cannot express them.
    """
    model = DBSCAN(eps=0.25, min_samples=5).fit(moons)
    assert model.n_clusters_ == 2
    assert model.n_noise_ == 0


def test_it_declines_to_assign_a_rare_state(blobs_with_rare_states):
    """The three isolated points are noise, not folded into a regime."""
    model = DBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states)
    assert model.n_clusters_ == 3
    # The three appended points are the last three rows.
    rare = model.labels_[-3:]
    assert np.all(rare == NOISE_LABEL)


def test_the_cluster_count_is_a_result_of_the_density_parameters(moons):
    """|C| is not requested, so sweeping `eps` is what a sweep means here.

    Task 38's selector sweeps |C| and does not apply to this family by
    construction; this is the sweep that replaces it.
    """
    counts = {
        eps: DBSCAN(eps=eps, min_samples=5).fit(moons).n_clusters_
        for eps in (0.08, 0.25, 5.0)
    }
    # A tight radius fragments, a generous one merges everything into one.
    assert counts[0.08] > counts[0.25]
    assert counts[5.0] == 1
    assert "n_clusters" not in DBSCAN().get_params()


def test_a_larger_min_samples_turns_more_points_into_noise(blobs_with_rare_states):
    """`min_samples` is the smallest group willing to be called a regime."""
    lenient = DBSCAN(eps=0.7, min_samples=3).fit(blobs_with_rare_states).n_noise_
    strict = DBSCAN(eps=0.7, min_samples=15).fit(blobs_with_rare_states).n_noise_
    assert strict > lenient


def test_the_same_input_gives_the_same_partition(blobs_with_rare_states):
    """`deterministic=True` is declared, so it must hold."""
    first = DBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states).labels_
    second = DBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states).labels_
    np.testing.assert_array_equal(first, second)


# ---------------------------------------------------------------------
# Group 4: declarations and parameters.
# ---------------------------------------------------------------------
def test_registered_under_its_permanent_name():
    assert REGISTRY.get("dbscan") is DBSCAN
    assert "dbscan" in REGISTRY.names(kind=ComponentKind.CLUSTERER)


def test_registered_by_importing_the_package():
    """A sweep over the family must see it without importing the module."""
    import importlib

    importlib.import_module("xxcluster")
    assert "dbscan" in REGISTRY.names(kind=ComponentKind.CLUSTERER)


def test_capabilities_say_what_the_write_up_says():
    """Sect. 8.2's table is generated from these, so a wrong field is a false row."""
    caps = DBSCAN.capabilities()
    assert caps.family is Family.PARTITIONAL
    assert caps.subfamily is SubFamily.DENSITY_BASED
    assert caps.backend is Backend.NATIVE
    assert caps.assignment is Assignment.CRISP
    assert caps.handles_noise is True
    assert caps.requires_n_clusters is False
    assert caps.is_inductive is False
    assert caps.supports_precomputed is True
    assert caps.scale_invariant is False
    assert caps.deterministic is True
    assert caps.references
    assert caps.doc_label == "sec:tech:dbscan"


def test_it_is_not_inductive():
    """Declared transductive, so it must not offer to label unseen data."""
    assert not hasattr(DBSCAN, "predict")


@pytest.mark.parametrize("eps", [0, -1.0])
def test_a_non_positive_eps_is_refused(moons, eps):
    """Every point would be noise, which a caller would read as a finding."""
    with pytest.raises(ValueError, match="eps must be a positive distance"):
        DBSCAN(eps=eps).fit(moons)


def test_a_min_samples_below_one_is_refused(moons):
    with pytest.raises(ValueError, match="min_samples must be an integer"):
        DBSCAN(eps=0.25, min_samples=0).fit(moons)


def test_params_round_trip_so_clone_works():
    from sklearn.base import clone

    model = DBSCAN(eps=0.3, min_samples=7, metric="manhattan")
    copy = clone(model)
    assert copy.get_params() == model.get_params()
    assert copy.eps == 0.3 and copy.min_samples == 7


# ---------------------------------------------------------------------
# Group 5: noise traceable to the period it came from.
# ---------------------------------------------------------------------
def test_noise_report_names_the_positions(blobs_with_rare_states):
    """Usable on data carrying no clock: the positions are still reported."""
    model = DBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states)
    report = model.noise_report()
    assert len(report) == model.n_noise_
    np.testing.assert_array_equal(
        np.sort(report["position"].to_numpy()),
        np.flatnonzero(model.noise_mask()),
    )


def test_noise_report_carries_the_timestamp(blobs_with_rare_states):
    """A rare state with a timestamp is something operations can be asked about."""
    model = DBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states)
    stamps = pd.date_range(
        "2026-01-01", periods=blobs_with_rare_states.shape[0], freq="h"
    )
    report = model.noise_report(timestamps=stamps)

    assert "when" in report.columns
    # Each reported time is the one at that observation's position.
    for position, when in zip(report["position"], report["when"]):
        assert when == stamps[position]


def test_noise_report_says_how_far_from_dense_each_point_was(blobs_with_rare_states):
    """One neighbour short is a different finding from entirely alone."""
    model = DBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states)
    report = model.noise_report()
    assert (report["short_by"] > 0).all()
    assert (
        report["short_by"] == model.min_samples - report["n_neighbours"]
    ).all()


def test_misaligned_timestamps_are_refused(blobs_with_rare_states):
    """Silently tracing a noise point to the wrong period is the failure here."""
    model = DBSCAN(eps=0.7, min_samples=5).fit(blobs_with_rare_states)
    with pytest.raises(ValueError, match="must line up"):
        model.noise_report(timestamps=np.arange(5))


def test_noise_report_before_fit_is_refused():
    from xxcluster.core.exceptions import NotFittedError as XXNotFitted

    model = DBSCAN()
    with pytest.raises((XXNotFitted, ContractViolationError, AttributeError)):
        model.noise_report()
