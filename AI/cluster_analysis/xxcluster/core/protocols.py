"""
Structural interfaces.

The base classes in `xxcluster.core.base` are the recommended way to
satisfy the contract, but they are not the only one: an adapted
third-party estimator, or a plain object supplied by another team, is
acceptable wherever it structurally matches the protocol below. The
pipeline, selection and evaluation layers therefore type against these
protocols and never against a concrete base class.

Runtime-checkable protocols verify method *presence* only, never
signatures; use them for guard clauses, not for validation.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .types import (
    DissimilarityMatrix,
    Embedding,
    Labels,
    LinkageMatrix,
    MatrixLike,
    Memberships,
)


@runtime_checkable
class Estimator(Protocol):
    """The minimum every component honours: parameters in, fitted state out."""

    def get_params(self, deep: bool = True) -> dict[str, Any]: ...

    def set_params(self, **params: Any) -> "Estimator": ...

    def fit(self, X: MatrixLike, y: Any = None) -> "Estimator": ...


@runtime_checkable
class Clusterer(Estimator, Protocol):
    """Partitions the fitted data. `labels_` is the single required output."""

    labels_: Labels

    def fit_predict(self, X: MatrixLike, y: Any = None) -> Labels: ...


@runtime_checkable
class Inductive(Protocol):
    """Assigns observations that were not present at fit time."""

    def predict(self, X: MatrixLike) -> Labels: ...


@runtime_checkable
class SoftClusterer(Protocol):
    """Reports degrees of membership rather than a single label."""

    memberships_: Memberships

    def predict_proba(self, X: MatrixLike) -> Memberships: ...


@runtime_checkable
class Hierarchical(Protocol):
    """Exposes a hierarchy that can be cut after fitting."""

    linkage_: LinkageMatrix

    def cut(
        self, n_clusters: int | None = None, threshold: float | None = None
    ) -> Labels: ...


@runtime_checkable
class Transformer(Estimator, Protocol):
    """Maps data into another representation."""

    def transform(self, X: MatrixLike) -> Any: ...


@runtime_checkable
class DimReducer(Transformer, Protocol):
    """Maps data into a lower-dimensional space."""

    def transform(self, X: MatrixLike) -> Embedding: ...


@runtime_checkable
class Dissimilarity(Protocol):
    """A dissimilarity measure d(., .), not necessarily a metric.

    See Def. 1 and Def. 2 of the documentation: a clustering method may
    use a measure that violates the triangle inequality, so metric
    properties are declared rather than assumed.
    """

    def pairwise(self, X: MatrixLike, Y: MatrixLike | None = None) -> DissimilarityMatrix: ...

    def __call__(self, x: MatrixLike, y: MatrixLike) -> float: ...


@runtime_checkable
class ValidityIndex(Protocol):
    """Scores a partition. `higher_is_better` fixes the direction."""

    higher_is_better: bool

    def score(self, X: MatrixLike, labels: Labels, **kwargs: Any) -> float: ...
