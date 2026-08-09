"""
test_baseline_cheapest_first.py

AquaBlend | Analysis & AI | Sprint 2

Four families of tests:

1. Agreement with `Baseline_HandCalculations.md` section 6, under both the
   documented 300 ML/day cap for yarra_kew and the 290 ML/day cap its section 3
   argues is the real one.
2. Ordering: cost ascending, the source_id tie-break, and unranked sources.
3. Rule behaviour: capacity exhaustion, infeasibility, exclusions, rounding.
4. The team's committed scenario files.

Run from anywhere:

    python3 -m pytest AI/tests/test_baseline_cheapest_first.py -v
"""

import copy
import json
import sys
from pathlib import Path

import pytest

# The modules under test live in a sibling folder, so put it on the import path
# before importing them.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "baselines"))

from baseline_cheapest_first import (  # noqa: E402
    BaselineInputError,
    allocate_cheapest_first,
    cost_rank,
    run_cheapest_first,
)

# Volumes and percentages are reported to one decimal place, so half of that
# last place is the tightest meaningful bound; money is reported to two.
VOLUME_TOLERANCE = 0.05
PERCENT_TOLERANCE = 0.05
COST_TOLERANCE = 0.01

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "scenarios"


# ---------------------------------------------------------------------------
# Toy configuration, in the MILP inline scenario shape. Sources, capacities and
# demand are the confirmed toy-model values in Baseline_HandCalculations.md
# section 2, with the real costs it confirmed for the two sources that have
# them. groundwater_bore_1's cost is a genuine unknown and carries none.
# ---------------------------------------------------------------------------

