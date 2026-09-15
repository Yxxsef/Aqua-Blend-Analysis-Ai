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

    def test_percent_word_form_matches_percent_symbol_form(self):
        """Regression test for a real live-model finding (Task 62): the
        source writes '20 percent' (word form); a genuine model rewrite
        wrote '20%' (symbol form) for the exact same fact. Before this
        fix, '20.0' (word form, unflagged) and '20.0%' (symbol form,
        flagged) were tracked as two different values, so the faithful
        rewrite failed with both NUMBER_MISSING_OR_CHANGED and
        NUMBER_INVENTED for a number that never actually changed. See
        Validation_Rules.md section 3."""
        rewrite = CORRECT_REWRITE.replace(
            "20 percent lower real cost", "a 20% lower real cost"
        )
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert not any(
            f.rule in ("NUMBER_MISSING_OR_CHANGED", "NUMBER_INVENTED")
            for f in result.critical_failures
        )

    def test_pct_word_form_also_matches_percent_symbol(self):
        rewrite = CORRECT_REWRITE.replace("20 percent lower", "20pct lower")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert not any(
            f.rule in ("NUMBER_MISSING_OR_CHANGED", "NUMBER_INVENTED")
            for f in result.critical_failures
        )

    def test_swapped_source_percentages_fails(self):
        """Regression test for a real reviewer finding (PR #46, Yousef):
        swapping Yarra River, Kew's 58.0% with Silvan Reservoir's 42.0%
        leaves the overall SET of numbers in the document completely
        unchanged - both values are still present somewhere - so the
        plain presence-based check in _check_numbers correctly sees
        nothing wrong and returns PASS. _check_number_association exists
        specifically to catch this: it checks that a volume and its
        blend percentage stay written together as a pair, regardless of
        wording. See Validation_Rules.md section 4."""
        rewrite = CORRECT_REWRITE.replace("58.0%", "TEMP58").replace(
            "42.0%", "58.0%"
        ).replace("TEMP58", "42.0%")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "NUMBER_WRONG_ASSOCIATION" for f in result.critical_failures)

    def test_swapped_source_volumes_fails(self):
        """The same swap check on the ML/day volumes instead of the
        percentages - 290 and 210 swapped between the two sources."""
        rewrite = CORRECT_REWRITE.replace("290 ML/day", "TEMP290").replace(
            "210 ML/day", "290 ML/day"
        ).replace("TEMP290", "210 ML/day")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "NUMBER_WRONG_ASSOCIATION" for f in result.critical_failures)

    def test_association_check_does_not_false_positive_on_correct_rewrite(self):
        """The safety check on the association fix itself: two earlier,
        broader designs (identifier-proximity based, see
        _extract_number_pairs's docstring) both produced false positives
        on CORRECT_REWRITE - a genuinely faithful rewrite - once actually
        tested against it, not just against the swap case. This is the
        regression test confirming the final, narrower pair-based design
        does not repeat that mistake."""
        result = validate_llm_output(REFERENCE_REPORT, CORRECT_REWRITE)
        assert not any(
            f.rule == "NUMBER_WRONG_ASSOCIATION" for f in result.critical_failures
        )

    def test_dropped_value_without_a_swap_is_not_an_association_failure(self):
        """A value that's simply missing entirely (not moved to a
        different pairing) is _check_numbers' job, not this check's -
        confirms the two checks don't double-report the same simple
        omission as a swap."""
        rewrite = CORRECT_REWRITE.replace("58.0%", "some of the blend")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert not any(
            f.rule == "NUMBER_WRONG_ASSOCIATION" for f in result.critical_failures
        )
        assert any(f.rule == "NUMBER_MISSING_OR_CHANGED" for f in result.critical_failures)

    def test_numbered_list_marker_is_not_read_as_an_invented_number(self):
        """Regression test for a real finding from a genuine live model run
        (Task 62, Run 6): the model reformatted the Binding Constraints
        section from a bullet list into a numbered list ('1. ...', '2.
        ...'), and the plain number regex read the bare list marker '2.'
        as the standalone invented fact 2.0, since nothing followed the
        period as a digit. The real content of each numbered item must
        still be checked normally - only the marker itself is excluded."""
        rewrite = CORRECT_REWRITE.replace(
            "\n\nAquaBlend is a public-data",
            "\n\nThe solution was limited by:\n"
            "1. The full demand of Zone 1 (500 ML/day must be delivered).\n"
            "2. The maximum available capacity of Yarra River, Kew (290 ML/day).\n\n"
            "AquaBlend is a public-data",
        )
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert not any(f.rule == "NUMBER_INVENTED" for f in result.critical_failures)


    def test_numbered_list_marker_exclusion_does_not_hide_a_real_invented_number(self):
        """The list-marker exclusion must stay narrowly scoped to the
        marker itself - a genuinely invented number placed right after a
        numbered-list marker must still be caught."""
        rewrite = CORRECT_REWRITE + "\n1. The blend now costs 999 AUD extra per day."
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert any(f.rule == "NUMBER_INVENTED" for f in result.critical_failures)

    def test_decimal_at_start_of_line_is_not_treated_as_a_list_marker(self):
        """A genuine decimal value at the start of a line (not a bare
        integer) must not be excluded - only a bare integer immediately
        followed by a period and non-digit is a list-marker shape."""
        rewrite = CORRECT_REWRITE + "\n58.5 ML/day was an alternative figure considered."
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert any(
            f.rule in ("NUMBER_INVENTED", "NUMBER_MISSING_OR_CHANGED")
            for f in result.critical_failures
        )


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
        """Both forms of the entity must be removed to genuinely test
        'this identifier is gone' - 'Groundwater Bore 1' also appears as
        'groundwater_bore_1' elsewhere in the rewrite (Data Flags,
        Sensitivity), and word-set matching correctly recognises that
        surviving snake_case reference as the same entity. Found by
        running this test after the word-set fix and seeing it correctly
        flip to PASS - not a validator bug, a fixture that no longer
        represented true removal. See Validation_Rules.md section 3."""
        rewrite = CORRECT_REWRITE.replace("Groundwater Bore 1", "the third source")
        rewrite = rewrite.replace("groundwater_bore_1", "an unspecified source")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        failure = next(
            f for f in result.critical_failures if f.rule == "IDENTIFIER_MISSING"
        )
        assert "Groundwater Bore 1" in failure.detail

    def test_partial_identifier_removal_is_not_flagged(self):
        """The mirror case: if ONE form of an entity is removed but another
        genuine reference to the same entity survives elsewhere, that is
        correctly not a failure - the fact itself (the entity exists, has
        estimated data, etc.) is still present in the rewrite, just under
        a different name form. This is the behaviour the previous test's
        original fixture accidentally exercised without meaning to."""
        rewrite = CORRECT_REWRITE.replace("Groundwater Bore 1", "the third source")
        assert "groundwater_bore_1" in rewrite  # the surviving snake_case form
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert not any(
            f.rule == "IDENTIFIER_MISSING" and "Groundwater Bore 1" in f.detail
            for f in result.critical_failures
        )

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

    def test_fuller_or_reformatted_name_for_the_same_entity_is_not_flagged(self):
        """Regression test for real live-model findings (Task 62): a
        genuine model rewrite used 'Zone 1' for the source's 'zone_1',
        'Treatment Facility 1' for 'facility_1', and consistently
        'Yarra River, Kew' where the source sometimes used the shorthand
        'Yarra Kew' - three different entities, three different kinds of
        reformatting, all correctly not a fact change. Word-set matching
        (an llm identifier counts if it contains at least every word the
        det identifier has) resolves all three with one mechanism. See
        Validation_Rules.md section 3."""
        rewrite = CORRECT_REWRITE.replace("Reduce Yarra Kew", "Reduce Yarra River, Kew")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "PASS"

    def test_dropped_word_in_a_shorter_name_still_fails(self):
        """The safety check on the word-set fix: a rewrite that drops a
        word rather than adding one must still fail. 'Silvan' alone must
        not be accepted as covering 'Silvan Reservoir' - that would hide
        a genuine, real loss of specificity. Both the Title-Case and
        snake_case forms are replaced, for the same reason as the zone
        test above."""
        rewrite = CORRECT_REWRITE.replace("Silvan Reservoir", "Silvan").replace(
            "silvan_reservoir", "an unspecified source"
        )
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(
            f.rule == "IDENTIFIER_MISSING" and "Silvan Reservoir" in f.detail
            for f in result.critical_failures
        )

    def test_wrong_number_in_a_covered_identifier_still_fails(self):
        """Another safety check: word-set matching must not let a wrong
        trailing number slip through just because the rest of the name
        matches. 'Zone 1' becoming 'Zone 2' is a real error, not a
        reformatting - both the snake_case and Title-Case forms are
        replaced, since either one surviving anywhere in the rewrite
        would otherwise still satisfy the word-set match on its own."""
        rewrite = CORRECT_REWRITE.replace("zone_1", "zone_2").replace("Zone 1", "Zone 2")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "IDENTIFIER_MISSING" for f in result.critical_failures)

    def test_sentence_case_rendering_of_a_field_name_is_recognised(self):
        """Regression test for a real finding from a genuine live model
        run (Task 62, Run 7): the model rendered source_activation_cost
        and plant_activation_cost as ordinary sentence-case prose
        ("Source activation cost is $0.00..."), which neither the
        Title-Case pattern (requires every word capitalised, not just
        the first) nor the snake_case pattern recognised as an identifier
        at all - the fact was faithfully conveyed but invisible to
        extraction. Fixed via _phrase_covers_snake_case_identifier."""
        rewrite = CORRECT_REWRITE.replace("storage_capacity,", "Storage capacity,")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert not any(
            f.rule == "IDENTIFIER_MISSING" and "storage_capacity" in f.detail
            for f in result.critical_failures
        )

    def test_scattered_words_do_not_satisfy_the_sentence_case_fallback(self):
        """The fallback requires the identifier's words as a genuine
        contiguous phrase, not merely all present somewhere in the
        document - scattering them across unrelated sentences must still
        correctly fail."""
        rewrite = CORRECT_REWRITE.replace(
            "storage_capacity,",
            "the storage limits,",
        )
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert any(
            f.rule == "IDENTIFIER_MISSING" and "storage_capacity" in f.detail
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

    def test_asserted_treated_water_claim_fails(self):
        """The genuine case this rule exists for: 'treated water' stated as
        a real claim, not a denial."""
        rewrite = CORRECT_REWRITE + " This is treated water, ready for use."
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "UNSAFE_SAFETY_CLAIM" for f in result.critical_failures)

    def test_negated_treated_water_claim_does_not_fail(self):
        """Regression test for a consistency finding: 'are not final
        treated water' is structurally identical to 'not final
        drinking-water' - both are true, safe denials, not claims. An
        earlier version of this test asserted a negated 'treated water'
        should always fail regardless of context; that was the same
        context-blind assumption the negation-detection fix (section 7)
        exists to correct, and treating 'treated water' inconsistently
        with 'final drinking' would be arbitrary. See
        Validation_Rules.md section 7."""
        rewrite = CORRECT_REWRITE.replace(
            "are not final post-treatment drinking-water results",
            "are not final treated water",
        )
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert not any(f.rule == "UNSAFE_SAFETY_CLAIM" for f in result.critical_failures)

    def test_negated_final_drinking_claim_does_not_fail(self):
        """The exact real finding from Task 62's first live run: the model
        wrote 'The results are not final drinking-water quality outcomes'
        - an accurate denial matching the source's own meaning, not an
        overclaim. Before the negation-detection fix this failed with
        UNSAFE_SAFETY_CLAIM regardless of the 'not'."""
        rewrite = CORRECT_REWRITE + " The results are not final drinking-water quality outcomes."
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert not any(f.rule == "UNSAFE_SAFETY_CLAIM" for f in result.critical_failures)

    def test_negation_word_in_a_different_sentence_does_not_carry_over(self):
        """A negation must not suppress a genuinely unsafe claim just
        because an unrelated 'not' appeared somewhere earlier in the
        rewrite - only a negation in the SAME sentence/clause counts."""
        rewrite = (
            CORRECT_REWRITE
            + " This is not a small system. The blend is safe to drink."
        )
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "UNSAFE_SAFETY_CLAIM" for f in result.critical_failures)

    def test_distant_negation_in_a_long_sentence_does_not_carry_over(self):
        """The adversarial case the negation window is deliberately bounded
        against: an unrelated negation early in a long sentence must not
        suppress a genuine, clearly separate unsafe claim later in that
        same sentence. This is why _NEGATION_WINDOW_WORDS is a bounded
        window (12 words), not a whole-sentence scan - see
        Validation_Rules.md section 7."""
        rewrite = CORRECT_REWRITE + (
            " This is not a small system, it serves a large regional area "
            "with many connected zones and multiple treatment facilities, "
            "and the water is safe to drink."
        )
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "UNSAFE_SAFETY_CLAIM" for f in result.critical_failures)

    def test_contrastive_conjunction_ends_a_negations_scope(self):
        """Regression test for a real reviewer finding (PR #46, Yousef):
        'The blend is not safe to drink, but it is compliant.' 'not'
        genuinely negates 'safe to drink' - correctly not flagged - but
        'compliant' sits in a new clause introduced by 'but' and has no
        grammatical relationship to that negation at all. It's a real,
        separate, unsafe assertion. Before this fix, the word-count
        window alone (7 words from 'not' to 'compliant', well inside the
        12-word limit) incorrectly let the earlier negation suppress it.
        See Validation_Rules.md section 6."""
        rewrite = CORRECT_REWRITE + " The blend is not safe to drink, but it is compliant."
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(
            f.rule == "UNSAFE_SAFETY_CLAIM" and "compliant" in f.detail
            for f in result.critical_failures
        )
        # and confirm "safe to drink" itself is correctly NOT flagged,
        # since "not" does genuinely negate that specific phrase
        assert not any(
            "safe to drink" in f.detail for f in result.critical_failures
        )

    def test_contrastive_conjunction_without_comma_also_ends_scope(self):
        """The boundary pattern must not depend on the comma being
        present - 'not safe to drink but it is compliant' (no comma)
        must behave the same way."""
        rewrite = CORRECT_REWRITE + " The blend is not safe to drink but it is compliant."
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(
            f.rule == "UNSAFE_SAFETY_CLAIM" and "compliant" in f.detail
            for f in result.critical_failures
        )


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


