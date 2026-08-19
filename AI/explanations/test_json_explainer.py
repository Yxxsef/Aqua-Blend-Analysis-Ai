"""
test_json_explainer.py

AquaBlend | Analysis & AI | Sprint 1 | Task 9

Two families of tests:

1. REFERENCE_JSON tests - the exact worked example from the AquaBlend MILP
   Configuration document, Section 8 ("The Final Output in JSON Format").
   This is the same scenario Tasks 6, 7 and 8 each hand-validated in their
   own PRs. Used here as the main test, per Task 9's checklist item
   "Reference JSON is used as the main test" / "Generated text is compared
   with the sample explanation" (checked against factual agreement, not
   exact wording, per the checklist).

2. Synthetic fixtures - every branch that the reference JSON does NOT
   exercise (each Task 6/7/8 PR admits only one scenario was ever hand-
   traced). These cover: infeasible status, zero selected sources, missing
   cost_per_ML, missing reason on an unused source, empty binding
   constraints, unknown constraint name, source-activation binding (both
   selected and unused), treatment-capacity binding, water-quality-range
   binding, a quality violation, a missing quality parameter, and missing
   required top-level fields.
"""

import copy
import sys
import pytest

from json_explainer import (
    ExplainerInputError,
    validate_input,
    check_feasibility,
    explain_sources,
    explain_binding_constraints,
    explain_quality_and_margins,
    explain_sensitivity,
    explain_estimated_fields,
    build_summary,
    generate_explanation,
)


# ---------------------------------------------------------------------------
# Reference JSON - AquaBlend MILP Configuration, Section 8, verbatim
# ---------------------------------------------------------------------------

