"""
Input validation helpers.

Thin wrappers over `sklearn.utils.validation`, added only where this
package needs a check scikit-learn does not provide -- a dissimilarity
matrix, a label vector using the noise convention, a request for a number
of clusters. Call these from `fit`, never from `__init__`.

Wrapping rather than reimplementing keeps the error messages and the
`n_features_in_`/`feature_names_in_` bookkeeping consistent with the rest
of the ecosystem.
"""

from __future__ import annotations

from typing import Any

from .types import DissimilarityMatrix, Labels, MatrixLike, Seed


def check_matrix(
    X: MatrixLike,
    *,
    allow_missing: bool = False,
    min_samples: int = 1,
    dtype: Any = "numeric",
) -> Any:
    """Validate and convert a feature matrix of shape (m, n).

    `allow_missing` is opened only by methods declaring `handles_missing`;
    everything else must fail loudly rather than propagate NaN into a
    distance computation.
    """
    raise NotImplementedError


def check_dissimilarity_matrix(D: MatrixLike, *, symmetric: bool = True) -> DissimilarityMatrix:
    """Validate a precomputed (m, m) dissimilarity matrix.

    Checks squareness, a zero diagonal and non-negativity. Symmetry is
    checked by default but can be relaxed: Def. 2 permits a dissimilarity
    that is not a metric, so an asymmetric measure is admissible provided
    the consuming method tolerates it.
    """
    raise NotImplementedError


def check_labels(labels: Any, *, n_samples: int | None = None, allow_noise: bool = True) -> Labels:
    """Validate a crisp label vector.

    Verifies length and integer dtype, and that -1 appears only where
    noise is permitted.
    """
    raise NotImplementedError


def check_n_clusters(n_clusters: Any, *, n_samples: int | None = None) -> int:
    """Validate a requested number of clusters, 2 <= |C| <= m."""
    raise NotImplementedError


def check_random_state(seed: Seed) -> Any:
    """Normalise a seed to a random state, so runs are reproducible."""
    raise NotImplementedError


def ensure_fitted(component: Any, *attributes: str) -> None:
    """Raise `NotFittedError` unless every named attribute is present."""
    raise NotImplementedError
