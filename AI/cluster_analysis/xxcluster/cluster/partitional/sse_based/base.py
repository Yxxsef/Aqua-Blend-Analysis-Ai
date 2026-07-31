"""
Base class for prototype-based (SSE) methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ....core.mixins import InductiveMixin
from ....core.types import ArrayLike, Labels, MatrixLike, MetricLike, Seed
from ..base import BasePartitionalClusterer


class BasePrototypeClusterer(InductiveMixin, BasePartitionalClusterer, ABC):
    """A method representing each cluster by a single prototype.

    Fitting alternates assignment and prototype update until the criterion
    stops improving. Subclasses define what a prototype is and how it is
    recomputed -- a mean, a medoid, a median -- and inherit the loop.

    Inductive by construction: `predict` assigns to the nearest prototype
    under the same measure used at fit time.

    Parameters
    ----------
    init
        Initialisation strategy, or an explicit array of prototypes. The
        dominant control on which local optimum is reached, so its value
        belongs with the reported result.
    metric
        Measure used for both assignment and, where the method requires it,
        the prototype update. Note that not every measure admits a closed
        form update -- a mean minimises squared Euclidean distance and not
        much else -- so a subclass must state which measures it accepts.

    Fitted attributes
    -----------------
    cluster_centers_ : ndarray of shape (|C|, n)
        Prototypes in the feature space, or the indices of the chosen
        observations for medoid methods.
    inertia_ : float
        Final SSE; the criterion value, exposed under scikit-learn's name.
    """

    cluster_centers_: ArrayLike
    inertia_: float

    def __init__(
        self,
        n_clusters: int = 2,
        *,
        init: str | ArrayLike = "k-means++",
        metric: MetricLike = "euclidean",
        max_iter: int = 300,
        tol: float = 1e-4,
        n_init: int = 10,
        random_state: Seed = None,
    ) -> None:
        super().__init__(
            n_clusters=n_clusters,
            max_iter=max_iter,
            tol=tol,
            n_init=n_init,
            random_state=random_state,
        )
        self.init = init
        self.metric = metric

    def predict(self, X: MatrixLike) -> Labels:
        """Assign each observation to the nearest fitted prototype."""
        raise NotImplementedError

    def transform(self, X: MatrixLike) -> ArrayLike:
        """Return distances to each prototype, shape (m, |C|).

        The prototype-space representation, useful as features for a
        downstream model and for the cluster profiles of Sect. 4.4.
        """
        raise NotImplementedError

    def _fit_once(self, X: MatrixLike, random_state: Any) -> Any:
        """Alternate assignment and update until the criterion converges.

        Shared by the whole family, which is why a concrete method here
        needs only `_update_centers`.
        """
        raise NotImplementedError

    def _assign(self, X: MatrixLike, centers: ArrayLike) -> Labels:
        """Assignment step: nearest prototype for every observation."""
        raise NotImplementedError

    @abstractmethod
    def _update_centers(self, X: MatrixLike, labels: Labels) -> ArrayLike:
        """Update step: recompute each prototype from its members.

        The one method that distinguishes k-means from k-medoids and
        k-medians.
        """
        ...
