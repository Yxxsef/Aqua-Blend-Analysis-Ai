"""
Input validation helpers.

Thin wrappers over `sklearn.utils.validation`, added only where this
package needs a check scikit-learn does not provide -- a square matrix
supplied as precomputed input, a label vector using the noise convention,
a request for a number of clusters. Call these from `fit`, never from
`__init__`.

Wrapping rather than reimplementing keeps the error messages and the
`n_features_in_`/`feature_names_in_` bookkeeping consistent with the rest
of the ecosystem.

The precomputed-matrix checks are implemented here and nowhere else.
`PrecomputedMixin` dispatches to them; no component should repeat the
logic, because two implementations of one rule diverge. They are the only
functions in this module that are written rather than declared: the
failures they catch -- a similarity matrix passed as a dissimilarity, a
squared distance, a non-zero diagonal -- do not raise on their own. They
produce a plausible-looking partition that is wrong, which is the kind of
error Sect. 4.5 exists to prevent.
"""

from __future__ import annotations

from typing import Any

import inspect

import numpy as np
from scipy.spatial.distance import squareform
from sklearn.utils.validation import check_array

from .types import DissimilarityMatrix, Labels, MatrixLike, Seed

#: scikit-learn renamed `force_all_finite` to `ensure_all_finite` in 1.6.
#: Resolved once here so callers pass one name across the supported range.
FINITE_KWARG = (
    "ensure_all_finite"
    if "ensure_all_finite" in inspect.signature(check_array).parameters
    else "force_all_finite"
)


def finite_policy(allow_missing: bool) -> dict[str, Any]:
    """Return the `check_array` keyword controlling NaN handling.

    `allow-nan` rather than `False`: a method declaring `handles_missing`
    tolerates missing values, not infinities.
    """
    return {FINITE_KWARG: "allow-nan" if allow_missing else True}

#: Absolute tolerance for the diagonal and symmetry checks. Loose enough to
#: accept a matrix that has been through a float32 round trip.
_TOL = 1e-6


# --- Feature matrices ------------------------------------------------------


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

    For components. An estimator does not call this: `BaseComponent.fit`
    routes through scikit-learn's `_validate_data`, which applies the same
    rules and additionally records `n_features_in_` and
    `feature_names_in_`. This function is for the objects that are not
    estimators and so have no such method -- validity indices, most of all.
    """
    return check_array(
        X,
        dtype=dtype,
        ensure_min_samples=min_samples,
        **finite_policy(allow_missing),
    )


# --- Precomputed square matrices -------------------------------------------


def _as_square(
    M: MatrixLike,
    *,
    name: str,
    n_samples: int | None = None,
    allow_missing: bool = False,
) -> np.ndarray:
    """Coerce to a square float array, accepting SciPy's condensed form."""
    M = np.asarray(M, dtype=float)

    if M.ndim == 1:
        try:
            M = squareform(M)
        except ValueError as exc:
            raise ValueError(
                f"{name} is one-dimensional but is not a valid condensed "
                f"distance vector: {exc}"
            ) from exc

    if M.ndim != 2 or M.shape[0] != M.shape[1]:
        raise ValueError(f"{name} must be square; got shape {M.shape}.")

    if n_samples is not None and M.shape[0] != n_samples:
        raise ValueError(
            f"{name} has shape {M.shape}, but {n_samples} observations were "
            f"expected. A precomputed matrix must cover exactly the sample "
            f"being fitted."
        )

    if not allow_missing and not np.isfinite(M).all():
        raise ValueError(
            f"{name} contains NaN or infinite entries. Pass allow_missing=True "
            f"only for a measure that declares accepts_missing."
        )

    return M


def _require_symmetric(M: np.ndarray, name: str) -> None:
    if M.size and np.nanmax(np.abs(M - M.T)) > _TOL:
        worst = float(np.nanmax(np.abs(M - M.T)))
        raise ValueError(
            f"{name} is not symmetric (largest discrepancy {worst:.3g}). "
            f"A method that reads only one triangle would silently discard "
            f"half of an asymmetric measure."
        )


