"""
Base class for nonlinear techniques.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ...core.base import BaseDimReducer
from ...core.mixins import PrecomputedMixin
from ...core.types import Embedding, MatrixLike, MetricLike, Seed


class BaseManifoldReducer(PrecomputedMixin, BaseDimReducer, ABC):
    """A technique recovering coordinates on a low-dimensional manifold.

    Transductive unless a subclass declares otherwise: `fit_transform` is
    the primary interface, and `transform` on unseen data must either
    implement a genuine out-of-sample extension or refuse. Refitting to
    accommodate new points silently is not acceptable -- it changes the
    embedding of every existing point.

    Most of these techniques reach the data only through pairwise
    dissimilarities, which is why `PrecomputedMixin` is mixed in: a custom
    measure from `xxcluster.measures.dissimilarity` can drive the embedding
    directly, and that is the route to embedding mixed-type data.

    Parameters
    ----------
    metric
        Measure defining the input neighbourhoods, or "precomputed".
    n_neighbors
        Size of the local neighbourhood the technique preserves. The
        balance between local and global structure, and the parameter most
        likely to change the conclusions drawn from a figure.
    random_state
        Required: these embeddings are stochastic, so a figure is only
        reproducible with the seed recorded alongside it.

    Fitted attributes
    -----------------
    embedding_ : ndarray of shape (m, n_components)
        Coordinates of the fitted sample; the primary output.
    stress_ : float
        Discrepancy between input and embedding structure, under whatever
        objective the technique minimises. The quantitative check against
        over-reading a picture.
    """

    stress_: float

    def __init__(
        self,
        n_components: int = 2,
        *,
        metric: MetricLike = "euclidean",
        n_neighbors: int = 15,
        random_state: Seed = None,
    ) -> None:
        super().__init__(n_components=n_components, random_state=random_state)
        self.metric = metric
        self.n_neighbors = n_neighbors

    def transform(self, X: MatrixLike) -> Embedding:
        """Embed unseen observations, where the technique supports it."""
        raise NotImplementedError

    @abstractmethod
    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Optimise the embedding and set `embedding_`.

        Abstract with no shared implementation: these techniques differ in
        the objective itself -- a divergence between neighbour
        distributions, a cross-entropy over a fuzzy simplicial set, a
        stress function -- not merely in its parameters.
        """
        ...

    def trustworthiness(self, X: MatrixLike, n_neighbors: int = 5) -> float:
        """Fraction of input neighbourhoods preserved in the embedding.

        Reported with any embedding used for a conclusion rather than for
        illustration.
        """
        raise NotImplementedError
