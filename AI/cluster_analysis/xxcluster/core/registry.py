"""
Component registry.

Maps a stable string name to a component class, so an experiment can be
specified as data rather than as code -- a list of method names in a
notebook or a configuration file -- and so the comparison of Sect. 8 can
sweep every registered method of a family without importing each by hand.

The registry also answers the shortlisting question: given what is known
about the dataset (missing values, mixed types, expected noise, size),
which registered methods declare themselves applicable? That query reads
`core.tags.Capabilities` only, and instantiates nothing.

Names are lower_snake_case and permanent: they end up in saved artefacts
and in the tables of the document, so renaming one invalidates results.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator, TypeVar

from .tags import Capabilities
from .types import ComponentKind, Family, SubFamily

_C = TypeVar("_C", bound=type)


class ComponentRegistry:
    """Name -> component class, partitioned by `ComponentKind`."""

    def register(
        self,
        name: str,
        *,
        kind: ComponentKind | None = None,
        overwrite: bool = False,
    ) -> Callable[[_C], _C]:
        """Return a class decorator that records the class under `name`.

        `kind` defaults to the class's own `_kind`. Registering a name that
        is already taken raises `RegistryError` unless `overwrite` is set.
        """
        raise NotImplementedError

    def get(self, name: str, *, kind: ComponentKind | None = None) -> type:
        """Return the class registered under `name`."""
        raise NotImplementedError

    def create(self, name: str, **params: Any) -> Any:
        """Instantiate a registered component with `params`.

        The single entry point used by the configuration-driven layers, so
        that a method named in a config is constructed the same way as one
        constructed by hand.
        """
        raise NotImplementedError

    def names(
        self,
        *,
        kind: ComponentKind | None = None,
        family: Family | None = None,
        subfamily: SubFamily | None = None,
    ) -> list[str]:
        """List registered names, optionally filtered by taxonomy."""
        raise NotImplementedError

    def capabilities(self, name: str) -> Capabilities:
        """Return the declared capabilities of a registered component."""
        raise NotImplementedError

    def applicable(self, *, kind: ComponentKind | None = None, **data_properties: bool) -> list[str]:
        """List the registered components applicable to the given data.

        Shortlists candidates before any fitting; see
        `Capabilities.is_applicable`.
        """
        raise NotImplementedError

    def __iter__(self) -> Iterator[tuple[str, type]]:
        """Iterate over the (name, class) pairs registered."""
        raise NotImplementedError


#: Process-wide registry. Import this rather than building another.
REGISTRY = ComponentRegistry()

#: Convenience alias, used as `@register("kmeans")` on a component class.
register = REGISTRY.register