REFERENCE_JSON = {
    "scenario_id": "scenario_2026_07_17_001",
    "solved_at": "2026-07-17T10:32:00Z",
    "status": "OPTIMAL",
    "objective": {
        "total_cost": 184150.00,
        "currency": "AUD",
        "unit": "cost for one representative day",
        "cost_breakdown": {
            "source_activation_cost": 0.00,
            "plant_activation_cost": 0.00,
            "source_draw_cost": 152150.00,
            "plant_treatment_cost": 32000.00,
        },
    },
    "demand_zones": [
        {"zone_id": "zone_1", "zone_name": "Zone 1", "demand_ml_per_day": 500, "volume_supplied_ml_per_day": 500}
    ],
    "sources": {
        "selected": [
            {
                "source_id": "silvan_reservoir",
                "source_name": "Silvan Reservoir",
                "source_type": "reservoir",
                "volume_drawn_ml_per_day": 210,
                "percent_of_blend": 42.0,
                "cost_per_ml": 400,
                "draw_cost": 84000.00,
            },
            {
                "source_id": "yarra_kew",
                "source_name": "Yarra River, Kew",
                "source_type": "river",
                "volume_drawn_ml_per_day": 290,
                "percent_of_blend": 58.0,
                "cost_per_ml": 235,
                "draw_cost": 68150.00,
            },
        ],
        "unused": [
            {
                "source_id": "groundwater_bore_1",
                "source_name": "Groundwater Bore 1",
                "source_type": "groundwater",
                "reason": (
                    "Higher cost per ML than the selected sources with no quality "
                    "benefit large enough to justify inclusion for this demand level"
                ),
            }
        ],
    },
    "transfer_paths": {
        "source_to_plant": [
            {"path_id": "silvan_reservoir_to_facility_1", "source_id": "silvan_reservoir", "plant_id": "facility_1", "active": True, "flow_ml_per_day": 210},
            {"path_id": "yarra_kew_to_facility_1", "source_id": "yarra_kew", "plant_id": "facility_1", "active": True, "flow_ml_per_day": 290},
            {"path_id": "groundwater_bore_1_to_facility_1", "source_id": "groundwater_bore_1", "plant_id": "facility_1", "active": False, "flow_ml_per_day": 0},
        ],
        "plant_to_zone": [
            {"path_id": "facility_1_to_zone_1", "plant_id": "facility_1", "zone_id": "zone_1", "active": True, "flow_ml_per_day": 500},
        ],
    },
    "plants": {
        "active": [
            {
                "plant_id": "facility_1",
                "plant_name": "Treatment Facility 1",
                "volume_processed_ml_per_day": 500,
                "treatment_cost_per_ml": 64,
                "treatment_cost": 32000.00,
            }
        ],
        "inactive": [],
    },
    "water_quality": {
        "applies_to": "blend_at_plant_inflow",
        "by_plant": {
            "facility_1": {
                "pH": {"value": 7.11, "unit": "pH", "constraint_min": 6.5, "constraint_max": 8.5,
                       "status": "PASS", "safety_margin_percent": 30.5},
                "alkalinity": {"value": 38.04, "unit": "mg/L CaCO3", "constraint_min": 20, "constraint_max": 100,
                               "status": "PASS", "safety_margin_percent": 22.6},
                "turbidity": {"value": 5.28, "unit": "NTU", "constraint_min": 0, "constraint_max": 8.0,
                              "status": "PASS", "safety_margin_percent": 34.0},
            }
        },
    },
    "constraints": [
        {"name": "demand_satisfaction_zone_1", "type": "inequality", "status": "PASS", "slack": 0.0, "binding": True},
        {"name": "source_capacity_silvan_reservoir", "type": "inequality", "status": "PASS", "slack": 40371.0, "binding": False},
        {"name": "source_capacity_yarra_kew", "type": "inequality", "status": "PASS", "slack": 0.0, "binding": True},
        {"name": "source_capacity_groundwater_bore_1", "type": "inequality", "status": "INACTIVE", "slack": 0.0, "binding": False},
        {"name": "plant_capacity_facility_1", "type": "inequality", "status": "PASS", "slack": 100.0, "binding": False},
        {"name": "quality_range_pH_facility_1", "type": "ranged", "status": "PASS", "slack": 0.61, "binding": False},
        {"name": "quality_range_alkalinity_facility_1", "type": "ranged", "status": "PASS", "slack": 18.04, "binding": False},
        {"name": "quality_range_turbidity_facility_1", "type": "ranged", "status": "PASS", "slack": 2.72, "binding": False},
    ],
    "binding_constraints_summary": ["demand_satisfaction_zone_1", "source_capacity_yarra_kew"],
    "alternative_feasible_solutions": [
        {
            "description": "Reduce Yarra Kew share to 45 percent and introduce Groundwater Bore 1 at 13 percent",
            "total_cost": 189400.00,
            "cost_difference_from_optimal": 5250.00,
            "notes": "Slightly higher cost, but reduces dependence on a single river source and adds redundancy if Yarra Kew availability drops",
        }
    ],
    "sensitivity_to_key_assumptions": [
        {
            "assumption": "cost_per_ml for groundwater_bore_1 (flagged estimated in the source view)",
            "impact": "If actual groundwater cost is 20 percent lower than estimated, groundwater_bore_1 would likely enter the optimal blend instead of remaining unused",
        },
        {
            "assumption": "max_available_ml_per_day for yarra_kew (flagged estimated in the source view)",
            "impact": "This constraint is currently binding; if real availability is lower than assumed, the model may become infeasible at this demand level",
        },
    ],
    "explanation": (
        "Silvan Reservoir is selected at 42 percent because it has low draw cost and ample "
        "remaining availability. Yarra Kew is blended at 58 percent, the maximum its estimated "
        "daily availability allows, because it is the cheapest available source for this scenario; "
        "this makes its capacity constraint binding. Groundwater Bore 1 is not used because its "
        "estimated cost is higher than both selected sources, and blending it in would raise "
        "total cost without a quality benefit large enough to justify inclusion. The blend "
        "arriving at Facility 1 sits within all three quality limits, with the widest margin on "
        "turbidity."
    ),
    "diagnostics": {
        "solver": "HiGHS",
        "solve_time_seconds": 0.084,
        "optimality_gap": 0.0,
        "num_continuous_variables": 7,
        "num_binary_variables": 8,
        "num_integer_variables": 0,
        "num_constraints": 20,
    },
    "data_flags": {
        "sources": [
            {
                "source_id": "silvan_reservoir",
                "has_estimated_values": True,
                "availability_origin": "database",
                "provenance": {
                    "storage_capacity": "estimate",
                    "reference_flow": "estimate",
                    "max_available": "estimate",
                    "cost": "estimate",
                    "alkalinity": "estimate",
                },
            },
            {
                "source_id": "yarra_kew",
                "has_estimated_values": True,
                "availability_origin": "database",
                "provenance": {
                    "storage_capacity": "estimate",
                    "reference_flow": "estimate",
                    "max_available": "estimate",
                    "cost": "estimate",
                    "alkalinity": "estimate",
                },
            },
            {
                "source_id": "groundwater_bore_1",
                "has_estimated_values": True,
                "availability_origin": "database",
                "provenance": {
                    "storage_capacity": "estimate",
                    "reference_flow": "estimate",
                    "max_available": "estimate",
                    "cost": "estimate",
                    "alkalinity": "estimate",
                },
            },
        ],
        "notes": [
            "source_activation_cost is structurally 0.00: the formulation charges F_s per activated source, but the loader has no input path for it, so the term evaluates to zero rather than being omitted.",
            "plant_activation_cost is 0.00 because the toy case holds the single plant active and its fixed cost is set to 0 in the input contract.",
            "Plant costs, plant capacity, link capacities and quality limits are defined in the scenario file and carry no provenance mechanism, unlike source fields which come from the database view.",
            "Quality limits are raw-blend limits applied at plant inflow, not post-treatment regulatory limits.",
        ],
    },
}