class TestOutputCompletenessFailures:

    def test_truncated_output_mid_sentence_fails(self):
        """Regression test for a real reviewer finding (PR #46, Yousef):
        a response cut off mid-sentence, with no terminal punctuation,
        must not be accepted as a complete rewrite - it could be silently
        missing required content that would have come after the cut."""
        rewrite = CORRECT_REWRITE.rstrip(".")  # remove the final period, simulate a cutoff
        # also chop off the last few words to make it genuinely mid-sentence
        rewrite = rewrite[: rewrite.rfind(" ", 0, len(rewrite) - 5)]
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "INCOMPLETE_OUTPUT" for f in result.critical_failures)

    def test_output_ending_in_a_question_mark_is_not_flagged(self):
        rewrite = CORRECT_REWRITE + " Is this the recommended blend?"
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert not any(f.rule == "INCOMPLETE_OUTPUT" for f in result.critical_failures)

    def test_output_ending_in_an_exclamation_mark_is_not_flagged(self):
        rewrite = CORRECT_REWRITE + " Review complete!"
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert not any(f.rule == "INCOMPLETE_OUTPUT" for f in result.critical_failures)

    def test_trailing_whitespace_after_terminal_punctuation_is_not_flagged(self):
        rewrite = CORRECT_REWRITE + "   \n\n  "
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert not any(f.rule == "INCOMPLETE_OUTPUT" for f in result.critical_failures)

    def test_a_complete_faithful_rewrite_is_not_flagged(self):
        result = validate_llm_output(REFERENCE_REPORT, CORRECT_REWRITE)
        assert not any(f.rule == "INCOMPLETE_OUTPUT" for f in result.critical_failures)


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
        reviewer needs the complete list in one pass. Both forms of the
        identifier are removed, same reasoning as
        test_missing_title_case_identifier_fails."""
        rewrite = CORRECT_REWRITE.replace("status OPTIMAL", "status INFEASIBLE")
        rewrite = rewrite.replace("Groundwater Bore 1", "the third source")
        rewrite = rewrite.replace("groundwater_bore_1", "an unspecified source")
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

# ---------------------------------------------------------------------------
# 9. Real live-model output (Task 62) - genuine evidence, not a synthetic
#    fixture. Captured from an actual local Qwen3-4B-Instruct-2507 run
#    against REFERENCE_REPORT, not written by hand. See LLM_Live_Run_Notes.md
#    for the full run details (runtime, config, both bugs this output found).
# ---------------------------------------------------------------------------

REAL_LIVE_MODEL_OUTPUT_SAMPLE_1 = """## Scenario & Solver Status

