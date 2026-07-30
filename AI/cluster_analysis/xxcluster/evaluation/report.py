"""
Running the comparison and reporting it.

Takes a set of methods and a protocol, produces one `RunResult` each, and
renders the tables the document expects: the side-by-side results of
Sect. 8.1 from the scores, and the qualitative comparison of Sect. 8.2
from the declared capabilities of `core.tags`.

The second of those is the reason the tags exist. A qualitative comparison
maintained by hand in LaTeX drifts from the code the moment a method's
parameters change; generated from the declarations, it cannot.

Exports to CSV, for a spreadsheet, and to a LaTeX table matching the
document's format, so a number reaches the document without being
retyped -- the single most likely place for a result to be corrupted.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from ..core.types import MatrixLike
from .protocol import Protocol, RunResult


class ComparisonRun:
    """Evaluates several methods under one protocol.

    Parameters
    ----------
    methods
        Components, or registered names resolved through the registry.
    protocol
        The shared setup; the same instance for every method.

    Attributes
    ----------
    results_ : list of RunResult
    """

    results_: list[RunResult]

    def __init__(
        self, methods: Sequence[Any] | None = None, *, protocol: Protocol | None = None
    ) -> None:
        self.methods = methods
        self.protocol = protocol

    def run(self, X: MatrixLike, y: Any = None) -> list[RunResult]:
        """Fit and score every method, returning one result each.

        A method that fails is recorded with its error and does not stop
        the run: a comparison missing its hardest case silently is worse
        than one that reports the failure.
        """
        raise NotImplementedError

    def best(self, index: str) -> RunResult:
        """Return the best result under one index, using its direction."""
        raise NotImplementedError


class ComparisonTable:
    """Renders results and declarations as tables.

    Kept separate from `ComparisonRun` so that stored results can be
    re-rendered without refitting, which is what happens every time the
    document's formatting changes.
    """

    def __init__(self, results: Iterable[RunResult] | None = None) -> None:
        self.results = results

    def quantitative(self) -> Any:
        """Scores per method and index: the table of Sect. 8.1."""
        raise NotImplementedError

    def qualitative(self) -> Any:
        """Declared capabilities per method: the table of Sect. 8.2."""
        raise NotImplementedError

    def to_csv(self, path: Any, *, which: str = "quantitative") -> None:
        """Write a table as CSV."""
        raise NotImplementedError

    def to_latex(self, path: Any, *, which: str = "quantitative", label: str | None = None) -> None:
        """Write a table as LaTeX, in the document's `tabularx` form.

        Emits the table body only, for `\\input` into a section file, so
        that regenerating results never touches the surrounding prose.
        """
        raise NotImplementedError


def profile_clusters(X: MatrixLike, labels: Any, **kwargs: Any) -> Any:
    """Summarise each cluster in terms of the original features.

    Per-cluster size and per-feature location and spread, with the
    features that most distinguish a cluster from the rest. This is the
    input to the interpretation and naming of Sect. 4.4, and the step that
    turns a partition into something the project can act on -- so it reads
    the original features, never a reduced or scaled representation.
    """
    raise NotImplementedError
