"""
Capability mixins.

Clustering methods vary along axes that cut across the taxonomy: a soft
assignment appears in both fuzzy and model-based methods, a hierarchy in
agglomerative and in some density-based methods. Those axes are mixins
rather than base classes, so a method inherits one family base plus the
capabilities it actually has, and no base class carries a method its
subclasses cannot honour.

Rules
-----
* Mix in left of the family base so the mixin's `__init__` and attributes
  resolve first: `class Ward(HierarchyMixin, BaseAgglomerative)`.
* A mixin's presence must agree with the class's `_capabilities`; the
  contract check in `BaseComponent._check_capabilities` enforces the pair.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

import numpy as np

from .exceptions import ContractViolationError
from .types import (
    NOISE_LABEL,
    ArrayLike,
    DissimilarityMatrix,
    Labels,
    LinkageMatrix,
    MatrixLike,
    Memberships,
    PrecomputedKind,
)
from .validation import (
    check_affinity_matrix,
    check_dissimilarity_matrix,
    check_kernel_matrix,
    check_labels,
    ensure_fitted,
)


class InductiveMixin(ABC):
    """Assigns observations unseen at fit time.

    The dividing line between a method that learns a rule covering the
    whole feature space (prototype-based, model-based) and one that only
    labels the sample it was given (most density-based and hierarchical
    methods). Only the former may expose `predict`, because only the
    former can answer without refitting.
    """

    @abstractmethod
    def predict(self, X: MatrixLike) -> Labels:
        """Assign each observation in `X` to a fitted cluster."""
        ...


class SoftAssignmentMixin(ABC):
    """Reports degrees of membership instead of a single label.

    Shared by fuzzy methods, where memberships express partial belonging,
    and probabilistic ones, where they are posterior probabilities. The
    interpretation differs; the interface does not. `labels_` remains
    available as the defuzzified partition.

    Fitted attributes
    -----------------
    memberships_ : ndarray of shape (m, |C|)
    """

    memberships_: Memberships

    @abstractmethod
    def predict_proba(self, X: MatrixLike) -> Memberships:
        """Return the membership of each observation in each cluster."""
        ...

    def defuzzify(self, memberships: Memberships | None = None) -> Labels:
        """Reduce memberships to a crisp partition, by default by argmax.

        Defaults to the fitted `memberships_` when none is given, so a
        fitted method can restate its own partition.

        Discarding the degrees is a loss, and where it matters the caller
        should read `memberships_` instead: an observation split 0.51/0.49
        and one at 1.00/0.00 become the same label here, and only the first
        is a boundary case worth reporting under Sect. 4.4.
        """
        if memberships is None:
            ensure_fitted(self, "memberships_")
            memberships = self.memberships_

        memberships = np.asarray(memberships)
        if memberships.ndim != 2:
            raise ValueError(
                f"memberships must be an (m, |C|) matrix; got shape "
                f"{memberships.shape}."
            )
        return np.argmax(memberships, axis=1).astype(int)


class HierarchyMixin(ABC):
    """Builds a hierarchy that can be cut after fitting.

    The practical value of HCA per Sect. 2.2: one fit yields every
    partition, and the number of clusters is chosen by cutting rather than
    by refitting. `cut` accepts a level or a threshold, never both.

    Fitted attributes
    -----------------
    linkage_ : ndarray of shape (m - 1, 4)
        SciPy-format linkage, so existing dendrogram tooling applies.
    children_ : ndarray of shape (m - 1, 2)
        Merge (or split) tree, in scikit-learn's form.
    """

    linkage_: LinkageMatrix
    children_: ArrayLike

    @abstractmethod
    def cut(
        self, n_clusters: int | None = None, threshold: float | None = None
    ) -> Labels:
        """Return the partition obtained by cutting the hierarchy."""
        ...


class NoiseAwareMixin:
    """May leave an observation unassigned.

    Density-based methods do not partition the dataset in the strict sense
    of Def. 2: points in no dense region are labelled -1. Everything that
    consumes labels must therefore agree on that convention, and validity
    indices must state whether noise is scored or excluded.

    Fitted attributes
    -----------------
    n_noise_ : int
    """

    #: Label reserved for unassigned observations; one definition, in
    #: `core.types`, shared with the validation helpers.
    NOISE_LABEL: int = NOISE_LABEL

    n_noise_: int

    def noise_mask(self, labels: Labels | None = None) -> ArrayLike:
        """Return a boolean mask selecting the noise observations.

        Defaults to the fitted `labels_`. The mask rather than the indices,
        because every downstream use is a selection -- excluding noise from
        an index that does not handle it, or colouring it distinctly in a
        figure.
        """
        if labels is None:
            ensure_fitted(self, "labels_")
            labels = self.labels_
        return check_labels(labels) == self.NOISE_LABEL


class ProbabilisticMixin(ABC):
    """Fits a generative model of the data.

    Adds the model selection quantities that only a likelihood-based
    method can report, which give an alternative to the internal indices
    of Sect. 4.2 for choosing the number of clusters.

    Both criteria are implemented here rather than per method: the
    formulae are the same for every likelihood-based model, and only the
    two quantities they read are method-specific. Lower is better for
    both, matching scikit-learn.

    Fitted attributes
    -----------------
    n_parameters_ : int
        Free parameters of the fitted model. The subclass computes it --
        for a Gaussian mixture it depends on the covariance structure --
        and it is required, because a criterion that penalises complexity
        cannot default the complexity.
    """

    n_parameters_: int

    @abstractmethod
    def score_samples(self, X: MatrixLike) -> ArrayLike:
        """Return the log-likelihood of each observation."""
        ...

    def _log_likelihood(self, X: MatrixLike) -> float:
        ensure_fitted(self, "n_parameters_")
        return float(np.sum(self.score_samples(X)))

    def bic(self, X: MatrixLike) -> float:
        """Bayesian information criterion of the fitted model.

        The stricter of the two: its penalty grows with the sample size,
        so it prefers fewer clusters than AIC on the same data. Reporting
        both and noting where they disagree is more honest than picking
        one silently.
        """
        n_samples = np.asarray(X).shape[0]
        return -2.0 * self._log_likelihood(X) + self.n_parameters_ * np.log(n_samples)

    def aic(self, X: MatrixLike) -> float:
        """Akaike information criterion of the fitted model."""
        return -2.0 * self._log_likelihood(X) + 2.0 * self.n_parameters_


class PrecomputedMixin:
    """Accepts a square matrix in place of a feature matrix.

    The bridge between `xxcluster.measures.dissimilarity` and any method
    that touches the data only through d(., .). Where a method supports
    it, `metric="precomputed"` lets a custom measure be used without the
    method knowing anything about it -- the route for mixed-type data and
    for time-series dissimilarities.

    It is also the only practical route to an adapted third-party method.
    A backend accepts metrics from its own list or a Python callable, and
    a callable is invoked m^2 times from the interpreter; a precomputed
    matrix is computed once, vectorised, and handed over.

    Not every method means the same thing by "precomputed", which is why
    the kind is declared rather than assumed. A dissimilarity has a zero
    diagonal, an affinity does not, and a kernel may have negative
    off-diagonal entries -- so validating one as another rejects valid
    input, or worse, accepts invalid input silently.

    Class attributes
    ----------------
    _precomputed_kind
        Which of the three kinds this method consumes.
    _precomputed_param
        Name of the parameter carrying the measure, since it is `metric`
        for most methods, `affinity` for graph-based ones and `kernel`
        for kernel methods.
    _precomputed_symmetric
        Whether symmetry is required. Relaxed only by a method that
        genuinely tolerates an asymmetric dissimilarity, which Def. 2
        permits.
    """

    _precomputed_kind: ClassVar[PrecomputedKind] = PrecomputedKind.DISSIMILARITY
    _precomputed_param: ClassVar[str] = "metric"
    _precomputed_symmetric: ClassVar[bool] = True

    def _is_precomputed(self) -> bool:
        """Report whether this instance is configured for precomputed input."""
        return getattr(self, self._precomputed_param, None) == "precomputed"

    def _check_precomputed(
        self, M: MatrixLike, *, n_samples: int | None = None
    ) -> DissimilarityMatrix:
        """Validate `M` against the declared kind.

        Dispatch only: the checks live in `core.validation` so that one
        rule has one implementation.
        """
        kind = self._precomputed_kind
        if kind is PrecomputedKind.DISSIMILARITY:
            return check_dissimilarity_matrix(
                M, symmetric=self._precomputed_symmetric, n_samples=n_samples
            )
        if kind is PrecomputedKind.AFFINITY:
            return check_affinity_matrix(M, n_samples=n_samples)
        if kind is PrecomputedKind.KERNEL:
            return check_kernel_matrix(M, n_samples=n_samples)
        raise ContractViolationError(
            f"{type(self).__name__} declares an unknown precomputed kind: {kind!r}"
        )


class PersistableMixin:
    """Saves and restores a fitted component.

    Persistence records the component together with the run metadata
    required by App. A -- library versions and seeds -- so a stored result
    can be traced back to the code that produced it. Storage lives in
    `xxcluster.io.artifacts`; this mixin only exposes the entry points.
    """

    def save(self, path: Any) -> None:
        """Persist the fitted component and its run metadata."""
        raise NotImplementedError

    @classmethod
    def load(cls, path: Any) -> Any:
        """Restore a component previously saved with `save`."""
        raise NotImplementedError
