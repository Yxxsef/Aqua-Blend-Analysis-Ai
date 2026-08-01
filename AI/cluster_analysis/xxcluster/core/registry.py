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

from .exceptions import RegistryError
from .tags import Capabilities
from .types import ComponentKind, Family, SubFamily

_C = TypeVar("_C", bound=type)


class ComponentRegistry:
    """Name -> component class, partitioned by `ComponentKind`.

    Insertion-ordered, so `names()` and every table built from it list
    components in the order their modules were imported. That ordering is
    stable across runs and therefore diffable, which an arbitrary set
    ordering would not be.
    """

    def __init__(self) -> None:
        self._entries: dict[str, type] = {}
        self._kinds: dict[str, ComponentKind | None] = {}

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

        The collision is an error rather than a last-one-wins because names
        end up in stored artefacts and in the document's tables: two
        classes answering to one name would make a saved result ambiguous
        about which code produced it.
        """

        def decorator(cls: _C) -> _C:
            if not isinstance(cls, type):
                raise RegistryError(
                    f"@register must decorate a class; got {cls!r}."
                )
            existing = self._entries.get(name)
            if existing is not None and not overwrite:
                raise RegistryError(
                    f"{name!r} is already registered to "
                    f"{existing.__module__}.{existing.__qualname__}. Names are "
                    f"permanent -- they appear in saved artefacts -- so pick "
                    f"another, or pass overwrite=True if this is deliberate."
                )
            self._entries[name] = cls
            self._kinds[name] = kind if kind is not None else getattr(cls, "_kind", None)
            return cls

        return decorator

    def get(self, name: str, *, kind: ComponentKind | None = None) -> type:
        """Return the class registered under `name`."""
        try:
            cls = self._entries[name]
        except KeyError:
            raise RegistryError(
                f"no component registered as {name!r}. Registered: "
                f"{', '.join(self.names()) or 'none'}. A component is "
                f"registered when its module is imported."
            ) from None

        if kind is not None and self._kinds.get(name) is not kind:
            raise RegistryError(
                f"{name!r} is a {self._kinds.get(name)}, not a {kind}."
            )
        return cls

    def create(self, name: str, **params: Any) -> Any:
        """Instantiate a registered component with `params`.

        The single entry point used by the configuration-driven layers, so
        that a method named in a config is constructed the same way as one
        constructed by hand.
        """
        cls = self.get(name)
        try:
            return cls(**params)
        except TypeError as exc:
            raise RegistryError(
                f"cannot construct {name!r} with {params!r}: {exc}"
            ) from exc

    def names(
        self,
        *,
        kind: ComponentKind | None = None,
        family: Family | None = None,
        subfamily: SubFamily | None = None,
    ) -> list[str]:
        """List registered names, optionally filtered by taxonomy."""
        selected = []
        for name, cls in self._entries.items():
            if kind is not None and self._kinds.get(name) is not kind:
                continue
            caps = self.capabilities(name)
            if family is not None and caps.family is not family:
                continue
            if subfamily is not None and caps.subfamily is not subfamily:
                continue
            selected.append(name)
        return selected

    def capabilities(self, name: str) -> Capabilities:
        """Return the declared capabilities of a registered component.

        Falls back to an empty `Capabilities` for a class that declares
        none, so the reporting layer gets a row of defaults rather than an
        exception. An undeclared capability is a gap in the write-up, and
        it shows up as such in the table.
        """
        cls = self.get(name)
        declared = getattr(cls, "_capabilities", None)
        return declared if isinstance(declared, Capabilities) else Capabilities()

    def applicable(self, *, kind: ComponentKind | None = None, **data_properties: bool) -> list[str]:
        """List the registered components applicable to the given data.

        Shortlists candidates before any fitting; see
        `Capabilities.is_applicable`.
        """
        return [
            name
            for name in self.names(kind=kind)
            if self.capabilities(name).is_applicable(**data_properties)
        ]

    def __iter__(self) -> Iterator[tuple[str, type]]:
        """Iterate over the (name, class) pairs registered."""
        return iter(self._entries.items())

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, name: object) -> bool:
        return name in self._entries


#: Process-wide registry. Import this rather than building another.
REGISTRY = ComponentRegistry()

#: Convenience alias, used as `@register("kmeans")` on a component class.
register = REGISTRY.register