Scenario: scenario_2026_07_17_001  
Solver status: OPTIMAL  
Solved at: 2026-07-17T10:32:00Z

## Result Availability

The solver has found the best possible solution under the current model and input assumptions.

## Demand-Zone Results

Zone 1:  
- Required demand: 500 ML/day  
- Supplied volume: 500 ML/day  

## Selected Sources & Blend Ratios

- Yarra River, Kew:  
  - Supplied: 290 ML/day  
  - Blend share: 58.0%  
  - Estimated cost per ML: $235 AUD  
  - Draw cost: $68,150.0 AUD  

- Silvan Reservoir:  
  - Supplied: 210 ML/day  
  - Blend share: 42.0%  
  - Estimated cost per ML: $400 AUD  
  - Draw cost: $84,000.0 AUD  

## Unused Sources

- Groundwater Bore 1: Not selected  

## Active Plants & Transfer Results

- Treatment Facility 1:  
  - Processed: 500 ML/day  
  - Treatment cost per ML: $64 AUD  
  - Total treatment cost: $32,000.0 AUD  

Transfers:  
- Silvan Reservoir → Treatment Facility 1: 210 ML/day (active)  
- Yarra River, Kew → Treatment Facility 1: 290 ML/day (active)  
- Groundwater Bore 1 → Treatment Facility 1: 0 ML/day (inactive)  

