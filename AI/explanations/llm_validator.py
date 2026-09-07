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

# Words that negate whatever follows them in the same sentence/clause.
# Used by _has_unnegated_occurrence so a phrase like "safe to drink"
# appearing inside "not safe to drink" - or, found in real testing (Task
# 62), inside "No claims are made about ... regulatory compliance" - is
# recognised as a denial, not an assertion. See Validation_Rules.md
# section 7 for the full reasoning, including why this is a bounded
# heuristic rather than real negation parsing.
_NEGATION_WORDS = {"not", "no", "never", "none", "without", "cannot", "nor"}

# How many words back (in the same sentence/clause) to look for a
# negation word before treating a phrase as genuinely asserted. Found by
# measuring the real sentence that motivated this fix: "No claims are
# made about water safety, regulatory compliance, or operational
# performance" puts 7 words between "No" and "regulatory compliance" -
# 12 gives real margin above that without being unbounded (see
# Validation_Rules.md section 7 for why unbounded/whole-sentence
# scanning was rejected).
_NEGATION_WINDOW_WORDS = 12

# How many characters apart a volume and its percentage can be and still
# count as a written-together pair (e.g. "290 ML/day, ... 58.0% of the
# blend"/"of the total") - see _extract_number_pairs. The genuine pairing
# is always short (9-19 characters across the real fixtures and live
# outputs checked) since a source's volume and its own percentage are
# always written in the same clause - 30 gives real margin above that
# without reaching the 50+ character distance a structurally unrelated
# pairing can reach once headings are stripped (Zone 1's own demand
# figure, also ML/day-tagged, sitting a full section away from a source's
# percentage - found from a real live run, Task 62, Run 7, and confirmed
# to also affect REFERENCE_REPORT itself once _strip_headings shortens
# the text between sections).
_PAIR_WINDOW_CHARS = 30

# Matches "ML/day" (optionally preceded by whitespace) immediately after a
# volume value - used to scope _extract_number_pairs to genuine volumes,
# not any plain number that happens to sit near a percentage.
_ML_PER_DAY_PATTERN = re.compile(r"\s*ML/day", re.IGNORECASE)

# A sentence/clause boundary the negation window must not cross - a
# negation on one side of these should never suppress a phrase on the
# other side, even if the word-count window would otherwise reach it.
_CLAUSE_BOUNDARY_PATTERN = re.compile(r"[.!?;\n]")

# A contrastive conjunction also ends a negation's scope, even mid-sentence
# with no terminal punctuation - found from a real review comment (PR #46):
# "The blend is not safe to drink, but it is compliant." "not" genuinely
# negates "safe to drink", but "compliant" sits in a new clause introduced
# by "but", and is not negated by anything - it's a real, separate, unsafe
# assertion that must still fail. Without this boundary, the word-count
# window alone (7 words from "not" to "compliant") would incorrectly let
# "not" suppress a claim it has no grammatical relationship to.
_CONTRASTIVE_BOUNDARY_PATTERN = re.compile(
    r",?\s*\b(?:but|however|yet|although|though|while|except|nonetheless|nevertheless)\b",
    re.IGNORECASE,
)


def _is_negated(text_lower: str, phrase_start: int) -> bool:
    """True if a negation word governs the phrase starting at
    `phrase_start` in `text_lower` - i.e. one of _NEGATION_WORDS appears
    within _NEGATION_WINDOW_WORDS words before it, without crossing a
    sentence, clause, or contrastive-conjunction boundary in between."""
    clause_matches = list(_CLAUSE_BOUNDARY_PATTERN.finditer(text_lower, 0, phrase_start))
    contrastive_matches = list(_CONTRASTIVE_BOUNDARY_PATTERN.finditer(text_lower, 0, phrase_start))
    boundary_ends = [m.end() for m in clause_matches] + [m.end() for m in contrastive_matches]
    clause_start = max(boundary_ends) if boundary_ends else 0
    preceding = text_lower[clause_start:phrase_start]
    words = re.findall(r"[a-z']+", preceding)
    window = words[-_NEGATION_WINDOW_WORDS:]
    return any(w in _NEGATION_WORDS or w.endswith("n't") for w in window)