def _require_non_negative(M: np.ndarray, name: str) -> None:
    if M.size and np.nanmin(M) < -_TOL:
        raise ValueError(
            f"{name} contains negative entries (minimum {float(np.nanmin(M)):.3g})."
        )


def _looks_like_similarity(M: np.ndarray) -> bool:
    """True where each diagonal entry is the largest in its row.

    The signature of a similarity matrix, and the most common way a
    precomputed input is wrong.
    """
    if not M.size or not np.isfinite(M).all():
        return False
    return bool(np.all(np.diagonal(M) >= M.max(axis=1) - _TOL))


def check_dissimilarity_matrix(
    D: MatrixLike,
    *,
    symmetric: bool = True,
    n_samples: int | None = None,
    allow_missing: bool = False,
) -> DissimilarityMatrix:
    """Validate a precomputed (m, m) dissimilarity matrix.

    Checks squareness, a zero diagonal and non-negativity. Symmetry is
    checked by default but can be relaxed: Def. 2 permits a dissimilarity
    that is not a metric, so an asymmetric measure is admissible provided
    the consuming method tolerates it.

    The triangle inequality is deliberately not checked -- it is O(m^3)
    over all triples, and Def. 2 permits its violation. Methods whose
    correctness depends on it read `BaseDissimilarity.is_metric`, which is
    a declaration.
    """
    D = _as_square(D, name="dissimilarity matrix", n_samples=n_samples, allow_missing=allow_missing)
    _require_non_negative(D, "dissimilarity matrix")

    diagonal = np.diagonal(D)
    if diagonal.size and np.nanmax(np.abs(diagonal)) > _TOL:
        hint = ""
        if _looks_like_similarity(D):
            hint = (
                " Each diagonal entry is the largest in its row, which is the "
                "signature of a similarity matrix -- pass it to "
                "check_affinity_matrix or check_kernel_matrix instead, or "
                "convert it with BaseDissimilarity.to_similarity."
            )
        raise ValueError(
            f"dissimilarity matrix has a non-zero diagonal (largest "
            f"{float(np.nanmax(np.abs(diagonal))):.3g}); d(x, x) must be 0.{hint}"
        )

    if symmetric:
        _require_symmetric(D, "dissimilarity matrix")
    return D


def check_affinity_matrix(
    S: MatrixLike,
    *,
    n_samples: int | None = None,
    allow_missing: bool = False,
) -> DissimilarityMatrix:
    """Validate a precomputed (m, m) affinity matrix.

    The edge weights of a similarity graph: non-negative and symmetric,
    with an unconstrained diagonal. Both requirements are structural --
    a negative weight makes the graph Laplacian meaningless, and an
    asymmetric one is not an undirected graph.
    """
    S = _as_square(S, name="affinity matrix", n_samples=n_samples, allow_missing=allow_missing)
    _require_non_negative(S, "affinity matrix")
    _require_symmetric(S, "affinity matrix")
    return S


def check_kernel_matrix(
    K: MatrixLike,
    *,
    n_samples: int | None = None,
    allow_missing: bool = False,
) -> DissimilarityMatrix:
    """Validate a precomputed (m, m) kernel matrix.

    Symmetric, with a non-negative diagonal since k(x, x) is a squared
    norm in the feature space. Off-diagonal entries may be negative -- a
    linear kernel on centred data routinely produces them -- so this is
    not an affinity check.

    Positive semi-definiteness is not verified here: it costs an
    eigendecomposition, which the technique performs anyway, and negative
    eigenvalues are more usefully reported from there with their
    magnitudes than as a boolean at the door.
    """
    K = _as_square(K, name="kernel matrix", n_samples=n_samples, allow_missing=allow_missing)
    _require_symmetric(K, "kernel matrix")

    diagonal = np.diagonal(K)
    if diagonal.size and np.nanmin(diagonal) < -_TOL:
        raise ValueError(
            f"kernel matrix has a negative diagonal entry "
            f"({float(np.nanmin(diagonal)):.3g}); k(x, x) is a squared norm "
            f"and cannot be negative."
        )
    return K


# --- Labels and parameters -------------------------------------------------


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
