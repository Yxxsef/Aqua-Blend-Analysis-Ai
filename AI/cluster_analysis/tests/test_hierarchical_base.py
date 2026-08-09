"""
Tests for `BaseHierarchicalClusterer` -- cutting, and the two tree formats.

Cutting a linkage matrix does not depend on how the matrix was built, so
`cut` is the family's. The practical value of that is pinned below: one
fit yields every partition, so sweeping the cut level costs no refitting.

The other half is the reconciliation of `linkage_` with `children_` and
`distances_`. SciPy and scikit-learn record the same tree in different
formats and different tools consume each, so the base derives whichever
was not set. That derivation is silent when wrong -- a mis-built linkage
matrix still cuts, still plots, and gives the wrong partition -- so it is
checked against SciPy directly.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.cluster.hierarchy import linkage as scipy_linkage

from xxcluster.cluster.hierarchical.base import BaseHierarchicalClusterer
from xxcluster.core.exceptions import ContractViolationError

rng = np.random.RandomState(0)
X = np.vstack([rng.normal(loc, 0.3, size=(8, 2)) for loc in (0.0, 5.0, 10.0)])

#: Three points at the corners of an equilateral triangle, plus one far
#: away. Merging any two corners puts their centroid closer to the third
#: than the pair were to each other, so centroid linkage inverts -- the
#: minimal case, and well-separated data will not produce one.
INVERTING = np.array([[0.0, 0.0], [1.0, 0.0], [0.5, 0.866], [10.0, 10.0]])


class Ward(BaseHierarchicalClusterer):
    """A native method reporting SciPy's format; `children_` is derived."""

    def _build_hierarchy(self, X):
        self.builds_ = getattr(self, "builds_", 0) + 1
        self.linkage_ = scipy_linkage(X, method=self.linkage)


class SklearnStyle(BaseHierarchicalClusterer):
    """A backend reporting scikit-learn's format; `linkage_` is derived."""

    def _build_hierarchy(self, X):
        Z = scipy_linkage(X, method="ward")
        self.children_ = Z[:, :2].astype(int)
        self.distances_ = Z[:, 2]


class Centroid(BaseHierarchicalClusterer):
    """Centroid linkage inverts, so its merge heights are not monotonic."""

    def _build_hierarchy(self, X):
        self.linkage_ = scipy_linkage(X, method="centroid")


# --- Fitting and cutting ---------------------------------------------------


def test_fit_builds_the_tree_and_applies_the_requested_cut():
    model = Ward(n_clusters=3).fit(X)
    assert model.n_clusters_ == 3
    assert model.linkage_.shape == (X.shape[0] - 1, 4)


def test_labels_are_zero_based():
    """SciPy's `fcluster` is one-based; the package convention is not."""
    assert Ward(n_clusters=3).fit(X).labels_.min() == 0


@pytest.mark.parametrize("k", [2, 3, 5, 9])
def test_cutting_at_k_yields_exactly_k_clusters(k):
    assert np.unique(Ward(n_clusters=3).fit(X).cut(n_clusters=k)).size == k


def test_sweeping_the_cut_level_costs_one_fit():
    """The reason a hierarchy is worth having: |C| is chosen by cutting."""
    model = Ward(n_clusters=3).fit(X)
    for k in range(2, 10):
        model.cut(n_clusters=k)
    assert model.builds_ == 1


def test_a_height_threshold_cuts_the_same_tree():
    model = Ward().fit(X)
    labels = model.cut(threshold=float(model.distances_[-2]))
    assert np.unique(labels).size >= 2


def test_an_uncut_hierarchy_is_its_own_leaves():
    """Fitting with neither a level nor a height is permitted."""
    model = Ward().fit(X)
    assert model.n_clusters_ == X.shape[0]


# --- The two formats -------------------------------------------------------


def test_children_and_distances_are_derived_from_linkage():
    model = Ward(n_clusters=3).fit(X)
    np.testing.assert_array_equal(model.children_, model.linkage_[:, :2].astype(int))
    np.testing.assert_allclose(model.distances_, model.linkage_[:, 2])


def test_linkage_is_reconstructed_from_children_and_distances():
    """Including the cluster-size column, which scikit-learn does not report."""
    np.testing.assert_allclose(
        SklearnStyle(n_clusters=3).fit(X).linkage_, scipy_linkage(X, method="ward")
    )


def test_both_formats_yield_the_identical_partition():
    np.testing.assert_array_equal(
        SklearnStyle(n_clusters=3).fit(X).labels_, Ward(n_clusters=3).fit(X).labels_
    )


def test_a_refit_does_not_inherit_the_previous_tree():
    model = Ward(n_clusters=3).fit(X)
    model.fit(X[:12])
    assert model.linkage_.shape == (11, 4)


# --- What it refuses -------------------------------------------------------


def test_cut_refuses_a_level_and_a_height_together():
    model = Ward(n_clusters=3).fit(X)
    with pytest.raises(ValueError, match="not both"):
        model.cut(n_clusters=3, threshold=1.0)


def test_cut_refuses_neither():
    model = Ward(n_clusters=3).fit(X)
    with pytest.raises(ValueError, match="either"):
        model.cut()


def test_cut_refuses_a_single_cluster():
    """`check_n_clusters` puts the floor at 2; one cluster is not a partition."""
    model = Ward(n_clusters=3).fit(X)
    with pytest.raises(ValueError, match="at least 2"):
        model.cut(n_clusters=1)


def test_fit_refuses_a_level_and_a_height_together():
    with pytest.raises(ValueError, match="mutually exclusive"):
        Ward(n_clusters=3, distance_threshold=1.0).fit(X)


def test_a_non_monotonic_tree_refuses_a_height_cut():
    """`fcluster` would still return something, so this is checked, not left."""
    model = Centroid().fit(INVERTING)
    with pytest.raises(ValueError, match="monotonic"):
        model.cut(threshold=0.5)


def test_a_non_monotonic_tree_still_cuts_by_level():
    """The inversion invalidates a height, not a level."""
    assert np.unique(Centroid().fit(INVERTING).cut(n_clusters=2)).size == 2


def test_building_no_tree_is_a_contract_violation():
    class NoTree(BaseHierarchicalClusterer):
        def _build_hierarchy(self, X):
            pass

    with pytest.raises(ContractViolationError, match="neither"):
        NoTree(n_clusters=3).fit(X)


def test_children_without_distances_is_a_contract_violation():
    class NoHeights(BaseHierarchicalClusterer):
        def _build_hierarchy(self, X):
            self.children_ = scipy_linkage(X, method="ward")[:, :2].astype(int)

    with pytest.raises(ContractViolationError, match="distances_"):
        NoHeights(n_clusters=3).fit(X)
