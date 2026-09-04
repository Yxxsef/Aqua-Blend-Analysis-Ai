"""
diagnostics_adapter.py

AquaBlend | Analysis & AI | Sprint 3 | Task 71
Prepare the AI interface for infeasible runs, without letting the AI infer
a mathematical cause from an INFEASIBLE status alone.

Governing principle (task description, and Infeasibility_AI_Interface.md):
the AI may explain a supplied diagnosis; otherwise it must remain
status-only. This module is the boundary that enforces that rule in code,
not just in a prompt instruction - a caller cannot accidentally hand the
AI a fabricated cause, because this module is the only thing that decides
whether a cause is safe to expose, and it only ever does so when real
diagnostic data was actually supplied.

Naming warning, read before touching this file: this module's
"infeasibility diagnostics" (likely causes, severities, affected IDs - a
provisional shape sourced from the integration architecture doc, section
20, "conceptual diagnostic result") is a COMPLETELY DIFFERENT THING from
the existing `diagnostics.*` object already defined in
Results_JSON_Field_Map.md (`diagnostics.solver`, `diagnostics.solve_time_
seconds`, `diagnostics.optimality_gap`, and the variable/constraint
counts) and already read by json_explainer.py's technical-appendix
handling. That `diagnostics` object is solver run metadata and exists
regardless of whether the run was feasible. This module's diagnostics are
a cause-of-infeasibility explanation and only exist for INFEASIBLE runs
when the external feasibility/diagnostic framework supplies them. Do not
merge these two concepts, do not read this module's input from a JSON
key literally named `diagnostics`, and do not let a caller pass the
solver-metadata object in by mistake - the constructor functions below
take the infeasibility-cause payload as an explicit, separately-named
parameter for exactly this reason.

This module does not call json_explainer.py, model_runner.py, or
llm_validator.py, and does not import anything from them - same
standalone-module pattern those three already use. It operates on plain
dicts/strings so it can be tested and used entirely on its own. It also
does not duplicate json_explainer.py's explain_result_availability(),
which already produces the generic "Solver status is INFEASIBLE..."
sentence for every non-OPTIMAL status - this module is strictly additive
to that, and only ever concerns the diagnostics-specific content
layered on top of it.

Provisional-contract warning: the exact shape of the infeasibility-
diagnostics payload (field names, whether "severity" is a fixed enum,
which ID fields appear) is NOT confirmed. It is sourced from the
integration architecture doc's own "conceptual diagnostic result"
example, explicitly hedged there as conceptual, not final. This module
is built to degrade safely on anything that doesn't match that shape
(see "Malformed input handling" below) specifically because the real
contract may still change - see Infeasibility_AI_Interface.md.

Outcomes this module distinguishes
-----------------------------------
Every run this module is given lands in exactly one of three buckets,
returned as InfeasibilityContext.outcome:

  TECHNICAL_FAILURE            - the solver did not run to a real
                                  conclusion (status ERROR, or any status
                                  this module does not recognise). This is
                                  a tooling/technical problem, not a
                                  mathematical proof of infeasibility, and
                                  must never be described as one.
  INFEASIBLE_WITH_DIAGNOSTICS  - status is INFEASIBLE, and at least one
                                  well-formed cause was supplied. The AI
                                  may explain these specific, supplied
                                  causes.
  INFEASIBLE_STATUS_ONLY       - status is INFEASIBLE (or UNBOUNDED - see
                                  below), but no usable diagnostics were
                                  supplied. The AI must not infer or
                                  invent a cause; render_diagnostics_
                                  section() correctly returns None for
                                  this outcome, and callers must not
                                  substitute their own explanation for it.

UNBOUNDED is treated the same as INFEASIBLE for this classification
(Results_JSON_Field_Map.md's "do not report a recommended blend" rule
applies to both) but is out of this task's primary scope - the external
diagnostic framework's example is written for INFEASIBLE specifically,
and this module has not been asked to assume UNBOUNDED diagnostics share
the same shape. UNBOUNDED therefore always lands in
INFEASIBLE_STATUS_ONLY here, even if a diagnostics payload is supplied
for it, until that assumption is confirmed - see
Infeasibility_AI_Interface.md section on open questions.

Malformed input handling
-------------------------
Consistent with json_explainer.py's own "deliberately tolerant" input
philosophy: a malformed or partial diagnostics payload degrades to no
diagnostics (INFEASIBLE_STATUS_ONLY), it does not raise. Specifically:

  - The payload is not a mapping, or has no "likely_causes" list at all,
    or that list is empty -> treated as no diagnostics supplied.
  - An individual cause entry missing the one truly required field
    (`type`) is skipped, not treated as fatal - the remaining well-formed
    causes (if any) are still used.
  - `severity` is passed through as given, defaulting to "unspecified"
    if missing - it is deliberately NOT validated against a fixed set of
    allowed values, since the real contract has not confirmed one.
  - Any extra fields on a cause entry beyond type/severity/details are
    collected into `affected_ids` (see DiagnosticCause below) rather than
    dropped, so a real payload's plant_id/source_id/zone_id/link fields
    (or any other identifying field the confirmed contract eventually
    uses) survive without this module needing to be updated for each new
    ID field name.

This module never raises on malformed diagnostics content. It DOES raise
DiagnosticsAdapterError on a genuinely unusable call - specifically, a
missing or empty `solver_status` - since that is a caller programming
error, not a real-world data-quality gap this module is designed to
absorb.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Status and outcome constants
# ---------------------------------------------------------------------------

# Matches json_explainer.py's own literal status strings exactly - see that
# module's FULL_REPORT_STATUSES and Results_JSON_Field_Map.md's "Special
# handling rules" section. Not imported from json_explainer.py, per this
# module's standalone-module design (see the module docstring) - kept in
# sync by convention, the same way llm_validator.py's status words are.
STATUS_OPTIMAL = "OPTIMAL"
STATUS_INFEASIBLE = "INFEASIBLE"
STATUS_UNBOUNDED = "UNBOUNDED"
STATUS_TIME_LIMIT = "TIME_LIMIT"
STATUS_ERROR = "ERROR"

# The statuses this module treats as "a genuine infeasibility-shaped
# result", as opposed to a technical failure to solve at all. UNBOUNDED is
# included per Results_JSON_Field_Map.md's shared "do not report a
# recommended blend" rule, but always resolves to INFEASIBLE_STATUS_ONLY -
# see the module docstring's UNBOUNDED note.
_INFEASIBILITY_SHAPED_STATUSES = frozenset({STATUS_INFEASIBLE, STATUS_UNBOUNDED})

OUTCOME_TECHNICAL_FAILURE = "TECHNICAL_FAILURE"
OUTCOME_INFEASIBLE_WITH_DIAGNOSTICS = "INFEASIBLE_WITH_DIAGNOSTICS"
OUTCOME_INFEASIBLE_STATUS_ONLY = "INFEASIBLE_STATUS_ONLY"

_KNOWN_CAUSE_FIELDS = frozenset({"type", "severity", "details"})
_DEFAULT_SEVERITY = "unspecified"


class DiagnosticsAdapterError(ValueError):
    """Raised only for a genuine caller programming error (a missing or
    empty solver_status) - never for malformed diagnostics content, which
    this module always degrades safely instead of raising on. See the
    module docstring's "Malformed input handling" section."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiagnosticCause:
    """One structured cause from a supplied infeasibility-diagnostics
    payload. Mirrors the integration doc's conceptual example
    (`type`, `severity`, `details`, and an ID field like `plant_id`), but
    deliberately does not hard-code which ID field names exist - see
    affected_ids below and the module docstring's provisional-contract
    warning."""

    cause_type: str
    severity: str = _DEFAULT_SEVERITY
    details: str | None = None
    # Any fields on the source cause entry other than type/severity/details
    # - e.g. {"plant_id": "plant_01"} or {"source_id": "source_a"} - kept
    # as a plain dict rather than named attributes so a real contract's ID
    # field, whatever it turns out to be named, is preserved without this
    # dataclass needing to change.
    affected_ids: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InfeasibilityContext:
    """The safe, structured result this module hands to a caller (the
    templating layer, or eventually the LLM rewrite prompt) - never the
    raw payload directly. `outcome` is always one of the three OUTCOME_*
    constants; `causes` is only ever non-empty when outcome is
    INFEASIBLE_WITH_DIAGNOSTICS."""

    outcome: str
    solver_status: str
    causes: tuple[DiagnosticCause, ...] = ()

    def has_causes(self) -> bool:
        return len(self.causes) > 0


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _parse_causes(raw_diagnostics: Any) -> tuple[DiagnosticCause, ...]:
    """Best-effort, never-raising parse of a raw infeasibility-diagnostics
    payload into DiagnosticCause objects. Returns an empty tuple for
    anything that doesn't match the expected shape - see the module
    docstring's "Malformed input handling" section for exactly what is
    tolerated."""
    if not isinstance(raw_diagnostics, Mapping):
        return ()

    raw_causes = raw_diagnostics.get("likely_causes")
    if not isinstance(raw_causes, list):
        return ()

    parsed: list[DiagnosticCause] = []
    for entry in raw_causes:
        if not isinstance(entry, Mapping):
            continue
        cause_type = entry.get("type")
        if not isinstance(cause_type, str) or not cause_type.strip():
            continue  # the one truly required field - skip, don't fail the batch
        severity = entry.get("severity")
        if not isinstance(severity, str) or not severity.strip():
            severity = _DEFAULT_SEVERITY
        details = entry.get("details")
        if not isinstance(details, str):
            details = None
        affected_ids = {
            k: v for k, v in entry.items() if k not in _KNOWN_CAUSE_FIELDS
        }
        parsed.append(DiagnosticCause(
            cause_type=cause_type,
            severity=severity,
            details=details,
            affected_ids=affected_ids,
        ))
    return tuple(parsed)


