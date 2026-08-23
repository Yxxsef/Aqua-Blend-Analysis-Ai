"""
llm_validator.py

AquaBlend | Analysis & AI | Sprint 2 | Task 25
Validate, test, and evaluate the first LLM pipeline.

This module is the factual and safety validator described in
Validation_Rules.md. It checks an LLM-rewritten report (Task 24's output)
against the deterministic report it was built from (Task 23's output) and
returns a structured PASS/FAIL result plus any non-critical warnings.

This module does not call Task 24's model_runner.py or Task 23's
json_explainer.py, and does not import anything from either. It operates on
two plain strings - the deterministic report text and the candidate rewrite
text - so it can be tested and used entirely on its own, the same way
json_explainer.py deliberately does not call results_adapter.adapt_results()
itself. Whatever calls this module is responsible for supplying the two
correct strings and for deciding what to do with the result (e.g. converting
model_runner.RewriteResult.report_mode from "LLM_UNVALIDATED" to
"LLM_VALIDATED" on a PASS, or discarding the rewrite and keeping
"TEMPLATE_FALLBACK" on a FAIL). That conversion is not this module's job.

What this checks, and why (see Validation_Rules.md for the full rationale
behind each rule and its exact detection method):

  Critical (any single failure makes the whole result FAIL):
    NUMBER_MISSING_OR_CHANGED   - a fact-bearing number from the
                                   deterministic report does not appear
                                   anywhere in the rewrite
    NUMBER_INVENTED             - a number appears in the rewrite that
                                   was not in the deterministic report
    UNIT_OR_CODE_MISSING        - a currency/unit code (AUD, ML, NTU, pH,
                                   etc.) present in the source is dropped
    IDENTIFIER_MISSING          - a source, plant, or zone name present
                                   in the source is dropped
    STATUS_MISSING              - a solver or quality status word (e.g.
                                   OPTIMAL, PASS) present in the source is
                                   dropped
    STATUS_INVENTED              - a status word appears that was not in
                                   the source (a status flip)
    INVENTED_CONTENT            - wording that reads as a reason,
                                   recommendation, calculation, comparison,
                                   or regulatory/compliance claim appears
                                   in the rewrite but not the source
    UNSAFE_SAFETY_CLAIM         - "safe to drink", "compliant", or similar
                                   wording appears anywhere in the rewrite,
                                   regardless of the source (always banned)
    DISCLAIMER_MISSING          - the prototype disclaimer's core wording
                                   is dropped
    WATER_QUALITY_NOTE_MISSING  - the plant-inflow-not-final-drinking-water
                                   note is dropped while quality content
                                   remains
    EMPTY_OUTPUT                - the rewrite is blank or whitespace-only

  Warning (recorded, does not fail the result on its own):
    NEW_IDENTIFIER              - a source/plant/zone-like name appears in
                                   the rewrite that was not in the source
    WEAK_INVENTED_CONTENT_PHRASE - a softer phrase that often, but not
                                   always, signals invented content
    LENGTH_ANOMALY               - the rewrite is under half the word
                                   count of the source report

Everything here is a deliberately simple, explainable, deterministic text
check - not a semantic understanding of the report. It cannot catch every
possible factual error and is not meant to. It catches the error patterns
Report_Structure.md and LLM_Report_Scope.md section 6 actually describe,
using signals that are cheap to compute and easy for a human reviewer to
double-check by eye. See Validation_Rules.md section 7 ("Known limits") for
what this deliberately does not attempt to catch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


class ValidatorInputError(TypeError):
    """Raised when validate_llm_output() receives the wrong input type."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Report_Structure.md section 2 / Results_JSON_Field_Map.md "Non-optimal
# runs": the confirmed contract's solver-status values. Deliberately NOT
# including "SUCCESS" or "FEASIBLE" - those were placeholder values from an
# earlier draft schema, not the confirmed model_output_contract.json set.
SOLVER_STATUS_WORDS = {"OPTIMAL", "INFEASIBLE", "UNBOUNDED", "TIME_LIMIT", "ERROR"}