def _has_unnegated_occurrence(text_lower: str, phrase: str) -> bool:
    """True if `phrase` appears in `text_lower` at least once without a
    negation governing it. A phrase that only ever appears negated (e.g.
    every occurrence is inside "not X" or "no ... X") is treated as
    absent for the purposes of the always-banned and invented-content
    checks - it was denied, not claimed."""
    start = 0
    while True:
        idx = text_lower.find(phrase, start)
        if idx == -1:
            return False
        if not _is_negated(text_lower, idx):
            return True
        start = idx + len(phrase)

# Numeric fact candidate: an optional leading '-' or '$', digits with
# optional thousands separators, an optional decimal part, an optional
# trailing '%'. A candidate is discarded by _extract_numbers below if it
# turns out to be embedded inside a longer identifier token (e.g. the "01"
# inside "scenario_2026_07_17_001", or "1" inside "facility_1") - see
# _is_embedded_in_identifier for why a single-character lookaround on the
# regex itself is not enough to catch every such case.
_NUMBER_PATTERN = re.compile(r"-?\$?\d[\d,]*(?:\.\d+)?%?")

# "45 percent" and "45%" are the same fact, just spelled differently - a
# faithful rewrite is entirely free to make this substitution, and did in
# real testing (see Validation_Rules.md section 3). Applied to both texts
# before number extraction, so "percent"/"pct" always normalises to the
# same '%' form regardless of which side wrote it which way.
_PERCENT_WORD_PATTERN = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*(?:percent|pct)\b", re.IGNORECASE
)


def _normalise_percent_words(text: str) -> str:
    return _PERCENT_WORD_PATTERN.sub(r"\1%", text)

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


def _is_numbered_list_marker(text: str, start: int, end: int) -> bool:
    """True if the number match at text[start:end] is a numbered-list
    marker ("1.", "2.") rather than a genuine numeric fact - found from a
    real live run (Task 62): the model reformatted the Binding Constraints
    section from a bullet list into a numbered list, and the plain number
    regex read "2." as the standalone fact 2.0, since nothing after the
    period was itself a digit. "1." happened to coincidentally match a
    number that already existed elsewhere in the source, so it slipped
    through unnoticed; "2." didn't, and was flagged as an invented number
    that was never actually invented - it's list-item numbering, not
    content.

    Scoped narrowly and structurally, not by value: a match only counts as
    a list marker if it sits at the very start of a line (only whitespace
    before it back to the last newline), is immediately followed by a
    period and then whitespace, and nothing follows that period as more
    digits (a genuine decimal like "2.50" is a completely different regex
    match already, this only ever applies to a bare integer). This
    shouldn't ever misfire on a real fact, since nothing in this report's
    actual generated content places a standalone number at the very start
    of a line followed immediately by a period - only reformatting choices
    like this one do."""
    line_start = text.rfind("\n", 0, start) + 1
    if text[line_start:start].strip():
        return False  # something other than whitespace precedes it on this line
    after = text[end:end + 2]
    return after.startswith(".") and (len(after) < 2 or not after[1].isdigit())


def _extract_numbers(text: str) -> set[tuple[float, bool]]:
    text = _normalise_percent_words(text)
    values = set()
    for m in _NUMBER_PATTERN.finditer(text):
        if _is_embedded_in_identifier(text, m.start(), m.end()):
            continue
        if _is_numbered_list_marker(text, m.start(), m.end()):
            continue
        values.add(_normalise_number(m.group()))
    return values


