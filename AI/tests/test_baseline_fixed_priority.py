"""
test_baseline_fixed_priority.py

AquaBlend | Analysis & AI | Sprint 2 | Task 17

Four families of tests:
1. Agreement with `Baseline_HandCalculations.md` section 7.
2. Ordering: the approved priority order, and sources absent from it.
3. Rule behaviour: capacity resolution (withdrawal limit vs link capacity),
   capacity exhaustion, infeasibility, exclusions, rounding.
4. The team's committed scenario files.

Run from anywhere:
    python3 -m pytest AI/tests/test_baseline_fixed_priority.py -v
"""

import copy
import json
import sys
from pathlib import Path

import pytest

# The module under test lives in a sibling folder, so put it on the import
# path before importing it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "baselines"))

from baseline_fixed_priority import (  # noqa: E402
    BaselineInputError,
    DEFAULT_PRIORITY_ORDER,
    allocate_fixed_priority,
    priority_rank,
    run_fixed_priority,
)

# Volumes and percentages are reported to one decimal place, so half of that
# last place is the tightest meaningful bound; money is reported to two.
VOLUME_TOLERANCE = 0.05
PERCENT_TOLERANCE = 0.05
COST_TOLERANCE = 0.01

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "scenarios"

# ---------------------------------------------------------------------------
# Toy configuration, in the MILP inline scenario shape. Sources, capacities
# and demand are the confirmed toy-model values in Baseline_HandCalculations.md
# section 2, with the real costs it confirmed for the two sources that have
# them. groundwater_bore_1's cost is a genuine unknown and carries none.
# ---------------------------------------------------------------------------
TOY_SCENARIO = {
    "scenario_id": "toy_model_fixed_priority_test",
    "scenario_name": "Fixed-priority baseline test configuration",
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
                "fixed_activation_cost": 0.0,
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


def set_row(scenario, source_id, **fields):
    row = next(
        r
        for r in scenario["data_source"]["source_rows"]
        if r["source_id"] == source_id
    )
    row.update(fields)


# ---------------------------------------------------------------------------
# 1. Agreement with the hand calculation, section 7
# ---------------------------------------------------------------------------
def test_matches_hand_calculation_volumes(scenario):
    """Silvan 350, Yarra Kew 150, Groundwater 0."""
    result = run_fixed_priority(scenario)
    selected = selected_by_id(result)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(350.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(150.0, abs=VOLUME_TOLERANCE)
    assert "groundwater_bore_1" not in selected
    assert result["status"] == "FEASIBLE"
    assert result["unmet_demand_ml_per_day"] == 0.0


def test_matches_hand_calculation_blend_shares_and_usage(scenario):
    """70.0% / 30.0%, capacity usage 100.0% / 50.0%."""
    selected = selected_by_id(run_fixed_priority(scenario))
    assert selected["silvan_reservoir"]["percent_of_blend"] == pytest.approx(70.0, abs=PERCENT_TOLERANCE)
    assert selected["yarra_kew"]["percent_of_blend"] == pytest.approx(30.0, abs=PERCENT_TOLERANCE)
    assert selected["silvan_reservoir"]["capacity_usage_percent"] == pytest.approx(100.0, abs=PERCENT_TOLERANCE)
    assert selected["yarra_kew"]["capacity_usage_percent"] == pytest.approx(50.0, abs=PERCENT_TOLERANCE)


def test_matches_hand_calculation_costs(scenario):
    """140,000 + 35,250 = 175,250 source cost, 32,000 treatment, 207,250 total.
    Complete here, because groundwater_bore_1 (no confirmed cost) is never
    drawn."""
    result = run_fixed_priority(scenario)
    selected = selected_by_id(result)
    objective = result["objective"]
    assert selected["silvan_reservoir"]["draw_cost"] == pytest.approx(140000.00, abs=COST_TOLERANCE)
    assert selected["yarra_kew"]["draw_cost"] == pytest.approx(35250.00, abs=COST_TOLERANCE)
    assert objective["cost_breakdown"]["source_draw_cost"] == pytest.approx(175250.00, abs=COST_TOLERANCE)
    assert objective["cost_breakdown"]["plant_treatment_cost"] == pytest.approx(32000.00, abs=COST_TOLERANCE)
    assert objective["cost_is_complete"] is True
    assert objective["sources_missing_cost"] == []
    assert objective["total_cost"] == pytest.approx(207250.00, abs=COST_TOLERANCE)


def test_never_reports_optimal(scenario):
    assert run_fixed_priority(scenario)["status"] in {"FEASIBLE", "INFEASIBLE"}


def test_metadata_carries_the_heuristic_label_and_justification(scenario):
    """Task 17 checklist: store the heuristic label and a short justification
    in metadata, so a consumer can tell this apart from a real recommendation
    without reading the source."""
    result = run_fixed_priority(scenario)
    assert result["metadata"]["strategy"] == "fixed_priority"
    assert "assumed benchmark" in result["metadata"]["justification"].lower()


def test_makes_no_water_quality_claim(scenario):
    """A fixed-order heuristic must not imply the blend passes quality limits."""
    result = run_fixed_priority(scenario)
    assert "water_quality" not in result
    assert result["baseline"] == "fixed_priority"


# ---------------------------------------------------------------------------
# 2. Ordering
# ---------------------------------------------------------------------------
def test_draws_in_the_approved_priority_order(scenario):
    """Silvan is filled to capacity before Yarra Kew is touched at all,
    regardless of cost — Yarra Kew is cheaper but drawn second."""
    selected = selected_by_id(run_fixed_priority(scenario))
    assert selected["silvan_reservoir"]["capacity_usage_percent"] == pytest.approx(100.0, abs=PERCENT_TOLERANCE)
    assert selected["yarra_kew"]["capacity_usage_percent"] < 100.0


def test_priority_rank_orders_the_approved_list_first():
    ranked = sorted(
        [
            {"source_id": "unlisted_source"},
            {"source_id": "groundwater_bore_1"},
            {"source_id": "yarra_kew"},
            {"source_id": "silvan_reservoir"},
        ],
        key=lambda s: priority_rank(s, DEFAULT_PRIORITY_ORDER),
    )
    assert [s["source_id"] for s in ranked] == [
        "silvan_reservoir",
        "yarra_kew",
        "groundwater_bore_1",
        "unlisted_source",
    ]


def test_source_outside_the_priority_order_is_drawn_last(scenario):
    """A fourth source, not in the approved list, only supplies what the
    three approved sources can't."""
    scenario["data_source"]["source_rows"].append(
        {
            "source_id": "emergency_bore",
            "source_name": "Emergency Bore",
            "source_type": "groundwater",
            "is_active": True,
            "max_available_ml_per_day": None,
            "cost_per_ml": 50,
        }
    )
    scenario["sources"].append(
        {"source_id": "emergency_bore", "enabled": True, "forced_inactive": False}
    )
    scenario["network"]["source_to_plant_links"].append(
        {
            "source_id": "emergency_bore",
            "plant_id": "facility_1",
            "enabled": True,
            "maximum_flow_ml_per_day": 100,
        }
    )
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 560
    result = run_fixed_priority(scenario)
    selected = selected_by_id(result)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(350.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(210.0, abs=VOLUME_TOLERANCE)
    assert "emergency_bore" not in selected
    assert any("not in the approved priority order" in w for w in result["warnings"])


def test_allocation_is_independent_of_input_order(scenario):
    reversed_scenario = copy.deepcopy(scenario)
    reversed_scenario["sources"].reverse()
    reversed_scenario["data_source"]["source_rows"].reverse()
    reversed_scenario["network"]["source_to_plant_links"].reverse()
    original = {s["source_id"]: s["volume_drawn_ml_per_day"] for s in run_fixed_priority(scenario)["sources"]["selected"]}
    flipped = {s["source_id"]: s["volume_drawn_ml_per_day"] for s in run_fixed_priority(reversed_scenario)["sources"]["selected"]}
    assert original == flipped


def test_output_order_follows_priority_not_input_order(scenario):
    reversed_scenario = copy.deepcopy(scenario)
    reversed_scenario["sources"].reverse()
    result = run_fixed_priority(reversed_scenario)
    assert [s["source_id"] for s in result["sources"]["selected"]] == [
        "silvan_reservoir",
        "yarra_kew",
    ]


# ---------------------------------------------------------------------------
# 3. Capacity resolution, including the Task 5 section 3 open item
# ---------------------------------------------------------------------------
def test_capacity_is_the_tighter_of_withdrawal_and_link(scenario):
    """Baseline_HandCalculations.md section 3 leaves it open whether
    yarra_kew's capacity is the link's 300 or the source's 290. min() of the
    two settles it without a ruling, matching baseline_equal_blend.py and
    baseline_cheapest_first.py. At the golden 500 ML/day demand this doesn't
    change the result, since 150 sits below both."""
    set_row(scenario, "yarra_kew", max_available_ml_per_day=290)
    selected = selected_by_id(run_fixed_priority(scenario))
    assert selected["yarra_kew"]["capacity_ml_per_day"] == pytest.approx(290.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(150.0, abs=VOLUME_TOLERANCE)


def test_tighter_capacity_changes_the_split_at_higher_demand(scenario):
    """At 660 ML/day, yarra_kew's real 290 ML/day limit (vs the documented
    300) means groundwater has to pick up the extra 10 ML."""
    set_row(scenario, "yarra_kew", max_available_ml_per_day=290)
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 660
    result = run_fixed_priority(scenario)
    selected = selected_by_id(result)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(350.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(290.0, abs=VOLUME_TOLERANCE)
    assert selected["groundwater_bore_1"]["volume_drawn_ml_per_day"] == pytest.approx(20.0, abs=VOLUME_TOLERANCE)
    assert result["feasible"] is True


def test_scenario_override_beats_the_source_row(scenario):
    set_row(scenario, "yarra_kew", max_available_ml_per_day=300)
    scenario["sources"][1]["maximum_withdrawal_ml_per_day_override"] = 100
    selected = selected_by_id(run_fixed_priority(scenario))
    assert selected["yarra_kew"]["capacity_ml_per_day"] == pytest.approx(100.0, abs=VOLUME_TOLERANCE)


# ---------------------------------------------------------------------------
# 4. Capacity exhaustion, infeasibility and edge cases
# ---------------------------------------------------------------------------
def test_capacity_exhaustion_moves_through_every_source(scenario):
    """710 ML is exactly the total capacity, so all three end at their cap."""
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 710
    result = run_fixed_priority(scenario)
    assert result["feasible"] is True
    assert result["unmet_demand_ml_per_day"] == 0.0
    for source in result["sources"]["selected"]:
        assert source["capacity_usage_percent"] == pytest.approx(100.0, abs=PERCENT_TOLERANCE)


def test_infeasible_when_capacity_is_below_demand(scenario):
    """Baseline_FixedPriority.md section 6: demand 800 against 710 total."""
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 800
    result = run_fixed_priority(scenario)
    assert result["status"] == "INFEASIBLE"
    assert result["feasible"] is False
    assert result["unmet_demand_ml_per_day"] == pytest.approx(90.0, abs=VOLUME_TOLERANCE)
    assert result["demand_zones"][0]["volume_supplied_ml_per_day"] == pytest.approx(710.0, abs=VOLUME_TOLERANCE)


def test_infeasible_when_no_source_is_usable(scenario):
    for entry in scenario["sources"]:
        entry["enabled"] = False
    result = run_fixed_priority(scenario)
    assert result["status"] == "INFEASIBLE"
    assert result["sources"]["selected"] == []
    assert result["unmet_demand_ml_per_day"] == pytest.approx(500.0, abs=VOLUME_TOLERANCE)


def test_zero_demand_selects_nothing(scenario):
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 0
    result = run_fixed_priority(scenario)
    assert result["feasible"] is True
    assert result["sources"]["selected"] == []
    assert len(result["sources"]["unused"]) == 3


def test_missing_demand_is_an_error_not_an_assumption(scenario):
    del scenario["network"]["demand_zones"][0]["demand_ml_per_day"]
    with pytest.raises(BaselineInputError, match="demand_ml_per_day"):
        run_fixed_priority(scenario)


def test_rounding_is_deferred_to_output(scenario):
    """A demand that lands mid-fraction still sums correctly, proving
    rounding happens once, on output, not mid-allocation."""
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 350 + 100 / 3
    result = run_fixed_priority(scenario)
    selected = selected_by_id(result)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(33.3, abs=VOLUME_TOLERANCE)
    assert result["demand_zones"][0]["volume_supplied_ml_per_day"] == pytest.approx(383.3, abs=VOLUME_TOLERANCE)
    assert result["unmet_demand_ml_per_day"] == 0.0


# ---------------------------------------------------------------------------
# 5. Activation, connectivity and capacity
# ---------------------------------------------------------------------------
def test_disabled_source_is_excluded_with_a_reason(scenario):
    scenario["sources"][1]["enabled"] = False
    result = run_fixed_priority(scenario)
    assert "yarra_kew" not in selected_by_id(result)
    assert "disabled" in unused_by_id(result)["yarra_kew"]["reason"]
    # Without yarra_kew, groundwater has to make up the difference.
    assert selected_by_id(result)["groundwater_bore_1"]["volume_drawn_ml_per_day"] == pytest.approx(60.0, abs=VOLUME_TOLERANCE)


def test_forced_inactive_source_is_excluded(scenario):
    scenario["sources"][1]["forced_inactive"] = True
    result = run_fixed_priority(scenario)
    assert "forced inactive" in unused_by_id(result)["yarra_kew"]["reason"]


def test_source_inactive_in_the_source_data_is_excluded(scenario):
    set_row(scenario, "yarra_kew", is_active=False)
    result = run_fixed_priority(scenario)
    assert "not active in the source data" in unused_by_id(result)["yarra_kew"]["reason"]


def test_disconnected_source_is_excluded(scenario):
    scenario["network"]["source_to_plant_links"][1]["enabled"] = False
    result = run_fixed_priority(scenario)
    assert "no enabled route to zone_1" in unused_by_id(result)["yarra_kew"]["reason"]


def test_disabled_plant_disconnects_every_source(scenario):
    scenario["network"]["plants"][0]["enabled"] = False
    result = run_fixed_priority(scenario)
    assert result["status"] == "INFEASIBLE"
    assert all("no enabled route" in s["reason"] for s in result["sources"]["unused"])


# ---------------------------------------------------------------------------
# 6. Contract checks the rule does not itself cover
# ---------------------------------------------------------------------------
def test_draw_below_minimum_withdrawal_is_warned_about(scenario):
    set_row(scenario, "silvan_reservoir", minimum_withdrawal_ml_per_day=360)
    warnings = run_fixed_priority(scenario)["warnings"]
    assert any("below its minimum withdrawal" in w for w in warnings)


def test_plant_throughput_breach_is_warned_about(scenario):
    scenario["network"]["plants"][0]["maximum_processing_capacity_ml_per_day"] = 400
    warnings = run_fixed_priority(scenario)["warnings"]
    assert any("above its maximum" in w for w in warnings)


def test_contract_warnings_do_not_change_the_allocation(scenario):
    baseline = run_fixed_priority(scenario)["sources"]["selected"]
    scenario["network"]["plants"][0]["maximum_processing_capacity_ml_per_day"] = 400
    assert run_fixed_priority(scenario)["sources"]["selected"] == baseline


def test_activation_costs_are_included(scenario):
    scenario["sources"][0]["fixed_activation_cost"] = 500.0
    scenario["network"]["plants"][0]["fixed_activation_cost"] = 250.0
    breakdown = run_fixed_priority(scenario)["objective"]["cost_breakdown"]
    assert breakdown["source_activation_cost"] == pytest.approx(500.00, abs=COST_TOLERANCE)
    assert breakdown["plant_activation_cost"] == pytest.approx(250.00, abs=COST_TOLERANCE)
    assert run_fixed_priority(scenario)["objective"]["total_cost"] == pytest.approx(208000.00, abs=COST_TOLERANCE)


# ---------------------------------------------------------------------------
# 7. The allocator on its own
# ---------------------------------------------------------------------------
def test_allocator_fills_in_priority_order():
    sources = [
        {"source_id": "silvan_reservoir", "capacity_ml_per_day": 350.0},
        {"source_id": "yarra_kew", "capacity_ml_per_day": 300.0},
        {"source_id": "groundwater_bore_1", "capacity_ml_per_day": 60.0},
    ]
    allocation, unmet = allocate_fixed_priority(sources, 500.0)
    assert allocation == pytest.approx(
        {"silvan_reservoir": 350.0, "yarra_kew": 150.0, "groundwater_bore_1": 0.0}
    )
    assert unmet == 0.0


def test_allocator_reports_unmet_volume():
    sources = [{"source_id": "silvan_reservoir", "capacity_ml_per_day": 10.0}]
    allocation, unmet = allocate_fixed_priority(sources, 100.0)
    assert allocation == pytest.approx({"silvan_reservoir": 10.0})
    assert unmet == pytest.approx(90.0)


def test_allocator_rejects_negative_demand():
    with pytest.raises(BaselineInputError):
        allocate_fixed_priority([], -1.0)


# ---------------------------------------------------------------------------
# 8. The team's committed scenario files
# ---------------------------------------------------------------------------
def load_scenario_file(*parts):
    with open(SCENARIO_DIR.joinpath(*parts)) as handle:
        return json.load(handle)


def test_runs_on_the_committed_normal_scenario():
    """A supabase scenario carries no source rows offline, so no source has a
    cost, but the priority order doesn't depend on cost anyway."""
    result = run_fixed_priority(load_scenario_file("normal-year-dry-year", "scenario_normal.json"))
    selected = selected_by_id(result)
    assert result["status"] == "FEASIBLE"
    assert result["demand_zones"][0]["volume_supplied_ml_per_day"] == pytest.approx(500.0, abs=VOLUME_TOLERANCE)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(350.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(150.0, abs=VOLUME_TOLERANCE)
    assert "groundwater_bore_1" not in selected


def test_runs_on_the_committed_dry_year_scenario():
    """Reduced link limits of 280 / 240 / 45. Silvan fills first at 280 (its
    own cap), then Yarra Kew takes the remaining 220."""
    result = run_fixed_priority(load_scenario_file("normal-year-dry-year", "scenario_dry_year.json"))
    selected = selected_by_id(result)
    assert result["status"] == "FEASIBLE"
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(280.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(220.0, abs=VOLUME_TOLERANCE)
    assert "groundwater_bore_1" not in selected


def test_committed_plant_outage_scenario_is_infeasible():
    result = run_fixed_priority(load_scenario_file("high-demand-outage", "scenario_plant_outage.json"))
    assert result["status"] == "INFEASIBLE"
    assert result["sources"]["selected"] == []
    assert result["unmet_demand_ml_per_day"] == pytest.approx(500.0, abs=VOLUME_TOLERANCE)
