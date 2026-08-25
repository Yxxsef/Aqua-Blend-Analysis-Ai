"""
Base class for hybrid methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from ...core.base import BaseClusterer
from ...core.types import MatrixLike


class BaseHybridClusterer(BaseClusterer, ABC):
    """A clustering method composed of other components.

    Holds its constituents as ordinary parameters, so `get_params(deep=True)`
    reaches into them and a hyperparameter search can tune the composition
    as one object. This is the reason to compose through the contract
    rather than by calling one method inside another.

    Parameters
    ----------
    steps
        The constituent components, in the order applied. Each must satisfy
        a protocol from `core.protocols`; the subclass says which.

    Fitted attributes
    -----------------
    steps_ : list
        The fitted constituents, retained so that an intermediate result --
        the map before the partition, say -- can still be inspected and
        plotted after fitting.
    """

    steps_: list[Any]

    def __init__(self, steps: Sequence[Any] | None = None) -> None:
        self.steps = steps

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Fit the constituents in order and derive `labels_` from the last."""
        raise NotImplementedError

    @abstractmethod
    def _check_steps(self) -> None:
        """Verify each constituent satisfies the protocol its position needs.

        Abstract because only the hybrid knows what it requires of each
        position. Checked before fitting: a mis-ordered composition should
        fail immediately, not after the expensive step.
        """
        ...
