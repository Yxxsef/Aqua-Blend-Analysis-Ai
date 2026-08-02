"""
Base class for graph-theoretic methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ....core.base import BaseClusterer
from ....core.mixins import PrecomputedMixin
from ....core.types import ArrayLike, Embedding, MatrixLike, MetricLike, PrecomputedKind


class BaseGraphClusterer(PrecomputedMixin, BaseClusterer, ABC):
    """A method that clusters by partitioning an affinity graph.

    Fitting has two stages -- build the graph, then partition it -- and
    both are exposed, because a poor result is usually the first stage's
    fault and that is not visible from the labels alone.

    Transductive by default: the graph is built over the fitted sample, so
    adding an observation changes the graph. A subclass with an
    out-of-sample extension must add `InductiveMixin` and declare it.

    Parameters
    ----------
    affinity
        How edge weights are derived: a kernel name, "nearest_neighbors",
        a callable, or "precomputed" to pass an affinity matrix directly.
    n_neighbors
        Neighbourhood size for a k-nearest-neighbour graph. Controls
        connectivity: too small disconnects the graph and the partition
        degenerates to its components.

    Fitted attributes
    -----------------
    affinity_matrix_ : ndarray of shape (m, m)
        The graph actually used.
    embedding_ : ndarray of shape (m, n_components)
        Spectral embedding, where the method computes one.
    """

    #: "precomputed" here means an affinity matrix, not a dissimilarity: the
    #: diagonal is unconstrained and the weights must be non-negative for the
    #: Laplacian to mean anything.
    _precomputed_kind = PrecomputedKind.AFFINITY
    _precomputed_param = "affinity"

    affinity_matrix_: ArrayLike
    embedding_: Embedding

    def __init__(
        self,
        n_clusters: int = 2,
        *,
        affinity: MetricLike = "rbf",
        n_neighbors: int = 10,
        random_state: Any = None,
    ) -> None:
        self.n_clusters = n_clusters
        self.affinity = affinity
        self.n_neighbors = n_neighbors
        self.random_state = random_state

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Build the affinity graph, then partition it."""
        raise NotImplementedError

    def _build_graph(self, X: MatrixLike) -> ArrayLike:
        """Construct the affinity matrix and check it is usable.

        A disconnected graph is a reportable finding, not a silent one.
        """
        raise NotImplementedError

    def _partition_graph(self, affinity: ArrayLike) -> Any:
        """Partition the graph and set the fitted attributes.

        The step that distinguishes the methods, once the graph is fixed:
        an eigendecomposition of the Laplacian, a modularity optimisation,
        a learned assignment.

        Required of a native method; an adapted one never reaches it.
        """
        raise NotImplementedError