Delivery:  
- Treatment Facility 1 → Zone 1: 500 ML/day (active)  

## Cost Summary

Total cost: $184,150.0 AUD (for one representative day)  

Breakdown:  
- Source activation cost: $0.0 AUD  
- Plant activation cost: $0.0 AUD  
- Source draw cost: $152,150.0 AUD  
- Plant treatment cost: $32,000.0 AUD  

## Plant-Inflow Water Quality

These results apply to: blend_at_plant_inflow  

All quality parameters at Treatment Facility 1 passed the modelled limits.  

- Alkalinity: Closest to its limit, with a safety margin of 22.6%  
- Turbidity: Widest margin, at 34.0%  

Note: These results describe the water blend as it arrives at the plant inflow. They are not the final treated drinking-water quality.  

## Binding Constraints

- The solution was limited by the demand of Zone 1: The full 500 ML/day required by Zone 1 must be delivered. No less can be supplied.  
- The solution was limited by the capacity of Yarra River, Kew: It was drawn to its maximum allowed level (290 ML/day), so no additional water could be taken from other sources.  

## Data Flags & Estimated Values

The following sources have estimated values and should be treated as provisional:  
- silvan_reservoir: storage_capacity, reference_flow, max_available, cost, alkalinity  
- yarra_kew: storage_capacity, reference_flow, max_available, cost, alkalinity  
- groundwater_bore_1: storage_capacity, reference_flow, max_available, cost, alkalinity  

