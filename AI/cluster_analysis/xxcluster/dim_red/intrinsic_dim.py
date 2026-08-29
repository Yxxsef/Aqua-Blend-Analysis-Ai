"""
Intrinsic dimension estimation.

Answers the question that decides how the rest of `dim_red` is used: how
many dimensions does the data actually occupy? An intrinsic dimension well
below d is the evidence for the manifold hypothesis of Sect. 6.2, and it
is also the principled way to choose `n_components` -- as opposed to
choosing 2 because that is what plots.

Estimators here are not reducers: they consume the data and return a
number, so they take the lighter `BaseComponent` contract rather than
`BaseDimReducer`. Report more than one, and report their disagreement:
these estimators are themselves affected by the sample size and noise
that the estimate is meant to characterise.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..core.base import BaseComponent
from ..core.types import ArrayLike, MatrixLike


class BaseIntrinsicDimEstimator(BaseComponent, ABC):
    """Estimates the intrinsic dimension of a dataset.

    Fitted attributes
    -----------------
    dimension_ : float
        Global estimate, not necessarily an integer.
    local_dimension_ : ndarray of shape (m,), optional
        Per-observation estimate, where the method produces one. Worth
        having: a dataset whose local estimates vary substantially is not
        one manifold, and a single global figure would hide that.
    """

    dimension_: float
    local_dimension_: ArrayLike

    @abstractmethod
    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Estimate the dimension and set `dimension_`."""
        ...


def manifold_hypothesis_report(X: MatrixLike, **kwargs: Any) -> dict[str, Any]:
    """Assemble the evidence for or against the manifold hypothesis.

    Runs the available estimators, compares them against the linear
    baseline -- the number of components needed to retain a given share of
    variance -- and returns both the estimates and their spread. Written as
    a function because the object of interest is the comparison, not any
    single estimator, and Objective 4 of the introduction asks for exactly
    that comparison.
    """
    raise NotImplementedError
