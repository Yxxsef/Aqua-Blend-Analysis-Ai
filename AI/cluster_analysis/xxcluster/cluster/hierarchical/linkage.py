"""
Linkage criteria.

A linkage criterion lifts a dissimilarity between observations to a
dissimilarity between clusters, and is the component AHC and DHC share.
It is kept separate from the methods for two reasons: the same criterion
is reused across methods, and the choice of criterion changes the shape of
cluster a method can recover -- single linkage chains, complete linkage
compacts, Ward minimises within-cluster variance -- which is a result to
report, not an implementation detail.

Criteria are registered by name so that `linkage="ward"` resolves the same
way whether the hierarchy is built natively or by an adapted backend.

Representation. A cluster is an ``ndarray`` of row indices into the
pairwise dissimilarity matrix ``D``. Passing indices rather than the
observation coordinates keeps a criterion working under
``metric="precomputed"`` and avoids allocating a new sub-array on every
merge. Ward is the exception, and ``check_linkage_metric`` below is where
that exception is enforced.

Update rule. All four criteria implemented here follow the Lance-Williams
recurrence (ref_10 Ch. 7; ref_11 Ch. 10.3), which expresses the
dissimilarity between a newly merged cluster and every other cluster as a
linear combination of the three prior dissimilarities. Overriding
``update`` with the recurrence is what makes the merge loop affordable:
recomputing ``between`` for every pair on every step is quadratic in the
sample size at each of ``m - 1`` merges, which is unusable at any real
data volume.

Document counterpart: the "Linkage criteria" section, labelled
``sec:tech:linkage``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

import numpy as np

from ...core.registry import REGISTRY, register
from ...core.types import DissimilarityMatrix


class BaseLinkage(ABC):
    """Dissimilarity between two clusters, given the dissimilarities within.

    Class attributes
    ----------------
    name
        Registry key, e.g. ``"ward"``. Permanent -- appears in stored
        artefacts and in Sect. 8.2's table.
    requires_euclidean
        True where the criterion is only defined for Euclidean distance,
        as Ward's is. Checked against the method's ``metric`` at fit
        time, so an invalid combination fails before producing a result.
    monotonic
        True where merge heights are non-decreasing, so the dendrogram
        has no inversions and a height threshold is a valid cut. Read by
        ``BaseHierarchicalClusterer.cut`` as the cheap guard alongside
        its own ``_check_monotonic`` on the fitted heights; the two must
        agree.
    """

    name: ClassVar[str]
    requires_euclidean: ClassVar[bool] = False
    monotonic: ClassVar[bool] = True

    @abstractmethod
    def between(
        self,
        D: DissimilarityMatrix,
        cluster_a: np.ndarray,
        cluster_b: np.ndarray,
    ) -> float:
        """Return the dissimilarity between two clusters.

        ``cluster_a`` and ``cluster_b`` are arrays of row indices into
        ``D``. This is the definitional form of the criterion; concrete
        subclasses implement the aggregation over pairwise dissimilarities
        (min for single, max for complete, mean for average) and Ward
        expresses its cost in terms of cluster sizes and centroid
        distance.
        """
        ...

    def update(
        self,
        d_ai: float,
        d_bi: float,
        d_ab: float,
        size_a: int,
        size_b: int,
        size_i: int,
    ) -> float:
        """Return the dissimilarity between the merged cluster and cluster i.

        Lance-Williams recurrence in its scalar form: given the three
        prior dissimilarities ``d(a, i)``, ``d(b, i)`` and ``d(a, b)``
        and the three cluster sizes, return ``d((a + b), i)``. Called
        once per remaining cluster ``i`` after a merge, versus
        ``between`` which is quadratic in the cluster sizes.

        Concrete subclasses override this with the coefficients from the
        recurrence; the default raises so that a criterion whose author
        did not derive the recurrence is a loud error rather than a
        silently expensive one.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement the Lance-Williams "
            f"recurrence. Override `update` with the criterion's "
            f"coefficients, or accept the O(m) per-merge cost of "
            f"`between` and use it explicitly."
        )


def _pairwise_block(
    D: DissimilarityMatrix,
    cluster_a: np.ndarray,
    cluster_b: np.ndarray,
) -> np.ndarray:
    """Return the ``|A| x |B|`` block of dissimilarities between the two clusters.

    A single fancy-index into ``D`` rather than a Python loop, since the
    aggregations below are vectorised on the block.
    """
    return D[np.ix_(np.asarray(cluster_a, dtype=int),
                    np.asarray(cluster_b, dtype=int))]