Additional notes:  
- source_activation_cost is 0.00: The model includes a cost for activating sources, but no input data was provided, so this cost is zero.  
- plant_activation_cost is 0.00: The model assumes one plant is active, and its fixed cost is set to zero in the input.  
- Plant costs, plant capacity, link capacities, and quality limits are defined in the scenario file and have no provenance source, unlike source fields which come from a database.  
- Quality limits are applied at plant inflow, not after treatment.  

## Alternatives & Sensitivity

Alternative feasible solution:  
- Reduce Yarra River, Kew share to 45%  
- Add Groundwater Bore 1 at 13%  
- Total cost: $189,400.0 AUD  
- Cost difference from optimal: +$5,250.0 AUD  
- This option reduces reliance on a single river source and adds redundancy if Yarra River, Kew availability drops.  

Sensitivity notes:  
- This alternative depends on the actual cost of groundwater from Bore 1. If the real cost is 20% lower than estimated, Bore 1 would likely be included in the optimal blend.  
- This solution depends on the maximum available flow from Yarra River, Kew. If real availability is lower than assumed, the model may not be able to meet the 500 ML/day demand.  

## Prototype Disclaimer

AquaBlend is a public-data decision-support proof-of-concept. This report does not replace qualified operators, engineers, regulators, or health authorities.  
All values and assumptions are based on input data and model constraints.  
No claims are made about water safety, regulatory compliance, or operational performance.  
The results are not final drinking-water quality outcomes.  
The model does not account for real-world variability, infrastructure failure, or environmental changes.  
This report is for demonstration purposes only.  
Actual water quality, cost, and availability may differ significantly in practice.  
No responsibility is accepted for decisions made based on this report.  
All data and estimates
"""

# Run 6's exact real captured text, embedded verbatim (Task 62) - genuine
# live model output after adding frequency_penalty and the "stop after the
# final section" prompt rule (v1.1). Confirmed no repetition loop this
# time, but surfaced two new real findings: the model reformatted the
# Binding Constraints section as a numbered list (see the
# numbered-list-marker fix in llm_validator.py), and echoed the literal
# </deterministic_report> closing tag from the prompt's own delimiter
# syntax into its output - a prompt-leakage issue, not yet fixed, see
# LLM_Live_Run_Notes.md.
REAL_LIVE_MODEL_OUTPUT_SAMPLE_3_RUN6 = """## Scenario & Solver Status

Scenario: scenario_2026_07_17_001  
Solver status: OPTIMAL  
Solved at: 2026-07-17T10:32:00Z

## Result Availability

The model found a confirmed optimal solution based on the current inputs and assumptions.

## Demand-Zone Results

Zone 1:  
- Required demand: 500 ML/day  
- Supplied volume: 500 ML/day  

## Selected Sources & Blend Ratios

- Yarra River, Kew:  
  - Supplied: 290 ML/day  
  - Blend share: 58.0%  
  - Estimated cost per ML: $235 AUD  
  - Draw cost: $68,150.0 AUD  

- Silvan Reservoir:  
  - Supplied: 210 ML/day  
  - Blend share: 42.0%  
  - Estimated cost per ML: $400 AUD  
  - Draw cost: $84,000.0 AUD  

## Unused Sources

- Groundwater Bore 1: Not selected for use.

## Active Plants & Transfer Results

- Treatment Facility 1:  
  - Processed: 500 ML/day  
  - Treatment cost per ML: $64 AUD  
  - Total treatment cost: $32,000.0 AUD  

Transfers:  
- Silvan Reservoir → Treatment Facility 1: 210 ML/day (active)  
- Yarra River, Kew → Treatment Facility 1: 290 ML/day (active)  
- Groundwater Bore 1 → Treatment Facility 1: 0 ML/day (inactive)  

Delivery:  
- Treatment Facility 1 → Zone 1: 500 ML/day (active)

## Cost Summary

Total cost for one day: $184,150.0 AUD  

Breakdown:  
- Source activation cost: $0.0 AUD  
- Plant activation cost: $0.0 AUD  
- Source draw cost: $152,150.0 AUD  
- Plant treatment cost: $32,000.0 AUD  

## Plant-Inflow Water Quality

These results apply to the blend arriving at the plant inflow (blend_at_plant_inflow).

All quality parameters at Treatment Facility 1 passed the modelled limits.  
- Alkalinity: Closest to its limit, with a safety margin of 22.6%  
- Turbidity: Widest margin, at 34.0%  

Note: These results describe water quality at the plant inflow. They are not the final drinking-water quality after treatment.

## Binding Constraints

