"""
test_kpi_supabase_integration.py — Task 87 (Sprint 4)

Confirms kpi_calculator.py / kpi_gate.py still work correctly once the
Results JSON comes from the real `milp_model_output` table (Supabase),
not a hand-built canonical dict. This does NOT re-implement the
normalization logic - it imports and runs the real
supabase_repository.normalize_output_columns(), the same function
AI/main.py calls (via extract_canonical_output) before results ever
reach kpi_gate.evaluate().

No real captured `milp_model_output` row exists anywhere in this repo as
of Sprint 4 (checked master and every relevant branch). Every row here is
a synthetic dict built strictly from milp_model_output.sql's real column
names, not invented field names. Values reuse the same reference scenario
(scenario_2026_07_17_001) used throughout Sprint 1-3 for continuity and
easy cross-checking against reference_output.json's already-verified
numbers ($184,150 total cost, 42%/58% blend split).

Known limitation, documented rather than hidden: because no real row
exists, this cannot catch a case where a live column's actual JSON
sub-shape differs from what's assumed here (e.g. if `quality` in
production never has a `by_plant` key at all, or `sources` entries use a
different volume field name than `volume_drawn_ml_per_day`). Re-run this
suite against a real captured row the moment one is available.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase_repository import normalize_output_columns
from kpi_calculator import calculate_kpis
from kpi_gate import evaluate_gate


def _base_row(**overrides):
    """A synthetic milp_model_output row using the real column names from
    milp_model_output.sql. Only the columns normalize_output_columns()
    actually reads are populated; everything else the real table defines
    (loader_status, preprocessing_status, solve_time_ms, ...) is left out
    deliberately, since normalize_output_columns() doesn't read them -
    populating them here would imply they're used when they aren't.
    """
    row = {
        "scenario_id": "scenario_2026_07_17_001",
        "solver_status": "optimal",
        "total_cost": 184150.00,
        "solver_objective_value": 184150.00,
        "sources": [
            {
                "source_id": "silvan_reservoir", "source_name": "Silvan Reservoir",
                "source_type": "reservoir", "volume_drawn_ml_per_day": 210,
                "percent_of_blend": 42.0, "cost_per_ml": 400, "draw_cost": 84000.00,
            },
            {
                "source_id": "yarra_kew", "source_name": "Yarra River, Kew",
                "source_type": "river", "volume_drawn_ml_per_day": 290,
                "percent_of_blend": 58.0, "cost_per_ml": 235, "draw_cost": 68250.00,
            },
            {
                "source_id": "groundwater_bore_1", "source_name": "Groundwater Bore 1",
                "source_type": "groundwater", "volume_drawn_ml_per_day": 0, "selected": False,
            },
        ],
        "plants": [
            {
                "plant_id": "facility_1", "plant_name": "Treatment Facility 1",
                "volume_processed_ml_per_day": 500, "treatment_cost_per_ml": 64,
                "treatment_cost": 32000.00,
            }
        ],
        "demand_zones": [
            {
                "zone_id": "zone_1", "zone_name": "Zone 1",
                "demand_ml_per_day": 500, "volume_supplied_ml_per_day": 500,
            }
        ],
        "flows_source_to_plant": [],
        "flows_plant_to_zone": [],
        "quality": {
            "applies_to": "blend_at_plant_inflow",
            "by_plant": {
                "facility_1": {
                    "pH": {"value": 7.11, "unit": "pH", "constraint_min": 6.5,
                           "constraint_max": 8.5, "status": "PASS", "safety_margin_percent": 30.5},
                    "alkalinity": {"value": 38.04, "unit": "mg/L CaCO3", "constraint_min": 20,
                                   "constraint_max": 100, "status": "PASS", "safety_margin_percent": 22.6},
                    "turbidity": {"value": 5.28, "unit": "NTU", "constraint_min": 0,
                                  "constraint_max": 8.0, "status": "PASS", "safety_margin_percent": 34.0},
                }
            },
        },
        "binding_constraints_summary": ["demand_satisfaction_zone_1", "source_capacity_yarra_kew"],
        "warnings": [],
    }
    row.update(overrides)
    return row


class TestRealSchemaOptimalRowPasses:
    """The full path: a synthetic-but-real-column-named OPTIMAL row ->
    the real normalize_output_columns() -> the real KPI calculator and
    gate -> PASS. Cross-checked against the exact same numbers
    reference_output.json already established in Sprint 2/3.
    """

    def test_full_pipeline_matches_known_reference_numbers(self):
        canonical = normalize_output_columns(_base_row())
        report = calculate_kpis(canonical)
        gate = evaluate_gate(report)

        assert report.feasibility.value == "OPTIMAL"
        assert report.demand_satisfaction.value == 100.0
        assert report.total_cost.value == 184150.00
        assert report.minimum_safety_margin.value == 22.6
        assert report.quality_violations.value == 0
        assert gate.overall_status == "PASS"


class TestLowercaseSolverStatusNormalizesCorrectly:
    """milp_model_output.sql's real default is 'NOT_SOLVED'; the column
    comment and supabase_repository._normalize_status() confirm live
    values are stored lowercase (e.g. "optimal"), not uppercase. Confirms
    the uppercase conversion this module depends on actually happens
    before kpi_calculator ever sees the value.
    """

    def test_lowercase_optimal_becomes_feasible(self):
        canonical = normalize_output_columns(_base_row(solver_status="optimal"))
        assert canonical["status"] == "OPTIMAL"
        report = calculate_kpis(canonical)
        assert report.feasibility.status == "OK"
        assert report.feasibility.value == "OPTIMAL"

    def test_lowercase_infeasible_is_correctly_a_fail(self):
        row = _base_row(solver_status="infeasible", total_cost=None, solver_objective_value=None)
        canonical = normalize_output_columns(row)
        assert canonical["status"] == "INFEASIBLE"
        report = calculate_kpis(canonical)
        gate = evaluate_gate(report)
        assert gate.overall_status == "FAIL"


class TestDeprecatedStatusValuesAreNotSilentlyAccepted:
    """Sprint 4 finding: results_validator.py's VALID_STATUS still permits
    "SUCCESS" and "FEASIBLE", but Results_JSON_Field_Map.md (the confirmed
    contract) and llm_validator.py both treat these as deprecated
    placeholder values from an earlier draft schema. If the real
    `solver_status` column is ever populated with one of these (whether
    from old data or a producer that hasn't been updated), this module
    must not silently treat it as a good result.
    """

    @pytest.mark.parametrize("deprecated_status", ["success", "feasible"])
    def test_deprecated_status_value_is_unable_to_evaluate_not_pass(self, deprecated_status):
        row = _base_row(solver_status=deprecated_status)
        canonical = normalize_output_columns(row)
        report = calculate_kpis(canonical)
        gate = evaluate_gate(report)

        assert report.feasibility.status == "UNKNOWN"
        assert gate.overall_status == "UNABLE_TO_EVALUATE"


class TestNotSolvedDefaultIsHandledSafely:
    """milp_model_output.sql's solver_status column defaults to
    'NOT_SOLVED' (not null - every row has some string here). Confirms a
    freshly-created, not-yet-solved row is reported as unable to
    evaluate, never silently treated as any kind of pass or fail.
    """

    def test_not_solved_default_is_unable_to_evaluate(self):
        row = _base_row(solver_status="NOT_SOLVED", total_cost=None, solver_objective_value=None)
        canonical = normalize_output_columns(row)
        report = calculate_kpis(canonical)
        gate = evaluate_gate(report)

        assert report.feasibility.status == "UNKNOWN"
        assert gate.overall_status == "UNABLE_TO_EVALUATE"


class TestQualityColumnMissingByPlantKey:
    """normalize_output_columns() has a fallback for when the real
    `quality` column doesn't have a `by_plant` key: it assumes the whole
    column is already a per-plant mapping and nests it under `by_plant`
    itself. Unverified against a real row (see module docstring); this
    test only proves kpi_calculator handles the fallback's *output*
    shape correctly once normalize_output_columns has produced it.
    """

    def test_flat_quality_column_without_by_plant_still_works(self):
        row = _base_row()
        # Simulate quality already being a bare per-plant mapping, no
        # "applies_to"/"by_plant" wrapper - the case normalize_output_columns
        # falls back for.
        row["quality"] = {
            "facility_1": {
                "pH": {"value": 7.11, "unit": "pH", "constraint_min": 6.5,
                       "constraint_max": 8.5, "status": "PASS", "safety_margin_percent": 30.5},
                "alkalinity": {"value": 38.04, "unit": "mg/L CaCO3", "constraint_min": 20,
                               "constraint_max": 100, "status": "PASS", "safety_margin_percent": 22.6},
                "turbidity": {"value": 5.28, "unit": "NTU", "constraint_min": 0,
                              "constraint_max": 8.0, "status": "PASS", "safety_margin_percent": 34.0},
            }
        }
        canonical = normalize_output_columns(row)
        assert "by_plant" in canonical["water_quality"]
        report = calculate_kpis(canonical)
        assert report.minimum_safety_margin.status == "OK"
        assert report.minimum_safety_margin.value == 22.6


class TestRealCapturedRowFromMilpTeam:
    """Sprint 4 (Task 87): the actual real captured milp_model_output row,
    provided by the team, not synthetic. This is what exposed two real
    bugs in normalize_output_columns() (not this module's file, flagged
    to the team - see Task87_Migration_Notes.md) and confirmed the real
    field names for demand_zones and quality that this module now
    handles: delivered_ml_per_day/unmet_demand_ml_per_day (not
    demand_ml_per_day/volume_supplied_ml_per_day), and
    quality.plant_inflow[].parameters[] with model_value/model_min/
    model_max/within_limits (not by_plant/safety_margin_percent).
    """

    @staticmethod
    def _load_real_row():
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "fixtures", "milp_model_output_example.json"
        )
        with open(path) as f:
            return json.load(f)

    def test_real_row_produces_a_full_pass(self):
        canonical = normalize_output_columns(self._load_real_row())
        report = calculate_kpis(canonical)
        gate = evaluate_gate(report)

        assert report.feasibility.value == "OPTIMAL"
        assert report.demand_satisfaction.status == "OK"
        assert report.demand_satisfaction.value == 100.0
        assert report.total_cost.status == "OK"
        assert report.total_cost.value == 9300.0
        assert report.minimum_safety_margin.status == "OK"
        assert report.quality_violations.status == "OK"
        assert report.quality_violations.value == 0
        assert gate.overall_status == "PASS"

    def test_ph_margin_is_computed_in_model_units_not_reported_units(self):
        # The real row's pH entry: reported_value=7.5 (pH units), but
        # model_value=31.6227766... (hydrogen-ion nmol/L, via the
        # ph_to_hydrogen_ion transform). Confirms margin is computed in
        # model space: min(31.62-3.16, 316.23-31.62)/(316.23-3.16)*100 = 9.1,
        # not whatever the equivalent reported-pH-space margin would be.
        canonical = normalize_output_columns(self._load_real_row())
        report = calculate_kpis(canonical)
        assert report.minimum_safety_margin.value == 9.1

    def test_inactive_plant_is_correctly_excluded_despite_the_shared_bug(self):
        # Real row: PLANT_002 has activated=false. normalize_output_columns()
        # incorrectly puts it in plants.active anyway (Sprint 4 finding,
        # flagged to the team). This module must not be fooled by that -
        # PLANT_002 must not be required to have complete quality data.
        canonical = normalize_output_columns(self._load_real_row())
        # If PLANT_002 were incorrectly treated as active and required to
        # have quality data, this would come back INCOMPLETE instead of OK,
        # since PLANT_002 has no quality.plant_inflow entry of its own
        # beyond what PLANT_001 already supplies.
        report = calculate_kpis(canonical)
        assert report.minimum_safety_margin.status == "OK"
        assert report.quality_violations.status == "OK"
