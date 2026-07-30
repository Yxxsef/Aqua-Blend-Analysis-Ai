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
from typing import Any

from .types import (
    ArrayLike,
    DissimilarityMatrix,
    Labels,
    LinkageMatrix,
    MatrixLike,
    Memberships,
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
    memberships_ : ndarray of shape (n, |C|)
    """

    memberships_: Memberships

    @abstractmethod
    def predict_proba(self, X: MatrixLike) -> Memberships:
        """Return the membership of each observation in each cluster."""
        ...

    def defuzzify(self, memberships: Memberships | None = None) -> Labels:
        """Reduce memberships to a crisp partition, by default by argmax."""
        raise NotImplementedError


class HierarchyMixin(ABC):
    """Builds a hierarchy that can be cut after fitting.

    The practical value of HCA per Sect. 2.2: one fit yields every
    partition, and the number of clusters is chosen by cutting rather than
    by refitting. `cut` accepts a level or a threshold, never both.

    Fitted attributes
    -----------------
    linkage_ : ndarray of shape (n - 1, 4)
        SciPy-format linkage, so existing dendrogram tooling applies.
    children_ : ndarray of shape (n - 1, 2)
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

    #: Label reserved for unassigned observations.
    NOISE_LABEL: int = -1

    n_noise_: int

    def noise_mask(self, labels: Labels | None = None) -> ArrayLike:
        """Return a boolean mask selecting the noise observations."""
        raise NotImplementedError


class ProbabilisticMixin(ABC):
    """Fits a generative model of the data.

    Adds the model selection quantities that only a likelihood-based
    method can report, which give an alternative to the internal indices
    of Sect. 4.2 for choosing the number of clusters.
    """

    @abstractmethod
    def score_samples(self, X: MatrixLike) -> ArrayLike:
        """Return the log-likelihood of each observation."""
        ...

    def bic(self, X: MatrixLike) -> float:
        """Bayesian information criterion of the fitted model."""
        raise NotImplementedError

    def aic(self, X: MatrixLike) -> float:
        """Akaike information criterion of the fitted model."""
        raise NotImplementedError


class PrecomputedMixin:
    """Accepts a dissimilarity matrix in place of a feature matrix.

    The bridge between `xxcluster.measures.dissimilarity` and any method
    that touches the data only through d(., .). Where a method supports
    it, `metric="precomputed"` lets a custom measure be used without the
    method knowing anything about it -- the route for mixed-type data and
    for time-series dissimilarities.
    """

    def _is_precomputed(self) -> bool:
        """Report whether this instance is configured for precomputed input."""
        raise NotImplementedError

    def _check_dissimilarity_matrix(self, D: MatrixLike) -> DissimilarityMatrix:
        """Validate a square, non-negative, zero-diagonal matrix."""
        raise NotImplementedError


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