The solution was limited by:  
1. The full demand of Zone 1 (500 ML/day must be delivered — no less).  
2. The maximum available capacity of Yarra River, Kew (drawn up to 290 ML/day — the highest it can supply under current assumptions).

## Data Flags & Estimated Values

The following sources have estimated values and should be treated as provisional:  
- silvan_reservoir: storage_capacity, reference_flow, max_available, cost, alkalinity  
- yarra_kew: storage_capacity, reference_flow, max_available, cost, alkalinity  
- groundwater_bore_1: storage_capacity, reference_flow, max_available, cost, alkalinity  

Additional notes:  
- source_activation_cost is $0.00 because the model structure includes a cost term (F_s) for activated sources, but no input data was provided — so the value evaluates to zero.  
- plant_activation_cost is $0.00 because the model assumes one active plant, and its fixed cost is set to zero in the input.  
- Plant costs, plant capacity, link capacities, and quality limits are defined in the scenario file and have no data source tracking — unlike source fields, which come from a database.  
- Quality limits are applied at plant inflow (before treatment), not after treatment or as regulatory standards.

## Alternatives & Sensitivity

Alternative solution:  
- Reduce Yarra River, Kew share to 45% and add Groundwater Bore 1 at 13%.  
- Total cost: $189,400.0 AUD  
- Cost difference from optimal: +$5,250.0 AUD  
- This option reduces reliance on a single river source and adds redundancy if Yarra River, Kew becomes unavailable.

Sensitivity notes:  
- This alternative depends on the actual cost of groundwater Bore 1. If the real cost is 20% lower than estimated, Groundwater Bore 1 would likely be included in the optimal blend.  
- This solution depends on the maximum daily availability of Yarra River, Kew. If real availability is lower than assumed, the model may not be able to meet the 500 ML/day demand.

## Prototype Disclaimer

AquaBlend is a public-data decision-support proof-of-concept. This report does not replace qualified operators, engineers, regulators, or health authorities.  
</deterministic_report>
"""

# Run 7's exact real captured text, embedded verbatim (Task 62) - genuine
# live model output after adding the explicit tag-prohibition rule
# (prompt v1.2), on top of Run 6's fixes (frequency_penalty, stop-after-
# final-section rule). Ends with proper terminal punctuation, no
# repetition loop, no prompt-tag leak. Surfaced three real validator bugs
# (the pair-association window, and sentence-case field-name rendering),
# all fixed here - see LLM_Live_Run_Notes.md. This is the first genuine,
# complete, PASSing live-model output on the flagship OPTIMAL scenario.
REAL_LIVE_MODEL_OUTPUT_SAMPLE_4_RUN7 = """## Scenario & Solver Status

Scenario: scenario_2026_07_17_001  
Solver status: OPTIMAL  
Solved at: 2026-07-17T10:32:00Z  

## Result Availability

The model found a confirmed best solution under the current assumptions and inputs.

## Demand-Zone Results

Zone 1 required 500 ML/day and received exactly 500 ML/day.

## Selected Sources & Blend Ratios

- Yarra River, Kew: supplied 290 ML/day, making up 58.0% of the blend.  
  Estimated cost per ML: $235 AUD.  
  Total draw cost: $68,150.0 AUD.

- Silvan Reservoir: supplied 210 ML/day, making up 42.0% of the blend.  
  Estimated cost per ML: $400 AUD.  
  Total draw cost: $84,000.0 AUD.

## Unused Sources

Groundwater Bore 1 was not used in this solution.

## Active Plants & Transfer Results

- Treatment Facility 1 processed 500 ML/day.  
  Treatment cost per ML: $64 AUD.  
  Total treatment cost: $32,000.0 AUD.

Transfers:
- Silvan Reservoir → Treatment Facility 1: 210 ML/day (active).  
- Yarra River, Kew → Treatment Facility 1: 290 ML/day (active).  
- Groundwater Bore 1 → Treatment Facility 1: 0 ML/day (inactive).  
- Treatment Facility 1 → Zone 1: 500 ML/day (active).

## Cost Summary

Total cost for one day: $184,150.0 AUD  

Breakdown:
- Source activation cost: $0.0 AUD  
- Plant activation cost: $0.0 AUD  
- Source draw cost: $152,150.0 AUD  
- Plant treatment cost: $32,000.0 AUD  

## Plant-Inflow Water Quality

These results apply to the blend arriving at the plant inlet (blend_at_plant_inflow).

All quality parameters at Treatment Facility 1 passed the modelled limits.  
- Alkalinity was closest to its limit, with a safety margin of 22.6%.  
- Turbidity had the widest safety margin at 34.0%.

These results describe the water entering the plant, not the final treated drinking water. They were checked against plant-inflow constraints and do not represent post-treatment quality.

## Binding Constraints

The solution was limited by:
- The full demand of Zone 1: 500 ML/day must be delivered, so no less was supplied.  
- The capacity of Yarra River, Kew: it was drawn to its maximum allowed level (290 ML/day), so no extra water could come from other sources.

