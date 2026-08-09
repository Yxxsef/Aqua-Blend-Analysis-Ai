"""
test_baseline_equal_blend.py

AquaBlend | Analysis & AI | Sprint 2 | Task 15

Three families of tests:

1. Sprint 1 agreement - the toy configuration from `Baseline_HandCalculations.md`
   section 5, checked against the hand-calculated 220 / 220 / 60 split and its
   cost figures within the tolerance stated below.
2. Rule behaviour - normal, capacity-limited (single and multi-round
   redistribution), and infeasible cases, plus zero demand, exclusion rules,
   the rounding rule, and the contract checks the Sprint 1 rule does not cover.
3. Committed scenario files - the baseline is run against the team's real
   `scenario_normal.json` and `scenario_plant_outage.json` so a change to those
   files cannot silently break it.

Run from anywhere:

    python3 -m pytest AI/tests/test_baseline_equal_blend.py -v
"""

import copy
import json
import sys
from pathlib import Path

import pytest

# The module under test lives in a sibling folder, so put it on the import path
# before importing it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "baselines"))

from baseline_equal_blend import (  # noqa: E402
    BaselineInputError,
    allocate_equal_blend,
    run_equal_blend,
)

# Accepted tolerance for "matches the Sprint 1 manual example". Volumes and
# percentages are reported to one decimal place, so half of that last place is
# the tightest meaningful bound; money is reported to two.
VOLUME_TOLERANCE = 0.05
PERCENT_TOLERANCE = 0.05
COST_TOLERANCE = 0.01

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "scenarios"


# ---------------------------------------------------------------------------
# Toy configuration, in the MILP inline scenario shape
# (MILP/docs/data_loader.md section 2.2). Sources, capacities and demand are
# the confirmed toy-model values recorded in Baseline_HandCalculations.md
# section 2; groundwater_bore_1 has no confirmed cost, so it carries none here
# rather than an invented figure.
# ---------------------------------------------------------------------------

TOY_SCENARIO = {
    "scenario_id": "toy_model_equal_blend_test",
    "scenario_name": "Equal-blend baseline test configuration",
    "status": "test",
    "data_source": {
        "type": "inline",
        "source_rows": [
            {
                "source_id": "silvan_reservoir",
                "source_name": "Silvan Reservoir",
                "source_type": "reservoir",
                "is_active": True,
                "max_available_ml_per_day": None,
                "cost_per_ml": 400,
            },
            {
                "source_id": "yarra_kew",
                "source_name": "Yarra River, Kew",
                "source_type": "river",
                "is_active": True,
                "max_available_ml_per_day": None,
                "cost_per_ml": 235,
            },
            {
                "source_id": "groundwater_bore_1",
                "source_name": "Groundwater Bore 1",
                "source_type": "groundwater",
                "is_active": True,
                "max_available_ml_per_day": None,
                "cost_per_ml": None,
            },
        ],
    },
    "sources": [
        {"source_id": "silvan_reservoir", "enabled": True, "forced_inactive": False},
        {"source_id": "yarra_kew", "enabled": True, "forced_inactive": False},
        {"source_id": "groundwater_bore_1", "enabled": True, "forced_inactive": False},
    ],
    "network": {
        "plants": [
            {
                "plant_id": "facility_1",
                "name": "Treatment Facility 1",
                "enabled": True,
                "minimum_processing_capacity_ml_per_day": 0,
                "maximum_processing_capacity_ml_per_day": 600,
                "treatment_cost_per_ml": 64,
            }
        ],
        "demand_zones": [
            {"zone_id": "zone_1", "name": "Zone 1", "demand_ml_per_day": 500}
        ],
        "source_to_plant_links": [
            {
                "source_id": "silvan_reservoir",
                "plant_id": "facility_1",
                "enabled": True,
                "maximum_flow_ml_per_day": 350,
            },
            {
                "source_id": "yarra_kew",
                "plant_id": "facility_1",
                "enabled": True,
                "maximum_flow_ml_per_day": 300,
            },
            {
                "source_id": "groundwater_bore_1",
                "plant_id": "facility_1",
                "enabled": True,
                "maximum_flow_ml_per_day": 60,
            },
        ],
        "plant_to_zone_links": [
            {
                "plant_id": "facility_1",
                "zone_id": "zone_1",
                "enabled": True,
                "maximum_flow_ml_per_day": 600,
            }
        ],
    },
}


@pytest.fixture
def scenario():
    return copy.deepcopy(TOY_SCENARIO)


