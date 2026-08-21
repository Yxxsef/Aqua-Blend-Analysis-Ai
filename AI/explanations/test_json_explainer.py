"""
test_json_explainer.py

AquaBlend | Analysis & AI | Sprint 2 | Task 23

Tests for the upgraded deterministic report generator, built to the
Task 22 reporting specification:

  LLM_Report_Scope.md, Report_Structure.md, Results_JSON_Field_Map.md
  (explanations/llm_reporting/docs/)

Two families of tests:

1. REFERENCE_JSON tests - the shared worked example. `REFERENCE_JSON` is the
   Task 21-adapted form of the Task 22 `model_output_example.json` fixture
   (also matches the original Sprint 1 reference scenario from the AquaBlend
   MILP Configuration document). Used as the main regression / happy-path
   test for a full OPTIMAL report.

2. Synthetic fixtures - edge cases the reference JSON does not exercise:
   missing optional fields, estimated/provisional data disclosure,
   water-quality stage handling (`applies_to` present/missing), every
   supported status (OPTIMAL full report vs. non-optimal status-only
   output), and determinism (identical input -> identical output).
"""

import copy
import sys
from pathlib import Path

import pytest

EXPLANATIONS_DIR = Path(__file__).resolve().parent
if str(EXPLANATIONS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPLANATIONS_DIR))

from json_explainer import (
    ExplainerInputError,
    validate_input,
    explain_scenario_and_status,
    explain_result_availability,
    explain_demand_zones,
    explain_selected_sources,
    explain_unused_sources,
    explain_active_plants_and_transfers,
    explain_cost_summary,
    explain_water_quality,
    explain_binding_constraints,
    explain_sensitivity,
    explain_estimated_fields,
    explain_alternatives_and_sensitivity,
    generate_explanation,
    FULL_REPORT_STATUSES,
    PROTOTYPE_DISCLAIMER,
    WATER_QUALITY_STAGE_NOTE,
)


# ---------------------------------------------------------------------------
# REFERENCE_JSON is the Task 21-adapted form of Task 22's model_output_example.json fixture
# ---------------------------------------------------------------------------