@register("single", kind=None)
class SingleLinkage(BaseLinkage):
    """Nearest-neighbour dissimilarity between clusters.

    ``d(A, B) = min_{a in A, b in B} d(a, b)``. Produces chains because
    a new observation only needs one near neighbour in a cluster to be
    absorbed by it; useful for elongated regimes, and pathological on
    plant data with dense operating envelopes because a single bridging
    observation can join two otherwise distinct regimes.
    """

    name = "single"
    requires_euclidean = False
    monotonic = True

    def between(self, D, cluster_a, cluster_b):
        return float(_pairwise_block(D, cluster_a, cluster_b).min())

    def update(self, d_ai, d_bi, d_ab, size_a, size_b, size_i):
        # Lance-Williams coefficients (alpha_a, alpha_b, beta, gamma)
        # = (1/2, 1/2, 0, -1/2); simplifies to the minimum of the two
        # prior dissimilarities. Coefficient table: ref_10, Ch. 7.
        return min(d_ai, d_bi)


@register("complete", kind=None)
class CompleteLinkage(BaseLinkage):
    """Farthest-neighbour dissimilarity between clusters.

    ``d(A, B) = max_{a in A, b in B} d(a, b)``. Produces compact,
    similarly-sized clusters, since a merge is penalised by the worst
    pairwise disagreement it introduces; the corresponding failure is
    that it can split a genuinely elongated regime into pieces.
    """

    name = "complete"
    requires_euclidean = False
    monotonic = True

    def between(self, D, cluster_a, cluster_b):
        return float(_pairwise_block(D, cluster_a, cluster_b).max())

    def update(self, d_ai, d_bi, d_ab, size_a, size_b, size_i):
        # Lance-Williams (1/2, 1/2, 0, 1/2); the maximum of the two.
        return max(d_ai, d_bi)


@register("average", kind=None)
class AverageLinkage(BaseLinkage):
    """Mean pairwise dissimilarity between clusters (UPGMA).

    ``d(A, B) = (1 / (|A| |B|)) sum_{a in A, b in B} d(a, b)``. A
    compromise between single and complete: less prone to chaining than
    single, less brittle to boundary observations than complete. This is
    the unweighted variant (UPGMA); the weighted variant (WPGMA) uses a
    different coefficient in the recurrence and is not implemented here.
    """

    name = "average"
    requires_euclidean = False
    monotonic = True

    def between(self, D, cluster_a, cluster_b):
        return float(_pairwise_block(D, cluster_a, cluster_b).mean())

    def update(self, d_ai, d_bi, d_ab, size_a, size_b, size_i):
        # Lance-Williams (|A| / (|A| + |B|), |B| / (|A| + |B|), 0, 0).
        # Size-weighted average of the two prior dissimilarities.
        total = size_a + size_b
        return (size_a * d_ai + size_b * d_bi) / total


@register("ward", kind=None)
class WardLinkage(BaseLinkage):
    """Minimum-variance criterion of Ward (1963).

    Merges the pair whose union increases the total within-cluster
    sum-of-squared error the least. Under Euclidean distance the
    increase can be written in the Lance-Williams form below without
    ever computing centroids explicitly.

    ``requires_euclidean = True`` because Ward's derivation identifies
    the SSE increase with a squared Euclidean distance between
    centroids; under any other dissimilarity the update formula is not
    the criterion it names, and a method built on it silently returns a
    partition it did not compute.
    ``BaseHierarchicalClusterer._validate_params`` calls
    ``check_linkage_metric`` below, so the refusal happens at the first
    step of ``fit``, before the input is even validated -- and on the
    adapted path as well as the native one, since ``_validate_params``
    is a step of the ``fit`` template rather than of ``_fit``.

    This implementation is the Ward2 variant (Murtagh & Legendre 2014):
    the input ``D`` holds Euclidean distances and the recurrence below
    tracks the squared-distance heights internally, matching SciPy's
    ``linkage(method='ward')`` and scikit-learn's Agglomerative Ward.
    """

    name = "ward"
    requires_euclidean = True
    monotonic = True

    def between(self, D, cluster_a, cluster_b):
        # Definitional form used only for validation and for the initial
        # dissimilarity matrix in a native merge loop; the recurrence in
        # ``update`` is what the loop actually calls after the first
        # step. Under a Euclidean D, this returns the squared distance
        # scaled by the harmonic factor of the two cluster sizes, which
        # is the SSE increase upon merging.
        na, nb = len(cluster_a), len(cluster_b)
        block = _pairwise_block(D, cluster_a, cluster_b)
        return float((na * nb / (na + nb)) * (block ** 2).mean())

    def update(self, d_ai, d_bi, d_ab, size_a, size_b, size_i):
        # Lance-Williams coefficients for Ward:
        #   alpha_a = (n_a + n_i) / (n_a + n_b + n_i)
        #   alpha_b = (n_b + n_i) / (n_a + n_b + n_i)
        #   beta    = -n_i        / (n_a + n_b + n_i)
        #   gamma   = 0
        # Derivation: ref_10, Ch. 7. The name "Ward2" for this variant,
        # and the distinction from the incompatible one that takes
        # squared distances, is Murtagh and Legendre's (2014) -- a
        # source with no mapping-sheet key yet, recorded as read in the
        # section's REFERENCES USED block.
        total = size_a + size_b + size_i
        return (
            (size_a + size_i) * d_ai
            + (size_b + size_i) * d_bi
            - size_i * d_ab
        ) / total


