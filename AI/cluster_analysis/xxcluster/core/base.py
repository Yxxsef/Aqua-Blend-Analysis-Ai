"""
Abstract base classes: the universal contract.

This module implements the abstract classes and interfaces,
and outlines the naming conventions and coding rules every component follows.

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
    raises `NotImplementedError`. `BaseComponent.fit` and the steps it
    runs are implemented and tested; no concrete method is.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Self

from sklearn.base import BaseEstimator, ClusterMixin, OutlierMixin, TransformerMixin

from .exceptions import ContractViolationError
from .tags import Capabilities
from .types import (
    ArrayLike,
    Assignment,
    Embedding,
    Labels,
    MatrixLike,
    Seed,
)
from .validation import finite_policy


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

    #: Attributes `_fit` must set, declared per class. Collected across the
    #: MRO, so a subclass lists only what it adds to its parent's.
    _required_fitted: ClassVar[tuple[str, ...]] = ()

    n_features_in_: int
    feature_names_in_: ArrayLike

    def fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> Self:
        """Fit the component and return `self`.

        Template method; override `_fit` instead. The sequence is fixed so
        that every component in the package is validated identically --
        which is what makes the comparison of Sect. 8 a comparison rather
        than a collection of differently-guarded runs.

        Parameters
        ----------
        X
            Data of shape (m, n), or an (m, m) matrix where the component
            declares `supports_precomputed`; see `mixins.PrecomputedMixin`
            for which kind of matrix that means.
        y
            Ignored by unsupervised components; present so that the
            signature matches scikit-learn's `Pipeline`.
        """
        self._validate_params()
        self._check_capabilities()
        X = self._validate_input(X, reset=True)
        self._fit(X, y, **fit_params)
        self._check_fitted()
        return self

    @abstractmethod
    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Do the actual fitting and set the declared fitted attributes."""
        ...

    @classmethod
    def capabilities(cls) -> Capabilities:
        """Return the capabilities declared by this class."""
        return cls._capabilities

    @property
    def is_fitted(self) -> bool:
        """Report whether `fit` has completed successfully."""
        required = self._required_fitted_attributes() or ("n_features_in_",)
        return all(hasattr(self, name) for name in required)

    # --- Steps of the template method -------------------------------------

    def _validate_params(self) -> None:
        """Check constructor parameters; called at the start of `fit`.

        Deferred from `__init__` so that parameters round-trip through
        `get_params`/`set_params` unchanged, which `clone` and
        `check_estimator` both depend on.

        Delegates to scikit-learn's constraint machinery where the class
        declares `_parameter_constraints`, so a range or a type is stated
        once as data rather than as code. The guard is needed because
        `BaseEstimator._validate_params` assumes that attribute exists.
        Subclasses adding checks should override this and call `super()`.
        """
        if hasattr(self, "_parameter_constraints"):
            super()._validate_params()

    def _check_capabilities(self) -> None:
        """Verify the declared capabilities match the actual interface.

        One direction only: a declaration must be backed by the interface
        it promises. The converse -- an interface present but undeclared --
        is not an error, since a class may expose more than it advertises,
        and flagging it would fire on every class that has not yet filled
        in its declaration.

        The checks are duck-typed rather than `isinstance` against the
        mixins: a class that implements `predict` directly is as inductive
        as one that inherits `InductiveMixin`.

        Where a capability has more than one legitimate spelling, any one
        satisfies it. `is_inductive` is the case that matters: it promises
        the fitted model applies to observations unseen at fit time, which
        a clusterer offers through `predict` and a reducer through
        `transform`. Requiring `predict` of both would fail every inductive
        dimensionality reduction technique.
        """
        caps = self._capabilities
        promised: list[tuple[bool, tuple[str, ...], str]] = [
            (caps.is_inductive, ("predict", "transform"), "is_inductive"),
            (caps.produces_hierarchy, ("cut",), "produces_hierarchy"),
            (caps.handles_noise, ("noise_mask",), "handles_noise"),
            (caps.supports_precomputed, ("_check_precomputed",), "supports_precomputed"),
            (
                caps.assignment is not Assignment.CRISP,
                ("predict_proba",),
                f"assignment={caps.assignment.value}",
            ),
        ]
        for declared, attributes, label in promised:
            if declared and not any(hasattr(self, name) for name in attributes):
                expected = " or ".join(f"`{name}`" for name in attributes)
                raise ContractViolationError(
                    f"{type(self).__name__} declares {label} but has no "
                    f"{expected}. Either mix in the capability or correct "
                    f"the declaration -- the comparison table of Sect. 8.2 is "
                    f"generated from it."
                )

    def _validate_input(self, X: MatrixLike, *, reset: bool = True) -> Any:
        """Validate `X` and record what the contract requires from it.

        Two routes, because a precomputed matrix is not a feature matrix
        and validating one as the other either rejects valid input or
        accepts invalid input silently.
        """
        if self._is_precomputed_input():
            expected = None if reset else getattr(self, "n_features_in_", None)
            M = self._check_precomputed(X, n_samples=expected)
            if reset:
                # sklearn's convention for precomputed input: the "features"
                # of an (m, m) matrix are the m reference observations.
                self.n_features_in_ = M.shape[1]
            return M

        return self._validate_data(
            X,
            reset=reset,
            dtype="numeric",
            **finite_policy(self._capabilities.handles_missing),
        )

    def _check_fitted(self) -> None:
        """Verify `_fit` set everything this class declared.

        Runs after every fit. A method that sets `labels_` but forgets
        `n_clusters_` fails here, naming the omission, rather than several
        layers away in a report with a missing column.
        """
        missing = [
            name for name in self._required_fitted_attributes() if not hasattr(self, name)
        ]
        if missing:
            raise ContractViolationError(
                f"{type(self).__name__}._fit did not set: {', '.join(missing)}. "
                f"Every attribute a class declares in `_required_fitted` must "
                f"exist once fitting succeeds."
            )

    def _is_precomputed_input(self) -> bool:
        """Report whether this instance expects a precomputed matrix."""
        checker = getattr(self, "_is_precomputed", None)
        return bool(checker()) if callable(checker) else False

    @classmethod
    def _required_fitted_attributes(cls) -> tuple[str, ...]:
        """Collect `_required_fitted` across the MRO, base first.

        Reading own declarations only, so a subfamily declares what it adds
        and inherits the rest -- a density-based method need not restate
        `labels_` to also require `n_noise_`.
        """
        collected: dict[str, None] = {}
        for klass in reversed(cls.__mro__):
            for name in klass.__dict__.get("_required_fitted", ()):
                collected[name] = None
        return tuple(collected)


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
    embedding_ : ndarray of shape (m, n_components)
        Representation of the training data.
    n_components_ : int
        Number of components actually retained.
    """

    _required_fitted = ("embedding_", "n_components_")

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
    labels_ : ndarray of shape (m,)
        Cluster index per observation; -1 marks noise.
    n_clusters_ : int
        Number of clusters found, excluding the noise cluster. Distinct
        from any `n_clusters` parameter, which is a request, not a result.
    """

    _required_fitted = ("labels_", "n_clusters_")

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
    labels_ : ndarray of shape (m,)
        Inlier/outlier flag per training observation.
    """

    _required_fitted = ("labels_",)

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