def build_infeasibility_context(
    solver_status: str,
    infeasibility_diagnostics: Any = None,
) -> InfeasibilityContext:
    """The main entry point. Classifies `solver_status` into one of the
    three OUTCOME_* buckets and, only for a genuine INFEASIBLE result with
    at least one well-formed cause, attaches the parsed causes.

    `infeasibility_diagnostics` is the raw external-framework payload
    (see the module docstring's conceptual shape) - NOT the existing
    `diagnostics.*` solver-metadata object already defined in
    Results_JSON_Field_Map.md. Passing that object here by mistake is
    exactly the naming collision this module's docstring warns about; it
    will simply parse to zero causes (it has no `likely_causes` key), so
    the failure mode is a silent status-only result, not a crash - still
    worth getting right at the call site.

    Raises DiagnosticsAdapterError only if solver_status is missing or
    empty - never for malformed diagnostics content."""
    if not solver_status or not solver_status.strip():
        raise DiagnosticsAdapterError(
            "build_infeasibility_context requires a non-empty solver_status"
        )

    if solver_status not in _INFEASIBILITY_SHAPED_STATUSES:
        # Covers STATUS_ERROR explicitly, and any other/unrecognised status
        # defensively - an unrecognised status is a technical/tooling
        # situation this module was not told how to interpret, not a
        # mathematical result, so it is never treated as one.
        return InfeasibilityContext(
            outcome=OUTCOME_TECHNICAL_FAILURE,
            solver_status=solver_status,
        )

    if solver_status == STATUS_UNBOUNDED:
        # Always status-only - see the module docstring's UNBOUNDED note.
        return InfeasibilityContext(
            outcome=OUTCOME_INFEASIBLE_STATUS_ONLY,
            solver_status=solver_status,
        )

    causes = _parse_causes(infeasibility_diagnostics)
    if causes:
        return InfeasibilityContext(
            outcome=OUTCOME_INFEASIBLE_WITH_DIAGNOSTICS,
            solver_status=solver_status,
            causes=causes,
        )
    return InfeasibilityContext(
        outcome=OUTCOME_INFEASIBLE_STATUS_ONLY,
        solver_status=solver_status,
    )


