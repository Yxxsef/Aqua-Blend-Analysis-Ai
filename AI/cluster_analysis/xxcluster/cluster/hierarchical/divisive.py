"""
Divisive Hierarchical Clustering (DHC).

Top-down construction: begin with one cluster containing every
observation and repeatedly split the cluster selected by the splitting
rule.

Two choices distinguish these methods, and both are exposed here: which
cluster to split next, and how to split it. The splitting step is often a
partitional method applied to a subset, which makes DHC the natural home
for the bisecting variants; a method whose splitting step is doing most of
the work may belong in `hybrid` instead.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ...core.types import MatrixLike
from .base import BaseHierarchicalClusterer


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

    @abstractmethod
    def _select_cluster(self, X: MatrixLike, labels: Any) -> int:
        """Choose the next cluster to split; the first of the two choices."""
        ...

    @abstractmethod
    def _split(self, X: MatrixLike) -> Any:
        """Split one cluster in two; the second of the two choices."""
        ...