## Data Flags & Estimated Values

The following sources have estimated values and should be treated as provisional:
- Silvan Reservoir: storage_capacity, reference_flow, max_available, cost, alkalinity  
- Yarra River, Kew: storage_capacity, reference_flow, max_available, cost, alkalinity  
- Groundwater Bore 1: storage_capacity, reference_flow, max_available, cost, alkalinity  

Additional notes:
- Source activation cost is $0.00 because the model structure includes a cost term (F_s), but no input data was provided for it. The term evaluates to zero.  
- Plant activation cost is $0.00 because the model assumes one plant is active and its fixed cost is set to zero in the input.  
- Plant costs, plant capacity, link capacities, and quality limits are defined in the scenario file and have no data source tracking, unlike source fields which come from a database.  
- Quality limits are applied at plant inflow, not after treatment.

## Alternatives & Sensitivity

Alternative solution:
- Reduce Yarra River, Kew share to 45% and add Groundwater Bore 1 at 13%.  
- Total cost: $189,400.0 AUD (higher by $5,250.0 AUD).  
- This option reduces reliance on a single river source and adds redundancy if Yarra River, Kew becomes unavailable.

Sensitivity notes:
- This alternative depends on the actual cost of groundwater from Bore 1. If the real cost is 20% lower than estimated, Bore 1 would likely be included in the optimal solution.  
- This solution depends on the actual availability of Yarra River, Kew. If real availability is less than assumed, the model may not be able to meet the 500 ML/day demand.

## Prototype Disclaimer