TOY_SCENARIO = {
    "scenario_id": "toy_model_cheapest_first_test",
    "scenario_name": "Cheapest-first baseline test configuration",
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
# 1. Agreement with the hand calculation, section 6
# ---------------------------------------------------------------------------


def test_matches_hand_calculation_documented_cap(scenario):
    """Primary result: yarra_kew 300, silvan_reservoir 200, groundwater 0."""
    result = run_cheapest_first(scenario)
    selected = selected_by_id(result)

    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(300.0, abs=VOLUME_TOLERANCE)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(200.0, abs=VOLUME_TOLERANCE)
    assert "groundwater_bore_1" not in selected
    assert result["status"] == "FEASIBLE"
    assert result["unmet_demand_ml_per_day"] == 0.0


def test_matches_hand_calculation_blend_shares_and_usage(scenario):
    """60.0% / 40.0%, capacity usage 100.0% / 57.1%."""
    selected = selected_by_id(run_cheapest_first(scenario))

    assert selected["yarra_kew"]["percent_of_blend"] == pytest.approx(60.0, abs=PERCENT_TOLERANCE)
    assert selected["silvan_reservoir"]["percent_of_blend"] == pytest.approx(40.0, abs=PERCENT_TOLERANCE)
    assert selected["yarra_kew"]["capacity_usage_percent"] == pytest.approx(100.0, abs=PERCENT_TOLERANCE)
    assert selected["silvan_reservoir"]["capacity_usage_percent"] == pytest.approx(57.1, abs=PERCENT_TOLERANCE)


def test_matches_hand_calculation_costs(scenario):
    """70,500 + 80,000 = 150,500 source cost, 32,000 treatment, 182,500 total.
    The total is complete here, unlike equal blend, because the source with no
    confirmed cost is never drawn."""
    result = run_cheapest_first(scenario)
    selected = selected_by_id(result)
    objective = result["objective"]

    assert selected["yarra_kew"]["draw_cost"] == pytest.approx(70500.00, abs=COST_TOLERANCE)
    assert selected["silvan_reservoir"]["draw_cost"] == pytest.approx(80000.00, abs=COST_TOLERANCE)
    assert objective["cost_breakdown"]["source_draw_cost"] == pytest.approx(150500.00, abs=COST_TOLERANCE)
    assert objective["cost_breakdown"]["plant_treatment_cost"] == pytest.approx(32000.00, abs=COST_TOLERANCE)
    assert objective["cost_is_complete"] is True
    assert objective["sources_missing_cost"] == []
    assert objective["total_cost"] == pytest.approx(182500.00, abs=COST_TOLERANCE)


def test_matches_hand_calculation_real_cap_reproduces_the_optimum(scenario):
    """Section 3 argues yarra_kew's real limit is 290, not the documented 300.
    At 290 the baseline reproduces the confirmed MILP optimum exactly, which is
    the evidence that 290 is right: a heuristic cannot beat the true optimum,
    and at 300 this baseline returns 182,500 against an optimum of 184,150."""
    set_row(scenario, "yarra_kew", max_available_ml_per_day=290)
    result = run_cheapest_first(scenario)
    selected = selected_by_id(result)

    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(290.0, abs=VOLUME_TOLERANCE)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(210.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["percent_of_blend"] == pytest.approx(58.0, abs=PERCENT_TOLERANCE)
    assert selected["silvan_reservoir"]["percent_of_blend"] == pytest.approx(42.0, abs=PERCENT_TOLERANCE)
    assert result["objective"]["cost_breakdown"]["source_draw_cost"] == pytest.approx(152150.00, abs=COST_TOLERANCE)
    assert result["objective"]["total_cost"] == pytest.approx(184150.00, abs=COST_TOLERANCE)


def test_never_reports_optimal(scenario):
    assert run_cheapest_first(scenario)["status"] in {"FEASIBLE", "INFEASIBLE"}


def test_makes_no_water_quality_claim(scenario):
    """A cost-only heuristic must not imply the blend passes quality limits."""
    result = run_cheapest_first(scenario)
    assert "water_quality" not in result
    assert result["baseline"] == "cheapest_first"


# ---------------------------------------------------------------------------
# 2. Ordering
# ---------------------------------------------------------------------------


def test_draws_cheapest_source_first(scenario):
    """yarra_kew at 235 outranks silvan_reservoir at 400, so it is filled to
    capacity before silvan is touched."""
    selected = selected_by_id(run_cheapest_first(scenario))
    assert selected["yarra_kew"]["capacity_usage_percent"] == pytest.approx(100.0, abs=PERCENT_TOLERANCE)
    assert selected["silvan_reservoir"]["capacity_usage_percent"] < 100.0


def test_cost_tie_is_broken_by_source_id(scenario):
    """Equal cost, so silvan_reservoir precedes yarra_kew alphabetically and is
    filled first: 350 then 150."""
    set_row(scenario, "silvan_reservoir", cost_per_ml=300)
    set_row(scenario, "yarra_kew", cost_per_ml=300)

    selected = selected_by_id(run_cheapest_first(scenario))
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(350.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(150.0, abs=VOLUME_TOLERANCE)


def test_unranked_source_is_drawn_last(scenario):
    """660 ML needs all three. groundwater_bore_1 has no cost, so it cannot be
    ranked and takes the remainder rather than being assumed cheap."""
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 660
    selected = selected_by_id(run_cheapest_first(scenario))

    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(300.0, abs=VOLUME_TOLERANCE)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(350.0, abs=VOLUME_TOLERANCE)
    assert selected["groundwater_bore_1"]["volume_drawn_ml_per_day"] == pytest.approx(10.0, abs=VOLUME_TOLERANCE)


def test_unranked_source_is_disclosed(scenario):
    warnings = run_cheapest_first(scenario)["warnings"]
    assert any("cannot be ranked by cost" in w for w in warnings)


def test_cost_rank_orders_none_last():
    ranked = sorted(
        [
            {"source_id": "c", "cost_per_ml": None},
            {"source_id": "b", "cost_per_ml": 10.0},
            {"source_id": "a", "cost_per_ml": 10.0},
            {"source_id": "d", "cost_per_ml": 5.0},
        ],
        key=cost_rank,
    )
    assert [s["source_id"] for s in ranked] == ["d", "a", "b", "c"]


def test_allocation_is_independent_of_input_order(scenario):
    reversed_scenario = copy.deepcopy(scenario)
    reversed_scenario["sources"].reverse()
    reversed_scenario["data_source"]["source_rows"].reverse()
    reversed_scenario["network"]["source_to_plant_links"].reverse()

    original = {s["source_id"]: s["volume_drawn_ml_per_day"] for s in run_cheapest_first(scenario)["sources"]["selected"]}
    flipped = {s["source_id"]: s["volume_drawn_ml_per_day"] for s in run_cheapest_first(reversed_scenario)["sources"]["selected"]}
    assert original == flipped


# ---------------------------------------------------------------------------
# 3. Capacity exhaustion, infeasibility and edge cases
# ---------------------------------------------------------------------------


def test_capacity_exhaustion_moves_through_every_source(scenario):
    """710 ML is exactly the total capacity, so all three end at their cap."""
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 710
    result = run_cheapest_first(scenario)

    assert result["feasible"] is True
    assert result["unmet_demand_ml_per_day"] == 0.0
    for source in result["sources"]["selected"]:
        assert source["capacity_usage_percent"] == pytest.approx(100.0, abs=PERCENT_TOLERANCE)


def test_infeasible_when_capacity_is_below_demand(scenario):
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 800
    result = run_cheapest_first(scenario)

    assert result["status"] == "INFEASIBLE"
    assert result["feasible"] is False
    assert result["unmet_demand_ml_per_day"] == pytest.approx(90.0, abs=VOLUME_TOLERANCE)
    assert result["demand_zones"][0]["volume_supplied_ml_per_day"] == pytest.approx(710.0, abs=VOLUME_TOLERANCE)


def test_infeasible_when_no_source_is_usable(scenario):
    for entry in scenario["sources"]:
        entry["enabled"] = False
    result = run_cheapest_first(scenario)

    assert result["status"] == "INFEASIBLE"
    assert result["sources"]["selected"] == []
    assert result["unmet_demand_ml_per_day"] == pytest.approx(500.0, abs=VOLUME_TOLERANCE)


def test_zero_demand_selects_nothing(scenario):
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 0
    result = run_cheapest_first(scenario)

    assert result["feasible"] is True
    assert result["sources"]["selected"] == []
    assert len(result["sources"]["unused"]) == 3


def test_missing_demand_is_an_error_not_an_assumption(scenario):
    del scenario["network"]["demand_zones"][0]["demand_ml_per_day"]
    with pytest.raises(BaselineInputError, match="demand_ml_per_day"):
        run_cheapest_first(scenario)


def test_rounding_is_deferred_to_output(scenario):
    """A 100/3 ML remainder reaches silvan at full precision. Rounding it
    early would not sum back to the 500 ML supplied."""
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 500 - 100 / 3
    result = run_cheapest_first(scenario)
    selected = selected_by_id(result)

    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(166.7, abs=VOLUME_TOLERANCE)
    assert result["demand_zones"][0]["volume_supplied_ml_per_day"] == pytest.approx(466.7, abs=VOLUME_TOLERANCE)
    assert result["unmet_demand_ml_per_day"] == 0.0


# ---------------------------------------------------------------------------
# 4. Activation, connectivity and capacity
# ---------------------------------------------------------------------------


def test_disabled_source_is_excluded_with_a_reason(scenario):
    scenario["sources"][1]["enabled"] = False
    result = run_cheapest_first(scenario)

    assert "yarra_kew" not in selected_by_id(result)
    assert "disabled" in unused_by_id(result)["yarra_kew"]["reason"]
    # Without the cheapest source, silvan fills first instead.
    assert selected_by_id(result)["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(350.0, abs=VOLUME_TOLERANCE)


def test_forced_inactive_source_is_excluded(scenario):
    scenario["sources"][1]["forced_inactive"] = True
    result = run_cheapest_first(scenario)
    assert "forced inactive" in unused_by_id(result)["yarra_kew"]["reason"]


def test_source_inactive_in_the_source_data_is_excluded(scenario):
    set_row(scenario, "yarra_kew", is_active=False)
    result = run_cheapest_first(scenario)
    assert "not active in the source data" in unused_by_id(result)["yarra_kew"]["reason"]


def test_disconnected_source_is_excluded(scenario):
    scenario["network"]["source_to_plant_links"][1]["enabled"] = False
    result = run_cheapest_first(scenario)
    assert "no enabled route to zone_1" in unused_by_id(result)["yarra_kew"]["reason"]


def test_disabled_plant_disconnects_every_source(scenario):
    scenario["network"]["plants"][0]["enabled"] = False
    result = run_cheapest_first(scenario)

    assert result["status"] == "INFEASIBLE"
    assert all("no enabled route" in s["reason"] for s in result["sources"]["unused"])


def test_capacity_is_the_tighter_of_withdrawal_and_link(scenario):
    set_row(scenario, "yarra_kew", max_available_ml_per_day=120)
    selected = selected_by_id(run_cheapest_first(scenario))

    assert selected["yarra_kew"]["capacity_ml_per_day"] == pytest.approx(120.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(120.0, abs=VOLUME_TOLERANCE)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(350.0, abs=VOLUME_TOLERANCE)


def test_scenario_override_beats_the_source_row(scenario):
    set_row(scenario, "yarra_kew", max_available_ml_per_day=300)
    scenario["sources"][1]["maximum_withdrawal_ml_per_day_override"] = 100
    selected = selected_by_id(run_cheapest_first(scenario))
    assert selected["yarra_kew"]["capacity_ml_per_day"] == pytest.approx(100.0, abs=VOLUME_TOLERANCE)


# ---------------------------------------------------------------------------
# 5. Contract checks the rule does not itself cover
# ---------------------------------------------------------------------------


def test_draw_below_minimum_withdrawal_is_warned_about(scenario):
    set_row(scenario, "silvan_reservoir", minimum_withdrawal_ml_per_day=250)
    warnings = run_cheapest_first(scenario)["warnings"]
    assert any("below its minimum withdrawal" in w for w in warnings)


def test_plant_throughput_breach_is_warned_about(scenario):
    scenario["network"]["plants"][0]["maximum_processing_capacity_ml_per_day"] = 400
    warnings = run_cheapest_first(scenario)["warnings"]
    assert any("above its maximum" in w for w in warnings)


def test_plant_minimum_alias_is_honoured(scenario):
    """The loader accepts minimum_operating_flow_ml_per_day as a fallback, so
    the baseline must read it too."""
    del scenario["network"]["plants"][0]["minimum_processing_capacity_ml_per_day"]
    scenario["network"]["plants"][0]["minimum_operating_flow_ml_per_day"] = 600
    warnings = run_cheapest_first(scenario)["warnings"]
    assert any("below its minimum" in w for w in warnings)


def test_contract_warnings_do_not_change_the_allocation(scenario):
    baseline = run_cheapest_first(scenario)["sources"]["selected"]
    scenario["network"]["plants"][0]["maximum_processing_capacity_ml_per_day"] = 400
    assert run_cheapest_first(scenario)["sources"]["selected"] == baseline


def test_activation_costs_are_included(scenario):
    scenario["sources"][1]["fixed_activation_cost"] = 500.0
    scenario["network"]["plants"][0]["fixed_activation_cost"] = 250.0

    breakdown = run_cheapest_first(scenario)["objective"]["cost_breakdown"]
    assert breakdown["source_activation_cost"] == pytest.approx(500.00, abs=COST_TOLERANCE)
    assert breakdown["plant_activation_cost"] == pytest.approx(250.00, abs=COST_TOLERANCE)
    assert run_cheapest_first(scenario)["objective"]["total_cost"] == pytest.approx(183250.00, abs=COST_TOLERANCE)


# ---------------------------------------------------------------------------
# 6. The allocator on its own
# ---------------------------------------------------------------------------


def test_allocator_fills_in_cost_order():
    sources = [
        {"source_id": "silvan_reservoir", "capacity_ml_per_day": 350.0, "cost_per_ml": 400.0},
        {"source_id": "yarra_kew", "capacity_ml_per_day": 300.0, "cost_per_ml": 235.0},
    ]
    allocation, unmet = allocate_cheapest_first(sources, 500.0)
    assert allocation == pytest.approx({"yarra_kew": 300.0, "silvan_reservoir": 200.0})
    assert unmet == 0.0


def test_allocator_reports_unmet_volume():
    sources = [{"source_id": "a", "capacity_ml_per_day": 10.0, "cost_per_ml": 1.0}]
    allocation, unmet = allocate_cheapest_first(sources, 100.0)
    assert allocation == pytest.approx({"a": 10.0})
    assert unmet == pytest.approx(90.0)


def test_allocator_rejects_negative_demand():
    with pytest.raises(BaselineInputError):
        allocate_cheapest_first([], -1.0)


# ---------------------------------------------------------------------------
# 7. The team's committed scenario files
# ---------------------------------------------------------------------------


def load_scenario_file(*parts):
    with open(SCENARIO_DIR.joinpath(*parts)) as handle:
        return json.load(handle)


def test_runs_on_the_committed_normal_scenario():
    """A supabase scenario carries no source rows offline, so no source has a
    cost and none can be ranked. All three fall back to the source_id
    tie-break, which the warning discloses rather than passing off as a cost
    ranking."""
    result = run_cheapest_first(load_scenario_file("normal-year-dry-year", "scenario_normal.json"))
    selected = selected_by_id(result)

    assert result["status"] == "FEASIBLE"
    assert result["demand_zones"][0]["volume_supplied_ml_per_day"] == pytest.approx(500.0, abs=VOLUME_TOLERANCE)
    assert selected["groundwater_bore_1"]["volume_drawn_ml_per_day"] == pytest.approx(60.0, abs=VOLUME_TOLERANCE)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(350.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(90.0, abs=VOLUME_TOLERANCE)
    assert result["objective"]["total_cost"] is None
    assert any("cannot be ranked by cost" in w for w in result["warnings"])


def test_runs_on_the_committed_dry_year_scenario():
    """Reduced link limits of 280 / 240 / 45 still cover 500 ML/day."""
    result = run_cheapest_first(load_scenario_file("normal-year-dry-year", "scenario_dry_year.json"))
    selected = selected_by_id(result)

    assert result["status"] == "FEASIBLE"
    assert selected["groundwater_bore_1"]["volume_drawn_ml_per_day"] == pytest.approx(45.0, abs=VOLUME_TOLERANCE)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(280.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(175.0, abs=VOLUME_TOLERANCE)


def test_committed_plant_outage_scenario_is_infeasible():
    result = run_cheapest_first(load_scenario_file("high-demand-outage", "scenario_plant_outage.json"))

    assert result["status"] == "INFEASIBLE"
    assert result["sources"]["selected"] == []
    assert result["unmet_demand_ml_per_day"] == pytest.approx(500.0, abs=VOLUME_TOLERANCE)
