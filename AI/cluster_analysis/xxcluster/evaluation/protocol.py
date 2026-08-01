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

import hashlib
import platform as _platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from importlib import metadata
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..core.types import Seed

#: Packages whose versions are recorded with every result. Mirrors
#: requirements.txt; absent ones are skipped rather than reported as missing,
#: so an optional backend does not appear until it is actually installed.
TRACKED_PACKAGES: tuple[str, ...] = (
    "numpy",
    "scipy",
    "scikit-learn",
    "pandas",
    "matplotlib",
    "hdbscan",
    "umap-learn",
)

#: numpy seeds must fit in 32 bits.
_SEED_MODULUS = 2**32


def _git_revision() -> str | None:
    """Return the short commit of this repository, or None outside one.

    Suffixed `-dirty` where the tree has uncommitted changes: a result
    produced from a modified tree cannot be traced to a commit, and saying
    so is more useful than recording a hash that does not describe the code
    that ran.

    Never raises -- provenance is worth having but not worth failing a run
    over.
    """
    here = Path(__file__).resolve().parent

    def _run(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=here,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    revision = _run("rev-parse", "--short", "HEAD")
    if revision is None:
        return None
    dirty = _run("status", "--porcelain")
    return f"{revision}-dirty" if dirty else revision


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
        """Record the current environment.

        Cached: the answer cannot change within a process, and the git
        lookup shells out. Call `_capture_environment.cache_clear()` if a
        test needs a fresh reading.
        """
        return _capture_environment()

    def summary(self) -> str:
        """One line naming the versions that matter, for a figure caption."""
        versions = ", ".join(f"{n} {v}" for n, v in sorted(self.package_versions.items()))
        revision = f", {self.revision}" if self.revision else ""
        return f"Python {self.python_version} ({versions}){revision}"


@lru_cache(maxsize=1)
def _capture_environment() -> Environment:
    versions: dict[str, str] = {}
    for name in TRACKED_PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return Environment(
        python_version=_platform.python_version(),
        package_versions=versions,
        platform=_platform.platform(),
        revision=_git_revision(),
    )


def _describe_component(obj: Any) -> Any:
    """Render a component as something serialisable.

    An estimator becomes its class name and parameters, so the stored
    protocol says what the preprocessing actually was rather than
    `<StandardScaler object at 0x...>`. Anything else falls back to
    `repr`, which is lossy but never fails.
    """
    if obj is None:
        return None
    if hasattr(obj, "get_params"):
        params = {}
        for name, value in sorted(obj.get_params(deep=False).items()):
            params[name] = (
                value if isinstance(value, (str, int, float, bool, type(None))) else repr(value)
            )
        return {"class": type(obj).__name__, "params": params}
    if isinstance(obj, (list, tuple)):
        return [_describe_component(item) for item in obj]
    return repr(obj)


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
        Captured at construction unless one is supplied. Passing a stored
        `Environment` is how a protocol read back from an artefact keeps
        the environment it actually ran under.
    """

    indices: Sequence[str] = ()
    n_restarts: int = 10
    random_state: Seed = None
    preprocessing: Any = None
    n_clusters_candidates: Sequence[int] = ()
    environment: Environment | None = None

    def __post_init__(self) -> None:
        if self.environment is None:
            object.__setattr__(self, "environment", Environment.capture())

    def seed_for(self, key: str) -> int:
        """Derive a reproducible per-run seed from the root seed.

        Deriving rather than reusing means two methods do not share a seed
        by accident, while the whole experiment still replays from one
        number.

        The derivation uses a cryptographic digest rather than Python's
        `hash`, which is salted per process: a seed built from `hash` would
        differ between runs of the same script, quietly defeating the
        reproducibility this exists to provide.

        A protocol with no root seed still derives deterministically from
        the key alone; the root shifts the whole family of seeds at once.
        """
        digest = hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()
        derived = int.from_bytes(digest, "big")
        root = int(self.random_state) if isinstance(self.random_state, int) else 0
        return (derived ^ root) % _SEED_MODULUS

    def to_dict(self) -> dict[str, Any]:
        """Serialise the protocol for storage beside a result.

        JSON-compatible throughout: the preprocessing pipeline is rendered
        as class names and parameters rather than pickled, so a stored
        protocol stays readable and stays comparable after a refactor.
        """
        return {
            "indices": list(self.indices),
            "n_restarts": self.n_restarts,
            "random_state": self.random_state if isinstance(self.random_state, int) else None,
            "preprocessing": _describe_component(self.preprocessing),
            "n_clusters_candidates": list(self.n_clusters_candidates),
            "environment": asdict(self.environment) if self.environment else None,
        }

    def _render_indices(self) -> str:
        """List the indices in reporting order, as prose."""
        names = list(self.indices)
        if not names:
            return "no validity indices"
        if len(names) == 1:
            return names[0]
        return f"{', '.join(names[:-1])} and {names[-1]}"

    def describe(self) -> str:
        """Render the protocol as prose for Sect. 4.1 and App. A."""
        lines = [
            f"Every method is scored on {self._render_indices()}, "
            f"reported in that order.",
            f"Stochastic methods are given {self.n_restarts} restarts each, "
            f"and the best run by the method's own criterion is retained.",
        ]
        if self.n_clusters_candidates:
            candidates = list(self.n_clusters_candidates)
            lines.append(
                f"Where the number of clusters must be fixed in advance it is "
                f"swept over {candidates[0]}--{candidates[-1]}."
            )
        lines.append(
            f"The root random seed is {self.random_state}; per-run seeds are "
            f"derived from it, so the whole experiment replays from that one "
            f"value."
            if isinstance(self.random_state, int)
            else "No root random seed is set, which limits reproducibility to "
            "the derivation from run keys alone."
        )
        if self.preprocessing is not None:
            lines.append(
                f"The shared preprocessing pipeline is "
                f"{type(self.preprocessing).__name__}; deviations are recorded "
                f"against the method that required them."
            )
        if self.environment is not None:
            lines.append(f"Run under {self.environment.summary()}.")
        return " ".join(lines)


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

    @property
    def failed(self) -> bool:
        """True where the run did not produce a partition."""
        return self.error is not None