# Field-name (not entity-reference) snake_case tokens that a rewrite may
# paraphrase into plain language instead of preserving verbatim - a
# deliberate, documented team-lead decision (Task 62), not a rule this
# validator relaxes silently or by default.
#
# Scoped narrowly to the two specific tokens actually observed causing
# this in two independent live-model runs: `cost_per_ml` and
# `max_available_ml_per_day`, both from the Sensitivity section's prose
# ("cost_per_ml for groundwater_bore_1"). Every OTHER snake_case field
# name in the same report - `storage_capacity`, `reference_flow`,
# `alkalinity`, `cost`, `max_available` in the Data Flags section - is
# NOT exempted, and correctly survived verbatim in both real runs anyway,
# since that section is a literal bullet list, which naturally resists
# paraphrasing the way free-flowing sentence prose does not. Widening this
# exemption to the whole field-name category was considered and rejected:
# it would weaken a check that is currently working correctly for those
# other fields, to fix a problem that has only actually been observed for
# these two.
#
# The reasoning: `cost_per_ml` and `max_available_ml_per_day` are
# attribute LABELS, not references to a specific real-world entity (unlike
# `silvan_reservoir`, `zone_1`, `facility_1`, which identify a particular
# source, zone, or plant and must still survive under this or a covering
# name - see _identifier_covered_by). The NUMERIC VALUE attached to each
# sensitivity item is still independently checked by the number-presence
# check regardless of what the surrounding field label is paraphrased
# into, so exempting the label's exact spelling here does not weaken fact
# coverage - it only stops penalising a rewrite for doing exactly what
# prompts.py permits ("simplify wording... organise the same facts more
# clearly") to a category of token an operator was never going to need to
# see verbatim in the first place.
EXEMPT_FIELD_NAME_TOKENS = {"cost_per_ml", "max_available_ml_per_day"}


def _extract_identifiers(text: str) -> set[str]:
    title_case = {
        m for m in _TITLE_CASE_IDENTIFIER_PATTERN.findall(text)
        if m.split(" ")[0].split(",")[0] not in _LEADING_WORD_STOPWORDS
    }
    snake_case = set(_SNAKE_CASE_IDENTIFIER_PATTERN.findall(text)) - EXEMPT_FIELD_NAME_TOKENS
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


def _identifier_word_set(identifier: str) -> frozenset[str]:
    """'zone_1' -> {'zone', '1'}; 'Treatment Facility 1' -> {'treatment',
    'facility', '1'}. Used to recognise that two differently-formatted
    identifiers refer to the same entity."""
    return frozenset(re.findall(r"[a-z0-9]+", identifier.lower()))


def _identifier_covered_by(det_id: str, llm_id: str) -> bool:
    """True if `llm_id` contains at least every word `det_id` has - so a
    rewrite is free to use a fuller or differently-formatted name for the
    same entity, but can never satisfy the check by dropping a word.

    Found by testing against a real model rewrite, not designed in
    advance: the source used 'zone_1', 'facility_1', and the shorthand
    'Yarra Kew' in different places; a genuinely faithful rewrite used
    'Zone 1', 'Treatment Facility 1', and 'Yarra River, Kew' throughout -
    same entities, fuller or differently-cased names, correctly not a
    fact change. Directionality matters: det_id's words must be a SUBSET
    of llm_id's, never the reverse - a rewrite that dropped a word (e.g.
    just 'Yarra' alone) must still fail, since that is real information
    loss, not reformatting. See Validation_Rules.md section 3."""
    det_words = _identifier_word_set(det_id)
    if not det_words:
        return False
    return det_words <= _identifier_word_set(llm_id)


def _phrase_covers_snake_case_identifier(text: str, identifier: str) -> bool:
    """True if a snake_case identifier's underscore-separated words appear
    as a contiguous, case-insensitive phrase somewhere in `text` - a
    fallback for a real gap found on a genuine live run (Task 62, Run 7):
    the model rendered source_activation_cost and plant_activation_cost
    as ordinary sentence-case prose ("Source activation cost is $0.00..."),
    which neither the Title-Case pattern (only the first word is
    capitalized, not every word) nor the snake_case pattern (no
    underscores) recognises as an identifier candidate at all - so the
    fact was correctly, faithfully conveyed, but invisible to the normal
    extraction-and-match logic entirely.

    Deliberately narrow and one-directional: this only ever helps decide
    whether a det-side snake_case identifier counts as covered - it never
    adds anything to the set of identifiers extracted from llm_output, so
    it cannot introduce a new false NEW_IDENTIFIER warning the way
    broadening extraction itself might have."""
    if "_" not in identifier:
        return False
    phrase = " ".join(identifier.split("_"))
    return re.search(r"\b" + re.escape(phrase) + r"\b", text, re.IGNORECASE) is not None