def ref():
    """Fresh deep copy so tests can mutate without affecting each other."""
    return copy.deepcopy(REFERENCE_JSON)

# ---------------------------------------------------------------------------
# 1. Reference JSON tests
# ---------------------------------------------------------------------------

class TestReferenceJSON:

    def test_validate_input_passes(self):
        validate_input(ref())  # should not raise

    def test_feasibility_gate_clear(self):
        assert check_feasibility(ref()) is None

    def test_sources_yarra_kew_cheapest_and_capacity_binding(self):
        text = explain_sources(ref())
        assert "Yarra River, Kew" in text
        assert "cheapest available source and was used at its full available capacity" in text
        assert "58.0% of the blend (290 ML)" in text
        assert "$235.00 AUD/ML" in text
        assert "(estimated)" in text  # yarra_kew has_estimated_values is True

    def test_sources_silvan_second_cheapest_not_binding(self):
        text = explain_sources(ref())
        assert "Silvan Reservoir" in text
        assert "second lowest cost" in text
        assert "42.0% of the blend (210 ML)" in text
        assert "$400.00 AUD/ML" in text

    def test_sources_ordering_by_percent_descending(self):
        text = explain_sources(ref())
        assert text.index("Yarra River, Kew") < text.index("Silvan Reservoir")

    def test_sources_unused_reason_verbatim(self):
        text = explain_sources(ref())
        assert "Groundwater Bore 1 was not selected because" in text
        assert "no quality benefit large enough to justify inclusion" in text

    def test_binding_constraints_demand_and_capacity(self):
        text = explain_binding_constraints(ref())
        assert "water demand for zone_1" in text
        assert "500 ML needed by zone_1" in text
        assert "available capacity of Yarra River, Kew" in text
        assert "290 ML" in text

    def test_quality_all_pass_headline_is_alkalinity(self):
        """Per the confirmed reference output, alkalinity has the tightest
        margin (22.6%), not pH - the toy model's real numbers differ from
        the earlier draft example this file was first built against."""
        text = explain_quality_and_margins(ref())
        assert "All tested plant-inflow blend quality parameters passed at facility_1" in text
        assert "alkalinity was closest to its limit" in text
        assert "22.6%" in text
        assert "widest margin at facility_1 was on turbidity at 34.0%" in text

    def test_estimated_fields_lists_all_three_sources(self):
        text = explain_estimated_fields(ref())
        for fragment in ["silvan_reservoir", "yarra_kew", "groundwater_bore_1", "storage_capacity"]:
            assert fragment in text

    def test_estimated_fields_includes_notes(self):
        text = explain_estimated_fields(ref())
        assert "source_activation_cost is structurally 0.00" in text

    def test_summary_reports_cost_and_pass(self):
        text = build_summary(ref())
        assert "OPTIMAL" in text
        assert "184,150.00 AUD" in text
        assert "2 source(s) selected, 1 unused" in text
        assert "Plant-inflow blend quality: PASS" in text

    def test_generate_explanation_has_all_sections(self):
        text = generate_explanation(ref())
        for heading in [
            "Selected & Unused Sources",
            "Binding Constraints",
            "Water Quality & Safety Margins",
            "Sensitivity to Key Assumptions",
            "Estimated Fields / Data Limitations",
            "Summary",
        ]:
            assert f"## {heading}" in text

    def test_sensitivity_reports_both_reference_assumptions(self):
        text = explain_sensitivity(ref())
        assert "cost_per_ml for groundwater_bore_1 (flagged estimated in the source view)" in text
        assert "groundwater_bore_1 would likely enter the optimal blend" in text
        assert "max_available_ml_per_day for yarra_kew" in text
        assert "model may become infeasible" in text

    def test_matches_reference_explanation_in_substance(self):
        """Not exact wording (per checklist: 'checks factual agreement, not
        exact wording') - just the same facts as the JSON's own free-text
        explanation field."""
        text = generate_explanation(ref())
        assert "Silvan Reservoir" in text and "42.0%" in text
        assert "Yarra River, Kew" in text and "58.0%" in text
        assert "Groundwater Bore 1" in text
        assert "turbidity" in text  # widest margin, matches reference explanation


