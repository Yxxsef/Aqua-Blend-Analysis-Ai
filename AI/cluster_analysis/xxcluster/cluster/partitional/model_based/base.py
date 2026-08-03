"""
Base classes for model-based methods.
"""

from __future__ import annotations

from abc import ABC
from typing import Any

import numpy as np

from ....core.exceptions import NotFittedError
from ....core.mixins import InductiveMixin, ProbabilisticMixin, SoftAssignmentMixin
from ....core.types import ArrayLike, Labels, MatrixLike, Memberships, Seed
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

    #: Direction of `criterion_` for this family. A model-based method
    #: reports a fit quality -- a log-likelihood, typically -- where a larger
    #: value is the better restart, which is the opposite of the SSE default
    #: inherited from `BasePartitionalClusterer`.
    _criterion_higher_is_better = True

    def predict(self, X: MatrixLike) -> Labels:
        """Assign each observation using the fitted model.

        Concrete for the whole family: the model answers the question, so
        this delegates rather than reimplementing an assignment rule that
        would then be free to disagree with the one that was fitted.
        """
        return np.asarray(
            self._model().predict(self._validate_input(X, reset=False))
        ).astype(int)

    def _model(self) -> Any:
        """Return the fitted model, whichever route produced it.

        `model_` for a native method, which names its own model; `backend_`
        for an adapted one, where the third-party estimator *is* the model.
        Checking both is what lets the four methods on this family be
        written once rather than once per route.
        """
        for name in ("model_", "backend_"):
            model = getattr(self, name, None)
            if model is not None:
                return model
        raise NotFittedError(
            f"{type(self).__name__} has neither `model_` nor `backend_`. Call "
            f"fit first; a native method sets `model_` in `_fit_once`, and an "
            f"adapted one gets `backend_` from the adapter."
        )


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

    def predict_proba(self, X: MatrixLike) -> Memberships:
        """Return the posterior probability of each component.

        The soft assignment `SoftAssignmentMixin` promises, shape (m, |C|)
        with rows summing to 1. `predict` is its argmax, and reading this
        instead is how Sect. 4.4 recovers the boundary cases that
        defuzzifying discards.
        """
        return np.asarray(
            self._model().predict_proba(self._validate_input(X, reset=False))
        )

    def score_samples(self, X: MatrixLike) -> ArrayLike:
        """Return the log-likelihood of each observation.

        Read by `ProbabilisticMixin.bic` and `.aic`, which is how a mixture
        offers an alternative to the internal indices of Sect. 4.2 for
        choosing the number of clusters.
        """
        return np.asarray(
            self._model().score_samples(self._validate_input(X, reset=False))
        )

    def sample(
        self, n_samples: int = 1, *, random_state: Seed = None
    ) -> tuple[ArrayLike, Labels]:
        """Draw synthetic observations from the fitted mixture.

        A generative model can also generate. Retained here because it is
        the bridge to the scenario generation of Sect. 2.3: a mixture
        fitted to operational data is one way to sample scenarios that
        respect the regimes found in it. See `core.base.BaseGenerator`.

        Returns the draws and the component each came from, so a generated
        observation can be attributed to the regime that produced it -- a
        scenario without that attribution cannot be interpreted, only used.

        Note that a mixture has unbounded support. A draw may therefore be
        physically impossible -- a negative concentration, a rate above
        plant capacity -- and nothing here clips it: silently moving a draw
        onto a feasible boundary piles probability mass there, and whatever
        consumes the sample would take that mass at face value. Rejecting
        and redrawing is the caller's decision, and the rejection rate is a
        finding about the fitted model worth reporting.
        """
        model = self._model()
        sampler = getattr(model, "sample", None)
        if sampler is None:
            raise NotImplementedError(
                f"{type(model).__name__} does not sample, so "
                f"{type(self).__name__} cannot generate from it."
            )

        if random_state is None:
            return sampler(n_samples)

        # Backends of this family take the seed from the estimator rather
        # than from the call, so a per-call seed is applied by setting it
        # for the draw and restoring it afterwards -- leaving it changed
        # would make the next draw depend on this one.
        if not hasattr(model, "random_state"):
            raise NotImplementedError(
                f"{type(model).__name__} exposes no `random_state`, so a "
                f"per-call seed cannot be honoured. Set the seed on the "
                f"estimator before fitting instead."
            )
        previous = model.random_state
        try:
            model.random_state = random_state
            return sampler(n_samples)
        finally:
            model.random_state = previous