# Report_Structure.md section 3 (water-quality parameter status).
QUALITY_STATUS_WORDS = {"PASS", "FAIL"}

STATUS_WORDS = SOLVER_STATUS_WORDS | QUALITY_STATUS_WORDS

# Report_Structure.md, "Prototype disclaimer" section - checked by marker
# phrase rather than exact text, since the LLM is explicitly allowed to
# reword it (prompts.py rule 5: "you may improve headings and sentence
# flow"). Any one of these surviving is treated as the disclaimer being
# present; this is a deliberately generous heuristic - see Validation_Rules.md
# section 7.
DISCLAIMER_MARKERS = ["proof-of-concept", "proof of concept"]

# Report_Structure.md, "Plant-inflow water-quality results" section - the
# mandatory stage note. Same generous-marker approach as the disclaimer.
WATER_QUALITY_STAGE_MARKERS = ["plant inflow", "plant-inflow", "plant\u2011inflow"]
WATER_QUALITY_SECTION_MARKERS = [
    "plant inflow", "plant-inflow", "blend_at_plant_inflow", "water quality",
]

# LLM_Report_Scope.md section 6: "an unsafe result described as safe". These
# four phrases are inherited directly from json_explainer's own permanent
# test guarantee (test_water_quality_never_claims_final_or_safe in
# test_json_explainer.py) that they never appear in the deterministic
# report - so their presence in a rewrite is always a rule 4 violation,
# never a legitimate carry-over from the source.
ALWAYS_BANNED_PHRASES = ["final drinking", "safe to drink", "compliant", "treated water"]

# LLM_Report_Scope.md section 6: "an invented reason" / rule 3's list
# (reasons, causal claims, recommendations, decisions, alternatives,
# sensitivity findings, regulatory claims, compliance claims, operational
# advice). These are flagged only when they appear in the rewrite but NOT
# in the deterministic report (a differential check, not a blanket ban) -
# see _check_invented_content and Validation_Rules.md section 4.
STRONG_INVENTED_CONTENT_PHRASES = [
    "because", "we recommend", "it is recommended", "you should",
    "we advise", "we suggest", "cheapest available", "lowest cost",
    "in compliance with", "meets regulation", "regulatory requirement",
    "regulatory compliance", "guarantees", "is certified",
    "approved for consumption", "ensures safety", "in order to",
    "this suggests that", "likely due to", "consider using",
    "an alternative option",
]

# Weaker signals - correlated with invented content but common enough in
# ordinary prose that a hard fail would risk false positives. Recorded as
# warnings for a human to check, not auto-failed.
WEAK_INVENTED_CONTENT_PHRASES = [
    "should be noted", "it is likely", "probably", "may indicate",
    "this shows", "as a result of",
]

# Identifier-like phrase: two or more consecutive Title-Case (or Title-Case
# plus digit/comma) words - e.g. "Silvan Reservoir", "Yarra River, Kew",
# "Treatment Facility 1", "Groundwater Bore 1", "Zone 1". Matches the actual
# naming pattern of every source, plant, and zone name in the confirmed
# contract's example data.
_TITLE_CASE_IDENTIFIER_PATTERN = re.compile(
    r"\b[A-Z][a-zA-Z]*(?:[ ,]+[A-Z0-9][a-zA-Z0-9]*)+\b"
)

# Snake-case identifier: the internal IDs and field names the deterministic
# report also quotes directly in the Data Flags and Sensitivity sections -
# e.g. "silvan_reservoir", "groundwater_bore_1", "storage_capacity",
# "cost_per_ml", "zone_1". These are a distinct fact category from the
# Title-Case display names above (both can refer to the same source) and
# are just as easy for a rewrite to accidentally drop or rename.
_SNAKE_CASE_IDENTIFIER_PATTERN = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")

