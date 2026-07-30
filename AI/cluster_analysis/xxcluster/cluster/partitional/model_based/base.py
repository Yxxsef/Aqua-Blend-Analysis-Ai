"""
Base classes for model-based methods.
"""

from __future__ import annotations

from abc import ABC
from typing import Any

from ....core.mixins import InductiveMixin, ProbabilisticMixin, SoftAssignmentMixin
from ....core.types import ArrayLike, Labels, MatrixLike
from ..base import BasePartitionalClusterer


class BaseModelBasedClusterer(InductiveMixin, BasePartitionalClusterer, ABC):
    """A method that clusters by fitting a model of the data.

    Inductive: the fitted model covers the feature space, so a new
    observation is assigned without refitting.

    Kept separate from `BaseMixtureClusterer` because not every model here
    is probabilistic -- a SOM has prototypes and a neighbourhood, not a
    likelihood -- and a base class should not promise a likelihood that a
    subclass cannot produce.

    Fitted attributes
    -----------------
    model_ : object
        The fitted model itself, whatever form it takes.
    """

    model_: Any

    def predict(self, X: MatrixLike) -> Labels:
        """Assign each observation using the fitted model."""
        raise NotImplementedError


class BaseMixtureClusterer(
    SoftAssignmentMixin, ProbabilisticMixin, BaseModelBasedClusterer, ABC
):
    """A method modelling the data as a mixture of component distributions.

    Adds the two things a generative mixture provides: soft assignment as a
    posterior probability, and a likelihood, hence the information criteria
    used for model selection.

    `n_components` is the model's parameter name and `n_clusters` the
    contract's; a subclass must keep them consistent, since a component is
    a cluster only when no two components are merged.

    Parameters
    ----------
    covariance_type
        Constraint on the component covariances, and the family's real
        control on cluster shape: relaxing it fits elongated and correlated
        clusters that the SSE family cannot, at the cost of parameters
        that must be estimated from the data available.
    """

    def __init__(
        self,
        n_clusters: int = 2,
        *,
        covariance_type: str = "full",
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
        self.covariance_type = covariance_type

    def predict_proba(self, X: MatrixLike) -> ArrayLike:
        """Return the posterior probability of each component."""
        raise NotImplementedError

    def score_samples(self, X: MatrixLike) -> ArrayLike:
        """Return the log-likelihood of each observation."""
        raise NotImplementedError

    def sample(self, n_samples: int = 1, *, random_state: Any = None) -> ArrayLike:
        """Draw synthetic observations from the fitted mixture.

        A generative model can also generate. Retained here because it is
        the bridge to the scenario generation of Sect. 2.3: a mixture
        fitted to operational data is one way to sample scenarios that
        respect the regimes found in it. See `core.base.BaseGenerator`.
        """
        raise NotImplementedError
