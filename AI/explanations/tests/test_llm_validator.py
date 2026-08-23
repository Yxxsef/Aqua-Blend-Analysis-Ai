"""
test_llm_validator.py

AquaBlend | Analysis & AI | Sprint 2 | Task 25
Tests for llm_validator.py.

Fixture families, per the task card's checklist ("Include correct,
incorrect, malformed, and missing-optional-field fixtures. Add non-optimal
fixtures only when official examples are provided."):

1. CORRECT   - a faithful, differently-worded rewrite of REFERENCE_REPORT
               (Task 23's own genuine Sample 1 output, verbatim, from
               sample_explanations_sprint2.txt). Must PASS with zero
               warnings.
2. INCORRECT - one fixture per critical rule in llm_validator.py, each
               built as REFERENCE_REWRITE with exactly one change, so each
               test isolates one failure category.
3. MALFORMED - empty and whitespace-only rewrite text.
4. MISSING-OPTIONAL-FIELD - a deterministic report that legitimately omits
               Report_Structure.md's optional sections (Alternatives &
               Sensitivity, Data Flags), paired with a correct rewrite of
               it, confirming the validator does not demand content that
               was never there to begin with.
5. WARNING-ONLY - fixtures that should produce a Warning_ without failing
               critical_result.

A sixth family, general status-handling robustness, is deliberately NOT
labelled "non-optimal fixtures" in the checklist sense: it exercises the
validator's logic against a short, real, already-published non-optimal
report (Task 23's genuine Sample 2 INFEASIBLE output), not a hand-built
LLM-output example. Per the task card, dedicated non-optimal LLM-rewrite
fixtures are deferred until official examples exist - see
Test_Pack_README.md section 4.
"""

import sys
from pathlib import Path

import pytest

EXPLANATIONS_DIR = Path(__file__).resolve().parents[1]
if str(EXPLANATIONS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPLANATIONS_DIR))

from llm_validator import ValidatorInputError, validate_llm_output


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