# ---------------------------------------------------------------------------
# 2. Required-field validation
# ---------------------------------------------------------------------------

class TestValidation:

    @pytest.mark.parametrize("field", ["status", "sources", "water_quality", "binding_constraints_summary"])
    def test_missing_required_field_raises(self, field):
        data = ref()
        del data[field]
        with pytest.raises(ExplainerInputError):
            validate_input(data)

    def test_missing_by_plant_raises(self):
        data = ref()
        del data["water_quality"]["by_plant"]
        with pytest.raises(ExplainerInputError):
            validate_input(data)

    def test_non_dict_input_raises(self):
        with pytest.raises(ExplainerInputError):
            validate_input(["not", "a", "dict"])

    def test_missing_optional_fields_do_not_crash(self):
        data = ref()
        del data["objective"]
        del data["data_flags"]
        del data["demand_zones"]
        del data["plants"]
        # should not raise
        text = generate_explanation(data)
        assert "not reported" in text  # cost clause falls back gracefully


# ---------------------------------------------------------------------------
# 3. Feasibility gate
# ---------------------------------------------------------------------------

class TestFeasibility:

    def test_infeasible_status_short_circuits(self):
        data = ref()
        data["status"] = "INFEASIBLE"
        result = generate_explanation(data)
        assert result == "No blend could be recommended for this scenario (INFEASIBLE)."
        assert "## Summary" not in result  # gate applies to whole explanation, not just sources


# ---------------------------------------------------------------------------
# 4. Source-selection edge cases (Task 6)
# ---------------------------------------------------------------------------

class TestSourcesEdgeCases:

    def test_zero_selected_and_zero_unused(self):
        data = ref()
        data["sources"] = {"selected": [], "unused": []}
        text = explain_sources(data)
        assert text == "No sources were required for this scenario."

    def test_missing_cost_per_ml_on_selected_uses_generic_fallback(self):
        data = ref()
        del data["sources"]["selected"][0]["cost_per_ml"]  # silvan_reservoir
        text = explain_sources(data)
        assert "included in the optimal blend to help meet demand at minimum total cost" in text

    def test_missing_reason_on_unused_source(self):
        data = ref()
        del data["sources"]["unused"][0]["reason"]
        text = explain_sources(data)
        assert "no reason provided in the solver output" in text

    def test_single_selected_source_no_ordering_needed(self):
        data = ref()
        data["sources"]["selected"] = [data["sources"]["selected"][0]]
        data["sources"]["unused"] = []
        text = explain_sources(data)
        assert "Silvan Reservoir" in text

    def test_cost_currency_matches_objective_currency_not_hardcoded(self):
        """Rubric C7 (LLM_Evaluation_Rubric.md) requires 'cost uses AUD'. The
        currency shown must come from objective.currency, not be hardcoded,
        so a non-AUD scenario is still labelled correctly."""
        data = ref()
        data["objective"]["currency"] = "NZD"
        text = explain_sources(data)
        assert "NZD" in text
        assert "AUD" not in text

    def test_cost_shown_without_currency_when_objective_missing(self):
        """Optional field: no crash, just a plain dollar figure with no
        currency suffix rather than a wrong or invented one."""
        data = ref()
        del data["objective"]
        text = explain_sources(data)
        assert "$235.00/ML" in text  # no trailing currency code
        assert "AUD" not in text

    def test_summary_and_source_cost_lines_use_same_currency(self):
        """The per-source lines and the summary total must not disagree on
        currency within the same explanation."""
        text = generate_explanation(ref())
        assert "$235.00 AUD/ML" in text
        assert "$184,150.00 AUD" in text

    def test_estimated_tag_uses_clean_per_source_flag(self):
        """Per the confirmed output contract, estimated-value disclosure is
        a direct data_flags.sources[].has_estimated_values boolean, not the
        old free-text substring matching against a flat estimated_fields[]
        list. A source with has_estimated_values explicitly False should
        never show '(estimated)'."""
        data = ref()
        for entry in data["data_flags"]["sources"]:
            if entry["source_id"] == "silvan_reservoir":
                entry["has_estimated_values"] = False
        text = explain_sources(data)
        silvan_line = [l for l in text.split("\n\n") if "Silvan Reservoir" in l][0]
        assert "(estimated)" not in silvan_line


