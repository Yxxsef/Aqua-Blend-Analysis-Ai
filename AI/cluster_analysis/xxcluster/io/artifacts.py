"""
Storing what a run produced.

An artefact is a fitted component, a set of labels, a scores table or a
figure, stored with the metadata needed to say where it came from: the
protocol, the environment, the dataset provenance and the parameters.

The reason to have this at all rather than saving files ad hoc is App. A.
A result in the document must be traceable to the code, data and seed that
produced it, and that is only true if the metadata is written at the same
moment as the result. Written afterwards, by hand, it is a description of
what someone remembers doing.

Storage layout and format are deliberately not decided here -- that is a
concrete choice for when the first artefact is written.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ArtifactMeta:
    """Provenance recorded with every stored artefact.

    Attributes
    ----------
    created_at, revision
        When, and from which commit of this repository.
    component, params
        What produced it, and how it was configured.
    protocol, environment
        Serialised from `evaluation.protocol`.
    dataset
        Provenance of the input, copied from the `Dataset`.
    """

    created_at: str = ""
    revision: str | None = None
    component: str = ""
    params: Mapping[str, Any] = field(default_factory=dict)
    protocol: Mapping[str, Any] = field(default_factory=dict)
    environment: Mapping[str, Any] = field(default_factory=dict)
    dataset: Mapping[str, Any] = field(default_factory=dict)


class BaseArtifactStore(ABC):
    """Reads and writes artefacts with their metadata.

    Metadata is not optional: `save` takes it as a required argument, so an
    artefact cannot be stored without it. A store that permitted anonymous
    artefacts would accumulate them.
    """

    @abstractmethod
    def save(self, name: str, obj: Any, meta: ArtifactMeta) -> Any:
        """Store an artefact and return its location."""
        ...

    @abstractmethod
    def load(self, name: str) -> tuple[Any, ArtifactMeta]:
        """Retrieve an artefact together with its metadata."""
        ...

    def list(self, pattern: str | None = None) -> list[str]:
        """List stored artefact names."""
        raise NotImplementedError
