"""
Declared capabilities of a component.

Each concrete class states, once, what it assumes and what it supports.
Three consumers read these tags:

1. `xxcluster.core.registry` -- filtering candidate methods for a dataset.
2. `xxcluster.evaluation.report` -- building the qualitative comparison
   table of Sect. 8.2 without restating any of it by hand.
3. The contract checks -- catching a class whose declaration contradicts
   its interface.

Tags are declarations, not measurements: fill them from the Assumptions
and Complexity paragraphs of the method's documentation section.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum

from .types import Assignment, Backend, Family, Scaling, SubFamily


@dataclass(frozen=True)
class Capabilities:
    """What a component assumes about the data and offers to the caller."""

    # --- Placement in the taxonomy ---------------------------------------
    family: Family | None = None
    subfamily: SubFamily | None = None
    backend: Backend = Backend.NATIVE

    # --- Interface --------------------------------------------------------
    assignment: Assignment = Assignment.CRISP
    #: Exposes `predict` for observations unseen during `fit`.
    is_inductive: bool = False
    #: Builds a full hierarchy that can be cut at an arbitrary level.
    produces_hierarchy: bool = False
    #: Accepts `metric="precomputed"` and a dissimilarity matrix as `X`.
    supports_precomputed: bool = False

    # --- Assumptions about the data --------------------------------------
    #: `n_clusters` (or an equivalent) must be fixed before fitting.
    requires_n_clusters: bool = False
    #: Can label an observation as noise (-1) instead of forcing membership.
    handles_noise: bool = False
    handles_missing: bool = False
    handles_categorical: bool = False
    #: Result is invariant to feature scaling.
    scale_invariant: bool = False
    #: Same input and seed always give the same partition.
    deterministic: bool = False

    # --- Cost -------------------------------------------------------------
    scales_to: Scaling = Scaling.MEDIUM
    #: Big-O in n and d, as reported in the Complexity paragraph.
    time_complexity: str | None = None
    space_complexity: str | None = None

    # --- Provenance -------------------------------------------------------
    #: Citation keys in documentation/literature.bib backing this method.
    references: tuple[str, ...] = field(default_factory=tuple)
    #: Label of the method's documentation subsection, e.g. "sec:tech:som".
    doc_label: str | None = None

    def describe(self) -> dict[str, object]:
        """Return the tags as a flat row for the comparison table.

        Enums render as their values and the reference tuple as a
        comma-separated string, so the row is directly writable to CSV or
        LaTeX without a second pass of type handling in the reporting
        layer. `references` and `doc_label` are dropped: they are
        provenance for the prose, not columns of Table 8.2.
        """
        row: dict[str, object] = {}
        for field_ in fields(self):
            if field_.name in ("references", "doc_label"):
                continue
            value = getattr(self, field_.name)
            row[field_.name] = value.value if isinstance(value, Enum) else value
        return row

    def is_applicable(self, **data_properties: bool) -> bool:
        """Report whether these capabilities cover the given data properties.

        Used to shortlist methods for a dataset (missing values, mixed
        types, expected noise) before any fitting is attempted.

        Each keyword names a property the data has; a method qualifies only
        if it declares the matching capability. Properties are passed as
        the `handles_*` name they are checked against, e.g.
        `is_applicable(handles_missing=True)`.

        A property the capabilities do not define is a caller's error, not
        a silent false. Misspelling one would otherwise shortlist every
        method rather than none, which is the failure that would go
        unnoticed.
        """
        known = {field_.name for field_ in fields(self)}
        for name, required in data_properties.items():
            if name not in known:
                raise ValueError(
                    f"unknown capability {name!r}; expected one of "
                    f"{', '.join(sorted(known))}."
                )
            if required and not getattr(self, name):
                return False
        return True