# ---------------------------------------------------------------------------
# 5. Binding-constraints edge cases (Task 7)
# ---------------------------------------------------------------------------

class TestBindingConstraintsEdgeCases:

    def test_empty_binding_list(self):
        data = ref()
        data["binding_constraints_summary"] = []
        text = explain_binding_constraints(data)
        assert text == "No constraint was binding; the solution stayed within every limit."

    def test_unknown_constraint_name(self):
        data = ref()
        data["binding_constraints_summary"] = ["some_unrecognised_constraint"]
        text = explain_binding_constraints(data)
        assert "no plain-language mapping available" in text

    def test_plant_capacity_binding(self):
        data = ref()
        data["binding_constraints_summary"] = ["plant_capacity_facility_1"]
        text = explain_binding_constraints(data)
        assert "Treatment Facility 1" in text
        assert "500 ML" in text
        # No batch counting: the confirmed formulation has zero integer
        # variables (diagnostics.num_integer_variables == 0), so there is
        # nothing to count in batches anymore.
        assert "batch" not in text.lower()

    def test_water_quality_range_binding(self):
        data = ref()
        data["binding_constraints_summary"] = ["quality_range_turbidity_facility_1"]
        text = explain_binding_constraints(data)
        assert "turbidity limit" in text
        assert "facility_1" in text
        assert "0" in text and "8.0" in text

    def test_link_capacity_source_to_plant_binding(self):
        """link_capacity_<from>_to_<to> is a real inequality constraint per
        the confirmed output contract (Section 3.8) and can legitimately
        appear in binding_constraints_summary - this was missing entirely
        before this fix and would have fallen into the generic unknown
        wording."""
        data = ref()
        data["binding_constraints_summary"] = ["link_capacity_silvan_reservoir_to_facility_1"]
        text = explain_binding_constraints(data)
        assert "Silvan Reservoir" in text
        assert "Treatment Facility 1" in text
        assert "210 ML" in text
        assert "no plain-language mapping available" not in text

    def test_link_capacity_plant_to_zone_binding(self):
        data = ref()
        data["binding_constraints_summary"] = ["link_capacity_facility_1_to_zone_1"]
        text = explain_binding_constraints(data)
        assert "Treatment Facility 1" in text
        assert "Zone 1" in text
        assert "500 ML" in text

    def test_link_capacity_unknown_path_id_falls_back(self):
        data = ref()
        data["binding_constraints_summary"] = ["link_capacity_nonexistent_to_nowhere"]
        text = explain_binding_constraints(data)
        assert "no plain-language mapping available" in text


# ---------------------------------------------------------------------------
# 5b. Binding-constraints: confirmed-contract naming, ordering, missing data
# ---------------------------------------------------------------------------

