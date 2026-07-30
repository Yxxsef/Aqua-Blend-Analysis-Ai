"""
Base class for fuzzy methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ....core.mixins import InductiveMixin, SoftAssignmentMixin
from ....core.types import ArrayLike, Labels, MatrixLike, Memberships, MetricLike
from ..base import BasePartitionalClusterer


class BaseFuzzyClusterer(
    SoftAssignmentMixin, InductiveMixin, BasePartitionalClusterer, ABC
):
    """A method assigning graded memberships rather than single labels.

    The iteration mirrors the prototype family -- update memberships,
    update prototypes -- with the assignment step relaxed from a hard
    argmin to a weighted one.

    `labels_` is still set, as the contract requires, by defuzzifying
    `memberships_`; both are reported, since the labels alone discard the
    distinction the method exists to capture.

    Parameters
    ----------
    fuzzifier
        The exponent m controlling how soft the partition is. m -> 1
        recovers crisp assignment; large m drives all memberships towards
        uniform. Data-dependent and subjective, one of the hyperparameters
        Sect. 2.1 flags as such, so its selection must be reported.

    Fitted attributes
    -----------------
    memberships_ : ndarray of shape (n, |C|)
    cluster_centers_ : ndarray of shape (|C|, d)
        Prototypes, each a weighted combination of every observation.
    fuzzy_partition_coefficient_ : float
        Summary of partition crispness, used for model selection within
        the family.
    """

    cluster_centers_: ArrayLike
    fuzzy_partition_coefficient_: float

    def __init__(
        self,
        n_clusters: int = 2,
        *,
        fuzzifier: float = 2.0,
        metric: MetricLike = "euclidean",
        max_iter: int = 300,
        tol: float = 1e-4,
        n_init: int = 10,
        random_state: Any = None,
    ) -> None:
        super().__init__(
            n_clusters=n_clusters,
            max_iter=max_iter,
            tol=tol,
            n_init=n_init,
            random_state=random_state,
        )
        self.fuzzifier = fuzzifier
        self.metric = metric

    def predict(self, X: MatrixLike) -> Labels:
        """Assign each observation to its highest-membership cluster."""
        raise NotImplementedError

    def predict_proba(self, X: MatrixLike) -> Memberships:
        """Return the membership of each observation in each cluster."""
        raise NotImplementedError

    def _fit_once(self, X: MatrixLike, random_state: Any) -> Any:
        """Alternate the membership and prototype steps until convergence."""
        raise NotImplementedError

    @abstractmethod
    def _update_memberships(self, X: MatrixLike, centers: ArrayLike) -> Memberships:
        """Membership step, given the current prototypes."""
        ...

    @abstractmethod
    def _update_centers(self, X: MatrixLike, memberships: Memberships) -> ArrayLike:
        """Prototype step, given the current memberships."""
        ...
