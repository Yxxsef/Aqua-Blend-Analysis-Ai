"""
Base class for prototype-based (SSE) methods.
"""

from __future__ import annotations

from abc import ABC
from typing import Any

import numpy as np
from sklearn.base import TransformerMixin
from sklearn.metrics import pairwise_distances

from ....core.mixins import InductiveMixin
from ....core.types import ArrayLike, Labels, MatrixLike, MetricLike, Seed
from ....core.validation import ensure_fitted
from ..base import BasePartitionalClusterer


class BasePrototypeClusterer(
    InductiveMixin, TransformerMixin, BasePartitionalClusterer, ABC
):
    """A method representing each cluster by a single prototype.

    Fitting alternates assignment and prototype update until the criterion
    stops improving. Subclasses define what a prototype is and how it is
    recomputed -- a mean, a medoid, a median -- and inherit the loop.

    Inductive by construction: `predict` assigns to the nearest prototype
    under the same measure used at fit time. `TransformerMixin` is mixed in
    because `transform` below maps into prototype space, and scikit-learn
    requires the matching `fit_transform` of anything exposing `transform` --
    without it `check_estimator` fails, which every contributor is told to
    run.

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

    #: Added to the family's declaration; see `BasePartitionalClusterer`.
    #: `inertia_` is scikit-learn's name for the same quantity the family
    #: calls `criterion_`, and an adapted method maps both onto its backend.
    _required_fitted = ("cluster_centers_", "inertia_")

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
        """Assign each observation to the nearest fitted prototype.

        Concrete for the whole family: once the prototypes exist, the
        assignment is the same geometry whatever recomputed them. Reads the
        distances from `transform` rather than recomputing them, so the two
        cannot disagree.
        """
        return np.argmin(self.transform(X), axis=1).astype(int)

    def transform(self, X: MatrixLike) -> ArrayLike:
        """Return distances to each prototype, shape (m, |C|).

        The prototype-space representation, useful as features for a
        downstream model and for the cluster profiles of Sect. 4.4.

        Validated with `reset=False`, so the feature count is checked
        against the fit rather than overwritten -- an X of the wrong width
        is refused here instead of producing distances to prototypes it does
        not correspond to.
        """
        ensure_fitted(self, "cluster_centers_")
        X = self._validate_input(X, reset=False)
        return pairwise_distances(X, self._prototypes(), metric=self._check_metric())

    def _check_metric(self) -> MetricLike:
        """Return the measure to assign under, refusing what it cannot do.

        This family has no `PrecomputedMixin`: a prototype is a point in the
        feature space, and a precomputed matrix covers only the observations
        it was built from, so there is no row for a prototype and no way to
        assign unseen data. Refused by name rather than ignored, because
        silently falling back to Euclidean would report a partition under a
        measure that never ran.
        """
        if self.metric == "precomputed":
            raise NotImplementedError(
                f"{type(self).__name__} cannot assign under "
                f"metric='precomputed': a prototype is a point in the feature "
                f"space and a precomputed matrix has no row for it. Use a "
                f"medoid method, whose prototypes are observations, or pass a "
                f"callable measure."
            )
        return self.metric

    def _prototypes(self) -> ArrayLike:
        """Return `cluster_centers_` as an (|C|, n) array of coordinates."""
        centers = np.asarray(self.cluster_centers_)
        if centers.ndim != 2:
            raise ValueError(
                f"{type(self).__name__}.cluster_centers_ has shape "
                f"{centers.shape}; an (|C|, n) array of coordinates is "
                f"required. A medoid method records the chosen rows in a "
                f"separate `medoid_indices_` and still exposes their "
                f"coordinates here."
            )
        return centers

    def _derive_fitted(self) -> None:
        """Also mirror `criterion_` into `inertia_`.

        They are the same quantity under two names -- the family's and
        scikit-learn's -- so a native method reports it once from
        `_fit_once` and both attributes follow.
        """
        super()._derive_fitted()
        criterion = getattr(self, "criterion_", None)
        if criterion is not None:
            self.inertia_ = float(criterion)

    def _fit_once(self, X: MatrixLike, random_state: Any) -> Any:
        """Alternate assignment and update until the criterion converges.

        Shared by the whole family, which is why a concrete method here
        needs only `_update_centers`.
        """
        raise NotImplementedError

    def _assign(self, X: MatrixLike, centers: ArrayLike) -> Labels:
        """Assignment step: nearest prototype for every observation."""
        raise NotImplementedError

    def _update_centers(self, X: MatrixLike, labels: Labels) -> ArrayLike:
        """Update step: recompute each prototype from its members.

        The one method that distinguishes k-means from k-medoids and
        k-medians. Required of a native method, which inherits the loop in
        `_fit_once`; an adapted method never reaches it.
        """
        raise NotImplementedError