# Ordinary connector/instruction words that happen to be capitalised only
# because they start a sentence (e.g. "Reduce Yarra Kew share to..." in an
# alternative-solution description). None of AquaBlend's actual source,
# plant, or zone names begin with any of these, so excluding a Title-Case
# match whose FIRST word is one of these removes a real, observed class of
# false positive without weakening genuine identifier coverage. See
# Validation_Rules.md section 3 for the reasoning and the false positive
# this was written to fix.
_LEADING_WORD_STOPWORDS = {
    "Reduce", "Increase", "Introduce", "Remove", "Add", "Consider", "See",
    "Note", "Include", "Exclude", "Downstream", "For", "Overall", "Given",
    "Based", "According",
}

# Numeric fact candidate: an optional leading '-' or '$', digits with
# optional thousands separators, an optional decimal part, an optional
# trailing '%'. A candidate is discarded by _extract_numbers below if it
# turns out to be embedded inside a longer identifier token (e.g. the "01"
# inside "scenario_2026_07_17_001", or "1" inside "facility_1") - see
# _is_embedded_in_identifier for why a single-character lookaround on the
# regex itself is not enough to catch every such case.
_NUMBER_PATTERN = re.compile(r"-?\$?\d[\d,]*(?:\.\d+)?%?")

# Currency and measurement codes used across the deterministic report.
# "pH" is mixed case and handled as its own literal alternative; the rest
# are 2-5 letter all-caps tokens (AUD, NZD, USD, ML, NTU, ...).
_UNIT_CODE_PATTERN = re.compile(r"\bpH\b|\b[A-Z]{2,5}\b")

# Report_Structure.md section order: headings are rendered as "## Title".
# Stripped out before fact-extraction so a legitimately reworded heading
# (explicitly permitted by the prompt) is never mistaken for a missing
# identifier or missing fact. See Validation_Rules.md section 3.
_HEADING_LINE_PATTERN = re.compile(r"^##[ \t]+.*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CriticalFailure:
    """One specific reason the result failed. `rule` is one of the
    critical rule names listed in this module's docstring."""

    rule: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "detail": self.detail}


@dataclass(frozen=True)
class Warning_:  # noqa: N801 - "Warning" collides with the builtin
    """One non-critical observation. Does not affect critical_result."""

    rule: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "detail": self.detail}


@dataclass(frozen=True)
class ValidationResult:
    """The complete output of validate_llm_output().

    critical_result is "PASS" only when critical_failures is empty.
    Warnings never change critical_result - they are surfaced for a human
    reviewer, per the task card's "return structured PASS, FAIL, and
    warning results."
    """

    critical_result: str
    critical_failures: list[CriticalFailure] = field(default_factory=list)
    warnings: list[Warning_] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "critical_result": self.critical_result,
            "critical_failures": [f.to_dict() for f in self.critical_failures],
            "warnings": [w.to_dict() for w in self.warnings],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_headings(report: str) -> str:
    """Remove '## Heading' lines. The LLM is explicitly allowed to reword
    headings (prompts.py rule 5), so fact-extraction must not run against
    them - a reworded heading is not a missing identifier or a missing
    fact."""
    return _HEADING_LINE_PATTERN.sub("", report)


def _normalise_number(token: str) -> tuple[float, bool]:
    """'$68,150.0' -> (68150.0, False), '-4.5%' -> (-4.5, True), '500' ->
    (500.0, False). Trailing '.0' vs no decimal point are treated as the
    same fact (235 and 235.00 are the same number), per the deliberate
    design choice documented in Validation_Rules.md section 3.

    The percent sign is part of the value's identity, not stripped away:
    '58.0%' and '58.0' are DIFFERENT facts, even though they share the
    same digits. Losing the '%' changes what the number means (a
    proportion becoming a bare, ambiguous figure), so an earlier version
    of this function that stripped '%' before comparing made that change
    invisible - '58.0%' silently becoming '58.0' passed validation. Found
    in review, not in the original test pack; see
    test_dropped_percent_sign_fails in test_llm_validator.py."""
    is_percent = token.endswith("%")
    cleaned = token.replace("$", "").replace(",", "").replace("%", "")
    return (float(cleaned), is_percent)