# Verbatim from AI/explanations/sample_explanations_sprint2.txt, Sample 1 -
# Task 23's own genuine output for an OPTIMAL scenario, not typed by hand.
REFERENCE_REPORT = """## Scenario & Solver Status

Scenario: scenario_2026_07_17_001. Solver status: OPTIMAL. Solved at: 2026-07-17T10:32:00Z.

## Result Availability

The solver produced a confirmed optimal solution under the current model and input assumptions.

## Demand-Zone Results

Zone 1: required demand 500 ML/day, supplied volume 500 ML/day.

## Selected Sources & Blend Ratios

Yarra River, Kew supplied 290 ML/day, 58.0% of the blend. Cost per ML: $235 AUD (estimated). Draw cost: $68,150.0 AUD.

Silvan Reservoir supplied 210 ML/day, 42.0% of the blend. Cost per ML: $400 AUD (estimated). Draw cost: $84,000.0 AUD.

## Unused Sources

Groundwater Bore 1 was not selected.

## Active Plants & Transfer Results

Treatment Facility 1 processed 500 ML/day. Treatment cost per ML: $64 AUD. Total treatment cost: $32,000.0 AUD.

Transfer results:

Silvan Reservoir to Treatment Facility 1: 210 ML/day (active).

Yarra River, Kew to Treatment Facility 1: 290 ML/day (active).

Groundwater Bore 1 to Treatment Facility 1: 0 ML/day (inactive).

Treatment Facility 1 to Zone 1: 500 ML/day (active).

## Cost Summary

Total cost: $184,150.0 AUD (cost for one representative day).

Cost breakdown: Source activation cost: $0.0 AUD. Plant activation cost: $0.0 AUD. Source draw cost: $152,150.0 AUD. Plant treatment cost: $32,000.0 AUD.

## Plant-Inflow Water Quality

These quality results apply to: blend_at_plant_inflow.

All tested plant-inflow blend quality parameters passed at facility_1. alkalinity was closest to its limit, with a safety margin of 22.6%.

The widest margin at facility_1 was on turbidity at 34.0%.

These quality results describe the blend arriving at plant inflow. They were checked against the modelled plant-inflow constraints and are not final post-treatment drinking-water results.

## Binding Constraints

The solution was limited by the water demand for zone_1: the full 500 ML needed by zone_1 had to be delivered, leaving no room to supply any less.

The solution was limited by the available capacity of Yarra River, Kew: Yarra River, Kew was drawn up to the most its capacity allows (290 ML, estimated), so any additional water had to come from other sources.

## Data Flags & Estimated Values

The following sources have one or more estimated fields, and should be treated as provisional:

- silvan_reservoir: storage_capacity, reference_flow, max_available, cost, alkalinity
- yarra_kew: storage_capacity, reference_flow, max_available, cost, alkalinity
- groundwater_bore_1: storage_capacity, reference_flow, max_available, cost, alkalinity

Additional notes on data provenance:

- source_activation_cost is structurally 0.00: the formulation charges F_s per activated source, but the loader has no input path for it, so the term evaluates to zero rather than being omitted.
- plant_activation_cost is 0.00 because the toy case holds the single plant active and its fixed cost is set to 0 in the input contract.
- Plant costs, plant capacity, link capacities and quality limits are defined in the scenario file and carry no provenance mechanism, unlike source fields which come from the database view.
- Quality limits are raw-blend limits applied at plant inflow, not post-treatment regulatory limits.

## Alternatives & Sensitivity

Alternative feasible solutions:

Reduce Yarra Kew share to 45 percent and introduce Groundwater Bore 1 at 13 percent. Total cost: 189400.0. Cost difference from optimal: 5250.0. Slightly higher cost, but reduces dependence on a single river source and adds redundancy if Yarra Kew availability drops.

This result is sensitive to cost_per_ml for groundwater_bore_1 (flagged estimated in the source view): If actual groundwater cost is 20 percent lower than estimated, groundwater_bore_1 would likely enter the optimal blend instead of remaining unused.

This result is sensitive to max_available_ml_per_day for yarra_kew (flagged estimated in the source view): This constraint is currently binding; if real availability is lower than assumed, the model may become infeasible at this demand level.

## Prototype Disclaimer

AquaBlend is a public-data decision-support proof-of-concept. This report does not replace qualified operators, engineers, regulators, or health authorities."""

# Verbatim from sample_explanations_sprint2.txt, Sample 2 - Task 23's own
# genuine output for an INFEASIBLE scenario. Used only for the general
# status-handling robustness tests, not as an "official non-optimal
# fixture" - see the module docstring above.
REFERENCE_REPORT_INFEASIBLE = """## Scenario & Solver Status

Scenario: scenario_2026_07_17_001. Solver status: INFEASIBLE. Solved at: 2026-07-17T10:32:00Z.

## Result Availability

Solver status is INFEASIBLE. This result is not confirmed as usable for a final recommendation.

## Prototype Disclaimer

AquaBlend is a public-data decision-support proof-of-concept. This report does not replace qualified operators, engineers, regulators, or health authorities."""

