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
and that ``update`` and ``between`` agree. Fourth, that the Euclidean
requirement is *enforced*: a method configured with ``linkage="ward"``
and a non-Euclidean metric is refused at fit time, before any tree is
built, and refused on exactly the inputs an adapted backend refuses.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.cluster.hierarchy import linkage as scipy_linkage
from scipy.spatial.distance import pdist, squareform
from sklearn.datasets import load_iris

from sklearn.cluster import AgglomerativeClustering

from xxcluster.cluster.hierarchical.agglomerative.base import BaseAgglomerative
from xxcluster.cluster.hierarchical.linkage import (
    EUCLIDEAN_METRICS,
    AverageLinkage,
    BaseLinkage,
    CompleteLinkage,
    SingleLinkage,
    WardLinkage,
    check_linkage_metric,
    linkage_names,
    resolve_linkage,
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


# ---------------------------------------------------------------------
# Group 4: the Euclidean requirement is enforced, not merely declared.
#
# `requires_euclidean` is worth nothing as a class attribute nobody
# reads, so these tests drive it through `fit`. Task 40 supplies the
# real Ward method; until then the stand-in below is the smallest
# hierarchical method that can be fitted -- test scaffolding, not a
# component, which is why it lives here and not in the package, the
# same rule Task 30 followed for the family bases.
# ---------------------------------------------------------------------
class _StubAgglomerative(BaseAgglomerative):
    """A native hierarchical method that records whether it did any work.

    `built` is the probe for "before doing any work": a refusal that
    fires after the tree was constructed is not the refusal the
    contract promises.
    """

    def __init__(self, n_clusters=None, *, metric="euclidean",
                 linkage="ward", distance_threshold=None, connectivity=None):
        super().__init__(
            n_clusters=n_clusters,
            metric=metric,
            linkage=linkage,
            distance_threshold=distance_threshold,
            connectivity=connectivity,
        )
        self.built = False

    def _build_hierarchy(self, X):
        self.built = True
        # Which criterion built the tree is irrelevant to this stub: it
        # exists to prove the guard runs first, so it always builds the
        # same cheap tree.
        self.linkage_ = scipy_linkage(pdist(X, metric="euclidean"),
                                      method="single")


@pytest.fixture
def blob() -> np.ndarray:
    """Twelve points in three dimensions; any fittable input will do."""
    return np.random.RandomState(0).rand(12, 3)


@pytest.mark.parametrize("metric", ["manhattan", "cosine", "cityblock", "l1"])
def test_ward_refuses_a_non_euclidean_metric_at_fit_time(blob, metric):
    """The declaration is enforced: `fit` refuses, naming both parties."""
    est = _StubAgglomerative(n_clusters=2, metric=metric, linkage="ward")
    with pytest.raises(ValueError, match="requires Euclidean distance"):
        est.fit(blob)


def test_ward_refuses_before_building_the_tree(blob):
    """"Before doing any work" is the contract, so nothing may be built."""
    est = _StubAgglomerative(n_clusters=2, metric="manhattan", linkage="ward")
    with pytest.raises(ValueError):
        est.fit(blob)
    assert est.built is False
    assert not hasattr(est, "linkage_")


def test_ward_refuses_a_precomputed_matrix(blob):
    """A supplied matrix carries no evidence that it is Euclidean."""
    D = squareform(pdist(blob, metric="euclidean"))
    est = _StubAgglomerative(n_clusters=2, metric="precomputed", linkage="ward")
    with pytest.raises(ValueError, match="precomputed"):
        est.fit(D)
    assert est.built is False


def test_ward_refuses_a_callable_metric(blob):
    """A callable's geometry is not readable from the parameter."""
    est = _StubAgglomerative(
        n_clusters=2,
        metric=lambda a, b: float(np.abs(a - b).sum()),
        linkage="ward",
    )
    with pytest.raises(ValueError, match="callable"):
        est.fit(blob)


@pytest.mark.parametrize("metric", sorted(EUCLIDEAN_METRICS))
def test_ward_accepts_every_euclidean_spelling(blob, metric):
    """Both names for the one distance are accepted, as the backend accepts both."""
    est = _StubAgglomerative(n_clusters=2, metric=metric, linkage="ward").fit(blob)
    assert est.built is True
    assert est.n_clusters_ == 2


@pytest.mark.parametrize("criterion", ["single", "complete", "average"])
def test_the_other_criteria_accept_a_non_euclidean_metric(blob, criterion):
    """Only Ward is constrained; the guard must not over-reach."""
    est = _StubAgglomerative(n_clusters=2, metric="manhattan",
                             linkage=criterion).fit(blob)
    assert est.built is True


def test_the_refusal_names_a_criterion_that_would_work(blob):
    """An error that does not say what to do instead is half an error."""
    est = _StubAgglomerative(n_clusters=2, metric="manhattan", linkage="ward")
    with pytest.raises(ValueError) as excinfo:
        est.fit(blob)
    message = str(excinfo.value)
    assert "metric='euclidean'" in message
    # The alternatives offered are the criteria that admit any
    # dissimilarity, and Ward is not among them.
    alternatives = message.split("any dissimilarity:")[1]
    assert "single" in alternatives
    assert "ward" not in alternatives


# ---------------------------------------------------------------------
# Group 5: one resolution path, native or adapted.
# ---------------------------------------------------------------------
def test_resolve_linkage_accepts_a_name_a_class_and_an_instance():
    """Three spellings of one request resolve to the same criterion."""
    instance = WardLinkage()
    assert isinstance(resolve_linkage("ward"), WardLinkage)
    assert isinstance(resolve_linkage(WardLinkage), WardLinkage)
    assert resolve_linkage(instance) is instance


def test_resolve_linkage_refuses_a_registered_non_criterion():
    """The registry is shared across kinds, so `kmeans` resolves -- but not to this."""
    with pytest.raises(ValueError, match="not a linkage"):
        resolve_linkage("kmeans")


def test_an_unregistered_criterion_fails_at_the_top_of_fit(blob):
    """A typo in `linkage=` is an error before fitting, not at the first merge."""
    est = _StubAgglomerative(n_clusters=2, linkage="wrad")
    with pytest.raises(Exception, match="wrad"):
        est.fit(blob)
    assert est.built is False


def test_linkage_names_lists_exactly_the_four_criteria():
    assert sorted(linkage_names()) == ["average", "complete", "single", "ward"]


@pytest.mark.parametrize("name", ["single", "complete", "average", "ward"])
def test_a_criterion_resolved_by_name_matches_the_backend_of_that_name(
    iris_D, iris_X, name
):
    """Resolving by name gives the tree the adapted backend gives under that name.

    This is the native-versus-adapted check: `linkage="average"` must
    not mean UPGMA here and WPGMA through the backend, or one
    registered name would report two different partitions.
    """
    ours = _merge_loop(iris_D, resolve_linkage(name))
    if name == "ward":
        theirs = scipy_linkage(iris_X, method="ward")
    else:
        theirs = scipy_linkage(pdist(iris_X, metric="euclidean"), method=name)
    np.testing.assert_allclose(
        np.sort(ours[:, 2]), np.sort(theirs[:, 2]), atol=1e-9
    )


@pytest.mark.parametrize(
    "metric", ["euclidean", "l2", "manhattan", "cosine", "precomputed"]
)
def test_the_ward_metric_rule_agrees_with_the_adapted_backend(blob, metric):
    """Our guard draws the line where scikit-learn's Ward draws it.

    Task 40 adapts `AgglomerativeClustering`, so a disagreement here
    would mean `linkage="ward"` accepts natively what the adapted
    method refuses, or the reverse: one registered name with two
    behaviours.
    """
    X = squareform(pdist(blob)) if metric == "precomputed" else blob

    try:
        AgglomerativeClustering(n_clusters=2, metric=metric,
                                linkage="ward").fit(X)
    except ValueError:
        backend_refused = True
    else:
        backend_refused = False

    try:
        check_linkage_metric("ward", metric)
    except ValueError:
        ours_refused = True
    else:
        ours_refused = False

    assert ours_refused == backend_refused