def _is_embedded_in_identifier(text: str, start: int, end: int) -> bool:
    """True if the number match at text[start:end] sits inside a longer
    run of letters/digits/underscores that contains at least one letter -
    i.e. it is really part of an identifier like "facility_1" or
    "scenario_2026_07_17_001", not a standalone fact.

    A single-character lookaround on the number regex catches the simple
    case (a digit run directly touching a letter or underscore), but not a
    multi-digit run where the match could start partway through - e.g. the
    "01" inside "..._17_001" starts right after another digit ('0'), which
    a plain lookbehind for "not a letter/underscore" would happily accept.
    Extending outward through the full contiguous alnum/underscore run
    (not just one character) closes that gap."""
    i = start
    while i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_"):
        i -= 1
    j = end
    while j < len(text) and (text[j].isalnum() or text[j] == "_"):
        j += 1
    surrounding = text[i:j]
    return any(ch.isalpha() or ch == "_" for ch in surrounding)


def _extract_numbers(text: str) -> set[tuple[float, bool]]:
    values = set()
    for m in _NUMBER_PATTERN.finditer(text):
        if not _is_embedded_in_identifier(text, m.start(), m.end()):
            values.add(_normalise_number(m.group()))
    return values


def _extract_identifiers(text: str) -> set[str]:
    title_case = {
        m for m in _TITLE_CASE_IDENTIFIER_PATTERN.findall(text)
        if m.split(" ")[0].split(",")[0] not in _LEADING_WORD_STOPWORDS
    }
    snake_case = set(_SNAKE_CASE_IDENTIFIER_PATTERN.findall(text))
    return title_case | snake_case


def _extract_unit_codes(text: str) -> set[str]:
    return set(_UNIT_CODE_PATTERN.findall(text))


def _extract_status_words(text: str) -> set[str]:
    tokens = set(re.findall(r"\b[A-Z_]{2,}\b", text))
    return tokens & STATUS_WORDS


def _contains_any(haystack_lower: str, phrases: list[str]) -> str | None:
    """First phrase from `phrases` found in `haystack_lower`, or None.
    `haystack_lower` must already be lower-cased; `phrases` must already be
    lower-case literals."""
    for phrase in phrases:
        if phrase in haystack_lower:
            return phrase
    return None


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _format_number(value_and_flag: tuple[float, bool]) -> str:
    value, is_percent = value_and_flag
    return f"{value}%" if is_percent else str(value)


def _check_numbers(det_body: str, llm_output: str) -> list[CriticalFailure]:
    """Presence-based, not repetition-count-based: a value must appear at
    least once in the rewrite if it appeared at least once in the source,
    and vice versa for invented values. An exact repetition count was
    tried and rejected - the deterministic report often restates the same
    fact across more than one section (e.g. a source's flow volume in both
    its selection line and its transfer-results line), and a faithful,
    naturally-compressed rewrite ("Flows into the facility were 210 ML/day
    from Silvan Reservoir...") can legitimately state a fact fewer times
    than the source without dropping it. See Validation_Rules.md section 3.

    Percent and plain values are distinct facts even at the same digits -
    see _normalise_number."""
    det_values = _extract_numbers(det_body)
    llm_values = _extract_numbers(llm_output)

    failures: list[CriticalFailure] = []

    for value in sorted(det_values - llm_values):
        failures.append(CriticalFailure(
            "NUMBER_MISSING_OR_CHANGED",
            f"The value {_format_number(value)!r} appears in the "
            "deterministic report but not in the rewrite.",
        ))

    for value in sorted(llm_values - det_values):
        failures.append(CriticalFailure(
            "NUMBER_INVENTED",
            f"The value {_format_number(value)!r} appears in the rewrite "
            "but was not present in the deterministic report.",
        ))

    return failures


