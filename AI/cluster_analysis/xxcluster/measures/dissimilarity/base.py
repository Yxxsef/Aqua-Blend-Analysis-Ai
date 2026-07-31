"""
Base class for dissimilarity measures.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ...core.base import BaseComponent
from ...core.types import ArrayLike, DissimilarityMatrix, MatrixLike


class BaseDissimilarity(BaseComponent, ABC):
    """A measure d(x, y) of how far apart two observations are.

    Derives from `BaseComponent` because some measures are fitted -- a
    Mahalanobis distance needs a covariance, a scaled measure needs feature
    ranges -- and treating those as estimators keeps the fitting inside the
    contract, where it will be refitted per fold rather than leaking
    information across a resampling boundary. Measures that need no fitting
    inherit a `fit` that only records the input dimensions.

    Class attributes
    ----------------
    is_metric
        True where the measure satisfies all three properties of Def. 1.
        Methods that require the triangle inequality check this.
    is_symmetric
        True where d(x, y) = d(y, x). Def. 2 permits asymmetry, so this is
        declared, not assumed.
    accepts_missing, accepts_categorical
        Whether the measure is defined on incomplete or non-numeric input.
        These decide whether a measure can serve mixed data without the
        encoding step that would otherwise impose an arbitrary geometry on
        the categories.
    bounded
        Range of the measure, where it has one; needed to combine measures
        across feature blocks on a common scale.
    """

    is_metric: bool = False
    is_symmetric: bool = True
    accepts_missing: bool = False
    accepts_categorical: bool = False
    bounded: tuple[float, float] | None = None

    @abstractmethod
    def __call__(self, x: ArrayLike, y: ArrayLike) -> float:
        """Return the dissimilarity between two single observations."""
        ...

    @abstractmethod
    def pairwise(
        self, X: MatrixLike, Y: MatrixLike | None = None
    ) -> DissimilarityMatrix:
        """Return all pairwise dissimilarities.

        Shape (m, m) for `X` against itself, or (m, m') where `Y` is given
        and has m' rows.

        Separate from `__call__` because the matrix is what methods
        actually consume, and computing it in one vectorised pass rather
        than m^2 scalar calls is the difference between usable and not.
        """
        ...

    def to_similarity(self, D: DissimilarityMatrix, **kwargs: Any) -> ArrayLike:
        """Convert dissimilarities to similarities.

        Needed by the graph-theoretic family, which requires affinities.
        The conversion is a modelling choice -- a kernel, with its own
        parameter -- so it is explicit rather than implied.
        """
        raise NotImplementedError

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Estimate whatever the measure needs from the data, if anything."""
        raise NotImplementedError