def selected_by_id(result):
    return {s["source_id"]: s for s in result["sources"]["selected"]}


def unused_by_id(result):
    return {s["source_id"]: s for s in result["sources"]["unused"]}


# ---------------------------------------------------------------------------
# 1. Agreement with the Sprint 1 hand calculation
# ---------------------------------------------------------------------------


def test_matches_sprint1_volumes(scenario):
    """Baseline_HandCalculations.md section 5: 220 / 220 / 60."""
    selected = selected_by_id(run_equal_blend(scenario))
    expected = {"silvan_reservoir": 220.0, "yarra_kew": 220.0, "groundwater_bore_1": 60.0}
    for source_id, volume in expected.items():
        assert selected[source_id]["volume_drawn_ml_per_day"] == pytest.approx(
            volume, abs=VOLUME_TOLERANCE
        )


def test_matches_sprint1_blend_shares(scenario):
    """Baseline_EqualBlend.md section 3: 44.0% / 44.0% / 12.0%."""
    selected = selected_by_id(run_equal_blend(scenario))
    expected = {"silvan_reservoir": 44.0, "yarra_kew": 44.0, "groundwater_bore_1": 12.0}
    for source_id, percent in expected.items():
        assert selected[source_id]["percent_of_blend"] == pytest.approx(
            percent, abs=PERCENT_TOLERANCE
        )
    assert sum(s["percent_of_blend"] for s in run_equal_blend(scenario)["sources"]["selected"]) == pytest.approx(100.0, abs=PERCENT_TOLERANCE)


def test_matches_sprint1_capacity_usage(scenario):
    """Baseline_HandCalculations.md section 5: 62.9% / 73.3% / 100.0%."""
    selected = selected_by_id(run_equal_blend(scenario))
    expected = {"silvan_reservoir": 62.9, "yarra_kew": 73.3, "groundwater_bore_1": 100.0}
    for source_id, usage in expected.items():
        assert selected[source_id]["capacity_usage_percent"] == pytest.approx(
            usage, abs=PERCENT_TOLERANCE
        )


def test_matches_sprint1_costs(scenario):
    """Section 5: 88,000 + 51,700 = 139,700 source cost, 32,000 treatment,
    171,700 total, with groundwater_bore_1's contribution a genuine unknown."""
    result = run_equal_blend(scenario)
    selected = selected_by_id(result)

    assert selected["silvan_reservoir"]["draw_cost"] == pytest.approx(88000.00, abs=COST_TOLERANCE)
    assert selected["yarra_kew"]["draw_cost"] == pytest.approx(51700.00, abs=COST_TOLERANCE)
    assert selected["groundwater_bore_1"]["draw_cost"] is None

    objective = result["objective"]
    assert objective["cost_breakdown"]["plant_treatment_cost"] == pytest.approx(32000.00, abs=COST_TOLERANCE)
    assert objective["total_cost_lower_bound"] == pytest.approx(171700.00, abs=COST_TOLERANCE)


def test_unknown_cost_is_flagged_not_invented(scenario):
    """KPI 3 forbids reconstructing a total from partial cost fields, so an
    incomplete total reads as null, never as the known part alone."""
    objective = run_equal_blend(scenario)["objective"]

    assert objective["cost_is_complete"] is False
    assert objective["sources_missing_cost"] == ["groundwater_bore_1"]
    assert objective["total_cost"] is None
    assert objective["cost_breakdown"]["source_draw_cost"] is None
    assert objective["currency"] == "AUD"


def test_complete_cost_data_produces_a_real_total(scenario):
    """With every cost known the total is reported outright and agrees with the
    lower bound: 139,700 + 60 x 500 = 169,700 source cost, plus 32,000."""
    scenario["data_source"]["source_rows"][2]["cost_per_ml"] = 500

    objective = run_equal_blend(scenario)["objective"]
    assert objective["cost_is_complete"] is True
    assert objective["sources_missing_cost"] == []
    assert objective["cost_breakdown"]["source_draw_cost"] == pytest.approx(169700.00, abs=COST_TOLERANCE)
    assert objective["total_cost"] == pytest.approx(201700.00, abs=COST_TOLERANCE)
    assert objective["total_cost_lower_bound"] == pytest.approx(201700.00, abs=COST_TOLERANCE)


