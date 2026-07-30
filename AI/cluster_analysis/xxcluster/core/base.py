"""
Abstract base classes: the universal contract.

Carried over from the original `base_class.py`: this module implements the
abstract classes and interfaces, and outlines the naming conventions and
coding rules every component follows.

Every component in this package is a scikit-learn estimator. Inheriting
`sklearn.base.BaseEstimator` is deliberate: it buys `get_params`/
`set_params`, `clone`, `Pipeline`, the `*SearchCV` classes and
`check_estimator` conformance for free, and means anything written here
composes with the wider scientific Python ecosystem instead of only with
itself.

Conventions
-----------
Parameters
    Accepted in `__init__` only, stored unmodified under their own name,
    never validated there. `check_estimator` depends on this.
Fitted state
    Set by `fit`, named with a trailing underscore (`labels_`), and absent
    until fitting succeeds. Every base class documents the attributes a
    subclass must set.
Template method
    Public `fit` is concrete and handles validation, bookkeeping and
    capability checks; subclasses override the private `_fit` and set their
    own fitted attributes there. Do not override `fit` itself.
Capabilities
    Declared once per concrete class as `_capabilities`; a class whose
    declaration contradicts its interface is a `ContractViolationError`.
Skeleton
    An `@abstractmethod` body is `...`; an unwritten concrete method
    raises `NotImplementedError`. Nothing here is implemented yet.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Self

from sklearn.base import BaseEstimator, ClusterMixin, OutlierMixin, TransformerMixin

from .tags import Capabilities
from .types import (
    ArrayLike,
    Embedding,
    Labels,
    MatrixLike,
    Seed,
)


class BaseComponent(BaseEstimator, ABC):
    """Root of the contract; not clustering-specific.

    Anything the package can fit -- a clustering method, a dimensionality
    reduction technique, a learned dissimilarity, and later a detector or
    a generator -- derives from here, so cross-cutting concerns (parameter
    handling, input validation, provenance, persistence) are stated once.

    Class attributes
    ----------------
    _kind
        Registry partition this component belongs to.
    _capabilities
        What the component assumes and supports; see `core.tags`.

    Fitted attributes
    -----------------
    n_features_in_ : int
    feature_names_in_ : ndarray of str, optional
        Set from the input; both required by scikit-learn convention.
    """

    _kind: ClassVar[Any]
    _capabilities: ClassVar[Capabilities] = Capabilities()

    n_features_in_: int
    feature_names_in_: ArrayLike

    def fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> Self:
        """Fit the component and return `self`.

        Template method; override `_fit` instead. The sequence is:
        validate parameters, validate and record the input, delegate to
        `_fit`, then verify the subclass set everything it declared.

        Parameters
        ----------
        X
            Data of shape (n, d), or an (n, n) dissimilarity matrix where
            the component declares `supports_precomputed`.
        y
            Ignored by unsupervised components; present so that the
            signature matches scikit-learn's `Pipeline`.
        """
        raise NotImplementedError

    @abstractmethod
    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Do the actual fitting and set the declared fitted attributes."""
        ...

    @classmethod
    def capabilities(cls) -> Capabilities:
        """Return the capabilities declared by this class."""
        raise NotImplementedError

    @property
    def is_fitted(self) -> bool:
        """Report whether `fit` has completed successfully."""
        raise NotImplementedError

    def _validate_params(self) -> None:
        """Check constructor parameters; called at the start of `fit`.

        Kept out of `__init__` so that parameters round-trip through
        `get_params`/`set_params` unchanged.
        """
        raise NotImplementedError

    def _check_capabilities(self) -> None:
        """Verify the declared capabilities match the actual interface."""
        raise NotImplementedError


class BaseTransformer(BaseComponent, TransformerMixin, ABC):
    """Maps data into another representation.

    `TransformerMixin` supplies `fit_transform`; subclasses provide
    `transform`.
    """

    @abstractmethod
    def transform(self, X: MatrixLike) -> Any:
        """Apply the fitted mapping to `X`."""
        ...

    def inverse_transform(self, X: MatrixLike) -> Any:
        """Map back to the input space, where the technique admits it.

        Optional: raises `NotImplementedError` for techniques with no
        inverse, which is most nonlinear ones.
        """
        raise NotImplementedError


