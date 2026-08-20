"""
test_kpi_calculator.py — Task 19 (Sprint 2)

Validates kpi_calculator.py against:
  1. The real model_output_contract.json reference scenario
     (scenario_2026_07_17_001), cross-checked against KPI_Set.md §5's own
     manual calculation table — this is the "match the Sprint 1 sample
     calculations" requirement from the Task 19 checklist.
  2. Synthetic infeasible, missing-data, incomplete-data, and edge cases.
"""

import copy
import json
import os

import pytest

from kpi_calculator import (
    calculate_kpis,
    calculate_feasibility,
    calculate_demand_satisfaction,
    calculate_total_cost,
    calculate_minimum_safety_margin,
    calculate_quality_violations,
    calculate_chemical_kpi,
)


REFERENCE_PATH = os.path.join(os.path.dirname(__file__), "reference_output.json")


@pytest.fixture
def reference():
    with open(REFERENCE_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Reference scenario — must match KPI_Set.md §5's manual calculation table
# ---------------------------------------------------------------------------
class TestReferenceScenarioMatchesKPISet:
    """KPI_Set.md §5 states these exact results for scenario_2026_07_17_001:
    Feasible/OPTIMAL; 100%; AUD 184,150; 22.6%; 0 violations; chemical N/A.
    """

    def test_feasibility(self, reference):
        result = calculate_feasibility(reference)
        assert result.status == "OK"
        assert result.value == "OPTIMAL"

    def test_demand_satisfaction(self, reference):
        result = calculate_demand_satisfaction(reference)
        assert result.status == "OK"
        assert result.value == 100.0

    def test_total_cost(self, reference):
        feas = calculate_feasibility(reference)
        result = calculate_total_cost(reference, feas)
        assert result.status == "OK"
        assert result.value == 184150.00
        assert result.unit == "AUD"

    def test_minimum_safety_margin(self, reference):
        # MIN(30.5, 22.6, 34.0) = 22.6, per the reference JSON's three
        # water_quality parameters at facility_1.
        result = calculate_minimum_safety_margin(reference)
        assert result.status == "OK"
        assert result.value == 22.6

    def test_quality_violations(self, reference):
        result = calculate_quality_violations(reference)
        assert result.status == "OK"
        assert result.value == 0

    def test_chemical_kpi_is_na(self, reference):
        result = calculate_chemical_kpi(reference)
        assert result.status == "N/A"

    def test_full_report_matches_kpi_set_table(self, reference):
        report = calculate_kpis(reference)
        assert report.scenario_id == "scenario_2026_07_17_001"
        assert report.feasibility.value == "OPTIMAL"
        assert report.demand_satisfaction.value == 100.0
        assert report.total_cost.value == 184150.00
        assert report.minimum_safety_margin.value == 22.6
        assert report.quality_violations.value == 0
        assert report.chemical_kpi.status == "N/A"


# ---------------------------------------------------------------------------
# 2. Feasibility statuses (KPI_Set.md §4, KPI 1)
# ---------------------------------------------------------------------------
class TestFeasibility:
    def test_optimal(self):
        r = calculate_feasibility({"status": "OPTIMAL"})
        assert r.status == "OK" and r.value == "OPTIMAL"

    def test_feasible(self):
        r = calculate_feasibility({"status": "FEASIBLE"})
        assert r.status == "OK" and r.value == "FEASIBLE"

    def test_infeasible(self):
        r = calculate_feasibility({"status": "INFEASIBLE"})
        assert r.status == "OK" and r.value == "INFEASIBLE"

    def test_unbounded(self):
        r = calculate_feasibility({"status": "UNBOUNDED"})
        assert r.status == "OK" and r.value == "UNBOUNDED"

    def test_error(self):
        r = calculate_feasibility({"status": "ERROR"})
        assert r.status == "OK" and r.value == "ERROR"

    def test_time_limit_without_incumbent_field_is_unknown(self):
        r = calculate_feasibility({"status": "TIME_LIMIT"})
        assert r.status == "UNKNOWN"

    def test_time_limit_with_verified_incumbent_is_ok(self):
        r = calculate_feasibility({"status": "TIME_LIMIT", "incumbent_feasible": True})
        assert r.status == "OK"
        assert r.value == "TIME_LIMIT_FEASIBLE_INCUMBENT"

    def test_missing_status_is_unknown(self):
        r = calculate_feasibility({})
        assert r.status == "UNKNOWN"

    def test_unrecognised_status_is_unknown(self):
        r = calculate_feasibility({"status": "SOMETHING_NEW"})
        assert r.status == "UNKNOWN"


# ---------------------------------------------------------------------------
# 3. Demand satisfaction (KPI_Set.md §4, KPI 2)
# ---------------------------------------------------------------------------
class TestDemandSatisfaction:
    def test_below_100_percent(self):
        results = {
            "demand_zones": [
                {"zone_id": "zone_1", "demand_ml_per_day": 500, "volume_supplied_ml_per_day": 450}
            ]
        }
        r = calculate_demand_satisfaction(results)
        assert r.status == "OK"
        assert r.value == 90.0

    def test_excess_supply_over_100_percent_is_legal(self):
        results = {
            "demand_zones": [
                {"zone_id": "zone_1", "demand_ml_per_day": 500, "volume_supplied_ml_per_day": 520}
            ]
        }
        r = calculate_demand_satisfaction(results)
        assert r.status == "OK"
        assert r.value == 104.0

    def test_multiple_zones_summed(self):
        results = {
            "demand_zones": [
                {"zone_id": "zone_1", "demand_ml_per_day": 300, "volume_supplied_ml_per_day": 300},
                {"zone_id": "zone_2", "demand_ml_per_day": 200, "volume_supplied_ml_per_day": 150},
            ]
        }
        r = calculate_demand_satisfaction(results)
        assert r.status == "OK"
        assert r.value == 90.0  # (300+150)/(300+200)*100

    def test_missing_zones_is_na(self):
        r = calculate_demand_satisfaction({})
        assert r.status == "N/A"

    def test_missing_field_in_one_zone_is_na_not_zero(self):
        results = {
            "demand_zones": [
                {"zone_id": "zone_1", "demand_ml_per_day": 500},  # no volume_supplied_ml_per_day
            ]
        }
        r = calculate_demand_satisfaction(results)
        assert r.status == "N/A"

    def test_zero_total_demand_is_na(self):
        results = {
            "demand_zones": [
                {"zone_id": "zone_1", "demand_ml_per_day": 0, "volume_supplied_ml_per_day": 0}
            ]
        }
        r = calculate_demand_satisfaction(results)
        assert r.status == "N/A"


# ---------------------------------------------------------------------------
# 4. Total cost (KPI_Set.md §4, KPI 3)
# ---------------------------------------------------------------------------
class TestTotalCost:
    def test_ok_when_feasible_and_present(self):
        feas = calculate_feasibility({"status": "OPTIMAL"})
        results = {"objective": {"total_cost": 100000.0, "currency": "AUD"}}
        r = calculate_total_cost(results, feas)
        assert r.status == "OK"
        assert r.value == 100000.0

    def test_na_when_infeasible_even_if_value_present(self):
        # This is the specific rule from KPI_Set.md: "report N/A ... even if
        # the solver output contains a temporary objective value."
        feas = calculate_feasibility({"status": "INFEASIBLE"})
        results = {"objective": {"total_cost": 999999.0, "currency": "AUD"}}
        r = calculate_total_cost(results, feas)
        assert r.status == "N/A"

    def test_ok_for_time_limit_with_verified_incumbent(self):
        # Regression test for the bug flagged in review: a verified TIME_LIMIT
        # incumbent is confirmed feasible by calculate_feasibility() and must
        # be treated as such here too, not silently fall back to N/A.
        feas = calculate_feasibility({"status": "TIME_LIMIT", "incumbent_feasible": True})
        results = {"objective": {"total_cost": 150000.0, "currency": "AUD"}}
        r = calculate_total_cost(results, feas)
        assert r.status == "OK"
        assert r.value == 150000.0

    def test_na_when_missing(self):
        feas = calculate_feasibility({"status": "OPTIMAL"})
        r = calculate_total_cost({}, feas)
        assert r.status == "N/A"


# ---------------------------------------------------------------------------
# 5. Minimum safety margin & quality violations (KPI_Set.md §4, KPI 4 & 5)
# ---------------------------------------------------------------------------
class TestQualityKPIs:
    def _results_with_plants(self, active_plant_ids, by_plant):
        return {
            "plants": {"active": [{"plant_id": pid} for pid in active_plant_ids]},
            "water_quality": {"by_plant": by_plant},
        }

    def test_all_pass_zero_violations(self):
        results = self._results_with_plants(
            ["facility_1"],
            {
                "facility_1": {
                    "pH": {"status": "PASS", "safety_margin_percent": 30.5},
                    "alkalinity": {"status": "PASS", "safety_margin_percent": 22.6},
                    "turbidity": {"status": "PASS", "safety_margin_percent": 34.0},
                }
            },
        )
        margin = calculate_minimum_safety_margin(results)
        violations = calculate_quality_violations(results)
        assert margin.status == "OK" and margin.value == 22.6
        assert violations.status == "OK" and violations.value == 0

    def test_one_fail_counts_as_one_violation(self):
        results = self._results_with_plants(
            ["facility_1"],
            {
                "facility_1": {
                    "pH": {"status": "FAIL", "safety_margin_percent": -5.0},
                    "alkalinity": {"status": "PASS", "safety_margin_percent": 22.6},
                    "turbidity": {"status": "PASS", "safety_margin_percent": 34.0},
                }
            },
        )
        violations = calculate_quality_violations(results)
        assert violations.status == "OK" and violations.value == 1

    def test_negative_margin_without_status_counts_as_violation(self):
        # KPI_Set.md §4 KPI 5: fallback rule when status is absent.
        results = self._results_with_plants(
            ["facility_1"],
            {"facility_1": {"pH": {"safety_margin_percent": -2.0}}},
        )
        violations = calculate_quality_violations(results)
        assert violations.value == 1

    def test_no_quality_data_is_na_for_both(self):
        results = self._results_with_plants(["facility_1"], {})
        margin = calculate_minimum_safety_margin(results)
        violations = calculate_quality_violations(results)
        assert margin.status == "N/A"
        assert violations.status == "N/A"

    def test_missing_parameter_on_active_plant_is_incomplete(self):
        # facility_1 is active but only reports pH, not alkalinity/turbidity.
        results = self._results_with_plants(
            ["facility_1"],
            {"facility_1": {"pH": {"status": "PASS", "safety_margin_percent": 30.5}}},
        )
        margin = calculate_minimum_safety_margin(results)
        violations = calculate_quality_violations(results)
        assert margin.status == "INCOMPLETE"
        assert violations.status == "INCOMPLETE"

    def test_active_plant_entirely_absent_from_water_quality_is_incomplete(self):
        results = self._results_with_plants(
            ["facility_1", "facility_2"],
            {
                "facility_1": {
                    "pH": {"status": "PASS", "safety_margin_percent": 30.5},
                    "alkalinity": {"status": "PASS", "safety_margin_percent": 22.6},
                    "turbidity": {"status": "PASS", "safety_margin_percent": 34.0},
                }
                # facility_2 missing entirely
            },
        )
        margin = calculate_minimum_safety_margin(results)
        assert margin.status == "INCOMPLETE"


# ---------------------------------------------------------------------------
# 6. Chemical KPI (KPI_Set.md §4, KPI 6)
# ---------------------------------------------------------------------------
class TestChemicalKPI:
    def test_always_na_with_no_approved_field(self):
        # Even if a plausible-looking field is present, it must not be used
        # unless explicitly whitelisted (never invented from treatment cost).
        results = {"plants": {"active": [{"treatment_cost": 32000.0}]}}
        r = calculate_chemical_kpi(results)
        assert r.status == "N/A"