# A faithful rewrite of REFERENCE_REPORT. Every number, unit/currency code,
# Title-Case and snake_case identifier, and status word in REFERENCE_REPORT
# appears at least once here; wording, sentence order, and section
# structure are changed freely, matching what prompts.py's rewrite prompt
# actually permits ("improve headings and sentence flow"). Verified against
# validate_llm_output() directly (see the module-level test below) rather
# than assumed correct by construction.
CORRECT_REWRITE = """Scenario scenario_2026_07_17_001 was solved with status OPTIMAL, completing at 2026-07-17T10:32:00Z. The optimiser reached a confirmed optimal solution given the current model and its input assumptions.

For Zone 1, the required demand of 500 ML/day was fully met with a supplied volume of 500 ML/day.

Two sources were drawn on to build the blend. Yarra River, Kew contributed 290 ML/day, making up 58.0% of the blend, at an estimated cost of $235 AUD per ML, for a draw cost of $68,150.0 AUD. Silvan Reservoir supplied 210 ML/day, or 42.0% of the blend, at an estimated $400 AUD per ML, for a draw cost of $84,000.0 AUD.

Groundwater Bore 1 was not selected for this scenario.

Treatment Facility 1 processed the full 500 ML/day, at a treatment cost of $64 AUD per ML, for a total treatment cost of $32,000.0 AUD. Flows into the facility were 210 ML/day from Silvan Reservoir (active) and 290 ML/day from Yarra River, Kew (active); the link from Groundwater Bore 1 carried 0 ML/day and was inactive. Treatment Facility 1 in turn supplied Zone 1 with 500 ML/day (active).

The total cost for this scenario was $184,150.0 AUD, covering one representative day. Broken down: source activation cost $0.0 AUD, plant activation cost $0.0 AUD, source draw cost $152,150.0 AUD, and plant treatment cost $32,000.0 AUD.

These water-quality results apply to blend_at_plant_inflow, meaning the blend as it arrives at plant inflow, and are not final post-treatment drinking-water results. Every tested parameter passed at facility_1. Alkalinity sat closest to its limit, with a 22.6% safety margin, while turbidity had the widest margin at facility_1, at 34.0%.

Two constraints limited the outcome. The full 500 ML demand at zone_1 had to be delivered, leaving no room to supply less. Yarra River, Kew was drawn to the maximum its estimated capacity allows, 290 ML, so any further volume had to come from elsewhere.

Several sources carry estimated rather than measured data and should be treated as provisional: silvan_reservoir, yarra_kew, and groundwater_bore_1, each across storage_capacity, reference_flow, max_available, cost, and alkalinity. A few additional notes on provenance: source_activation_cost is structurally 0.00 because the loader has no input path for the per-activated-source charge the formulation defines; plant_activation_cost is 0.00 since the toy case's single plant stays active with a fixed cost of 0 in the input contract; plant costs, plant capacity, link capacities and quality limits carry no provenance mechanism at all, unlike source fields; and quality limits are raw-blend limits at plant inflow, not post-treatment regulatory limits.

An alternative feasible solution exists: reducing Yarra Kew's share to 45 percent and introducing Groundwater Bore 1 at 13 percent, for a total cost of 189400.0, a difference of 5250.0 from the optimum. This is slightly more expensive but reduces reliance on a single river source and adds redundancy if Yarra Kew's availability drops. The result is also sensitive to two estimated assumptions: cost_per_ml for groundwater_bore_1, where a 20 percent lower real cost would likely bring groundwater_bore_1 into the optimal blend, and max_available_ml_per_day for yarra_kew, a currently binding constraint that could make the model infeasible if real availability is lower than assumed.

AquaBlend is a public-data decision-support proof-of-concept. This report does not replace qualified operators, engineers, regulators, or health authorities."""


# ---------------------------------------------------------------------------
# 1. Correct fixture
# ---------------------------------------------------------------------------

class TestCorrectFixture:

    def test_faithful_rewrite_passes_with_no_warnings(self):
        result = validate_llm_output(REFERENCE_REPORT, CORRECT_REWRITE)
        assert result.critical_result == "PASS"
        assert result.critical_failures == []
        assert result.warnings == []

    def test_identical_text_passes_with_no_warnings(self):
        """The trivial case: returning the deterministic report completely
        unchanged (e.g. the runner's own TEMPLATE_FALLBACK text) must
        always pass, since nothing was altered - and must not produce any
        warnings either, since nothing was actually added.

        Regression test: an earlier version of this check stripped '##
        Heading' lines from the deterministic side only, not the rewrite
        side. Report_Structure.md's own headings are frequently Title-Case
        two-word phrases ("Selected Sources", "Active Plants"), so
        comparing a heading-stripped source against an unstripped rewrite
        made every heading look like a brand new identifier - even when
        the rewrite was character-for-character identical to the source.
        Found by testing this exact identical-input case, not assumed
        safe."""
        result = validate_llm_output(REFERENCE_REPORT, REFERENCE_REPORT)
        assert result.critical_result == "PASS"
        assert result.critical_failures == []
        assert result.warnings == []


# ---------------------------------------------------------------------------
# 2. Incorrect fixtures - one per critical rule
# ---------------------------------------------------------------------------

