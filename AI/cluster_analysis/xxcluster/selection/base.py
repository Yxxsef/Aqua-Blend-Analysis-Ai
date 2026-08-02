"""
Base class for selectors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from ..core.base import BaseComponent
from ..core.types import ComponentKind, Labels, MatrixLike, ParamGrid


class BaseSelector(BaseComponent, ABC):
    """Chooses a configuration of a clustering method from the data.

    A selector wraps a method, evaluates it over candidate configurations,
    and exposes the winner. It is itself a component, and so composable,
    registrable and reportable like any other -- a selector wrapping a
    method is a legitimate thing to place in a pipeline, and the search it
    performed is then part of the recorded result rather than something a
    notebook did once.

    Parameters
    ----------
    estimator
        The method to configure. Cloned before each fit, never mutated, so
        the instance handed in is left as the caller left it.
    param_grid
        Candidate configurations.
    scoring
        Index or criterion used to compare candidates. Where several are
        given, all are recorded and the first decides -- their disagreement
        is a result worth keeping.
    refit
        Whether to refit the winning configuration on the full data and
        expose its result directly.

    Fitted attributes
    -----------------
    best_params_ : dict
    best_estimator_ : object
        Present only where `refit` is set.
    results_ : dict
        Every candidate and every score, not only the winner. The input to
        the selection figures, and the record that makes a selection
        auditable.
    labels_ : ndarray of shape (m,)
        Partition of the winning configuration, so a fitted selector can
        stand in for a clusterer.
    """

    _kind: ClassVar[ComponentKind | None] = ComponentKind.SELECTOR

    best_params_: dict[str, Any]
    best_estimator_: Any
    results_: dict[str, Any]
    labels_: Labels

    def __init__(
        self,
        estimator: Any = None,
        *,
        param_grid: ParamGrid | None = None,
        scoring: Any = None,
        refit: bool = True,
    ) -> None:
        self.estimator = estimator
        self.param_grid = param_grid
        self.scoring = scoring
        self.refit = refit

    @abstractmethod
    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Evaluate the candidates and record the selection."""
        ...

    def _evaluate_candidate(self, X: MatrixLike, params: dict[str, Any]) -> dict[str, float]:
        """Fit one candidate and score it under every `scoring` entry."""
        raise NotImplementedError
