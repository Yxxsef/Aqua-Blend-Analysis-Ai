"""
Base class shared by hierarchical methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ...core.base import BaseClusterer
from ...core.mixins import HierarchyMixin, PrecomputedMixin
from ...core.types import Labels, MatrixLike, MetricLike


class BaseHierarchicalClusterer(HierarchyMixin, PrecomputedMixin, BaseClusterer, ABC):
    """A clustering method that builds a hierarchy over the sample.

    Fitting produces the full tree; `n_clusters` is therefore a cut level
    rather than a fitting parameter, and `labels_` is the partition at the
    requested level. Leaving both `n_clusters` and `distance_threshold`
    unset is valid: the tree is built and no cut is applied until `cut` is
    called.

    Both construction directions consume a dissimilarity and a linkage
    criterion, so both are declared here. `metric="precomputed"` accepts a
    dissimilarity matrix directly, which is how a custom measure from
    `xxcluster.measures.dissimilarity` reaches this family.

    Parameters
    ----------
    n_clusters
        Cut level applied after fitting, if any.
    metric
        Name of a measure, a callable, or "precomputed".
    linkage
        Name of a criterion registered in `linkage.py`.
    distance_threshold
        Cut height, as an alternative to `n_clusters`. Mutually exclusive
        with it.

    Fitted attributes
    -----------------
    linkage_, children_
        The hierarchy; see `HierarchyMixin`.
    distances_ : ndarray of shape (m - 1,)
        Merge or split height at each step, for the dendrogram.
    """

    distances_: Any

    def __init__(
        self,
        n_clusters: int | None = None,
        *,
        metric: MetricLike = "euclidean",
        linkage: str = "ward",
        distance_threshold: float | None = None,
    ) -> None:
        self.n_clusters = n_clusters
        self.metric = metric
        self.linkage = linkage
        self.distance_threshold = distance_threshold

    def cut(
        self, n_clusters: int | None = None, threshold: float | None = None
    ) -> Labels:
        """Return the partition obtained by cutting the fitted hierarchy.

        Concrete for the whole family: cutting a linkage matrix does not
        depend on how the matrix was built.
        """
        raise NotImplementedError

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Build the hierarchy, then apply the requested cut, if any."""
        raise NotImplementedError

    @abstractmethod
    def _build_hierarchy(self, X: MatrixLike) -> None:
        """Construct the tree and set `linkage_`, `children_`, `distances_`.

        The one step that differs between agglomerative and divisive
        construction, and the only one a concrete method must write.
        """
        ...
