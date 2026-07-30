"""
The experimental protocol.

One object holding everything that must be identical across methods: the
indices reported, the number of restarts, the seeds, the preprocessing, and
the environment. Every result carries the protocol that produced it, which
is what makes App. A reproducible without a separate record kept by hand.

Written as a declaration rather than a script so that the protocol can be
serialised, compared against the one a stored result was produced under,
and cited in the document.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..core.types import Seed


@dataclass(frozen=True)
class Environment:
    """The software environment a result was produced in.

    Captured automatically at run time, not written by hand: the point is
    to detect a version change that moved a number, which a hand-maintained
    list will not do.
    """

    python_version: str = ""
    package_versions: Mapping[str, str] = field(default_factory=dict)
    platform: str = ""
    #: Commit of this repository, where available.
    revision: str | None = None

    @classmethod
    def capture(cls) -> "Environment":
        """Record the current environment."""
        raise NotImplementedError


@dataclass(frozen=True)
class Protocol:
    """The shared experimental setup.

    Parameters
    ----------
    indices
        Validity indices reported for every method, in reporting order.
    n_restarts
        Restarts per stochastic method, so that all are given the same
        opportunity to escape a poor local optimum.
    random_state
        Root seed. Per-run seeds are derived from it, so the whole
        experiment is reproducible from this one value.
    preprocessing
        The pipeline applied before every method. A method needing a
        deviation records it against itself, per the template's
        Application paragraph, rather than changing this.
    n_clusters_candidates
        Candidate values swept wherever |C| must be fixed.
    environment
        Captured at construction.
    """

    indices: Sequence[str] = ()
    n_restarts: int = 10
    random_state: Seed = None
    preprocessing: Any = None
    n_clusters_candidates: Sequence[int] = ()
    environment: Environment | None = None

    def seed_for(self, key: str) -> int:
        """Derive a reproducible per-run seed from the root seed.

        Deriving rather than reusing means two methods do not share a seed
        by accident, while the whole experiment still replays from one
        number.
        """
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """Serialise the protocol for storage beside a result."""
        raise NotImplementedError

    def describe(self) -> str:
        """Render the protocol as prose for Sect. 4.1 and App. A."""
        raise NotImplementedError


@dataclass(frozen=True)
class RunResult:
    """What one method produced under one protocol.

    The unit the reporting layer aggregates. It holds the scores and the
    provenance, not the fitted model: a table is assembled from many of
    these, and loading every model to build one would not scale.
    """

    method: str
    params: Mapping[str, Any] = field(default_factory=dict)
    scores: Mapping[str, float] = field(default_factory=dict)
    n_clusters_found: int | None = None
    n_noise: int | None = None
    fit_seconds: float | None = None
    #: Set where the run failed, in which case `scores` is empty. A failure
    #: is reported, never dropped: Sect. 4.5 needs to know what did not work.
    error: str | None = None
