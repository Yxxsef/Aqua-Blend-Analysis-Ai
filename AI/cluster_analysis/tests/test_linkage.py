"""
Tests for the four linkage criteria in
``xxcluster/cluster/hierarchical/linkage.py``.

The tests fall into three groups. First, that each criterion reproduces
its SciPy counterpart on a real dataset (iris) to floating-point
tolerance -- the sanity check that the Lance-Williams coefficients are
right. Second, that single-linkage chains and complete-linkage compacts
on a fixture built to show the contrast, since that contrast is what the
document reports. Third, that Ward's Euclidean requirement is honestly
declared, that every criterion is registered under its documented name,
and that ``update`` and ``between`` agree.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.cluster.hierarchy import linkage as scipy_linkage
from scipy.spatial.distance import pdist, squareform
from sklearn.datasets import load_iris

from xxcluster.cluster.hierarchical.linkage import (
    AverageLinkage,
    BaseLinkage,
    CompleteLinkage,
    SingleLinkage,
    WardLinkage,
)
from xxcluster.core.registry import REGISTRY


# ---------------------------------------------------------------------
# Merge-loop helper.
#
# Task 40 will implement the real merge loop on
# ``BaseAgglomerative._build_hierarchy``; the tests here need to compare
# a criterion's output against SciPy without depending on a class that
# does not yet exist. This helper is a straight Lance-Williams merge
# loop: sizes tracked, dissimilarities updated in place, one row and
# column removed per merge, heights recorded. It is not part of the
# package and lives here on purpose -- it is test scaffolding, not a
# reusable component.
# ---------------------------------------------------------------------
def _merge_loop(D0: np.ndarray, criterion: BaseLinkage) -> np.ndarray:
    """Run an agglomerative merge under ``criterion`` and return the linkage matrix.

    ``D0`` is the initial pairwise dissimilarity. For Ward, ``D0`` holds
    Euclidean distances; the loop tracks the squared SSE-increase
    heights that Ward's ``update`` returns, to match SciPy's
    ``linkage(method='ward')`` height convention.
    """
    m = D0.shape[0]
    D = D0.astype(float).copy()

    # For Ward the merge loop tracks squared-distance heights internally
    # so the recurrence's linear form is correct on its own outputs.
    if isinstance(criterion, WardLinkage):
        D = D ** 2

    active = list(range(m))          # current row -> original id
    sizes = {i: 1 for i in range(m)}
    next_id = m
    Z = np.zeros((m - 1, 4))

    for step in range(m - 1):
        # Pick the closest pair among current rows.
        # Set the diagonal to +inf so argmin ignores it.
        np.fill_diagonal(D, np.inf)
        flat = np.argmin(D)
        i, j = divmod(flat, D.shape[0])
        if i > j:
            i, j = j, i

        id_a, id_b = active[i], active[j]
        size_a, size_b = sizes[id_a], sizes[id_b]
        d_ab = float(D[i, j])
        merged_id = next_id
        next_id += 1

        # Record: SciPy's format stores sqrt(height) for Ward.
        height = np.sqrt(d_ab) if isinstance(criterion, WardLinkage) else d_ab
        Z[step] = (id_a, id_b, height, size_a + size_b)

        # Update dissimilarities from the merged cluster to every other
        # remaining cluster using the criterion's recurrence.
        new_row = np.empty(D.shape[0])
        for k in range(D.shape[0]):
            if k == i or k == j:
                continue
            id_k = active[k]
            new_row[k] = criterion.update(
                d_ai=float(D[i, k]),
                d_bi=float(D[j, k]),
                d_ab=d_ab,
                size_a=size_a,
                size_b=size_b,
                size_i=sizes[id_k],
            )

        # Drop row/col j and overwrite row/col i with the merged cluster.
        D[i, :] = new_row
        D[:, i] = new_row
        D[i, i] = 0.0
        D = np.delete(D, j, axis=0)
        D = np.delete(D, j, axis=1)

        active[i] = merged_id
        active.pop(j)
        sizes[merged_id] = size_a + size_b

    return Z


# ---------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def iris_D() -> np.ndarray:
    """The 150 x 150 Euclidean distance matrix on iris."""
    X = load_iris().data
    return squareform(pdist(X, metric="euclidean"))


@pytest.fixture(scope="module")
def iris_X() -> np.ndarray:
    return load_iris().data


@pytest.fixture
def chain_D() -> np.ndarray:
    """A 1-D fixture built to distinguish single from complete linkage.

    Points at 0, 1, 2, 10, 11: two tight groups joined by a stepping
    stone. Single linkage will chain 0 -> 1 -> 2 -> 10 -> 11 into one
    cluster at height 8; complete linkage keeps the two groups apart
    until the last merge, at height 11.
    """
    xs = np.array([[0.0], [1.0], [2.0], [10.0], [11.0]])
    return squareform(pdist(xs, metric="euclidean"))


# ---------------------------------------------------------------------
# Group 1: heights match SciPy on iris (fp tolerance).
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "criterion_cls,scipy_name",
    [
        (SingleLinkage, "single"),
        (CompleteLinkage, "complete"),
        (AverageLinkage, "average"),
        (WardLinkage, "ward"),
    ],
)
def test_heights_match_scipy_on_iris(iris_D, iris_X, criterion_cls, scipy_name):
    """Every criterion's merge heights match SciPy's, to fp tolerance."""
    ours = _merge_loop(iris_D, criterion_cls())
    if scipy_name == "ward":
        # SciPy's linkage(method='ward') takes the coordinates, not D.
        theirs = scipy_linkage(iris_X, method="ward")
    else:
        # Every other method takes the condensed dissimilarity vector.
        theirs = scipy_linkage(pdist(iris_X, metric="euclidean"),
                               method=scipy_name)

    ours_heights = np.sort(ours[:, 2])
    theirs_heights = np.sort(theirs[:, 2])
    np.testing.assert_allclose(ours_heights, theirs_heights, atol=1e-9)


# ---------------------------------------------------------------------
# Group 2: chains vs compacts.
# ---------------------------------------------------------------------
def test_single_linkage_chains_across_the_stepping_stone(chain_D):
    """Single linkage joins the two groups at height 8 via the mid-point."""
    Z = _merge_loop(chain_D, SingleLinkage())
    # Merges at heights 1, 1, 1, 8 -- the last is the chain step.
    np.testing.assert_allclose(np.sort(Z[:, 2]), [1.0, 1.0, 1.0, 8.0])


def test_complete_linkage_keeps_the_groups_apart(chain_D):
    """Complete linkage's last merge is at height 11, not 8."""
    Z = _merge_loop(chain_D, CompleteLinkage())
    # The two groups only join once every pair is inside 11 units.
    assert np.max(Z[:, 2]) == pytest.approx(11.0)


