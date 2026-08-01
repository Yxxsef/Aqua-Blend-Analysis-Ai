"""
Base class shared by validity indices.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ...core.types import DissimilarityMatrix, Labels, MatrixLike, MetricLike


class BaseValidityIndex(ABC):
    """Scores a clustering result.

    Not a `BaseComponent`: an index is not fitted and holds no state beyond
    its configuration, so the estimator contract would add nothing. It is
    still registered, so that an index can be named in a configuration.

    Class attributes
    ----------------
    name
        Registry key and column heading in the reported tables.
    higher_is_better
        Direction of the index. Required, with no default: an index whose
        direction is assumed is an index that will eventually be compared
        the wrong way round.
    range_
        Attainable range, where bounded, for the interpretation column of
        Table 1 in Sect. 4.2.
    requires_labels_true
        True for external indices, which need a reference partition.
    requires_X
        True where the index reads the data as well as the labels; false
        for indices computed from the contingency table alone.
    handles_noise
        Whether the index is defined when observations are labelled -1. If
        false, the caller must decide explicitly what to do with them, and
        `score` refuses rather than dropping them silently.
    """

    name: str
    higher_is_better: bool
    range_: tuple[float, float] | None = None
    requires_labels_true: bool = False
    requires_X: bool = True
    handles_noise: bool = False

    @abstractmethod
    def score(
        self,
        X: MatrixLike | None = None,
        labels: Labels | None = None,
        *,
        labels_true: Labels | None = None,
        metric: MetricLike | DissimilarityMatrix = "euclidean",
        **kwargs: Any,
    ) -> float:
        """Return the index value for one clustering result.

        The signature is uniform across all three groups so the evaluation
        harness can call any index the same way; each subclass consumes the
        arguments it declares and ignores the rest.

        `metric` accepts a precomputed dissimilarity matrix as well as a
        name. It should be the same measure the method was fitted with, e.g.
        K-Means determines clusters using Euclidean distance,
        so validity must be a Eulidean distance.
        """
        ...

    def __call__(self, *args: Any, **kwargs: Any) -> float:
        """Alias for `score`, so an index is usable as a plain callable."""
        raise NotImplementedError

    def is_better(self, a: float, b: float) -> bool:
        """Report whether score `a` is better than `b` under this index.

        The single place the direction is applied. Callers compare through
        this rather than with a bare inequality.
        """
        raise NotImplementedError