class TestNumberFailures:

    def test_changed_number_fails(self):
        rewrite = CORRECT_REWRITE.replace("58.0% of the blend", "60.0% of the blend")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        rules = {f.rule for f in result.critical_failures}
        assert "NUMBER_MISSING_OR_CHANGED" in rules
        assert "NUMBER_INVENTED" in rules

    def test_invented_number_fails(self):
        rewrite = CORRECT_REWRITE + " This is a 15 percent improvement over the previous quarter."
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "NUMBER_INVENTED" for f in result.critical_failures)
        # Nothing existing was removed, so this must be the only category.
        assert all(f.rule == "NUMBER_INVENTED" for f in result.critical_failures)

    def test_missing_number_fails(self):
        rewrite = CORRECT_REWRITE.replace("22.6% safety margin", "a safety margin")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(
            f.rule == "NUMBER_MISSING_OR_CHANGED" for f in result.critical_failures
        )

    def test_legitimate_compression_does_not_fail(self):
        """A value the source states more than once may be stated fewer
        times in the rewrite without failing, as long as it still appears
        at least once - this is exactly what CORRECT_REWRITE already does
        for 290, 210, and the repeated identifiers, so this test just makes
        the design choice explicit and named. See Validation_Rules.md
        section 3."""
        result = validate_llm_output(REFERENCE_REPORT, CORRECT_REWRITE)
        assert result.critical_result == "PASS"

    def test_dropped_percent_sign_fails(self):
        """Regression test for a review finding: '58.0%' and '58.0' used to
        normalise to the identical value, so dropping the percent sign
        while keeping the same digits passed validation - a real fact
        change (a proportion becoming an ambiguous bare number) went
        undetected. Percent and plain values are now tracked as distinct
        facts; see _normalise_number's docstring."""
        rewrite = CORRECT_REWRITE.replace("58.0% of the blend", "58.0 of the blend")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        rules = {f.rule for f in result.critical_failures}
        assert "NUMBER_MISSING_OR_CHANGED" in rules
        assert "NUMBER_INVENTED" in rules

    def test_added_percent_sign_also_fails(self):
        """The same check in the other direction: a plain number in the
        source must not silently gain a percent sign in the rewrite."""
        rewrite = CORRECT_REWRITE.replace("$235 AUD per ML", "$235% AUD per ML")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        rules = {f.rule for f in result.critical_failures}
        assert "NUMBER_MISSING_OR_CHANGED" in rules
        assert "NUMBER_INVENTED" in rules


class TestUnitCodeFailures:

    def test_missing_currency_code_fails(self):
        rewrite = CORRECT_REWRITE.replace(" AUD", "")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        failure = next(
            f for f in result.critical_failures if f.rule == "UNIT_OR_CODE_MISSING"
        )
        assert "AUD" in failure.detail


class TestIdentifierFailures:

    def test_missing_title_case_identifier_fails(self):
        rewrite = CORRECT_REWRITE.replace("Groundwater Bore 1", "the third source")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        failure = next(
            f for f in result.critical_failures if f.rule == "IDENTIFIER_MISSING"
        )
        assert "Groundwater Bore 1" in failure.detail

    def test_missing_snake_case_identifier_fails(self):
        rewrite = CORRECT_REWRITE.replace("storage_capacity, ", "")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        failure = next(
            f for f in result.critical_failures if f.rule == "IDENTIFIER_MISSING"
        )
        assert "storage_capacity" in failure.detail

    def test_new_identifier_is_a_warning_not_a_failure(self):
        rewrite = CORRECT_REWRITE + " This is broadly similar to the nearby Coliban Channel source."
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "PASS"
        assert any(w.rule == "NEW_IDENTIFIER" for w in result.warnings)

    def test_leading_word_stopword_does_not_false_positive(self):
        """Regression test: 'Reduce Yarra Kew share to 45 percent...' in
        REFERENCE_REPORT's own text is a sentence-initial common verb
        directly followed by a genuine proper noun. Without the leading-word
        stopword filter, this was flagged as a phantom identifier
        ('Reduce Yarra Kew') that a faithful rewrite could never
        reasonably reproduce. See Validation_Rules.md section 3."""
        result = validate_llm_output(REFERENCE_REPORT, CORRECT_REWRITE)
        assert not any(
            f.rule == "IDENTIFIER_MISSING" and "Reduce" in f.detail
            for f in result.critical_failures
        )