def test_the_contrast_is_real(chain_D):
    """The two criteria give different final merge heights on this fixture."""
    single_top = np.max(_merge_loop(chain_D, SingleLinkage())[:, 2])
    complete_top = np.max(_merge_loop(chain_D, CompleteLinkage())[:, 2])
    assert single_top < complete_top


# ---------------------------------------------------------------------
# Group 3: declarations, recurrence, registry.
# ---------------------------------------------------------------------
def test_ward_declares_the_euclidean_requirement():
    """Ward, and only Ward, requires the input dissimilarity to be Euclidean."""
    assert WardLinkage.requires_euclidean is True
    assert SingleLinkage.requires_euclidean is False
    assert CompleteLinkage.requires_euclidean is False
    assert AverageLinkage.requires_euclidean is False


@pytest.mark.parametrize(
    "criterion_cls",
    [SingleLinkage, CompleteLinkage, AverageLinkage, WardLinkage],
)
def test_every_criterion_declares_monotonicity(criterion_cls):
    """All four are monotonic; the second, cheaper guard cut() reads."""
    assert criterion_cls.monotonic is True


@pytest.mark.parametrize(
    "criterion_cls,name",
    [
        (SingleLinkage, "single"),
        (CompleteLinkage, "complete"),
        (AverageLinkage, "average"),
        (WardLinkage, "ward"),
    ],
)
def test_registered_by_documented_name(criterion_cls, name):
    """Each criterion resolves under the name the document uses."""
    assert REGISTRY.get(name) is criterion_cls
    assert criterion_cls.name == name


def test_the_base_lance_williams_default_raises():
    """A criterion whose author did not derive the recurrence is a loud error."""
    class Unfinished(BaseLinkage):
        name = "unfinished"

        def between(self, D, cluster_a, cluster_b):
            return 0.0

    with pytest.raises(NotImplementedError, match="Lance-Williams"):
        Unfinished().update(1.0, 1.0, 1.0, 1, 1, 1)


@pytest.mark.parametrize(
    "criterion_cls",
    [SingleLinkage, CompleteLinkage, AverageLinkage],
)
def test_update_and_between_agree_on_singletons(criterion_cls):
    """The recurrence and the definitional form must give the same first merge.

    On singletons the two are literally the same number: single is
    ``min(d_ai, d_bi)`` in both places, and so on. Ward's ``between``
    scales its output differently by construction (see its docstring)
    and is exercised through the SciPy match instead.
    """
    D = np.array([
        [0.0, 1.0, 2.0, 5.0],
        [1.0, 0.0, 3.0, 6.0],
        [2.0, 3.0, 0.0, 4.0],
        [5.0, 6.0, 4.0, 0.0],
    ])
    c = criterion_cls()
    # Merge {0} and {1}, then ask for the dissimilarity to {2}.
    via_recurrence = c.update(
        d_ai=D[0, 2], d_bi=D[1, 2], d_ab=D[0, 1],
        size_a=1, size_b=1, size_i=1,
    )
    via_definition = c.between(D, np.array([0, 1]), np.array([2]))
    assert via_recurrence == pytest.approx(via_definition)
