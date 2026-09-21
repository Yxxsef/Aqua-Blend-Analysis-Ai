"""Gower dissimilarity for incomplete, explicitly typed observations.

Document: Sect. 7.1, ``sec:measure:gower`` (01-gower.tex).
Original similarity: Gower (1971), doi:10.2307/2528823; we return 1 - S.
Ordinal scope: declared, equally spaced ordered levels, not Podani's
tie-adjusted alternative (1999), doi:10.2307/1224438. Those two sources
await assigned keys in the shared citation sheet. Existing references:
ref_8 (metric axioms) and ref_3 (clustering challenges).
"""

from __future__ import annotations

from collections.abc import Mapping
from numbers import Integral, Number
from typing import ClassVar

import numpy as np
import pandas as pd
from scipy import sparse

from ...core.registry import register
from ...core.tags import Capabilities
from ...core.types import Backend, Scaling
from ...core.validation import ensure_fitted, validate_data
from .base import BaseDissimilarity


@register("gower")
class Gower(BaseDissimilarity):
    """Weighted Gower dissimilarity with ranges learned only during fit.

    Parameters
    ----------
    feature_types : sequence of str or None, default=None
        One type per column: ``numeric``, ``categorical``, ``ordinal``,
        ``symmetric_binary`` or ``asymmetric_binary``. None means every
        column is numeric. Types are modelling decisions, never inferred
        from category codes or column values.
    weights : array-like of shape (n,) or None, default=None
        Finite, non-negative feature weights, at least one positive.
        None assigns equal weights. Zero disables a feature. Fitting
        rescales a copy by the maximum, leaving the parameter unchanged.
    ordinal_categories : dict or None, default=None
        Column positions mapped to sequences of levels in increasing
        order, required for every ordinal column. The distance between
        levels is their positional difference divided by (levels - 1).
        This assumes equally spaced ranks; it does not estimate empirical
        ranks or implement Podani's tie correction. Unknown levels fail.

    Notes
    -----
    Missing values (None, NaN, pd.NA, NaT) exclude that feature for the
    affected pair. An asymmetric binary feature additionally excludes
    joint zeros. Binary observations must be 0/1 or booleans. Nominal
    categories use equality, including previously unseen categories.

    Constant numeric features, single-level ordinal features and columns
    entirely missing at fit are excluded from both sums for every pair.
    Query batches never update these decisions or the fitted ranges.
    Numeric differences beyond a fitted range saturate at 1; this is an
    explicit out-of-range extension, not a claim from the original paper.

    When the denominator is zero, identical vectors (including matching
    missing positions) have distance 0 by convention. Every other such
    pair raises ValueError: absence of evidence is not a measured distance.
    This convention also makes square, rectangular and scalar calls agree.
    Output is symmetric and in [0, 1], but pair-dependent availability can
    violate identity of indiscernibles and the triangle inequality.

    ``fit`` is inherited. Only ``_fit`` estimates state. The local input
    hook keeps sklearn's shape/name checks but permits declared mixed
    values; the shared BaseComponent otherwise forces numeric input.

    Fitted attributes
    -----------------
    feature_types_ : tuple of str
        Validated schema in feature order.
    weights_ : ndarray of shape (n,)
        Rescaled copy of feature weights.
    ranges_ : ndarray of shape (n,)
        Observed numeric ranges or declared ordinal rank ranges; NaN for
        nominal/binary columns or numeric columns with no observations.
    active_ : ndarray of shape (n,)
        Features with positive weight and usable training information.
    ordinal_categories_ : dict
        Independent, immutable level sequences used for future queries.
    """

    is_metric = False
    is_symmetric = True
    accepts_missing = True
    accepts_categorical = True
    bounded = (0.0, 1.0)

    _required_fitted = (
        "feature_types_", "weights_", "ranges_", "active_", "ordinal_categories_",
    )
    _capabilities: ClassVar[Capabilities] = Capabilities(
        backend=Backend.NATIVE,
        handles_missing=True,
        handles_categorical=True,
        deterministic=True,
        scale_invariant=True,  # positive numeric rescaling, with refitting
        scales_to=Scaling.MEDIUM,
        time_complexity="O(m * n) fit; O(m * m_prime * n) pairwise",
        space_complexity="O(m * m_prime + (m + m_prime) * n)",
        doc_label="sec:measure:gower",
        references=("ref_8", "ref_3"),
    )

    def __init__(self, *, feature_types=None, weights=None, ordinal_categories=None):
        self.feature_types = feature_types
        self.weights = weights
        self.ordinal_categories = ordinal_categories

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        tags.input_tags.allow_nan = True
        tags.input_tags.categorical = True
        tags.input_tags.string = True
        return tags

    def _validate_input(self, X, *, reset=True):
        # Keep column names for sklearn's feature-order check. Normalize
        # missing *sentinels*, never replace a missing measurement.
        if isinstance(X, pd.DataFrame):
            X = X.astype(object).where(X.notna(), np.nan)
        elif not sparse.issparse(X):
            X = np.asarray(X, dtype=object)
            X = np.where(pd.isna(X), np.nan, X)
        X = validate_data(self, X, reset=reset, dtype=None, ensure_all_finite=False)
        for value in np.asarray(X, dtype=object).flat:
            if isinstance(value, complex):
                raise ValueError("Complex data not supported")
            if isinstance(value, Number) and not pd.isna(value) and not np.isfinite(value):
                raise ValueError("Input contains infinity or a value too large.")
        return np.asarray(X, dtype=object)

    def _fit(self, X, y=None, **fit_params):
        n = X.shape[1]
        allowed = {"numeric", "categorical", "ordinal", "symmetric_binary", "asymmetric_binary"}
        if self.feature_types is None:
            kinds = ("numeric",) * n
        else:
            if isinstance(self.feature_types, str):
                raise ValueError("feature_types must be a sequence with one type per column.")
            kinds = tuple(self.feature_types)
            if len(kinds) != n or any(not isinstance(k, str) or k not in allowed for k in kinds):
                raise ValueError(f"feature_types must contain {n} entries from {sorted(allowed)}.")

        weights = np.ones(n) if self.weights is None else np.asarray(self.weights, dtype=float)
        if (weights.shape != (n,) or not np.isfinite(weights).all()
                or (weights < 0).any() or not (weights > 0).any()):
            raise ValueError("weights must be finite, non-negative, length n, and not all zero.")
        weights = weights / weights.max()

        orders = {} if self.ordinal_categories is None else self.ordinal_categories
        if not isinstance(orders, Mapping):
            raise ValueError("ordinal_categories must map ordinal column positions to ordered levels.")
        expected = {j for j, kind in enumerate(kinds) if kind == "ordinal"}
        if (any(not isinstance(j, Integral) or isinstance(j, bool) for j in orders)
                or set(orders) != expected):
            raise ValueError("ordinal_categories must specify exactly the ordinal column positions.")
        levels = {}
        for j, order in orders.items():
            if isinstance(order, (str, bytes, set, frozenset)):
                raise ValueError("Ordinal levels must be an ordered sequence.")
            order = tuple(order)
            try:
                valid = bool(order) and len(set(order)) == len(order) and not any(pd.isna(v) for v in order)
            except (TypeError, ValueError):
                valid = False
            if not valid:
                raise ValueError("Ordinal levels must be distinct, hashable, non-missing scalars.")
            levels[j] = order

        # Build locals first: a failed fit must not leave a complete set
        # of declared fitted attributes that falsely reports success.
        ranges = np.full(n, np.nan)
        active = weights > 0
        for j, kind in enumerate(kinds):
            values, observed = self._column(X[:, j], kind, levels.get(j), j)
            active[j] &= observed.any()
            if kind == "numeric" and observed.any():
                with np.errstate(over="ignore"):
                    ranges[j] = values[observed].max() - values[observed].min()
                if not np.isfinite(ranges[j]):
                    raise ValueError(f"Numeric range in column {j} exceeds floating-point capacity.")
                active[j] &= ranges[j] > 0
            elif kind == "ordinal":
                ranges[j] = len(levels[j]) - 1
                active[j] &= ranges[j] > 0

        self.feature_types_ = kinds
        self.weights_ = weights
        self.ranges_ = ranges
        self.active_ = active
        self.ordinal_categories_ = levels

    @staticmethod
    def _column(column, kind, levels, j):
        observed = ~pd.isna(column)
        if kind == "categorical":
            try:
                for value in column[observed]:
                    hash(value)
            except TypeError as exc:
                raise TypeError(f"Categorical column {j} requires hashable scalar values.") from exc
            return column, observed
        values = np.full(column.shape, np.nan, dtype=float)
        if kind == "ordinal":
            lookup = {level: rank for rank, level in enumerate(levels)}
            try:
                values[observed] = [lookup[v] for v in column[observed]]
            except (KeyError, TypeError) as exc:
                raise ValueError(f"Unknown ordinal level in column {j}; use the declared levels.") from exc
        else:
            try:
                values[observed] = column[observed].astype(float)
            except (ValueError, TypeError) as exc:
                raise type(exc)(f"Column {j} declared {kind} requires numeric values: {exc}") from exc
            if not np.isfinite(values[observed]).all():
                raise ValueError(f"Column {j} contains a non-finite numeric value.")
            if kind.endswith("binary") and not np.isin(values[observed], [0, 1]).all():
                raise ValueError(f"Binary column {j} requires 0/1 or boolean values.")
        return values, observed

    def __call__(self, x, y):
        """Return d(x, y) through exactly the same path as pairwise."""
        # dtype=object preserves numeric category 1 versus string "1" in
        # heterogeneous Python rows; NumPy's default string coercion would
        # otherwise make the scalar result disagree with the matrix path.
        x = x.to_frame().T if isinstance(x, pd.Series) else np.atleast_2d(np.asarray(x, dtype=object))
        y = y.to_frame().T if isinstance(y, pd.Series) else np.atleast_2d(np.asarray(y, dtype=object))
        return float(self.pairwise(x, y)[0, 0])

    def pairwise(self, X, Y=None):
        """Return a (m, m) or (m, m') float matrix without refitting.

        Iterates over features; all observation pairs are broadcast in
        NumPy. No m-by-m-by-n tensor or scalar-call loop is constructed.
        Inputs and learned ranges are never modified. Raises ValueError
        for non-identical vectors with no positive-weight comparable data.
        """
        ensure_fitted(self)
        X = self._validate_input(X, reset=False)
        Y = X if Y is None else self._validate_input(Y, reset=False)
        shape = (X.shape[0], Y.shape[0])
        numerator = np.zeros(shape, dtype=float)
        denominator = np.zeros(shape, dtype=float)
        identical = np.ones(shape, dtype=bool)

        for j, kind in enumerate(self.feature_types_):
            x, ox = self._column(X[:, j], kind, self.ordinal_categories_.get(j), j)
            y, oy = self._column(Y[:, j], kind, self.ordinal_categories_.get(j), j)
            both = ox[:, None] & oy[None, :]
            equal = x[:, None] == y[None, :]
            identical &= (both & equal) | (~ox[:, None] & ~oy[None, :])
            if not self.active_[j]:
                continue
            if kind == "asymmetric_binary":
                both &= ~((x[:, None] == 0) & (y[None, :] == 0))
            if kind in ("numeric", "ordinal"):
                with np.errstate(over="ignore", invalid="ignore"):
                    delta = np.minimum(np.abs(x[:, None] - y[None, :]) / self.ranges_[j], 1.0)
            else:
                delta = ~equal
            numerator += self.weights_[j] * np.where(both, delta, 0.0)
            denominator += self.weights_[j] * both

        undefined = (denominator == 0) & ~identical
        if undefined.any():
            i, j = np.argwhere(undefined)[0]
            raise ValueError(
                f"No comparable positive-weight features for pair ({i}, {j}). "
                "Gower is undefined for non-identical observations with no overlap; "
                "review feature coverage rather than impute a distance."
            )
        D = np.divide(numerator, denominator, out=np.zeros(shape), where=denominator > 0)
        return np.clip(D, 0.0, 1.0)