class TestStatusFailures:

    def test_status_flip_fails_both_ways(self):
        rewrite = CORRECT_REWRITE.replace("status OPTIMAL", "status INFEASIBLE")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        rules = {f.rule for f in result.critical_failures}
        assert "STATUS_MISSING" in rules
        assert "STATUS_INVENTED" in rules

    def test_dropped_status_word_fails(self):
        rewrite = CORRECT_REWRITE.replace("status OPTIMAL", "status")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "STATUS_MISSING" for f in result.critical_failures)


class TestInventedContentFailures:

    def test_invented_reason_fails(self):
        """Uses 'cheapest available' rather than 'because' - REFERENCE_REPORT's
        own Data Flags notes genuinely contain the word 'because' already
        (explaining why source_activation_cost is 0.00), so 'because' would
        not be a NEW phrase and would not trigger the differential check.
        'cheapest available' does not appear anywhere in the reference
        report, matching Task 23's own removal of cost-ranking language."""
        rewrite = CORRECT_REWRITE.replace(
            "Yarra River, Kew contributed 290 ML/day",
            "Yarra River, Kew contributed 290 ML/day as the cheapest available "
            "option for this scenario",
        )
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "INVENTED_CONTENT" for f in result.critical_failures)

    def test_invented_recommendation_fails(self):
        rewrite = CORRECT_REWRITE + " We recommend proceeding with this blend."
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "INVENTED_CONTENT" for f in result.critical_failures)

    def test_weak_phrase_is_a_warning_not_a_failure(self):
        rewrite = CORRECT_REWRITE + " This shows the blend comfortably meets requirements."
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "PASS"
        assert any(
            w.rule == "WEAK_INVENTED_CONTENT_PHRASE" for w in result.warnings
        )

    def test_phrase_already_in_source_is_not_flagged(self):
        """The differential check only flags phrases that are NEW in the
        rewrite. REFERENCE_REPORT's own text contains 'because' nowhere,
        so this test instead confirms a phrase present in BOTH texts is not
        flagged - using a word that genuinely appears in both."""
        rewrite = CORRECT_REWRITE.replace(
            "at an estimated cost of $235 AUD per ML",
            "at an estimated cost of $235 AUD per ML, noting this cost is estimated",
        )
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        # "estimated" is not a banned phrase; this just confirms ordinary
        # shared vocabulary never trips the invented-content check.
        assert not any(f.rule == "INVENTED_CONTENT" for f in result.critical_failures)


class TestSafetyClaimFailures:

    def test_safe_to_drink_always_fails(self):
        rewrite = CORRECT_REWRITE + " The final blend is safe to drink."
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "UNSAFE_SAFETY_CLAIM" for f in result.critical_failures)

    def test_compliant_always_fails(self):
        rewrite = CORRECT_REWRITE + " The result is fully compliant."
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "UNSAFE_SAFETY_CLAIM" for f in result.critical_failures)

    def test_treated_water_always_fails(self):
        rewrite = CORRECT_REWRITE.replace(
            "are not final post-treatment drinking-water results",
            "are not final treated water",
        )
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "UNSAFE_SAFETY_CLAIM" for f in result.critical_failures)


class TestDisclaimerAndWaterQualityNoteFailures:

    def test_missing_disclaimer_fails(self):
        rewrite = CORRECT_REWRITE.rsplit("\n\n", 1)[0]  # drop the final paragraph
        assert "proof-of-concept" not in rewrite.lower()
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "DISCLAIMER_MISSING" for f in result.critical_failures)

    def test_missing_water_quality_note_fails(self):
        """Every 'plant inflow' marker must be removed, not just the one in
        the quality section itself - CORRECT_REWRITE also mentions 'plant
        inflow' once more in the Data Flags notes paragraph (following the
        reference report's own wording), and the check looks for the
        marker anywhere in the rewrite, not specifically within the
        quality section. See Validation_Rules.md section 7 for why this is
        a deliberate, documented simplification rather than a bug."""
        rewrite = CORRECT_REWRITE.replace("plant inflow", "the treatment stage")
        assert "plant inflow" not in rewrite.lower()
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(
            f.rule == "WATER_QUALITY_NOTE_MISSING" for f in result.critical_failures
        )

    def test_disclaimer_check_is_skipped_when_source_has_none(self):
        """If the deterministic report itself never had a disclaimer,
        the rewrite cannot be faulted for lacking one."""
        det = "Scenario test_1. Solver status: ERROR."
        llm = "Scenario test_1 finished with status ERROR."
        result = validate_llm_output(det, llm)
        assert not any(f.rule == "DISCLAIMER_MISSING" for f in result.critical_failures)