def _check_unit_codes(det_body: str, llm_output: str) -> list[CriticalFailure]:
    det_codes = _extract_unit_codes(det_body)
    llm_codes = _extract_unit_codes(llm_output)
    missing = det_codes - llm_codes
    return [
        CriticalFailure(
            "UNIT_OR_CODE_MISSING",
            f"The unit or code '{code}' appears in the deterministic report "
            "but not in the rewrite.",
        )
        for code in sorted(missing)
    ]


def _check_identifiers(
    det_body: str, llm_output: str
) -> tuple[list[CriticalFailure], list[Warning_]]:
    det_ids = _extract_identifiers(det_body)
    llm_ids = _extract_identifiers(llm_output)

    missing = det_ids - llm_ids
    failures = [
        CriticalFailure(
            "IDENTIFIER_MISSING",
            f"'{name}' appears in the deterministic report but not in the "
            "rewrite.",
        )
        for name in sorted(missing)
    ]

    new = llm_ids - det_ids
    warnings = [
        Warning_(
            "NEW_IDENTIFIER",
            f"'{name}' appears in the rewrite but was not in the "
            "deterministic report. May be a legitimate rewording, or may be "
            "an invented name - worth a human check.",
        )
        for name in sorted(new)
    ]
    return failures, warnings


def _check_status_words(det_body: str, llm_output: str) -> list[CriticalFailure]:
    det_status = _extract_status_words(det_body)
    llm_status = _extract_status_words(llm_output)

    failures = [
        CriticalFailure(
            "STATUS_MISSING",
            f"The status word '{word}' appears in the deterministic report "
            "but not in the rewrite.",
        )
        for word in sorted(det_status - llm_status)
    ]
    failures += [
        CriticalFailure(
            "STATUS_INVENTED",
            f"The status word '{word}' appears in the rewrite but was not "
            "in the deterministic report.",
        )
        for word in sorted(llm_status - det_status)
    ]
    return failures


def _check_invented_content(
    det_report_lower: str, llm_output_lower: str
) -> tuple[list[CriticalFailure], list[Warning_]]:
    failures = []
    for phrase in STRONG_INVENTED_CONTENT_PHRASES:
        if phrase in llm_output_lower and phrase not in det_report_lower:
            failures.append(CriticalFailure(
                "INVENTED_CONTENT",
                f"The phrase '{phrase}' appears in the rewrite but not in "
                "the deterministic report. This usually signals an invented "
                "reason, recommendation, or claim.",
            ))

    warnings = []
    for phrase in WEAK_INVENTED_CONTENT_PHRASES:
        if phrase in llm_output_lower and phrase not in det_report_lower:
            warnings.append(Warning_(
                "WEAK_INVENTED_CONTENT_PHRASE",
                f"The phrase '{phrase}' appears in the rewrite but not in "
                "the deterministic report. This can be ordinary phrasing or "
                "can signal invented content - worth a human check.",
            ))
    return failures, warnings


def _check_always_banned_safety_claims(llm_output_lower: str) -> list[CriticalFailure]:
    failures = []
    for phrase in ALWAYS_BANNED_PHRASES:
        if phrase in llm_output_lower:
            failures.append(CriticalFailure(
                "UNSAFE_SAFETY_CLAIM",
                f"The phrase '{phrase}' appears in the rewrite. This wording "
                "is never permitted in an AquaBlend report, regardless of "
                "the source text (LLM_Report_Scope.md section 6).",
            ))
    return failures


def _check_disclaimer(det_report_lower: str, llm_output_lower: str) -> list[CriticalFailure]:
    det_has_disclaimer = _contains_any(det_report_lower, DISCLAIMER_MARKERS) is not None
    if not det_has_disclaimer:
        return []
    if _contains_any(llm_output_lower, DISCLAIMER_MARKERS) is None:
        return [CriticalFailure(
            "DISCLAIMER_MISSING",
            "The deterministic report includes the prototype disclaimer, "
            "but no recognisable form of it was found in the rewrite.",
        )]
    return []