REFERENCE_JSON = {
    "scenarioId": "scenario_2026_07_17_001",
    "solvedAt": "2026-07-17T10:32:00Z",
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
    "demandZones": [
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
    "transferPaths": {
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
    "waterQuality": {
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
    "bindingConstraintsSummary": ["demand_satisfaction_zone_1", "source_capacity_yarra_kew"],
    "alternativeFeasibleSolutions": [
        {
            "description": "Reduce Yarra Kew share to 45 percent and introduce Groundwater Bore 1 at 13 percent",
            "total_cost": 189400.00,
            "cost_difference_from_optimal": 5250.00,
            "notes": "Slightly higher cost, but reduces dependence on a single river source and adds redundancy if Yarra Kew availability drops",
        }
    ],
    "sensitivityToKeyAssumptions": [
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
    "dataFlags": {
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
# 1. Reference JSON - full OPTIMAL report, regression coverage
# ---------------------------------------------------------------------------

class TestReferenceJSON:

    def test_validate_input_passes(self):
        validate_input(ref())  # should not raise

    def test_scenario_and_status_section(self):
        text = explain_scenario_and_status(ref())
        assert "scenario_2026_07_17_001" in text
        assert "OPTIMAL" in text
        assert "2026-07-17T10:32:00Z" in text

    def test_result_availability_optimal(self):
        text = explain_result_availability(ref())
        assert "confirmed optimal solution" in text

    def test_demand_zones_section(self):
        text = explain_demand_zones(ref())
        assert "Zone 1" in text
        assert "required demand 500 ML/day" in text
        assert "supplied volume 500 ML/day" in text

    def test_selected_sources_reports_exact_values(self):
        text = explain_selected_sources(ref())
        assert "Yarra River, Kew" in text
        assert "290 ML/day" in text
        assert "58.0% of the blend" in text
        assert "$235 AUD" in text
        assert "(estimated)" in text  # yarra_kew has_estimated_values is True
        assert "Silvan Reservoir" in text
        assert "210 ML/day" in text
        assert "42.0% of the blend" in text
        assert "$400 AUD" in text
        assert "$84,000.0 AUD" in text  # draw_cost

    def test_selected_sources_never_invents_a_reason(self):
        """LLM_Report_Scope.md section 4 forbids the template from creating
        source-selection reasons - this must never appear again."""
        text = explain_selected_sources(ref())
        for banned in ["because", "cheapest", "lowest cost", "capacity remaining", "supplemented"]:
            assert banned not in text.lower()

    def test_unused_sources_never_renders_reason_field(self):
        """sources.unused[].reason ownership is unconfirmed
        (LLM_Report_Scope.md section 10) - must never be copied into the
        report, even when present in the input."""
        text = explain_unused_sources(ref())
        assert "Groundwater Bore 1 was not selected." in text
        assert "quality benefit" not in text
        assert "because" not in text.lower()

    def test_active_plants_and_transfers_section(self):
        text = explain_active_plants_and_transfers(ref())
        assert "Treatment Facility 1" in text
        assert "500 ML/day" in text
        assert "$64 AUD" in text  # treatment_cost_per_ml
        assert "$32,000.0 AUD" in text  # treatment_cost
        assert "Silvan Reservoir to Treatment Facility 1: 210 ML/day (active)" in text
        assert "Treatment Facility 1 to Zone 1: 500 ML/day (active)" in text

    def test_cost_summary_section(self):
        text = explain_cost_summary(ref())
        assert "$184,150.0 AUD" in text
        assert "cost for one representative day" in text
        assert "$152,150.0 AUD" in text  # source_draw_cost
        assert "$32,000.0 AUD" in text  # plant_treatment_cost

    def test_water_quality_applies_to_and_stage_note(self):
        text = explain_water_quality(ref())
        assert "apply to: blend_at_plant_inflow" in text
        assert "alkalinity was closest to its limit" in text
        assert "22.6%" in text
        assert "widest margin at facility_1 was on turbidity at 34.0%" in text
        assert WATER_QUALITY_STAGE_NOTE in text

    def test_water_quality_never_claims_final_or_safe(self):
        text = explain_water_quality(ref())
        for banned in ["final drinking", "safe to drink", "compliant", "treated water"]:
            assert banned not in text.lower()

    def test_binding_constraints_demand_and_capacity(self):
        text = explain_binding_constraints(ref())
        assert "water demand for zone_1" in text
        assert "500 ML needed by zone_1" in text
        assert "available capacity of Yarra River, Kew" in text
        assert "290 ML" in text

    def test_estimated_fields_lists_all_three_sources(self):
        text = explain_estimated_fields(ref())
        for fragment in ["silvan_reservoir", "yarra_kew", "groundwater_bore_1", "storage_capacity"]:
            assert fragment in text

    def test_estimated_fields_includes_notes(self):
        text = explain_estimated_fields(ref())
        assert "source_activation_cost is structurally 0.00" in text

    def test_sensitivity_reports_both_reference_assumptions(self):
        text = explain_sensitivity(ref())
        assert "cost_per_ml for groundwater_bore_1 (flagged estimated in the source view)" in text
        assert "groundwater_bore_1 would likely enter the optimal blend" in text
        assert "max_available_ml_per_day for yarra_kew" in text
        assert "model may become infeasible" in text

    def test_alternatives_and_sensitivity_section(self):
        text = explain_alternatives_and_sensitivity(ref())
        assert "Alternative feasible solutions" in text
        assert "Reduce Yarra Kew share to 45 percent" in text
        assert "189400.0" in text or "189400" in text
        assert "sensitive to cost_per_ml for groundwater_bore_1" in text

    def test_generate_explanation_has_all_full_report_sections(self):
        text = generate_explanation(ref())
        for heading in [
            "Scenario & Solver Status",
            "Result Availability",
            "Demand-Zone Results",
            "Selected Sources & Blend Ratios",
            "Unused Sources",
            "Active Plants & Transfer Results",
            "Cost Summary",
            "Plant-Inflow Water Quality",
            "Binding Constraints",
            "Data Flags & Estimated Values",
            "Alternatives & Sensitivity",
            "Prototype Disclaimer",
        ]:
            assert f"## {heading}" in text

    def test_generate_explanation_follows_report_structure_order(self):
        text = generate_explanation(ref())
        headings = [
            "Scenario & Solver Status", "Result Availability", "Demand-Zone Results",
            "Selected Sources & Blend Ratios", "Unused Sources",
            "Active Plants & Transfer Results", "Cost Summary",
            "Plant-Inflow Water Quality", "Binding Constraints",
            "Data Flags & Estimated Values", "Alternatives & Sensitivity",
            "Prototype Disclaimer",
        ]
        positions = [text.index(f"## {h}") for h in headings]
        assert positions == sorted(positions)

    def test_generate_explanation_never_uses_explanation_field_as_input(self):
        """The JSON's own `explanation` field must never be treated as a
        factual source (LLM_Report_Scope.md section 3)."""
        data = ref()
        text_with_field = generate_explanation(data)
        del data["explanation"]
        text_without_field = generate_explanation(data)
        assert text_with_field == text_without_field

    def test_prototype_disclaimer_always_present(self):
        text = generate_explanation(ref())
        assert PROTOTYPE_DISCLAIMER in text

    def test_matches_reference_explanation_in_substance(self):
        """Not exact wording - the same underlying facts as the JSON's own
        free-text explanation field (which is never read as input)."""
        text = generate_explanation(ref())
        assert "Silvan Reservoir" in text and "42.0%" in text
        assert "Yarra River, Kew" in text and "58.0%" in text
        assert "Groundwater Bore 1" in text
        assert "turbidity" in text


# ---------------------------------------------------------------------------
# 2. Required-field validation
# ---------------------------------------------------------------------------

class TestValidation:

    @pytest.mark.parametrize("field", ["status", "scenarioId"])
    def test_missing_required_field_raises(self, field):
        data = ref()
        del data[field]
        with pytest.raises(ExplainerInputError):
            validate_input(data)

    def test_non_dict_input_raises(self):
        with pytest.raises(ExplainerInputError):
            validate_input(["not", "a", "dict"])

    def test_missing_optional_top_level_fields_do_not_crash(self):
        data = ref()
        for field in ["objective", "dataFlags", "demandZones", "plants",
                      "transferPaths", "alternativeFeasibleSolutions",
                      "sensitivityToKeyAssumptions", "constraints"]:
            del data[field]
        text = generate_explanation(data)
        assert "Cost summary is unavailable" in text
        assert "No demand-zone result was provided" in text
        assert "No active-plant result was provided" in text


# ---------------------------------------------------------------------------
# 3. Status handling: OPTIMAL full report vs. non-optimal status-only
# ---------------------------------------------------------------------------

class TestStatusHandling:

    @pytest.mark.parametrize("status", ["INFEASIBLE", "UNBOUNDED", "TIME_LIMIT", "ERROR"])
    def test_non_optimal_status_is_status_only(self, status):
        data = ref()
        data["status"] = status
        text = generate_explanation(data)
        assert "## Scenario & Solver Status" in text
        assert "## Result Availability" in text
        assert "## Prototype Disclaimer" in text
        assert status in text
        assert "not confirmed as usable for a final recommendation" in text
        # None of the full-report-only sections should appear.
        for heading in [
            "Demand-Zone Results", "Selected Sources & Blend Ratios",
            "Unused Sources", "Active Plants & Transfer Results",
            "Cost Summary", "Plant-Inflow Water Quality", "Binding Constraints",
        ]:
            assert f"## {heading}" not in text

    def test_unknown_status_string_is_also_status_only(self):
        data = ref()
        data["status"] = "SOMETHING_NEW"
        text = generate_explanation(data)
        assert "## Cost Summary" not in text
        assert "SOMETHING_NEW" in text

    def test_optimal_is_the_only_full_report_status(self):
        assert FULL_REPORT_STATUSES == {"OPTIMAL"}

    def test_result_availability_missing_status(self):
        text = explain_result_availability({})
        assert "result state is unknown" in text


# ---------------------------------------------------------------------------
# 4. Demand-zone edge cases
# ---------------------------------------------------------------------------

class TestDemandZones:

    def test_empty_array(self):
        data = ref()
        data["demandZones"] = []
        assert explain_demand_zones(data) == "No demand-zone result was provided."

    def test_missing_field_entirely(self):
        data = ref()
        del data["demandZones"]
        assert explain_demand_zones(data) == "No demand-zone result was provided."

    def test_missing_zone_name_falls_back_to_zone_id(self):
        data = ref()
        del data["demandZones"][0]["zone_name"]
        text = explain_demand_zones(data)
        assert "zone_1" in text

    def test_missing_demand_value_states_not_reported(self):
        data = ref()
        del data["demandZones"][0]["demand_ml_per_day"]
        text = explain_demand_zones(data)
        assert "required demand not reported" in text


# ---------------------------------------------------------------------------
# 5. Selected-source edge cases
# ---------------------------------------------------------------------------

class TestSelectedSourcesEdgeCases:

    def test_empty_selected(self):
        data = ref()
        data["sources"]["selected"] = []
        assert explain_selected_sources(data) == "No selected-source result was provided."

    def test_missing_cost_per_ml_omits_cost_clause_not_a_guess(self):
        data = ref()
        del data["sources"]["selected"][0]["cost_per_ml"]  # silvan_reservoir
        text = explain_selected_sources(data)
        assert "Silvan Reservoir supplied 210 ML/day, 42.0% of the blend." in text
        assert "Cost per ML" not in text.split("Yarra")[0]

    def test_missing_source_name_falls_back_to_source_id(self):
        data = ref()
        del data["sources"]["selected"][1]["source_name"]  # yarra_kew
        text = explain_selected_sources(data)
        assert "yarra_kew" in text

    def test_currency_matches_objective_currency_not_hardcoded(self):
        data = ref()
        data["objective"]["currency"] = "NZD"
        text = explain_selected_sources(data)
        assert "NZD" in text
        assert "AUD" not in text

    def test_no_currency_when_objective_missing(self):
        data = ref()
        del data["objective"]
        text = explain_selected_sources(data)
        assert "$235" in text
        assert "AUD" not in text

    def test_estimated_tag_uses_clean_per_source_flag(self):
        data = ref()
        for entry in data["dataFlags"]["sources"]:
            if entry["source_id"] == "silvan_reservoir":
                entry["has_estimated_values"] = False
        text = explain_selected_sources(data)
        silvan_line = [l for l in text.split("\n\n") if "Silvan Reservoir" in l][0]
        assert "(estimated)" not in silvan_line


# ---------------------------------------------------------------------------
# 6. Unused-source edge cases
# ---------------------------------------------------------------------------

class TestUnusedSourcesEdgeCases:

    def test_empty_unused(self):
        data = ref()
        data["sources"]["unused"] = []
        assert explain_unused_sources(data) == "No unused-source result was provided."

    def test_missing_source_name_falls_back_to_source_id(self):
        data = ref()
        del data["sources"]["unused"][0]["source_name"]
        text = explain_unused_sources(data)
        assert "groundwater_bore_1 was not selected." in text

    def test_reason_absent_from_input_does_not_crash(self):
        data = ref()
        del data["sources"]["unused"][0]["reason"]
        text = explain_unused_sources(data)
        assert "Groundwater Bore 1 was not selected." in text


# ---------------------------------------------------------------------------
# 7. Active plants & transfer-results edge cases
# ---------------------------------------------------------------------------

class TestActivePlantsAndTransfersEdgeCases:

    def test_no_active_plants(self):
        data = ref()
        data["plants"]["active"] = []
        text = explain_active_plants_and_transfers(data)
        assert "No active-plant result was provided." in text

    def test_missing_transfer_paths_omits_transfer_subpart(self):
        data = ref()
        del data["transferPaths"]
        text = explain_active_plants_and_transfers(data)
        assert "Treatment Facility 1" in text
        assert "Transfer results" not in text

    def test_missing_plant_name_falls_back_to_plant_id(self):
        data = ref()
        del data["plants"]["active"][0]["plant_name"]
        text = explain_active_plants_and_transfers(data)
        assert "facility_1" in text


# ---------------------------------------------------------------------------
# 8. Cost-summary edge cases
# ---------------------------------------------------------------------------

class TestCostSummaryEdgeCases:

    def test_missing_objective(self):
        data = ref()
        del data["objective"]
        assert explain_cost_summary(data) == "Cost summary is unavailable."

    def test_missing_total_cost(self):
        data = ref()
        del data["objective"]["total_cost"]
        assert explain_cost_summary(data) == "Cost summary is unavailable."

    def test_missing_cost_breakdown_omits_breakdown_line(self):
        data = ref()
        del data["objective"]["cost_breakdown"]
        text = explain_cost_summary(data)
        assert "$184,150.0 AUD" in text
        assert "Cost breakdown" not in text


# ---------------------------------------------------------------------------
# 9. Water-quality: stage handling, applies_to, violations, missing data
# ---------------------------------------------------------------------------

class TestWaterQualityEdgeCases:

    def test_missing_applies_to_is_a_validation_warning(self):
        data = ref()
        del data["waterQuality"]["applies_to"]
        text = explain_water_quality(data)
        assert "Validation warning" in text
        assert "applies_to is missing" in text
        # Must not fall through to a normal quality interpretation.
        assert "PASS" not in text and "FAIL" not in text

    def test_empty_by_plant_returns_not_provided(self):
        data = ref()
        data["waterQuality"]["by_plant"] = {}
        assert explain_water_quality(data) == "No water-quality result was provided."

    def test_missing_water_quality_entirely(self):
        data = ref()
        del data["waterQuality"]
        assert explain_water_quality(data) == "No water-quality result was provided."

    def test_violation_reported_without_acceptability_claim(self):
        data = ref()
        data["waterQuality"]["by_plant"]["facility_1"]["turbidity"]["status"] = "FAIL"
        data["waterQuality"]["by_plant"]["facility_1"]["turbidity"]["safety_margin_percent"] = -4.5
        data["waterQuality"]["by_plant"]["facility_1"]["turbidity"]["value"] = 8.4
        text = explain_water_quality(data)
        assert "Not all plant-inflow blend quality parameters passed at facility_1" in text
        assert "turbidity breached its allowed range" in text
        assert "-4.5%" in text
        assert "acceptable" not in text.lower()

    def test_missing_parameter_flagged_not_assumed_pass(self):
        data = ref()
        del data["waterQuality"]["by_plant"]["facility_1"]["alkalinity"]
        text = explain_water_quality(data)
        assert "alkalinity at facility_1 was not reported in the results and could not be assessed" in text

    def test_multiple_plants_each_reported_separately(self):
        data = ref()
        data["waterQuality"]["by_plant"]["facility_2"] = {
            "pH": {"value": 7.0, "unit": "pH", "constraint_min": 6.5, "constraint_max": 8.5,
                   "status": "PASS", "safety_margin_percent": 33.3},
            "alkalinity": {"value": 40.0, "unit": "mg/L CaCO3", "constraint_min": 20, "constraint_max": 100,
                           "status": "PASS", "safety_margin_percent": 25.0},
            "turbidity": {"value": 3.0, "unit": "NTU", "constraint_min": 0, "constraint_max": 8.0,
                          "status": "PASS", "safety_margin_percent": 62.5},
        }
        text = explain_water_quality(data)
        assert "facility_1" in text
        assert "facility_2" in text

    def test_stage_note_present_even_on_violation(self):
        data = ref()
        data["waterQuality"]["by_plant"]["facility_1"]["turbidity"]["status"] = "FAIL"
        text = explain_water_quality(data)
        assert WATER_QUALITY_STAGE_NOTE in text


# ---------------------------------------------------------------------------
# 10. Binding-constraints edge cases
# ---------------------------------------------------------------------------

class TestBindingConstraintsEdgeCases:

    def test_empty_binding_list(self):
        data = ref()
        data["bindingConstraintsSummary"] = []
        text = explain_binding_constraints(data)
        assert text == "No binding inequality or ranged constraint was reported for this scenario."

    def test_missing_binding_field_adds_validation_warning(self):
        data = ref()
        del data["bindingConstraintsSummary"]
        text = explain_binding_constraints(data)
        assert "Validation warning" in text
        assert "bindingConstraintsSummary is missing" in text

    def test_unknown_constraint_name(self):
        data = ref()
        data["bindingConstraintsSummary"] = ["some_unrecognised_constraint"]
        text = explain_binding_constraints(data)
        assert "no plain-language mapping available" in text

    def test_plant_capacity_binding(self):
        data = ref()
        data["bindingConstraintsSummary"] = ["plant_capacity_facility_1"]
        text = explain_binding_constraints(data)
        assert "Treatment Facility 1" in text
        assert "500 ML" in text
        assert "batch" not in text.lower()

    def test_water_quality_range_binding(self):
        data = ref()
        data["bindingConstraintsSummary"] = ["quality_range_turbidity_facility_1"]
        text = explain_binding_constraints(data)
        assert "turbidity limit" in text
        assert "facility_1" in text
        assert "0" in text and "8.0" in text

    def test_link_capacity_source_to_plant_binding(self):
        data = ref()
        data["bindingConstraintsSummary"] = ["link_capacity_silvan_reservoir_to_facility_1"]
        text = explain_binding_constraints(data)
        assert "Silvan Reservoir" in text
        assert "Treatment Facility 1" in text
        assert "210 ML" in text
        assert "no plain-language mapping available" not in text

    def test_link_capacity_plant_to_zone_binding(self):
        data = ref()
        data["bindingConstraintsSummary"] = ["link_capacity_facility_1_to_zone_1"]
        text = explain_binding_constraints(data)
        assert "Treatment Facility 1" in text
        assert "Zone 1" in text
        assert "500 ML" in text

    def test_link_capacity_unknown_path_id_falls_back(self):
        data = ref()
        data["bindingConstraintsSummary"] = ["link_capacity_nonexistent_to_nowhere"]
        text = explain_binding_constraints(data)
        assert "no plain-language mapping available" in text

    def test_category_ordering_ignores_json_order(self):
        data = ref()
        data["bindingConstraintsSummary"] = [
            "quality_range_turbidity_facility_1", "demand_satisfaction_zone_1", "source_capacity_yarra_kew"
        ]
        text = explain_binding_constraints(data)
        assert text.index("water demand for zone_1") < text.index("available capacity of Yarra River, Kew")
        assert text.index("available capacity of Yarra River, Kew") < text.index("turbidity limit")

    def test_estimated_disclosure_reads_per_source_flag(self):
        text = explain_binding_constraints(ref())
        assert "(290 ML, estimated)" in text

    def test_missing_demand_ml_per_day_drops_clause_not_whole_sentence(self):
        data = ref()
        del data["demandZones"][0]["demand_ml_per_day"]
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
        data["bindingConstraintsSummary"] = ["plant_capacity_facility_1"]
        text = explain_binding_constraints(data)
        assert "was already treating as much as it can handle, leaving no spare capacity" in text
        assert "None" not in text

    def test_missing_quality_range_fields_drops_clause(self):
        data = ref()
        del data["waterQuality"]["by_plant"]["facility_1"]["turbidity"]["constraint_min"]
        data["bindingConstraintsSummary"] = ["quality_range_turbidity_facility_1"]
        text = explain_binding_constraints(data)
        assert "sat right at the edge of its modelled constraint range, so the blend" in text
        assert "None" not in text

    def test_missing_source_name_falls_back_to_source_id(self):
        data = ref()
        del data["sources"]["selected"][1]["source_name"]  # yarra_kew
        text = explain_binding_constraints(data)
        assert "yarra_kew" in text

    def test_missing_plant_name_falls_back_to_plant_id(self):
        data = ref()
        del data["plants"]["active"][0]["plant_name"]
        data["bindingConstraintsSummary"] = ["plant_capacity_facility_1"]
        text = explain_binding_constraints(data)
        assert "facility_1" in text

    def test_quality_never_discloses_estimated(self):
        data = ref()
        data["bindingConstraintsSummary"] = ["quality_range_turbidity_facility_1"]
        text = explain_binding_constraints(data)
        assert "estimated" not in text.lower()


# ---------------------------------------------------------------------------
# 11. Sensitivity section
# ---------------------------------------------------------------------------

class TestSensitivitySection:

    def test_missing_field_entirely(self):
        data = ref()
        del data["sensitivityToKeyAssumptions"]
        text = explain_sensitivity(data)
        assert text == "No sensitivity information was reported for this scenario."

    def test_empty_list(self):
        data = ref()
        data["sensitivityToKeyAssumptions"] = []
        text = explain_sensitivity(data)
        assert text == "No sensitivity information was reported for this scenario."

    def test_malformed_item_missing_impact_is_skipped_not_guessed(self):
        data = ref()
        data["sensitivityToKeyAssumptions"] = [{"assumption": "some assumption with no impact field"}]
        text = explain_sensitivity(data)
        assert text == "No sensitivity information was reported for this scenario."

    def test_malformed_item_missing_assumption_is_skipped_not_guessed(self):
        data = ref()
        data["sensitivityToKeyAssumptions"] = [{"impact": "some impact with no assumption field"}]
        text = explain_sensitivity(data)
        assert text == "No sensitivity information was reported for this scenario."


# ---------------------------------------------------------------------------
# 12. Estimated-fields / data-flags section
# ---------------------------------------------------------------------------

class TestEstimatedFieldsSection:

    def test_missing_data_flags_entirely_is_a_validation_warning(self):
        data = ref()
        del data["dataFlags"]
        text = explain_estimated_fields(data)
        assert "Validation warning" in text
        assert "dataFlags is missing" in text

    def test_present_but_empty_is_omitted_entirely(self):
        data = ref()
        data["dataFlags"]["sources"] = []
        data["dataFlags"]["notes"] = []
        assert explain_estimated_fields(data) is None

    def test_present_but_empty_section_absent_from_full_report(self):
        data = ref()
        data["dataFlags"]["sources"] = []
        data["dataFlags"]["notes"] = []
        text = generate_explanation(data)
        assert "## Data Flags & Estimated Values" not in text

    def test_missing_data_flags_section_present_in_full_report(self):
        data = ref()
        del data["dataFlags"]
        text = generate_explanation(data)
        assert "## Data Flags & Estimated Values" in text
        assert "Validation warning" in text

    def test_source_with_has_estimated_values_false_is_excluded(self):
        data = ref()
        data["dataFlags"]["sources"] = [
            {"source_id": "silvan_reservoir", "has_estimated_values": False,
             "availability_origin": "database", "provenance": {}}
        ]
        data["dataFlags"]["notes"] = []
        assert explain_estimated_fields(data) is None

    def test_notes_shown_even_with_no_estimated_sources(self):
        data = ref()
        data["dataFlags"]["sources"] = []
        text = explain_estimated_fields(data)
        assert "source_activation_cost is structurally 0.00" in text


# ---------------------------------------------------------------------------
# 13. Alternatives & sensitivity section (omit-when-both-empty behaviour)
# ---------------------------------------------------------------------------

class TestAlternativesAndSensitivitySection:

    def test_both_empty_is_omitted_entirely(self):
        data = ref()
        data["alternativeFeasibleSolutions"] = []
        data["sensitivityToKeyAssumptions"] = []
        assert explain_alternatives_and_sensitivity(data) is None

    def test_both_missing_is_omitted_entirely(self):
        data = ref()
        del data["alternativeFeasibleSolutions"]
        del data["sensitivityToKeyAssumptions"]
        assert explain_alternatives_and_sensitivity(data) is None

    def test_omitted_section_absent_from_full_report(self):
        data = ref()
        data["alternativeFeasibleSolutions"] = []
        data["sensitivityToKeyAssumptions"] = []
        text = generate_explanation(data)
        assert "## Alternatives & Sensitivity" not in text

    def test_only_alternatives_present(self):
        data = ref()
        data["sensitivityToKeyAssumptions"] = []
        text = explain_alternatives_and_sensitivity(data)
        assert "Alternative feasible solutions" in text
        assert "sensitive to" not in text

    def test_only_sensitivity_present(self):
        data = ref()
        data["alternativeFeasibleSolutions"] = []
        text = explain_alternatives_and_sensitivity(data)
        assert "Alternative feasible solutions" not in text
        assert "sensitive to" in text


# ---------------------------------------------------------------------------
# 14. Determinism: identical input must always produce identical text
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_repeated_calls_produce_identical_output(self):
        data = ref()
        outputs = {generate_explanation(copy.deepcopy(data)) for _ in range(5)}
        assert len(outputs) == 1

    def test_key_order_in_by_plant_does_not_change_output(self):
        """by_plant is a dict; explain_water_quality must sort its keys, so
        report order can never depend on whatever order an upstream
        producer happened to serialise plants in. Uses two plants so
        forward vs. reversed key order is a genuinely different input."""
        data = ref()
        data["waterQuality"]["by_plant"]["facility_0"] = copy.deepcopy(
            data["waterQuality"]["by_plant"]["facility_1"]
        )

        forward = generate_explanation(copy.deepcopy(data))

        reordered = copy.deepcopy(data)
        reordered["waterQuality"]["by_plant"] = dict(
            reversed(list(reordered["waterQuality"]["by_plant"].items()))
        )
        backward = generate_explanation(reordered)

        assert forward == backward

    def test_non_optimal_status_output_is_also_deterministic(self):
        data = ref()
        data["status"] = "INFEASIBLE"
        outputs = {generate_explanation(copy.deepcopy(data)) for _ in range(5)}
        assert len(outputs) == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

