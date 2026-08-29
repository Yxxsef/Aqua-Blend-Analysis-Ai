"""
Base class for linear techniques.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ...core.base import BaseDimReducer
from ...core.types import ArrayLike, Embedding, MatrixLike


class BaseLinearReducer(BaseDimReducer, ABC):
    """A technique learning a linear map into a lower-dimensional space.

    Inductive by construction, so `transform` and `inverse_transform` are
    both part of the contract here rather than optional.

    Fitted attributes
    -----------------
    components_ : ndarray of shape (n_components, n)
        The learned directions, in terms of the input features. The basis
        of any interpretation of the reduced space, so it is required
        rather than optional.
    mean_ : ndarray of shape (n,)
        Centring applied before projection, needed to invert it.
    explained_variance_ratio_ : ndarray of shape (n_components,)
        Share of variance per component, where the technique defines it.
        Feeds the choice of n_components.
    """

    components_: ArrayLike
    mean_: ArrayLike
    explained_variance_ratio_: ArrayLike

    def transform(self, X: MatrixLike) -> Embedding:
        """Project `X` onto the learned components."""
        raise NotImplementedError

    def inverse_transform(self, X: MatrixLike) -> ArrayLike:
        """Reconstruct an approximation of the original features."""
        raise NotImplementedError

    @abstractmethod
    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Learn the components and set the fitted attributes.

        What the components maximise is the technique: variance for PCA,
        class separation for LDA. `transform` and `inverse_transform` are
        shared, since both are matrix products once the basis is known.
        """
        ...