# ---------------------------------------------------------------------------
# 3. Malformed fixtures
# ---------------------------------------------------------------------------

class TestMalformedFixtures:

    def test_empty_string_fails(self):
        result = validate_llm_output(REFERENCE_REPORT, "")
        assert result.critical_result == "FAIL"
        assert len(result.critical_failures) == 1
        assert result.critical_failures[0].rule == "EMPTY_OUTPUT"

    def test_whitespace_only_fails(self):
        result = validate_llm_output(REFERENCE_REPORT, "   \n\t  ")
        assert result.critical_result == "FAIL"
        assert result.critical_failures[0].rule == "EMPTY_OUTPUT"

    def test_empty_output_short_circuits_other_checks(self):
        """An empty rewrite must not also report every source/number as
        'missing' - that would bury the one failure that actually matters
        under noise."""
        result = validate_llm_output(REFERENCE_REPORT, "")
        assert len(result.critical_failures) == 1

    def test_non_string_deterministic_report_raises(self):
        with pytest.raises(ValidatorInputError):
            validate_llm_output(12345, CORRECT_REWRITE)

    def test_non_string_llm_output_raises(self):
        with pytest.raises(ValidatorInputError):
            validate_llm_output(REFERENCE_REPORT, None)


# ---------------------------------------------------------------------------
# 4. Missing-optional-field fixture
# ---------------------------------------------------------------------------

class TestMissingOptionalFieldFixture:
    """A deterministic report that legitimately omits Report_Structure.md's
    optional sections (Data Flags, Alternatives & Sensitivity - both
    correctly absent per json_explainer.py when there is nothing to
    disclose), paired with a faithful rewrite of the shorter report. The
    validator must not demand content that was never in the source."""

    DET_REPORT_SHORT = """## Scenario & Solver Status

Scenario: scenario_2026_08_01_002. Solver status: OPTIMAL. Solved at: 2026-08-01T09:00:00Z.

## Result Availability

The solver produced a confirmed optimal solution under the current model and input assumptions.

## Selected Sources & Blend Ratios

Silvan Reservoir supplied 500 ML/day, 100.0% of the blend. Cost per ML: $400 AUD.

## Prototype Disclaimer

AquaBlend is a public-data decision-support proof-of-concept. This report does not replace qualified operators, engineers, regulators, or health authorities."""

    REWRITE_SHORT = """Scenario scenario_2026_08_01_002 reached a confirmed optimal solution with status OPTIMAL, solved at 2026-08-01T09:00:00Z.

Silvan Reservoir supplied the entire blend: 500 ML/day, or 100.0% of the total, at $400 AUD per ML.

AquaBlend is a public-data decision-support proof-of-concept. This report does not replace qualified operators, engineers, regulators, or health authorities."""

    def test_short_report_with_faithful_rewrite_passes(self):
        result = validate_llm_output(self.DET_REPORT_SHORT, self.REWRITE_SHORT)
        assert result.critical_result == "PASS"
        assert result.critical_failures == []

    def test_absent_optional_sections_are_not_demanded(self):
        """Neither Data Flags nor Alternatives & Sensitivity content exists
        in DET_REPORT_SHORT, so their absence from REWRITE_SHORT must not
        be treated as a fact being dropped."""
        result = validate_llm_output(self.DET_REPORT_SHORT, self.REWRITE_SHORT)
        assert not any(
            f.rule in ("IDENTIFIER_MISSING", "NUMBER_MISSING_OR_CHANGED")
            for f in result.critical_failures
        )


