"""
Base class for tasks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..evaluation.protocol import Protocol, RunResult
from ..io.datasets import Dataset


@dataclass(frozen=True)
class TaskResult:
    """What a task produced.

    Holds the results, the figures and the provenance together, because a
    task's output is an argument rather than a number: the tables, the
    figures that qualify them, and the record of what produced both.
    """

    task: str
    runs: Sequence[RunResult] = ()
    figures: Mapping[str, Any] = field(default_factory=dict)
    tables: Mapping[str, Any] = field(default_factory=dict)
    #: Findings the task itself flags -- an inconclusive selection, an
    #: unstable partition, a failed run. Reported, not filtered.
    caveats: Sequence[str] = ()


class BaseTask(ABC):
    """An end-to-end analysis.

    A task composes components; it does not implement algorithms. Anything
    reusable belongs in the subpackage for its kind, where the registry and
    the comparison can reach it -- a method defined inside a task is
    invisible to both.

    Not a `BaseComponent`: a task is not fitted and has no `transform`, and
    forcing it into the estimator contract would only obscure that it runs
    once and returns a report.

    Parameters
    ----------
    dataset
        The data, already loaded; tasks do not read files.
    protocol
        The shared setup, so that two tasks over the same data are
        comparable.
    """

    name: str

    def __init__(self, dataset: Dataset | None = None, *, protocol: Protocol | None = None) -> None:
        self.dataset = dataset
        self.protocol = protocol

    @abstractmethod
    def run(self, **kwargs: Any) -> TaskResult:
        """Execute the analysis and return its results."""
        ...

    def components(self) -> Mapping[str, Any]:
        """Return the components this task uses, by role.

        Declared so a task's composition is inspectable before it is run,
        and so the reported result can name what produced it.
        """
        raise NotImplementedError