#: Metric names that denote Euclidean distance, and therefore satisfy
#: ``requires_euclidean``. Matches the pair scikit-learn's
#: ``AgglomerativeClustering`` accepts under ``linkage="ward"``, so a
#: criterion resolved natively and one resolved by an adapted backend
#: refuse the same inputs.
EUCLIDEAN_METRICS: frozenset[str] = frozenset({"euclidean", "l2"})


def resolve_linkage(linkage: str | BaseLinkage | type[BaseLinkage]) -> BaseLinkage:
    """Return a criterion instance for a name, a class, or an instance.

    One resolution path for the whole family, so ``linkage="ward"``
    means the same object whether the hierarchy is built natively or by
    an adapted backend. Names go through the process-wide registry,
    which is what makes them permanent and what lets a configuration
    file name a criterion.

    A name that resolves to something which is not a criterion is
    refused here rather than at the first merge: the registry is shared
    across component kinds, so ``linkage="kmeans"`` resolves to a class
    -- just not to one that lifts a dissimilarity to clusters.
    """
    if isinstance(linkage, BaseLinkage):
        return linkage

    if isinstance(linkage, type):
        cls = linkage
    else:
        cls = REGISTRY.get(str(linkage))

    if not (isinstance(cls, type) and issubclass(cls, BaseLinkage)):
        raise ValueError(
            f"linkage={linkage!r} resolves to "
            f"{getattr(cls, '__qualname__', cls)!r}, which is not a linkage "
            f"criterion. Registered criteria: "
            f"{', '.join(sorted(linkage_names()))}."
        )
    return cls()


def linkage_names() -> list[str]:
    """List the names the registered linkage criteria answer to."""
    return [
        name
        for name, cls in REGISTRY
        if isinstance(cls, type) and issubclass(cls, BaseLinkage)
    ]


def check_linkage_metric(
    linkage: str | BaseLinkage | type[BaseLinkage],
    metric: object,
) -> BaseLinkage:
    """Refuse a criterion/metric pair the criterion is not defined for.

    Returns the resolved criterion, so a caller that needs it does not
    resolve twice.

    Only Ward declares ``requires_euclidean`` today, and the rule it
    enforces is deliberately strict: anything this function cannot
    *verify* as Euclidean is refused, rather than accepted on the
    caller's word.

    - A named metric passes only if it is in ``EUCLIDEAN_METRICS``.
    - A callable is refused: its geometry is not readable from here.
    - ``"precomputed"`` is refused: a supplied matrix may well hold
      Euclidean distances, but nothing in the parameter says so, and the
      failure mode of guessing wrong is a partition reported under a
      criterion that never computed it. This is the same line
      scikit-learn's ``AgglomerativeClustering`` draws, which keeps the
      native and adapted paths in agreement.

    The alternative -- letting Ward run on whatever matrix arrives -- is
    the silent-wrong-answer case that ``requires_euclidean`` exists to
    prevent, and is why this is checked before any work rather than
    reported as a caveat afterwards.
    """
    criterion = resolve_linkage(linkage)
    if not criterion.requires_euclidean:
        return criterion

    if isinstance(metric, str) and metric in EUCLIDEAN_METRICS:
        return criterion

    if metric == "precomputed":
        detail = (
            "a precomputed matrix carries no evidence that its entries are "
            "Euclidean distances, and this criterion is only defined when "
            "they are"
        )
    elif callable(metric):
        detail = (
            "a callable metric cannot be verified as Euclidean from the "
            "parameter"
        )
    else:
        detail = (
            f"{metric!r} is not one of "
            f"{sorted(EUCLIDEAN_METRICS)}"
        )

    raise ValueError(
        f"linkage={criterion.name!r} requires Euclidean distance: {detail}. "
        f"Ward's merge cost is an increase in within-cluster sum-of-squares, "
        f"which equals a squared Euclidean distance between centroids and "
        f"nothing else, so under metric={metric!r} the recurrence would "
        f"return a number that is not the criterion it names. Pass "
        f"metric='euclidean' (or 'l2'), or choose a criterion defined for "
        f"any dissimilarity: "
        f"{', '.join(sorted(n for n in linkage_names() if n != criterion.name))}."
    )
