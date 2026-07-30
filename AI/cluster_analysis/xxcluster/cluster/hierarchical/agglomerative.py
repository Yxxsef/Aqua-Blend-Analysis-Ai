"""
Agglomerative Hierarchical Clustering (AHC).

Bottom-up construction: begin with n singletons and repeatedly merge the
closest pair under the linkage criterion until one cluster remains.

Concrete methods go here, one class each -- the variants differ only in
their linkage criterion, so most of them are a base class plus a
declaration.
"""

from __future__ import annotations

from abc import ABC
from typing import Any

from ...core.types import MatrixLike
from .base import BaseHierarchicalClusterer


class BaseAgglomerative(BaseHierarchicalClusterer, ABC):
    """Bottom-up hierarchical construction.

    Subclasses supply the linkage criterion; the merge loop itself is
    shared, which is why it lives here rather than in each method. This
    base is therefore complete apart from that criterion, and leaves no
    abstract method behind: a concrete AHC method is a declaration -- a
    linkage, a set of capabilities, a registered name -- and not new code.

    Parameters
    ----------
    connectivity
        Optional sparse structure restricting which pairs may merge. Where
        given, merges are confined to it, which changes the result and must
        be reported with it.
    """

    def __init__(
        self,
        n_clusters: int | None = None,
        *,
        metric: Any = "euclidean",
        linkage: str = "ward",
        distance_threshold: float | None = None,
        connectivity: Any = None,
    ) -> None:
        super().__init__(
            n_clusters=n_clusters,
            metric=metric,
            linkage=linkage,
            distance_threshold=distance_threshold,
        )
        self.connectivity = connectivity

    def _build_hierarchy(self, X: MatrixLike) -> None:
        """Run the merge loop and record the resulting tree."""
        raise NotImplementedError