def _check_identifiers(
    det_body: str, llm_output: str
) -> tuple[list[CriticalFailure], list[Warning_]]:
    det_ids = _extract_identifiers(det_body)
    llm_ids = _extract_identifiers(llm_output)

    missing = []
    covered_llm_ids = set()
    for det_id in sorted(det_ids):
        if det_id in llm_ids:
            covered_llm_ids.add(det_id)
            continue
        match = next(
            (llm_id for llm_id in llm_ids if _identifier_covered_by(det_id, llm_id)),
            None,
        )
        if match is not None:
            covered_llm_ids.add(match)
        elif _phrase_covers_snake_case_identifier(llm_output, det_id):
            continue  # covered via a sentence-case phrase, not an extracted identifier
        else:
            missing.append(det_id)

    failures = [
        CriticalFailure(
            "IDENTIFIER_MISSING",
            f"'{name}' appears in the deterministic report but not in the "
            "rewrite.",
        )
        for name in missing
    ]

    new = sorted((llm_ids - det_ids) - covered_llm_ids)
    warnings = [
        Warning_(
            "NEW_IDENTIFIER",
            f"'{name}' appears in the rewrite but was not in the "
            "deterministic report. May be a legitimate rewording, or may be "
            "an invented name - worth a human check.",
        )
        for name in new
    ]
    return failures, warnings



def _extract_number_pairs(text: str) -> set[tuple[tuple[float, bool], tuple[float, bool]]]:
    """Returns the set of (volume_value, percent_value) pairs where a
    volume specifically tagged "ML/day" and a percentage appear within a
    short character window of each other in `text` - the
    "290 ML/day, ... 58.0% of the blend" (or "...of the total", or any
    other faithful rewording) pattern a source's volume and blend share
    are always written in together, in some order, regardless of how the
    surrounding sentence is phrased.

    This is the third iteration of this check, after several earlier,
    broader or differently-scoped attempts each proved fragile once
    tested against real, varied phrasing rather than just the one case
    that motivated it - see _check_number_association for why plain
    identifier-proximity was rejected first. Within this pair-based
    approach specifically: pairing ANY plain number with ANY nearby
    percent was too broad (a real live run, Task 62 Run 7, showed a
    source's cost figure sitting close enough to its percentage to be
    mistaken for the pair). Scoping the plain-number side to values
    followed by "ML/day" fixed that, but a wide window was still needed
    to reach across a line break in one real case, which then caused a
    genuinely unrelated pairing elsewhere (Zone 1's own demand figure,
    also ML/day-tagged, sitting within that same wide window of a
    source's percentage once _strip_headings shortens the text between
    sections - found against REFERENCE_REPORT itself, not synthetic).
    Anchoring the percent side to specific wording ("of the blend") was
    tried next and also broken by a real, legitimate fixture phrasing it
    as "of the total" instead.

    What actually holds across every real case checked: a source's own
    volume and its own percentage are always written within about 20
    characters of each other, in the same clause, while every spurious
    candidate pairing found so far sits 50+ characters away. The window
    alone, combined with the ML/day requirement, does the real work here -
    no wording anchor needed on the percent side, since distance already
    reliably separates genuine from spurious once headings are stripped
    consistently on both sides of the comparison."""
    text = _normalise_percent_words(text)
    matches = [
        m for m in _NUMBER_PATTERN.finditer(text)
        if not _is_embedded_in_identifier(text, m.start(), m.end())
    ]
    pairs: set[tuple[tuple[float, bool], tuple[float, bool]]] = set()
    for i, m1 in enumerate(matches):
        v1 = _normalise_number(m1.group())
        if v1[1]:
            continue  # only a plain (non-percent) value can be the volume side
        if not _ML_PER_DAY_PATTERN.match(text, m1.end()):
            continue  # must specifically be a volume, not any plain number
        for m2 in matches[i + 1:i + 4]:
            if m2.start() - m1.end() > _PAIR_WINDOW_CHARS:
                break
            v2 = _normalise_number(m2.group())
            if v2[1]:
                pairs.add((v1, v2))
    return pairs


