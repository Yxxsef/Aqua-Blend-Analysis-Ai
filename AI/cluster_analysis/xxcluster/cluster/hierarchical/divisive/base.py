"""
Base class for Divisive Hierarchical Clustering (DHC).

Two choices distinguish these methods, and both are exposed here: which
cluster to split next, and how to split it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ....core.types import MatrixLike
from ..base import BaseHierarchicalClusterer


class BaseDivisive(BaseHierarchicalClusterer, ABC):
    """Top-down hierarchical construction.

    Parameters
    ----------
    splitter
        Component used to split a selected cluster, where the method
        delegates the split rather than defining it.
    max_depth
        Optional cap on recursion depth, which bounds the cost of the
        exhaustive split search.
    """

    def __init__(
        self,
        n_clusters: int | None = None,
        *,
        metric: Any = "euclidean",
        linkage: str = "ward",
        distance_threshold: float | None = None,
        splitter: Any = None,
        max_depth: int | None = None,
    ) -> None:
        super().__init__(
            n_clusters=n_clusters,
            metric=metric,
            linkage=linkage,
            distance_threshold=distance_threshold,
        )
        self.splitter = splitter
        self.max_depth = max_depth

    def _build_hierarchy(self, X: MatrixLike) -> None:
        """Run the recursive split and record the resulting tree."""
        raise NotImplementedError

    def _select_cluster(self, X: MatrixLike, labels: Any) -> int:
        """Choose the next cluster to split; the first of the two choices.

        Required of a native method; an adapted one never reaches it.
        """
        raise NotImplementedError

    def _split(self, X: MatrixLike) -> Any:
        """Split one cluster in two; the second of the two choices.

        Required of a native method; an adapted one never reaches it.
        """
        raise NotImplementedError
