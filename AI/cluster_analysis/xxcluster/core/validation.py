"""
Input validation helpers.

Thin wrappers over `sklearn.utils.validation`, added only where this
package needs a check scikit-learn does not provide -- a square matrix
supplied as precomputed input, a label vector using the noise convention,
a request for a number of clusters. Call these from `fit`, never from
`__init__`.

`validate_data` is re-exported unchanged, so a component reaches every
input check through this one module rather than importing some from here
and some from scikit-learn.

Wrapping rather than reimplementing keeps the error messages and the
`n_features_in_`/`feature_names_in_` bookkeeping consistent with the rest
of the ecosystem.

The precomputed-matrix checks are implemented here and nowhere else.
`PrecomputedMixin` dispatches to them; no component should repeat the
logic, because two implementations of one rule diverge. They came first
because the failures they catch -- a similarity matrix passed as a
dissimilarity, a squared distance, a non-zero diagonal -- do not raise on
their own. They produce a plausible-looking partition that is wrong,
which is the kind of error Sect. 4.5 exists to prevent.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.spatial.distance import squareform
from sklearn.utils import check_random_state as sk_check_random_state
from sklearn.utils.validation import check_array, check_is_fitted, validate_data

from .exceptions import NotFittedError
from .types import NOISE_LABEL, DissimilarityMatrix, Labels, MatrixLike, Seed

__all__ = [
    "validate_data",
    "finite_policy",
    "check_matrix",
    "check_dissimilarity_matrix",
    "check_affinity_matrix",
    "check_kernel_matrix",
    "check_labels",
    "check_n_clusters",
    "check_random_state",
    "ensure_fitted",
]


def finite_policy(allow_missing: bool) -> dict[str, Any]:
    """Return the `check_array` keyword controlling NaN handling.

    `allow-nan` rather than `False`: a method declaring `handles_missing`
    tolerates missing values, not infinities.

    The keyword is `ensure_all_finite`, which is scikit-learn's name from
    1.6 onwards; the earlier `force_all_finite` was removed in 1.8, and
    `requirements.txt` floors above the rename so no branch is needed.
    """
    return {"ensure_all_finite": "allow-nan" if allow_missing else True}

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

    Integral floats are accepted and converted, because a label vector that
    has been through a DataFrame column or a `np.zeros` initialisation
    arrives as float without meaning anything different. Non-integral
    values are refused: they are memberships, not a partition, and
    truncating them would silently defuzzify.

    `allow_noise=False` is passed by a consumer that cannot interpret an
    unassigned observation -- most validity indices, per
    `BaseValidityIndex.handles_noise`. Refusing here forces the caller to
    decide what happens to the noise points, rather than having them
    scored as though they were a cluster of their own.
    """
    labels = np.asarray(labels)

    if labels.ndim != 1:
        raise ValueError(
            f"labels must be a one-dimensional vector of cluster indices; got "
            f"shape {labels.shape}. An (m, |C|) array is a membership matrix "
            f"-- defuzzify it first."
        )

    if not np.issubdtype(labels.dtype, np.integer):
        try:
            as_float = np.asarray(labels, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"labels must be integer cluster indices; got dtype "
                f"{labels.dtype}. Encode names to indices before scoring."
            ) from exc
        if not np.isfinite(as_float).all() or not np.array_equal(
            as_float, np.floor(as_float)
        ):
            raise ValueError(
                "labels contains non-integral values, so it is a membership "
                "vector rather than a partition."
            )
        labels = as_float.astype(int)

    if n_samples is not None and labels.shape[0] != n_samples:
        raise ValueError(
            f"labels has length {labels.shape[0]}, but {n_samples} observations "
            f"were expected."
        )

    if labels.size and labels.min() < NOISE_LABEL:
        raise ValueError(
            f"labels contains {int(labels.min())}; {NOISE_LABEL} is the only "
            f"negative label, and it means noise."
        )

    if not allow_noise and labels.size and (labels == NOISE_LABEL).any():
        n_noise = int((labels == NOISE_LABEL).sum())
        raise ValueError(
            f"labels marks {n_noise} observation(s) as noise, which this "
            f"consumer is not defined on. Exclude them explicitly, or use one "
            f"that declares handles_noise."
        )

    return labels


def check_n_clusters(n_clusters: Any, *, n_samples: int | None = None) -> int:
    """Validate a requested number of clusters, 2 <= |C| <= m.

    The lower bound is 2 by Def. 2: one cluster is not a partition of the
    data into groups, and every validity index of Sect. 4.2 is undefined
    there since none has a between-cluster term to compute.
    """
    if isinstance(n_clusters, bool) or not isinstance(n_clusters, (int, np.integer)):
        raise ValueError(
            f"n_clusters must be an integer; got {n_clusters!r}. A method that "
            f"determines |C| itself should leave it unset rather than pass None."
        )

    n_clusters = int(n_clusters)
    if n_clusters < 2:
        raise ValueError(
            f"n_clusters must be at least 2; got {n_clusters}. A single cluster "
            f"is not a partition, and every validity index is undefined on it."
        )

    if n_samples is not None and n_clusters > n_samples:
        raise ValueError(
            f"n_clusters={n_clusters} exceeds the {n_samples} observations "
            f"available."
        )

    return n_clusters


def check_random_state(seed: Seed) -> Any:
    """Normalise a seed to a random state, so runs are reproducible.

    Not a bare re-export of scikit-learn's function of the same name: that
    one rejects a `numpy.random.Generator`, which is the modern interface
    and which `core.types.Seed` admits. A Generator is passed through
    unchanged; everything else goes to scikit-learn so that a legacy
    `RandomState` still behaves exactly as a backend expects.
    """
    if isinstance(seed, np.random.Generator):
        return seed
    return sk_check_random_state(seed)


def ensure_fitted(component: Any, *attributes: str) -> None:
    """Raise `NotFittedError` unless every named attribute is present.

    With no attributes named, falls back to the component's own
    `_required_fitted` declaration -- so a caller writes `ensure_fitted(m)`
    and the check stays correct as the class's declaration grows. Where
    there is no declaration either, scikit-learn's convention applies: any
    attribute ending in an underscore counts as evidence of fitting.
    """
    names = tuple(attributes)
    if not names:
        declared = getattr(component, "_required_fitted_attributes", None)
        names = tuple(declared()) if callable(declared) else ()

    if not names:
        check_is_fitted(component)
        return

    missing = [name for name in names if not hasattr(component, name)]
    if missing:
        raise NotFittedError(
            f"{type(component).__name__} is not fitted: {', '.join(missing)} "
            f"missing. Call fit before using this component."
        )