def _check_number_association(det_body: str, llm_output: str) -> list[CriticalFailure]:
    """Catches a real gap _check_numbers cannot see on its own: two values
    that are each genuinely present somewhere in the rewrite, but no
    longer paired with each other - found from a real review comment
    (PR #46, Yousef): swapping Yarra River, Kew's 58.0% with Silvan
    Reservoir's 42.0% leaves the overall set of numbers in the document
    completely unchanged, so the plain presence-based check in
    _check_numbers correctly sees nothing wrong. This check instead looks
    at which values were written together as a pair (a volume with its
    blend percentage) and confirms that same pairing survives in the
    rewrite, regardless of wording or which identifier sits nearby - see
    _extract_number_pairs for why this narrower design replaced two
    broader, identifier-proximity-based attempts that both produced false
    positives on genuinely correct text."""
    det_pairs = _extract_number_pairs(det_body)
    llm_pairs = _extract_number_pairs(llm_output)

    failures: list[CriticalFailure] = []
    for plain, percent in sorted(det_pairs - llm_pairs):
        # Only a real association failure if both values are still
        # present individually - if the source dropped one of them
        # entirely, that's already NUMBER_MISSING_OR_CHANGED's job.
        if plain in _extract_numbers(llm_output) and percent in _extract_numbers(llm_output):
            failures.append(CriticalFailure(
                "NUMBER_WRONG_ASSOCIATION",
                f"{_format_number(plain)!r} and {_format_number(percent)!r} "
                "are written together in the deterministic report, but no "
                "longer appear paired in the rewrite - one of them may have "
                "been swapped with a different source's figure.",
            ))
    return failures


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
        if (
            phrase not in det_report_lower
            and _has_unnegated_occurrence(llm_output_lower, phrase)
        ):
            failures.append(CriticalFailure(
                "INVENTED_CONTENT",
                f"The phrase '{phrase}' appears in the rewrite but not in "
                "the deterministic report. This usually signals an invented "
                "reason, recommendation, or claim.",
            ))

    warnings = []
    for phrase in WEAK_INVENTED_CONTENT_PHRASES:
        if (
            phrase not in det_report_lower
            and _has_unnegated_occurrence(llm_output_lower, phrase)
        ):
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
        if _has_unnegated_occurrence(llm_output_lower, phrase):
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


# A response that doesn't end with terminal punctuation almost always means
# generation stopped mid-sentence - typically the model hit its max_tokens
# limit before finishing. Found from a real review comment (PR #46,
# Yousef): the accepted Run 1 output was truncated at "All data and
# estimates," with nothing after, and was still being recorded as an
# accepted PASS. A cut-off response can be silently missing anything that
# would have come after the cut point, including required disclaimer
# content - that risk applies regardless of what facts happen to already
# be correct in the part that did get generated, which is exactly why this
# is a critical failure and not a length-anomaly warning.
_TERMINAL_PUNCTUATION_PATTERN = re.compile(r"[.!?]['\")]?\s*$")


def _check_output_completeness(llm_output: str) -> list[CriticalFailure]:
    stripped = llm_output.strip()
    if not stripped:
        return []  # _check_empty_output already covers this case
    if _TERMINAL_PUNCTUATION_PATTERN.search(stripped):
        return []
    return [CriticalFailure(
        "INCOMPLETE_OUTPUT",
        "The rewrite does not end with terminal punctuation, which "
        "suggests generation was cut off before finishing - most likely "
        "by hitting the model's max_tokens limit. A truncated response "
        "could be silently missing required content (such as the "
        "prototype disclaimer) that would have appeared after the cut "
        "point, and must not be accepted as a complete rewrite. Rerun "
        "with a higher max_tokens rather than accepting a partial "
        "response.",
    )]


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
    critical_failures += _check_number_association(det_body, llm_body)
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
    critical_failures += _check_output_completeness(llm_output)

    warnings += _check_length_anomaly(deterministic_report, llm_output)

    critical_result = "FAIL" if critical_failures else "PASS"
    return ValidationResult(
        critical_result=critical_result,
        critical_failures=critical_failures,
        warnings=warnings,
    )