class BaseDimReducer(BaseTransformer, ABC):
    """Dimensionality reduction technique; see Sect. 6.

    The contract splits techniques by whether the learned mapping extends
    to unseen points. A linear technique is inductive: `transform` applies
    to new data. Most manifold learners are transductive: they embed only
    the points they were fitted on, so `transform` on new data is either
    an approximation or an error, and the class must say which through
    `_capabilities.is_inductive`.

    Fitted attributes
    -----------------
    embedding_ : ndarray of shape (n, n_components)
        Representation of the training data.
    n_components_ : int
        Number of components actually retained.
    """

    embedding_: Embedding
    n_components_: int

    def __init__(
        self,
        n_components: int | float | str | None = None,
        *,
        random_state: Seed = None,
    ) -> None:
        self.n_components = n_components
        self.random_state = random_state

    @abstractmethod
    def transform(self, X: MatrixLike) -> Embedding:
        """Embed `X` into the learned lower-dimensional space."""
        ...


class BaseClusterer(BaseComponent, ClusterMixin, ABC):
    """Clustering method; the map phi_d of Def. 2.

    Implements a partition: every observation receives exactly one label,
    the clusters are disjoint and their union is the dataset. Methods that
    may leave an observation unassigned label it as noise (-1) and declare
    `handles_noise`; see `mixins.NoiseAwareMixin`.

    `ClusterMixin` supplies `fit_predict`. `predict` is deliberately absent
    from this class: only methods that generalise to unseen observations
    expose it, by mixing in `mixins.InductiveMixin`.

    Fitted attributes
    -----------------
    labels_ : ndarray of shape (n,)
        Cluster index per observation; -1 marks noise.
    n_clusters_ : int
        Number of clusters found, excluding the noise cluster. Distinct
        from any `n_clusters` parameter, which is a request, not a result.
    """

    labels_: Labels
    n_clusters_: int

    @abstractmethod
    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Fit the method and set at least `labels_` and `n_clusters_`."""
        ...

    def criterion(self, X: MatrixLike, labels: Labels | None = None) -> float:
        """Value of the method's own objective function for a partition.

        Reported alongside the shared validity indices of Sect. 4.2, which
        are external to the method; this one is the quantity the method
        itself optimises, so it is comparable only across runs of the same
        method. Optional.
        """
        raise NotImplementedError


class BaseOutlierDetector(BaseComponent, OutlierMixin, ABC):
    """Anomaly and novelty detection.

    Present so the package extends horizontally without reworking the
    contract; no detector is implemented yet. `OutlierMixin` fixes the
    scikit-learn convention that `fit_predict` returns +1 for inliers and
    -1 for outliers.

    Fitted attributes
    -----------------
    labels_ : ndarray of shape (n,)
        Inlier/outlier flag per training observation.
    """

    labels_: Labels

    @abstractmethod
    def score_samples(self, X: MatrixLike) -> ArrayLike:
        """Return an outlier score per observation, higher being more normal."""
        ...


class BaseGenerator(BaseComponent, ABC):
    """Generative model, for scenario generation.

    Present for the same reason as `BaseOutlierDetector`. The intended use
    is problem-driven scenario generation as discussed in Sect. 2.3: fit a
    model to the operational feature space, then draw scenarios that feed
    the optimisation model.
    """

    @abstractmethod
    def sample(self, n_samples: int = 1, *, random_state: Seed = None) -> ArrayLike:
        """Draw `n_samples` synthetic observations from the fitted model."""
        ...

    def score_samples(self, X: MatrixLike) -> ArrayLike:
        """Return the log-likelihood of each observation, where defined."""
        raise NotImplementedError


class BasePredictor(BaseComponent, ABC):
    """Supervised model.

    Included so that a supervised step -- a regime classifier trained on
    cluster labels, or a demand forecaster -- carries the same contract as
    the unsupervised components. Mix in scikit-learn's `ClassifierMixin`
    or `RegressorMixin` for the matching `score` method.
    """

    @abstractmethod
    def predict(self, X: MatrixLike) -> ArrayLike:
        """Predict the target for `X`."""
        ...