# ---------------------------------------------------------------------------
# Deterministic rendering
# ---------------------------------------------------------------------------


def render_diagnostics_section(context: InfeasibilityContext) -> str | None:
    """Deterministic, template-only text for the diagnostics-specific
    portion of a report - additive to, and never a replacement for,
    json_explainer.py's own explain_result_availability(), which already
    covers the generic "Solver status is INFEASIBLE..." sentence for every
    non-OPTIMAL status.

    Returns None for OUTCOME_INFEASIBLE_STATUS_ONLY - there is deliberately
    nothing to say here, and a caller must not substitute its own guess
    for that None. Returns a short, safe, non-diagnostic note for
    OUTCOME_TECHNICAL_FAILURE, explicitly distinguishing "the solver did
    not run to completion" from "the solver proved this infeasible" - the
    exact distinction this module exists to keep from being blurred.
    Returns a factual, template-only rendering of the supplied causes for
    OUTCOME_INFEASIBLE_WITH_DIAGNOSTICS - every word traces to a supplied
    cause's fields; nothing is invented or inferred beyond them."""
    if context.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY:
        return None

    if context.outcome == OUTCOME_TECHNICAL_FAILURE:
        return (
            f"Solver status is {context.solver_status}. This is a technical "
            "failure to complete the solve, not a mathematical proof that "
            "the scenario is infeasible - the two should not be treated as "
            "the same finding."
        )

    lines = ["Diagnostic information was supplied for this infeasible result:"]
    for cause in context.causes:
        parts = [f"- {cause.cause_type} (severity: {cause.severity})"]
        if cause.details:
            parts.append(f": {cause.details}")
        if cause.affected_ids:
            id_text = ", ".join(f"{k}={v}" for k, v in sorted(cause.affected_ids.items()))
            parts.append(f" [{id_text}]")
        lines.append("".join(parts))
    return "\n".join(lines)