def test_feasible_and_fully_supplied(scenario):
    result = run_equal_blend(scenario)
    assert result["status"] == "FEASIBLE"
    assert result["feasible"] is True
    assert result["unmet_demand_ml_per_day"] == 0.0
    zone = result["demand_zones"][0]
    assert zone["volume_supplied_ml_per_day"] == pytest.approx(500.0, abs=VOLUME_TOLERANCE)
    assert zone["demand_ml_per_day"] == pytest.approx(500.0, abs=VOLUME_TOLERANCE)


def test_never_reports_optimal(scenario):
    """A heuristic must not borrow the solver's OPTIMAL status."""
    assert run_equal_blend(scenario)["status"] in {"FEASIBLE", "INFEASIBLE"}


# ---------------------------------------------------------------------------
# 2. Capacity resolution, including the Task 5 section 3 open item
# ---------------------------------------------------------------------------


def test_capacity_is_the_tighter_of_withdrawal_and_link(scenario):
    """Baseline_HandCalculations.md section 3 leaves it open whether yarra_kew's
    capacity is the link's 300 or the source's 290. min() of the two settles it
    without a ruling, and equal-blend is unaffected either way because 220 sits
    below both."""
    rows = scenario["data_source"]["source_rows"]
    next(r for r in rows if r["source_id"] == "yarra_kew")["max_available_ml_per_day"] = 290

    selected = selected_by_id(run_equal_blend(scenario))
    assert selected["yarra_kew"]["capacity_ml_per_day"] == pytest.approx(290.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(220.0, abs=VOLUME_TOLERANCE)


def test_withdrawal_limit_can_bind_below_the_link_limit(scenario):
    """When the source-side limit is the tighter one, it governs."""
    rows = scenario["data_source"]["source_rows"]
    next(r for r in rows if r["source_id"] == "silvan_reservoir")["max_available_ml_per_day"] = 100

    selected = selected_by_id(run_equal_blend(scenario))
    assert selected["silvan_reservoir"]["capacity_ml_per_day"] == pytest.approx(100.0, abs=VOLUME_TOLERANCE)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(100.0, abs=VOLUME_TOLERANCE)


def test_scenario_override_beats_the_source_row(scenario):
    """MILP/docs/data_loader.md section 3.1 precedence."""
    rows = scenario["data_source"]["source_rows"]
    next(r for r in rows if r["source_id"] == "silvan_reservoir")["max_available_ml_per_day"] = 300
    scenario["sources"][0]["maximum_withdrawal_ml_per_day_override"] = 120

    selected = selected_by_id(run_equal_blend(scenario))
    assert selected["silvan_reservoir"]["capacity_ml_per_day"] == pytest.approx(120.0, abs=VOLUME_TOLERANCE)


def test_legacy_max_available_override_is_accepted(scenario):
    scenario["sources"][0]["max_available_ml_per_day_override"] = 90
    selected = selected_by_id(run_equal_blend(scenario))
    assert selected["silvan_reservoir"]["capacity_ml_per_day"] == pytest.approx(90.0, abs=VOLUME_TOLERANCE)


def test_missing_withdrawal_limit_is_warned_about(scenario):
    """The MILP loader requires the value; falling back to link limits alone is
    recorded rather than passed off as complete input."""
    warnings = run_equal_blend(scenario)["warnings"]
    assert sum("no maximum_withdrawal_ml_per_day" in w for w in warnings) == 3


# ---------------------------------------------------------------------------
# 3. Redistribution, infeasibility and edge cases
# ---------------------------------------------------------------------------


def test_capacity_limited_single_redistribution_round(scenario):
    """The Sprint 1 example itself: one source capped, one redistribution."""
    selected = selected_by_id(run_equal_blend(scenario))
    assert selected["groundwater_bore_1"]["volume_drawn_ml_per_day"] == pytest.approx(60.0, abs=VOLUME_TOLERANCE)
    assert selected["groundwater_bore_1"]["capacity_usage_percent"] == pytest.approx(100.0, abs=PERCENT_TOLERANCE)


def test_capacity_limited_multiple_redistribution_rounds(scenario):
    """700 ML across 350/300/60 caps: groundwater caps first (60), then
    yarra_kew (300), leaving silvan_reservoir with 340."""
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 700
    result = run_equal_blend(scenario)
    selected = selected_by_id(result)

    assert selected["groundwater_bore_1"]["volume_drawn_ml_per_day"] == pytest.approx(60.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(300.0, abs=VOLUME_TOLERANCE)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(340.0, abs=VOLUME_TOLERANCE)
    assert result["feasible"] is True


def test_infeasible_when_capacity_is_below_demand(scenario):
    """Step 7: every source at its cap, 710 total, 90 ML unmet."""
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 800
    result = run_equal_blend(scenario)

    assert result["status"] == "INFEASIBLE"
    assert result["feasible"] is False
    assert result["unmet_demand_ml_per_day"] == pytest.approx(90.0, abs=VOLUME_TOLERANCE)
    assert result["demand_zones"][0]["volume_supplied_ml_per_day"] == pytest.approx(710.0, abs=VOLUME_TOLERANCE)
    for source in result["sources"]["selected"]:
        assert source["capacity_usage_percent"] == pytest.approx(100.0, abs=PERCENT_TOLERANCE)


def test_infeasible_when_no_source_is_usable(scenario):
    for entry in scenario["sources"]:
        entry["enabled"] = False
    result = run_equal_blend(scenario)

    assert result["status"] == "INFEASIBLE"
    assert result["sources"]["selected"] == []
    assert result["unmet_demand_ml_per_day"] == pytest.approx(500.0, abs=VOLUME_TOLERANCE)


def test_zero_demand_selects_nothing(scenario):
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 0
    result = run_equal_blend(scenario)

    assert result["feasible"] is True
    assert result["sources"]["selected"] == []
    assert len(result["sources"]["unused"]) == 3
    assert all(s["reason"] for s in result["sources"]["unused"])


def test_missing_demand_is_an_error_not_an_assumption(scenario):
    del scenario["network"]["demand_zones"][0]["demand_ml_per_day"]
    with pytest.raises(BaselineInputError, match="demand_ml_per_day"):
        run_equal_blend(scenario)


# ---------------------------------------------------------------------------
# 4. Active and connected sources only
# ---------------------------------------------------------------------------


def test_disabled_source_is_excluded_with_a_reason(scenario):
    scenario["sources"][2]["enabled"] = False
    result = run_equal_blend(scenario)

    assert "groundwater_bore_1" not in selected_by_id(result)
    assert "disabled" in unused_by_id(result)["groundwater_bore_1"]["reason"]
    # 500 across the two remaining sources, both well under their caps.
    assert selected_by_id(result)["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(250.0, abs=VOLUME_TOLERANCE)


def test_forced_inactive_source_is_excluded(scenario):
    scenario["sources"][2]["forced_inactive"] = True
    result = run_equal_blend(scenario)
    assert "forced inactive" in unused_by_id(result)["groundwater_bore_1"]["reason"]


def test_source_inactive_in_the_source_data_is_excluded(scenario):
    scenario["data_source"]["source_rows"][2]["is_active"] = False
    result = run_equal_blend(scenario)
    assert "not active in the source data" in unused_by_id(result)["groundwater_bore_1"]["reason"]


def test_disconnected_source_is_excluded(scenario):
    scenario["network"]["source_to_plant_links"][2]["enabled"] = False
    result = run_equal_blend(scenario)
    assert "no enabled route to zone_1" in unused_by_id(result)["groundwater_bore_1"]["reason"]


def test_disabled_plant_disconnects_every_source(scenario):
    scenario["network"]["plants"][0]["enabled"] = False
    result = run_equal_blend(scenario)

    assert result["status"] == "INFEASIBLE"
    assert len(result["sources"]["unused"]) == 3
    assert all("no enabled route" in s["reason"] for s in result["sources"]["unused"])


# ---------------------------------------------------------------------------
# 5. Rounding rule and determinism
# ---------------------------------------------------------------------------


def test_rounding_is_deferred_to_output(scenario):
    """500 / 3 = 166.666... Rounding each share to 166.7 and summing would give
    500.1, so the supplied total proves the sum was taken before rounding."""
    for link in scenario["network"]["source_to_plant_links"]:
        link["maximum_flow_ml_per_day"] = 400
    result = run_equal_blend(scenario)

    for source in result["sources"]["selected"]:
        assert source["volume_drawn_ml_per_day"] == pytest.approx(166.7, abs=VOLUME_TOLERANCE)
        assert source["percent_of_blend"] == pytest.approx(33.3, abs=PERCENT_TOLERANCE)
    assert result["demand_zones"][0]["volume_supplied_ml_per_day"] == pytest.approx(500.0, abs=VOLUME_TOLERANCE)


def test_output_order_follows_the_scenario(scenario):
    result = run_equal_blend(scenario)
    assert [s["source_id"] for s in result["sources"]["selected"]] == [
        "silvan_reservoir",
        "yarra_kew",
        "groundwater_bore_1",
    ]


def test_allocation_is_independent_of_source_order(scenario):
    reversed_scenario = copy.deepcopy(scenario)
    reversed_scenario["sources"].reverse()
    reversed_scenario["network"]["source_to_plant_links"].reverse()

    original = {s["source_id"]: s["volume_drawn_ml_per_day"] for s in run_equal_blend(scenario)["sources"]["selected"]}
    flipped = {s["source_id"]: s["volume_drawn_ml_per_day"] for s in run_equal_blend(reversed_scenario)["sources"]["selected"]}
    assert original == flipped


def test_allocator_caps_and_redistributes_without_a_scenario():
    allocation, unmet = allocate_equal_blend({"a": 350.0, "b": 300.0, "c": 60.0}, 500.0)
    assert allocation == pytest.approx({"a": 220.0, "b": 220.0, "c": 60.0})
    assert unmet == 0.0


def test_allocator_reports_unmet_volume():
    allocation, unmet = allocate_equal_blend({"a": 10.0, "b": 20.0}, 100.0)
    assert allocation == pytest.approx({"a": 10.0, "b": 20.0})
    assert unmet == pytest.approx(70.0)


def test_allocator_rejects_negative_demand():
    with pytest.raises(BaselineInputError):
        allocate_equal_blend({"a": 10.0}, -1.0)


# ---------------------------------------------------------------------------
# 6. Contract checks the Sprint 1 rule does not cover
# ---------------------------------------------------------------------------


def test_draw_below_minimum_withdrawal_is_warned_about(scenario):
    """W_lower_s is a hard constraint on an active source in the MILP
    formulation, so a blend that breaches it is not comparable to a solve."""
    scenario["data_source"]["source_rows"][2]["minimum_withdrawal_ml_per_day"] = 80
    warnings = run_equal_blend(scenario)["warnings"]
    assert any("below its minimum withdrawal" in w for w in warnings)


def test_plant_throughput_breach_is_warned_about(scenario):
    scenario["network"]["plants"][0]["maximum_processing_capacity_ml_per_day"] = 400
    warnings = run_equal_blend(scenario)["warnings"]
    assert any("above its maximum" in w for w in warnings)


def test_contract_warnings_do_not_change_the_allocation(scenario):
    """Warnings report; they never quietly rewrite the approved rule."""
    baseline = run_equal_blend(scenario)["sources"]["selected"]
    scenario["network"]["plants"][0]["maximum_processing_capacity_ml_per_day"] = 400
    assert run_equal_blend(scenario)["sources"]["selected"] == baseline


# ---------------------------------------------------------------------------
# 7. The team's committed scenario files
# ---------------------------------------------------------------------------


def load_scenario_file(*parts):
    with open(SCENARIO_DIR.joinpath(*parts)) as handle:
        return json.load(handle)


def test_runs_on_the_committed_normal_scenario():
    """scenario_normal.json is a supabase scenario, so it carries no source
    rows offline: capacity comes from its link limits and cost is unavailable
    rather than invented. The volumes still match Sprint 1."""
    result = run_equal_blend(load_scenario_file("normal-year-dry-year", "scenario_normal.json"))
    selected = selected_by_id(result)

    assert result["status"] == "FEASIBLE"
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(220.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(220.0, abs=VOLUME_TOLERANCE)
    assert selected["groundwater_bore_1"]["volume_drawn_ml_per_day"] == pytest.approx(60.0, abs=VOLUME_TOLERANCE)
    assert result["objective"]["cost_is_complete"] is False
    assert result["objective"]["total_cost"] is None
    assert len(result["objective"]["sources_missing_cost"]) == 3


def test_runs_on_the_committed_dry_year_scenario():
    """Reduced link limits of 280 / 240 / 45 still cover 500 ML/day."""
    result = run_equal_blend(load_scenario_file("normal-year-dry-year", "scenario_dry_year.json"))
    selected = selected_by_id(result)

    assert result["status"] == "FEASIBLE"
    assert selected["groundwater_bore_1"]["volume_drawn_ml_per_day"] == pytest.approx(45.0, abs=VOLUME_TOLERANCE)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(227.5, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(227.5, abs=VOLUME_TOLERANCE)


def test_committed_plant_outage_scenario_is_infeasible():
    """facility_1 is the only plant, so disabling it removes every route."""
    result = run_equal_blend(load_scenario_file("high-demand-outage", "scenario_plant_outage.json"))

    assert result["status"] == "INFEASIBLE"
    assert result["sources"]["selected"] == []
    assert result["unmet_demand_ml_per_day"] == pytest.approx(500.0, abs=VOLUME_TOLERANCE)
