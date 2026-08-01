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
from typing import Any, ClassVar, Mapping

from .base import BaseClusterer, BaseDimReducer
from .types import MatrixLike


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
        """
        raise NotImplementedError

    def _backend_params(self) -> dict[str, Any]:
        """Translate our parameters into the backend's keyword arguments."""
        raise NotImplementedError

    def _build_backend(self) -> Any:
        """Instantiate the backend with the translated parameters."""
        raise NotImplementedError

    def _collect_fitted(self) -> None:
        """Copy the backend's fitted attributes onto `self` via `_attr_map`.

        Attributes the backend does not expose are derived here, so that
        the contract holds regardless of which backend was used.
        """
        raise NotImplementedError


class AdaptedClusterer(BackendAdapter, BaseClusterer, ABC):
    """A clustering method backed by a third-party implementation.

    Subclasses normally declare only `_backend_import`, the maps, and
    `_capabilities`; `_fit` is inherited and needs no override.
    """

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Build the backend, fit it, then collect its fitted attributes."""
        raise NotImplementedError


class AdaptedDimReducer(BackendAdapter, BaseDimReducer, ABC):
    """A dimensionality reduction technique backed by a third party.

    Note the transductive case: where the backend has no `transform` for
    unseen data, the subclass must leave `is_inductive` false and let the
    inherited `transform` refuse, rather than silently refitting.
    """

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Build the backend, fit it, then collect its fitted attributes."""
        raise NotImplementedError

    def transform(self, X: MatrixLike) -> Any:
        """Delegate to the backend, subject to the inductive check above."""
        raise NotImplementedError