def _check_water_quality_note(
    det_report_lower: str, llm_output_lower: str
) -> list[CriticalFailure]:
    det_has_quality_content = _contains_any(det_report_lower, WATER_QUALITY_SECTION_MARKERS) is not None
    if not det_has_quality_content:
        return []
    if _contains_any(llm_output_lower, WATER_QUALITY_STAGE_MARKERS) is None:
        return [CriticalFailure(
            "WATER_QUALITY_NOTE_MISSING",
            "The deterministic report includes plant-inflow water-quality "
            "content, but the rewrite does not state that these results "
            "apply to plant inflow rather than final treated water.",
        )]
    return []


def _check_length_anomaly(det_report: str, llm_output: str) -> list[Warning_]:
    det_words = len(det_report.split())
    llm_words = len(llm_output.split())
    if det_words > 0 and llm_words < det_words * 0.5:
        return [Warning_(
            "LENGTH_ANOMALY",
            f"The rewrite is {llm_words} words, under half the deterministic "
            f"report's {det_words} words. May indicate dropped content.",
        )]
    return []


def _check_empty_output(llm_output: str) -> list[CriticalFailure]:
    if not llm_output.strip():
        return [CriticalFailure(
            "EMPTY_OUTPUT",
            "The rewrite is empty or contains only whitespace.",
        )]
    return []


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def validate_llm_output(deterministic_report: str, llm_output: str) -> ValidationResult:
    """Validate an LLM rewrite against the deterministic report it was
    built from.

    Args:
        deterministic_report: The trusted report text produced by
            json_explainer.generate_explanation() (Task 23).
        llm_output: The candidate rewrite text - typically a successful
            model_runner.RewriteResult.report_text where report_mode is
            "LLM_UNVALIDATED" (Task 24).

    Returns:
        A ValidationResult. critical_result is "FAIL" if critical_failures
        is non-empty, "PASS" otherwise. Warnings never affect
        critical_result.

    Raises:
        ValidatorInputError: If either argument is not a string.
    """
    if not isinstance(deterministic_report, str):
        raise ValidatorInputError("deterministic_report must be a string")
    if not isinstance(llm_output, str):
        raise ValidatorInputError("llm_output must be a string")

    empty_failure = _check_empty_output(llm_output)
    if empty_failure:
        # Every other check either does nothing useful or produces noisy,
        # misleading results (e.g. "every number is missing") against an
        # empty string - report only the one failure that actually matters.
        return ValidationResult(critical_result="FAIL", critical_failures=empty_failure)

    # Headings are stripped from BOTH sides before number/identifier
    # extraction, not just the deterministic side. Report_Structure.md's
    # section headings are frequently Title-Case two-word phrases
    # ("Selected Sources", "Active Plants") that would otherwise match the
    # identifier pattern - stripping only one side made an unchanged
    # rewrite (llm_output == deterministic_report) spuriously report its
    # own headings as "new" identifiers, found by testing the identical-
    # input case directly rather than assumed safe.
    det_body = _strip_headings(deterministic_report)
    llm_body = _strip_headings(llm_output)
    det_report_lower = deterministic_report.lower()
    llm_output_lower = llm_output.lower()

    critical_failures: list[CriticalFailure] = []
    warnings: list[Warning_] = []

    critical_failures += _check_numbers(det_body, llm_body)
    critical_failures += _check_unit_codes(det_body, llm_body)

    id_failures, id_warnings = _check_identifiers(det_body, llm_body)
    critical_failures += id_failures
    warnings += id_warnings

    critical_failures += _check_status_words(det_body, llm_body)

    content_failures, content_warnings = _check_invented_content(
        det_report_lower, llm_output_lower
    )
    critical_failures += content_failures
    warnings += content_warnings

    critical_failures += _check_always_banned_safety_claims(llm_output_lower)
    critical_failures += _check_disclaimer(det_report_lower, llm_output_lower)
    critical_failures += _check_water_quality_note(det_report_lower, llm_output_lower)

    warnings += _check_length_anomaly(deterministic_report, llm_output)

    critical_result = "FAIL" if critical_failures else "PASS"
    return ValidationResult(
        critical_result=critical_result,
        critical_failures=critical_failures,
        warnings=warnings,
    )