# ---------------------------------------------------------------------------
# 5. Warning-only fixtures
# ---------------------------------------------------------------------------

class TestWarningsDoNotAffectCriticalResult:

    def test_length_anomaly_is_a_warning_only(self):
        det = (
            "This is a short deterministic report with plenty of words to "
            "set a clear baseline length for the purpose of this particular "
            "test case, which checks only for a length anomaly warning."
        )
        llm = "Short version."
        result = validate_llm_output(det, llm)
        assert result.critical_result == "PASS"
        assert any(w.rule == "LENGTH_ANOMALY" for w in result.warnings)

    def test_no_length_warning_when_rewrite_is_a_reasonable_length(self):
        result = validate_llm_output(REFERENCE_REPORT, CORRECT_REWRITE)
        assert not any(w.rule == "LENGTH_ANOMALY" for w in result.warnings)

    def test_multiple_warnings_can_coexist_with_a_pass(self):
        rewrite = (
            CORRECT_REWRITE
            + " This shows the blend comfortably meets requirements, "
            "similar to the nearby Coliban Channel source."
        )
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "PASS"
        assert len(result.warnings) >= 2


# ---------------------------------------------------------------------------
# 6. Multiple simultaneous failures
# ---------------------------------------------------------------------------

class TestMultipleFailuresAggregate:

    def test_several_independent_failures_are_all_reported(self):
        """The validator must not stop at the first failure it finds - a
        reviewer needs the complete list in one pass."""
        rewrite = CORRECT_REWRITE.replace("status OPTIMAL", "status INFEASIBLE")
        rewrite = rewrite.replace("Groundwater Bore 1", "the third source")
        rewrite += " The water is safe to drink."
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        rules = {f.rule for f in result.critical_failures}
        assert "STATUS_MISSING" in rules
        assert "STATUS_INVENTED" in rules
        assert "IDENTIFIER_MISSING" in rules
        assert "UNSAFE_SAFETY_CLAIM" in rules
        assert len(result.critical_failures) >= 4


# ---------------------------------------------------------------------------
# 7. Result shape
# ---------------------------------------------------------------------------

class TestResultShape:

    def test_to_dict_round_trips_pass(self):
        result = validate_llm_output(REFERENCE_REPORT, CORRECT_REWRITE)
        d = result.to_dict()
        assert d["critical_result"] == "PASS"
        assert d["critical_failures"] == []
        assert d["warnings"] == []

    def test_to_dict_round_trips_fail(self):
        result = validate_llm_output(REFERENCE_REPORT, "")
        d = result.to_dict()
        assert d["critical_result"] == "FAIL"
        assert d["critical_failures"][0]["rule"] == "EMPTY_OUTPUT"
        assert "detail" in d["critical_failures"][0]


# ---------------------------------------------------------------------------
# 8. General status-handling robustness (not an "official" non-optimal
#    fixture - see the module docstring)
# ---------------------------------------------------------------------------

class TestNonOptimalReportRobustness:

    CORRECT_REWRITE_INFEASIBLE = (
        "Scenario scenario_2026_07_17_001 finished with solver status "
        "INFEASIBLE, recorded at 2026-07-17T10:32:00Z. This result is not "
        "confirmed as usable for a final recommendation.\n\n"
        "AquaBlend is a public-data decision-support proof-of-concept. "
        "This report does not replace qualified operators, engineers, "
        "regulators, or health authorities."
    )

    def test_faithful_rewrite_of_a_short_status_only_report_passes(self):
        result = validate_llm_output(
            REFERENCE_REPORT_INFEASIBLE, self.CORRECT_REWRITE_INFEASIBLE
        )
        assert result.critical_result == "PASS"

    def test_dropping_the_status_from_a_short_report_still_fails(self):
        rewrite = self.CORRECT_REWRITE_INFEASIBLE.replace("INFEASIBLE", "unavailable")
        result = validate_llm_output(REFERENCE_REPORT_INFEASIBLE, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "STATUS_MISSING" for f in result.critical_failures)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
