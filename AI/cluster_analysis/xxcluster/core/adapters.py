"""
Adapters over third-party estimators.

The default way to add a method is to adapt a mature implementation
(scikit-learn, SciPy, hdbscan, umap-learn) rather than reimplement it. The
adapter exists because those implementations disagree on details that the
comparison of Sect. 8 cannot tolerate: parameter names for the same
quantity, whether noise is -1 or a separate attribute, whether the number
of clusters found is exposed at all.

An adapter therefore does three things and nothing more:

1. translates our parameter names to the backend's,
2. copies the backend's fitted attributes onto ours, filling in any the
   backend does not provide,
3. declares the capabilities the backend actually has.

Write a native subclass instead, only overriding `_fit` on a family base
directly, if no good implementation exists, or where the point is to
follow the formulation in the documentation. `_capabilities.backend`
records which route a class took, so a result can always be traced to the
code that produced it.
"""

from __future__ import annotations

from abc import ABC
from importlib import import_module
from typing import Any, ClassVar, Mapping

import numpy as np

from .base import BaseClusterer, BaseDimReducer
from .exceptions import BackendUnavailableError, ContractViolationError
from .types import NOISE_LABEL, MatrixLike
from .validation import ensure_fitted


class BackendAdapter(ABC):
    """Wraps a third-party estimator behind this package's contract.

    Class attributes
    ----------------
    _backend_import
        Dotted path to the backend class, imported on first fit so that an
        optional dependency does not break `import xxcluster`.
    _param_map
        Our parameter name -> backend parameter name. Identity by default;
        list only the names that differ.
    _attr_map
        Our fitted attribute name -> backend attribute name.
    _fixed_params
        Backend parameters pinned by us and not exposed to the caller.

    Attributes
    ----------
    backend_ : object
        The fitted third-party estimator, kept for inspection and for
        anything the adapter deliberately does not surface.
    """

    _backend_import: ClassVar[str]
    _param_map: ClassVar[Mapping[str, str]] = {}
    _attr_map: ClassVar[Mapping[str, str]] = {}
    _fixed_params: ClassVar[Mapping[str, Any]] = {}

    backend_: Any

    @classmethod
    def _load_backend(cls) -> type:
        """Import and return the backend class.

        Raises `BackendUnavailableError` when the dependency is missing,
        naming the package to install.

        Imported here rather than at module scope so that an optional
        backend does not break `import xxcluster`; the cost is one import
        per fit, which is negligible beside the fit.
        """
        module_path, _, class_name = cls._backend_import.rpartition(".")
        try:
            module = import_module(module_path)
        except ImportError as exc:
            distribution = module_path.split(".")[0]
            raise BackendUnavailableError(
                f"{cls.__name__} adapts {cls._backend_import}, which is not "
                f"installed. Install it with `pip install {distribution}` and "
                f"uncomment it in requirements.txt."
            ) from exc

        try:
            return getattr(module, class_name)
        except AttributeError as exc:
            raise BackendUnavailableError(
                f"{module_path} has no {class_name!r}; the backend's API has "
                f"changed since {cls.__name__} was written against it."
            ) from exc

    def _backend_params(self) -> dict[str, Any]:
        """Translate our parameters into the backend's keyword arguments.

        Names not in `_param_map` pass through unchanged. A name mapped to
        `None` is dropped, which is how a parameter we expose for contract
        reasons is kept from reaching a backend that has no equivalent.
        `_fixed_params` is applied last and wins, since it is the adapter's
        own decision rather than the caller's.
        """
        params: dict[str, Any] = {}
        for name, value in self.get_params(deep=False).items():
            target = self._param_map.get(name, name)
            if target is None:
                continue
            params[target] = value
        params.update(self._fixed_params)
        return params

    def _build_backend(self) -> Any:
        """Instantiate the backend with the translated parameters."""
        backend_cls = self._load_backend()
        params = self._backend_params()
        try:
            return backend_cls(**params)
        except TypeError as exc:
            raise ContractViolationError(
                f"{type(self).__name__} passed {sorted(params)} to "
                f"{backend_cls.__name__}, which rejected them: {exc}. Correct "
                f"`_param_map` -- the backend's signature has probably changed."
            ) from exc

    def _collect_fitted(self) -> None:
        """Copy the backend's fitted attributes onto `self` via `_attr_map`.

        Attributes the backend does not expose are derived here, so that
        the contract holds regardless of which backend was used.

        Only the attributes this class declares in `_required_fitted` are
        copied. Mirroring everything the backend sets would put its
        vocabulary into ours, which is the coupling the adapter exists to
        prevent; anything else stays reachable through `backend_`.
        """
        for name in self._required_fitted_attributes():
            source = self._attr_map.get(name, name)
            if source is not None and hasattr(self.backend_, source):
                setattr(self, name, getattr(self.backend_, source))

        self._derive_missing()

    def _derive_missing(self) -> None:
        """Fill in contract attributes the backend does not report.

        Backends disagree on exactly these: scikit-learn's clusterers
        expose `labels_` but not how many clusters resulted, and none of
        them counts noise. Deriving from `labels_` gives one answer for
        every backend, which is what makes the Sect. 8 table comparable.
        """
        labels = getattr(self, "labels_", None)
        if labels is not None:
            labels = np.asarray(labels)
            if not hasattr(self, "n_clusters_"):
                assigned = labels[labels != NOISE_LABEL]
                self.n_clusters_ = int(np.unique(assigned).size)
            if hasattr(type(self), "NOISE_LABEL") and not hasattr(self, "n_noise_"):
                self.n_noise_ = int(np.sum(labels == NOISE_LABEL))

        embedding = getattr(self, "embedding_", None)
        if embedding is not None and not hasattr(self, "n_components_"):
            self.n_components_ = int(np.asarray(embedding).shape[1])


class AdaptedClusterer(BackendAdapter, BaseClusterer, ABC):
    """A clustering method backed by a third-party implementation.

    Subclasses normally declare only `_backend_import`, the maps, and
    `_capabilities`; `_fit` is inherited and needs no override.
    """

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Build the backend, fit it, then collect its fitted attributes."""
        self.backend_ = self._build_backend()
        self.backend_.fit(X, **fit_params)
        self._collect_fitted()


class AdaptedDimReducer(BackendAdapter, BaseDimReducer, ABC):
    """A dimensionality reduction technique backed by a third party.

    Note the transductive case: where the backend has no `transform` for
    unseen data, the subclass must leave `is_inductive` false and let the
    inherited `transform` refuse, rather than silently refitting.
    """

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Build the backend, fit it, then collect its fitted attributes.

        `fit_transform` rather than `fit`: a transductive technique has no
        other way to expose its embedding, and for an inductive one the
        backend computes the same thing either way.
        """
        self.backend_ = self._build_backend()
        self.embedding_ = self.backend_.fit_transform(X, **fit_params)
        self._collect_fitted()

    def transform(self, X: MatrixLike) -> Any:
        """Delegate to the backend, subject to the inductive check above.

        A transductive technique refuses. The alternative -- refitting on
        the new data -- would return an embedding from a different fit
        while looking like the mapping the caller asked for, and any
        figure drawn from it would be of a model that was never reported.
        """
        ensure_fitted(self, "backend_")

        if not self._capabilities.is_inductive:
            raise NotImplementedError(
                f"{type(self).__name__} is transductive: it embeds only the "
                f"observations it was fitted on. Use `embedding_` for those, "
                f"or refit on the combined data and say so in the write-up."
            )
        return self.backend_.transform(X)