class TestBindingConstraintsUpdatedTemplate:

    def test_category_ordering_ignores_json_order(self):
        """Water-quality listed FIRST in binding_constraints_summary must
        still render AFTER demand and source-capacity, per the fixed
        category order: demand, source_capacity, plant_capacity, water_quality."""
        data = ref()
        data["binding_constraints_summary"] = [
            "quality_range_turbidity_facility_1", "demand_satisfaction_zone_1", "source_capacity_yarra_kew"
        ]
        text = explain_binding_constraints(data)
        assert text.index("water demand for zone_1") < text.index("available capacity of Yarra River, Kew")
        assert text.index("available capacity of Yarra River, Kew") < text.index("turbidity limit")

    def test_estimated_disclosure_reads_per_source_flag(self):
        """(290 ML, estimated) - yarra_kew's data_flags.sources[] entry has
        has_estimated_values: True, per the confirmed output contract."""
        text = explain_binding_constraints(ref())
        assert "(290 ML, estimated)" in text

    def test_missing_demand_ml_per_day_drops_clause_not_whole_sentence(self):
        data = ref()
        del data["demand_zones"][0]["demand_ml_per_day"]
        text = explain_binding_constraints(data)
        assert "the full volume needed by zone_1 had to be delivered" in text
        assert "None" not in text

    def test_missing_volume_drawn_ml_per_day_drops_clause(self):
        data = ref()
        del data["sources"]["selected"][1]["volume_drawn_ml_per_day"]  # yarra_kew
        text = explain_binding_constraints(data)
        assert "was drawn up to the most its capacity allows, so" in text
        assert "None" not in text

    def test_missing_plant_fields_drops_clause(self):
        data = ref()
        del data["plants"]["active"][0]["volume_processed_ml_per_day"]
        data["binding_constraints_summary"] = ["plant_capacity_facility_1"]
        text = explain_binding_constraints(data)
        assert "was already treating as much as it can handle, leaving no spare capacity" in text
        assert "None" not in text

    def test_missing_quality_range_fields_drops_clause(self):
        data = ref()
        del data["water_quality"]["by_plant"]["facility_1"]["turbidity"]["constraint_min"]
        data["binding_constraints_summary"] = ["quality_range_turbidity_facility_1"]
        text = explain_binding_constraints(data)
        assert "sat right at the edge of its safe range, so the blend" in text
        assert "None" not in text

    def test_missing_source_name_falls_back_to_source_id(self):
        data = ref()
        del data["sources"]["selected"][1]["source_name"]  # yarra_kew
        text = explain_binding_constraints(data)
        assert "yarra_kew" in text  # falls back to the id, not "None"

    def test_missing_plant_name_falls_back_to_plant_id(self):
        data = ref()
        del data["plants"]["active"][0]["plant_name"]
        data["binding_constraints_summary"] = ["plant_capacity_facility_1"]
        text = explain_binding_constraints(data)
        assert "facility_1" in text

    def test_no_estimated_tag_when_figure_dropped(self):
        """If the clause carrying the figure is dropped under Missing-field,
        no estimated tag should appear either - there's no figure left to
        qualify. Demand itself never discloses estimated at all now, since
        the confirmed contract has no provenance mechanism for demand."""
        data = ref()
        del data["demand_zones"][0]["demand_ml_per_day"]
        data["binding_constraints_summary"] = ["demand_satisfaction_zone_1"]  # isolate
        text = explain_binding_constraints(data)
        assert "estimated" not in text.lower()

    def test_quality_never_discloses_estimated(self):
        """Per the confirmed output contract's own 'known gaps' (Section 6),
        quality limits carry no provenance mechanism at all, so this
        category should never show '(estimated)', unlike source_capacity."""
        data = ref()
        data["binding_constraints_summary"] = ["quality_range_turbidity_facility_1"]
        text = explain_binding_constraints(data)
        assert "estimated" not in text.lower()


