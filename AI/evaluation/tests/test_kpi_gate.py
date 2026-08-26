"""
test_kpi_gate.py — Task 19 (Sprint 2)

Tests the overall PASS / FAIL / UNABLE_TO_EVALUATE gate logic in
kpi_gate.py, including against the real reference scenario.
"""

import json
import os

import pytest

from kpi_gate import evaluate


REFERENCE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reference_output.json")


@pytest.fixture
def reference():
    with open(REFERENCE_PATH) as f:
        return json.load(f)


def test_reference_scenario_passes(reference):
    report, gate = evaluate(reference)
    assert gate.overall_status == "PASS"


def test_infeasible_result_fails():
    results = {"status": "INFEASIBLE"}
    report, gate = evaluate(results)
    assert gate.overall_status == "FAIL"
    assert "INFEASIBLE" in gate.reasons[0]


def test_unbounded_result_fails():
    results = {"status": "UNBOUNDED"}
    _, gate = evaluate(results)
    assert gate.overall_status == "FAIL"


def test_missing_status_is_unable_to_evaluate():
    results = {}
    _, gate = evaluate(results)
    assert gate.overall_status == "UNABLE_TO_EVALUATE"


def test_time_limit_without_incumbent_is_unable_to_evaluate():
    results = {"status": "TIME_LIMIT"}
    _, gate = evaluate(results)
    assert gate.overall_status == "UNABLE_TO_EVALUATE"


def test_time_limit_with_verified_incumbent_passes_when_otherwise_complete():
    # Regression test for the bug flagged in review: previously this fell
    # through to UNABLE_TO_EVALUATE even though calculate_feasibility() had
    # already confirmed it feasible. End-to-end via evaluate(), covering the
    # exact path Abdulla/Amxntha flagged (gate, not just the calculator).
    results = {
        "status": "TIME_LIMIT",
        "incumbent_feasible": True,
        "demand_zones": [
            {"zone_id": "zone_1", "demand_ml_per_day": 500, "volume_supplied_ml_per_day": 500}
        ],
        "objective": {"total_cost": 150000.0, "currency": "AUD"},
        "plants": {"active": [{"plant_id": "facility_1"}]},
        "water_quality": {
            "by_plant": {
                "facility_1": {
                    "pH": {"status": "PASS", "safety_margin_percent": 30.5},
                    "alkalinity": {"status": "PASS", "safety_margin_percent": 22.6},
                    "turbidity": {"status": "PASS", "safety_margin_percent": 34.0},
                }
            }
        },
    }
    report, gate = evaluate(results)
    assert report.total_cost.status == "OK"
    assert report.total_cost.value == 150000.0
    assert gate.overall_status == "PASS"


def test_demand_below_100_percent_fails():
    results = {
        "status": "OPTIMAL",
        "demand_zones": [
            {"zone_id": "zone_1", "demand_ml_per_day": 500, "volume_supplied_ml_per_day": 480}
        ],
        "plants": {"active": [{"plant_id": "facility_1"}]},
        "water_quality": {
            "by_plant": {
                "facility_1": {
                    "pH": {"status": "PASS", "safety_margin_percent": 30.5},
                    "alkalinity": {"status": "PASS", "safety_margin_percent": 22.6},
                    "turbidity": {"status": "PASS", "safety_margin_percent": 34.0},
                }
            }
        },
    }
    _, gate = evaluate(results)
    assert gate.overall_status == "FAIL"
    assert any("96.0%" in r for r in gate.reasons)


def test_quality_violation_fails_even_with_full_demand():
    results = {
        "status": "OPTIMAL",
        "demand_zones": [
            {"zone_id": "zone_1", "demand_ml_per_day": 500, "volume_supplied_ml_per_day": 500}
        ],
        "plants": {"active": [{"plant_id": "facility_1"}]},
        "water_quality": {
            "by_plant": {
                "facility_1": {
                    "pH": {"status": "FAIL", "safety_margin_percent": -3.0},
                    "alkalinity": {"status": "PASS", "safety_margin_percent": 22.6},
                    "turbidity": {"status": "PASS", "safety_margin_percent": 34.0},
                }
            }
        },
    }
    _, gate = evaluate(results)
    assert gate.overall_status == "FAIL"
    assert any("violation" in r for r in gate.reasons)


def test_missing_demand_data_is_unable_to_evaluate_even_if_feasible():
    results = {"status": "OPTIMAL"}  # no demand_zones at all
    _, gate = evaluate(results)
    assert gate.overall_status == "UNABLE_TO_EVALUATE"


def test_incomplete_quality_data_is_unable_to_evaluate():
    results = {
        "status": "OPTIMAL",
        "demand_zones": [
            {"zone_id": "zone_1", "demand_ml_per_day": 500, "volume_supplied_ml_per_day": 500}
        ],
        "plants": {"active": [{"plant_id": "facility_1"}]},
        "water_quality": {
            "by_plant": {
                "facility_1": {"pH": {"status": "PASS", "safety_margin_percent": 30.5}}
                # alkalinity and turbidity missing
            }
        },
    }
    _, gate = evaluate(results)
    assert gate.overall_status == "UNABLE_TO_EVALUATE"


def test_cost_never_gates_the_result():
    # Two otherwise-identical feasible/complete results with very different
    # costs must both PASS — cost is comparative only, never a gate.
    base = {
        "status": "OPTIMAL",
        "demand_zones": [
            {"zone_id": "zone_1", "demand_ml_per_day": 500, "volume_supplied_ml_per_day": 500}
        ],
        "plants": {"active": [{"plant_id": "facility_1"}]},
        "water_quality": {
            "by_plant": {
                "facility_1": {
                    "pH": {"status": "PASS", "safety_margin_percent": 30.5},
                    "alkalinity": {"status": "PASS", "safety_margin_percent": 22.6},
                    "turbidity": {"status": "PASS", "safety_margin_percent": 34.0},
                }
            }
        },
    }
    cheap = {**base, "objective": {"total_cost": 1000.0, "currency": "AUD"}}
    expensive = {**base, "objective": {"total_cost": 999999.0, "currency": "AUD"}}
    _, gate_cheap = evaluate(cheap)
    _, gate_expensive = evaluate(expensive)
    assert gate_cheap.overall_status == "PASS"
    assert gate_expensive.overall_status == "PASS"
