"""Tests for AI/results/app_response/visualization.py (deterministic
chart-ready data for the App response)."""

from __future__ import annotations

import sys
from pathlib import Path

APP_RESPONSE_DIR = Path(__file__).resolve().parents[1] / "results" / "app_response"
if str(APP_RESPONSE_DIR) not in sys.path:
    sys.path.insert(0, str(APP_RESPONSE_DIR))

from visualization import build_visualization_data


RESULTS = {
    "objective": {
        "total_cost": 184150.0,
        "currency": "AUD",
        "cost_breakdown": {
            "source_activation_cost": 0.0,
            "plant_activation_cost": 0.0,
            "source_draw_cost": 152150.0,
            "plant_treatment_cost": 32000.0,
        },
    },
    "sources": {
        "selected": [
            {"source_id": "yarra_kew", "source_name": "Yarra River, Kew",
             "volume_drawn_ml_per_day": 290.0, "percent_of_blend": 58.0},
            {"source_id": "silvan_reservoir", "source_name": "Silvan Reservoir",
             "volume_drawn_ml_per_day": 210.0, "percent_of_blend": 42.0},
        ],
        "unused": [
            {"source_id": "groundwater_bore_1", "source_name": "Groundwater Bore 1"},
        ],
    },
    "water_quality": {
        "applies_to": "blend_at_plant_inflow",
        "by_plant": {
            "facility_1": {
                "alkalinity": {
                    "value": 38.04, "unit": "mg/L CaCO3", "constraint_min": 20,
                    "constraint_max": 100, "status": "PASS", "safety_margin_percent": 22.6,
                },
            },
        },
    },
    "alternative_feasible_solutions": [
        {"description": "Reduce Yarra Kew share to 45%", "total_cost": 189400.0},
    ],
}


def test_blend_ratios_use_real_source_values():
    data = build_visualization_data(RESULTS)
    ratios = {r["source"]: r for r in data["blend_ratios"]}
    assert ratios["Yarra River, Kew"]["volume_ml_day"] == 290.0
    assert ratios["Yarra River, Kew"]["share_pct"] == 58.0
    assert ratios["Silvan Reservoir"]["share_pct"] == 42.0


def test_cost_breakdown_omits_categories_not_reported():
    partial_results = {
        "objective": {
            "total_cost": 100.0,
            "cost_breakdown": {"source_draw_cost": 80.0},
        },
    }
    data = build_visualization_data(partial_results)
    categories = {c["category"] for c in data["cost_breakdown"]}
    assert categories == {"Source draw cost"}


def test_quality_margins_include_status_and_bounds():
    data = build_visualization_data(RESULTS)
    margin = data["quality_margins"][0]
    assert margin["parameter"] == "alkalinity"
    assert margin["margin_pct"] == 22.6
    assert margin["status"] == "PASS"
    assert margin["limit_min"] == 20
    assert margin["limit_max"] == 100


def test_solution_costs_include_optimal_and_alternatives():
    data = build_visualization_data(RESULTS)
    solutions = {s["solution"]: s["amount_aud"] for s in data["solution_costs"]}
    assert solutions["Optimal"] == 184150.0
    assert solutions["Alternative 1"] == 189400.0


def test_solution_costs_use_short_labels_not_the_full_description():
    """The chart label must be short ('Alternative 1'), never the complete
    alternative description - but the full description is still available
    separately in the JSON for anything that wants to display it."""
    data = build_visualization_data(RESULTS)
    optimal, alternative = data["solution_costs"]

    assert optimal["solution"] == "Optimal"
    assert optimal["description"] is None

    assert alternative["solution"] == "Alternative 1"
    assert alternative["description"] == "Reduce Yarra Kew share to 45%"
    assert alternative["solution"] != alternative["description"]


def test_multiple_alternatives_are_numbered_in_order():
    results = {
        "objective": {"total_cost": 100.0},
        "alternative_feasible_solutions": [
            {"description": "First alternative", "total_cost": 110.0},
            {"description": "Second alternative", "total_cost": 120.0},
        ],
    }
    data = build_visualization_data(results)
    solutions = {s["solution"]: s for s in data["solution_costs"]}

    assert solutions["Alternative 1"]["description"] == "First alternative"
    assert solutions["Alternative 1"]["amount_aud"] == 110.0
    assert solutions["Alternative 2"]["description"] == "Second alternative"
    assert solutions["Alternative 2"]["amount_aud"] == 120.0


def test_alternative_without_a_description_still_gets_a_short_label():
    results = {
        "objective": {"total_cost": 100.0},
        "alternative_feasible_solutions": [{"total_cost": 150.0}],
    }
    data = build_visualization_data(results)
    alternative = data["solution_costs"][1]
    assert alternative["solution"] == "Alternative 1"
    assert alternative["description"] is None


def test_unknown_values_are_omitted_or_null_never_zero():
    results = {
        "objective": {"total_cost": None, "cost_breakdown": {}},
        "sources": {
            "selected": [
                {"source_id": "a", "source_name": "A"},  # no volume/percent reported
            ],
        },
        "water_quality": {
            "by_plant": {
                "facility_1": {
                    "pH": {"value": None, "constraint_min": None, "constraint_max": None,
                           "safety_margin_percent": None, "status": None},
                },
            },
        },
    }

    data = build_visualization_data(results)

    ratio = data["blend_ratios"][0]
    assert ratio["volume_ml_day"] is None
    assert ratio["share_pct"] is None
    assert ratio["volume_ml_day"] != 0
    assert ratio["share_pct"] != 0

    assert data["cost_breakdown"] == []  # nothing reported, nothing invented
    assert data["solution_costs"] == []  # total_cost unknown -> omitted, not $0

    margin = data["quality_margins"][0]
    assert margin["value"] is None
    assert margin["margin_pct"] is None


def test_no_source_data_at_all_returns_none():
    assert build_visualization_data({}) is None
    assert build_visualization_data("not a dict") is None
