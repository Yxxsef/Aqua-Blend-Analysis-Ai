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

import math
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from ..core.exceptions import RegistryError
from ..core.registry import REGISTRY
from ..core.tags import Capabilities
from ..core.types import MatrixLike
from ..core.validation import check_labels
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
        """Scores per method and index: the table of Sect. 8.1.

        One row per run, indexed by method. Failed runs are kept with NaN
        scores and their error, because a comparison that drops what did
        not work reads as though everything worked.
        """
        results = list(self.results or ())
        if not results:
            return pd.DataFrame()

        rows = []
        for result in results:
            row: dict[str, Any] = {"method": result.method}
            row.update(dict(result.scores))
            row["n_clusters_found"] = result.n_clusters_found
            row["n_noise"] = result.n_noise
            row["fit_seconds"] = result.fit_seconds
            row["error"] = result.error
            rows.append(row)

        table = pd.DataFrame(rows).set_index("method")
        # A column no method reported -- `n_noise` where none handles noise,
        # `error` where none failed -- is an empty column in the document.
        return table.dropna(axis=1, how="all")

    def qualitative(self) -> Any:
        """Declared capabilities per method: the table of Sect. 8.2.

        Read from the registry rather than from the results, since the
        declaration belongs to the class and does not depend on a run.
        An unregistered method yields a row of NaN rather than an error:
        the gap is visible in the table, which is the point.
        """
        results = list(self.results or ())
        if not results:
            return pd.DataFrame()

        # An empty dict would make pandas drop the row rather than render it
        # as blank, which would hide exactly the gap this is meant to show.
        unknown = dict.fromkeys(Capabilities().describe(), None)

        rows = {}
        for result in results:
            try:
                rows[result.method] = REGISTRY.capabilities(result.method).describe()
            except RegistryError:
                rows[result.method] = dict(unknown)

        table = pd.DataFrame.from_dict(rows, orient="index")
        table.index.name = "method"
        return table

    def _table(self, which: str, columns: Sequence[str] | None = None) -> Any:
        if which == "quantitative":
            table = self.quantitative()
        elif which == "qualitative":
            table = self.qualitative()
        else:
            raise ValueError(
                f"which must be 'quantitative' or 'qualitative'; got {which!r}."
            )
        return table if columns is None else table[list(columns)]

    def to_csv(
        self, path: Any, *, which: str = "quantitative", columns: Sequence[str] | None = None
    ) -> None:
        """Write a table as CSV."""
        self._table(which, columns).to_csv(path)

    def to_latex(
        self,
        path: Any,
        *,
        which: str = "quantitative",
        label: str | None = None,
        columns: Sequence[str] | None = None,
    ) -> None:
        """Write a table as LaTeX, in the document's `tabularx` form.

        Emits the table body only, for `\\input` into a section file, so
        that regenerating results never touches the surrounding prose.

        "Body" means the `tabularx` environment and its rules, not the
        surrounding `table` float: the caption and label are prose and
        stay in the section file, while the column count follows the
        indices actually reported and so cannot be maintained by hand.
        The first column uses the `L` type defined in `preamble.tex`.

        `columns` selects and orders what is emitted, which the
        qualitative table needs: `Capabilities` has seventeen fields and
        no page fits them, so Sect. 8.2 picks the ones its argument turns
        on rather than dumping the declaration.
        """
        table = self._table(which, columns)
        column_spec = ["L"] + ["l"] * len(table.columns)

        lines = [
            "% Generated by xxcluster.evaluation.report -- do not edit by hand.",
            f"\\begin{{tabularx}}{{\\textwidth}}{{@{{}}{' '.join(column_spec)}@{{}}}}",
            "  \\toprule",
            "  " + " & ".join(
                [f"\\textbf{{{_escape_latex(str(table.index.name or ''))}}}"]
                + [f"\\textbf{{{_escape_latex(str(c))}}}" for c in table.columns]
            )
            + r" \\",
            "  \\midrule",
        ]
        # Integrality is decided per column, not per cell: a count column
        # must not print 3 beside 4.000, and a score column must not lose
        # its decimals because one method happened to score exactly 1.
        integral = {c: _is_integral(table[c]) for c in table.columns}
        for name, row in table.iterrows():
            cells = [_escape_latex(str(name))] + [
                _format_cell(value, integral=integral[column])
                for column, value in row.items()
            ]
            lines.append("  " + " & ".join(cells) + r" \\")
        lines += ["  \\bottomrule", "\\end{tabularx}"]

        if label is not None:
            lines.append(f"\\label{{{label}}}")

        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _escape_latex(text: str) -> str:
    """Escape the characters that would otherwise be markup.

    Underscores above all: every method name and index name in this
    package is lower_snake_case, and an unescaped one is a compile error
    in the document rather than a wrong number, which at least fails
    loudly.
    """
    for char, replacement in (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ):
        text = text.replace(char, replacement)
    return text


def _is_integral(column: Any) -> bool:
    """True where every value present in a column is a whole number."""
    values = column.dropna()
    if values.empty or not pd.api.types.is_numeric_dtype(values):
        return False
    return bool((values == values.astype(int)).all())


def _format_cell(value: Any, *, integral: bool = False) -> str:
    """Render one cell, with missing values as the document's dash."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "--"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if integral:
        return str(int(value))
    if isinstance(value, float):
        return f"{value:.3f}"
    return _escape_latex(str(value))


def profile_clusters(
    X: MatrixLike,
    labels: Any,
    *,
    feature_names: Sequence[str] | None = None,
    **kwargs: Any,
) -> Any:
    """Summarise each cluster in terms of the original features.

    Per-cluster size and per-feature location and spread, with the
    features that most distinguish a cluster from the rest. This is the
    input to the interpretation and naming of Sect. 4.4, and the step that
    turns a partition into something the project can act on -- so it reads
    the original features, never a reduced or scaled representation.

    Returns a frame indexed by cluster, with `size` and `share`, then
    `mean`, `std` and `separation` per feature. `separation` is the
    cluster's mean minus the overall mean in units of the overall standard
    deviation -- the quantity that answers "what makes this cluster
    different", which is what a name has to be defensible against.

    Noise is profiled as its own row labelled -1 rather than dropped: how
    many observations a method declined to assign, and where they sit, is
    a property of the result worth reporting.
    """
    labels = check_labels(labels)

    if isinstance(X, pd.DataFrame):
        frame = X.copy()
    else:
        array = np.asarray(X)
        names = feature_names or [f"x{i}" for i in range(array.shape[1])]
        frame = pd.DataFrame(array, columns=list(names))

    if len(frame) != labels.shape[0]:
        raise ValueError(
            f"X has {len(frame)} observations but labels has {labels.shape[0]}."
        )

    numeric = frame.select_dtypes(include="number")
    overall_mean = numeric.mean()
    overall_std = numeric.std().replace(0.0, np.nan)

    grouped = numeric.groupby(labels)
    profile = pd.concat(
        {
            "mean": grouped.mean(),
            "std": grouped.std(),
            "separation": grouped.mean().sub(overall_mean, axis=1).div(overall_std, axis=1),
        },
        axis=1,
    ).swaplevel(axis=1)

    sizes = pd.Series(labels).value_counts().sort_index()
    profile.insert(0, ("", "size"), sizes)
    profile.insert(1, ("", "share"), sizes / sizes.sum())
    profile.index.name = "cluster"
    return profile.sort_index(axis=1)