class TestQualityEdgeCases:

    def test_violation_reported(self):
        data = ref()
        data["water_quality"]["by_plant"]["facility_1"]["turbidity"]["status"] = "FAIL"
        data["water_quality"]["by_plant"]["facility_1"]["turbidity"]["safety_margin_percent"] = -4.5
        data["water_quality"]["by_plant"]["facility_1"]["turbidity"]["value"] = 8.4
        text = explain_quality_and_margins(data)
        assert "Not all plant-inflow blend quality parameters passed at facility_1" in text
        assert "turbidity breached its allowed range" in text
        assert "-4.5%" in text

    def test_missing_parameter_flagged_not_assumed_pass(self):
        data = ref()
        del data["water_quality"]["by_plant"]["facility_1"]["alkalinity"]
        text = explain_quality_and_margins(data)
        assert "alkalinity at facility_1 was not reported in the results and could not be assessed" in text

    def test_multiple_plants_each_reported_separately(self):
        """The confirmed contract reports quality per plant
        (water_quality.by_plant), so a scenario with more than one active
        plant must report each plant's blend on its own, not merge them."""
        data = ref()
        data["water_quality"]["by_plant"]["facility_2"] = {
            "pH": {"value": 7.0, "unit": "pH", "constraint_min": 6.5, "constraint_max": 8.5,
                   "status": "PASS", "safety_margin_percent": 33.3},
            "alkalinity": {"value": 40.0, "unit": "mg/L CaCO3", "constraint_min": 20, "constraint_max": 100,
                           "status": "PASS", "safety_margin_percent": 25.0},
            "turbidity": {"value": 3.0, "unit": "NTU", "constraint_min": 0, "constraint_max": 8.0,
                          "status": "PASS", "safety_margin_percent": 62.5},
        }
        text = explain_quality_and_margins(data)
        assert "facility_1" in text
        assert "facility_2" in text

    def test_no_plants_reported_returns_explicit_message(self):
        data = ref()
        data["water_quality"]["by_plant"] = {}
        text = explain_quality_and_margins(data)
        assert text == "No plant-inflow blend quality was reported for this scenario."


# ---------------------------------------------------------------------------
# 7. Sensitivity-to-assumptions section (Task 9, added after Task 13 review)
# ---------------------------------------------------------------------------

class TestSensitivitySection:

    def test_missing_field_entirely(self):
        data = ref()
        del data["sensitivity_to_key_assumptions"]
        text = explain_sensitivity(data)
        assert text == "No sensitivity information was reported for this scenario."

    def test_empty_list(self):
        data = ref()
        data["sensitivity_to_key_assumptions"] = []
        text = explain_sensitivity(data)
        assert text == "No sensitivity information was reported for this scenario."

    def test_malformed_item_missing_impact_is_skipped_not_guessed(self):
        data = ref()
        data["sensitivity_to_key_assumptions"] = [
            {"assumption": "some assumption with no impact field"}
        ]
        text = explain_sensitivity(data)
        assert text == "No sensitivity information was reported for this scenario."

    def test_malformed_item_missing_assumption_is_skipped_not_guessed(self):
        data = ref()
        data["sensitivity_to_key_assumptions"] = [
            {"impact": "some impact with no assumption field"}
        ]
        text = explain_sensitivity(data)
        assert text == "No sensitivity information was reported for this scenario."

    def test_one_valid_and_one_malformed_item(self):
        data = ref()
        data["sensitivity_to_key_assumptions"] = [
            {"assumption": "valid assumption", "impact": "valid impact"},
            {"assumption": "incomplete"},
        ]
        text = explain_sensitivity(data)
        assert "valid assumption" in text
        assert "valid impact" in text
        assert text.count("sensitive to") == 1


# ---------------------------------------------------------------------------
# 8. Estimated-fields section (Task 9, rebuilt against data_flags.sources[]
#    + data_flags.notes[] per the confirmed output contract, Section 3.11)
# ---------------------------------------------------------------------------

class TestEstimatedFieldsSection:

    def test_no_estimated_sources_and_no_notes(self):
        data = ref()
        data["data_flags"]["sources"] = []
        data["data_flags"]["notes"] = []
        text = explain_estimated_fields(data)
        assert text == "No fields in this result were flagged as estimated."

    def test_missing_data_flags_entirely(self):
        data = ref()
        del data["data_flags"]
        text = explain_estimated_fields(data)
        assert text == "No fields in this result were flagged as estimated."

    def test_source_with_has_estimated_values_false_is_excluded(self):
        data = ref()
        data["data_flags"]["sources"] = [
            {"source_id": "silvan_reservoir", "has_estimated_values": False,
             "availability_origin": "database", "provenance": {}}
        ]
        data["data_flags"]["notes"] = []
        text = explain_estimated_fields(data)
        assert "silvan_reservoir" not in text
        assert text == "No fields in this result were flagged as estimated."

    def test_notes_shown_even_with_no_estimated_sources(self):
        data = ref()
        data["data_flags"]["sources"] = []
        text = explain_estimated_fields(data)
        assert "source_activation_cost is structurally 0.00" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