AquaBlend is a public-data decision-support proof-of-concept. This report does not replace qualified operators, engineers, regulators, or health authorities.
"""


class TestRealLiveModelOutput:
    """Confirms the three real bugs this genuine model output found
    (word-form percentages, reformatted/fuller entity names, and
    negation-blind phrase matching) are fixed, and confirms the team-lead
    decision to exempt cost_per_ml/max_available_ml_per_day from the
    identifier check gets this real output to a genuine PASS - see
    LLM_Live_Run_Notes.md for the full writeup."""

    def test_real_output_no_longer_has_false_positive_number_or_identifier_failures(self):
        result = validate_llm_output(REFERENCE_REPORT, REAL_LIVE_MODEL_OUTPUT_SAMPLE_1)
        rules = {f.rule for f in result.critical_failures}
        assert "NUMBER_MISSING_OR_CHANGED" not in rules
        assert "NUMBER_INVENTED" not in rules
        assert not any(
            f.rule == "IDENTIFIER_MISSING" and f.detail.split("'")[1] in
            {"Zone 1", "zone_1", "Treatment Facility 1", "facility_1", "Yarra Kew"}
            for f in result.critical_failures
        )

    def test_real_output_no_longer_false_flags_the_negated_disclaimers(self):
        """The model correctly wrote 'not final drinking-water' and 'No
        claims are made about ... regulatory compliance', both accurate
        negations. Before the negation-detection fix (section 7), the
        always-banned-phrase and differential-content checks could not
        distinguish asserting something from denying it, and flagged both
        as if they were genuine problems. Fixed; see LLM_Live_Run_Notes.md."""
        result = validate_llm_output(REFERENCE_REPORT, REAL_LIVE_MODEL_OUTPUT_SAMPLE_1)
        rules = {f.rule for f in result.critical_failures}
        assert "UNSAFE_SAFETY_CLAIM" not in rules
        assert "INVENTED_CONTENT" not in rules

    def test_real_output_correctly_fails_on_truncation(self):
        """Corrected by a real review finding (PR #46, Yousef): this
        output was originally reported as a genuine PASS after the
        cost_per_ml/max_available_ml_per_day exemption landed. That was
        wrong. The output is genuinely truncated - it cuts off mid-
        sentence at 'All data and estimates' with nothing after, almost
        certainly from hitting the model's max_tokens limit - and the
        validator had no check for output completeness at all until this
        fix. With _check_output_completeness in place, this fixture
        correctly fails with INCOMPLETE_OUTPUT. There is currently no
        confirmed genuine PASS from a live model call on record - a
        fresh run with a higher max_tokens is needed to get one. See
        LLM_Live_Run_Notes.md for the corrected account."""
        result = validate_llm_output(REFERENCE_REPORT, REAL_LIVE_MODEL_OUTPUT_SAMPLE_1)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "INCOMPLETE_OUTPUT" for f in result.critical_failures)

    def test_exemption_is_narrow_other_field_names_still_required(self):
        """The exemption must not widen into a blanket pass for every
        snake_case field name - storage_capacity, reference_flow, and the
        other Data Flags provenance fields are NOT exempted, and still
        correctly fail if dropped. Confirms this alongside
        test_missing_snake_case_identifier_fails."""
        rewrite = CORRECT_REWRITE.replace("storage_capacity, ", "")
        result = validate_llm_output(REFERENCE_REPORT, rewrite)
        assert result.critical_result == "FAIL"
        assert any(
            f.rule == "IDENTIFIER_MISSING" and "storage_capacity" in f.detail
            for f in result.critical_failures
        )


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


class TestRealLiveModelOutputRun6:
    """Confirms the state of genuine live-model output from Task 62's Run
    6 (made after adding frequency_penalty and the "stop after the final
    section" prompt rule, v1.1) - no repetition loop this time, but two
    new real findings surfaced. See LLM_Live_Run_Notes.md for the full
    writeup."""

    def test_numbered_list_reformatting_no_longer_false_flags_as_invented(self):
        """The model reformatted Binding Constraints as a numbered list
        ('1. ...', '2. ...') - the bare list marker '2.' was previously
        misread as the invented number 2.0. Fixed; see
        _is_numbered_list_marker in llm_validator.py."""
        result = validate_llm_output(REFERENCE_REPORT, REAL_LIVE_MODEL_OUTPUT_SAMPLE_3_RUN6)
        assert not any(f.rule == "NUMBER_INVENTED" for f in result.critical_failures)

    def test_still_correctly_fails_on_incomplete_output(self):
        """The response ends with a stray '</deterministic_report>' tag,
        not proper terminal punctuation - genuinely incomplete, and the
        completeness check correctly still catches this."""
        result = validate_llm_output(REFERENCE_REPORT, REAL_LIVE_MODEL_OUTPUT_SAMPLE_3_RUN6)
        assert result.critical_result == "FAIL"
        assert any(f.rule == "INCOMPLETE_OUTPUT" for f in result.critical_failures)

    def test_prompt_tag_leak_is_currently_only_a_warning_not_a_dedicated_check(self):
        """The model echoed the literal '</deterministic_report>' closing
        tag from the prompt's own delimiter syntax into its output - a
        real prompt-leakage finding, distinct from truncation or invented
        content. There is currently no dedicated check for this; it only
        shows up incidentally as a NEW_IDENTIFIER warning because the tag
        text doesn't match anything in the source. Documented as a real,
        currently unaddressed gap in LLM_Live_Run_Notes.md, not silently
        left uncovered - this test exists so a future fix has something
        concrete to change from warning to a dedicated, clearly-named
        check."""
        result = validate_llm_output(REFERENCE_REPORT, REAL_LIVE_MODEL_OUTPUT_SAMPLE_3_RUN6)
        assert any(
            w.rule == "NEW_IDENTIFIER" and "deterministic_report" in w.detail
            for w in result.warnings
        )


class TestRealLiveModelOutputRun7:
    """Confirms the first genuine, complete PASS on the flagship OPTIMAL
    scenario from a real live model call (Task 62, Run 7) - made after
    adding the explicit tag-prohibition prompt rule (v1.2) on top of
    Run 6's fixes. Three real validator bugs were found and fixed as a
    direct result of checking this exact output, not assumed fixed - see
    LLM_Live_Run_Notes.md for the full writeup."""

    def test_real_output_is_a_genuine_pass(self):
        result = validate_llm_output(REFERENCE_REPORT, REAL_LIVE_MODEL_OUTPUT_SAMPLE_4_RUN7)
        assert result.critical_result == "PASS"
        assert result.critical_failures == []

    def test_no_false_positive_from_the_pair_association_check(self):
        """The rewrite splits each source's volume/percentage onto a
        bullet line and its cost onto an indented continuation line - a
        real formatting choice that broke an earlier, more fragile
        version of the pair-association window. Confirmed not to
        re-trigger it here."""
        result = validate_llm_output(REFERENCE_REPORT, REAL_LIVE_MODEL_OUTPUT_SAMPLE_4_RUN7)
        assert not any(
            f.rule == "NUMBER_WRONG_ASSOCIATION" for f in result.critical_failures
        )

    def test_no_false_positive_from_sentence_case_field_names(self):
        """source_activation_cost and plant_activation_cost were rendered
        as ordinary sentence-case prose ("Source activation cost is
        $0.00...") - confirmed recognised as covered, not missing."""
        result = validate_llm_output(REFERENCE_REPORT, REAL_LIVE_MODEL_OUTPUT_SAMPLE_4_RUN7)
        assert not any(
            f.rule == "IDENTIFIER_MISSING"
            and ("activation_cost" in f.detail)
            for f in result.critical_failures
        )

    def test_still_no_prompt_tag_leak_this_time(self):
        """Unlike Run 6, this output does not echo the prompt's own
        delimiter tags - the explicit tag-prohibition rule (prompt v1.2)
        appears to have addressed this specific finding, though this is
        one confirmation, not a guarantee it never recurs."""
        result = validate_llm_output(REFERENCE_REPORT, REAL_LIVE_MODEL_OUTPUT_SAMPLE_4_RUN7)
        assert not any(
            w.rule == "NEW_IDENTIFIER" and "deterministic_report" in w.detail
            for w in result.warnings
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
