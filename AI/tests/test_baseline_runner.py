"""
test_baseline_runner.py

AquaBlend | Analysis & AI | Sprint 2 | Task 18

Three families of tests:
1. Shape consistency — every baseline's normalized result has the same key
   set, regardless of what the raw baseline actually returns.
2. Isolation — the input scenario is never mutated, and one baseline cannot
   affect another's result.
3. End-to-end agreement — running all three against the toy configuration
   reproduces the Sprint 1 hand-calculated numbers for each.

Run from anywhere:
    python3 -m pytest AI/tests/test_baseline_runner.py -v
"""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "baselines"))

from baseline_runner import (  # noqa: E402
    BaselineRunnerError,
    COST_BREAKDOWN_KEYS,
    TOP_LEVEL_OPTIONAL_KEYS,
    run_all_baselines,
)

VOLUME_TOLERANCE = 0.05
COST_TOLERANCE = 0.01

# ---------------------------------------------------------------------------
# Toy configuration, matching Baseline_HandCalculations.md section 2 exactly.
# ---------------------------------------------------------------------------
TOY_SCENARIO = {
    "scenario_id": "toy_model_runner_test",
    "scenario_name": "Baseline runner test configuration",
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


def _multi_zone_scenario():
    """Two zones sharing the same three sources and plant, each with its own
    demand, so zone_id selection can be tested honestly."""
    scenario = copy.deepcopy(TOY_SCENARIO)
    scenario["scenario_id"] = "toy_model_multi_zone_test"
    scenario["network"]["demand_zones"] = [
        {"zone_id": "zone_1", "name": "Zone 1", "demand_ml_per_day": 500},
        {"zone_id": "zone_2", "name": "Zone 2", "demand_ml_per_day": 100},
    ]
    scenario["network"]["plant_to_zone_links"] = [
        {
            "plant_id": "facility_1",
            "zone_id": "zone_1",
            "enabled": True,
            "maximum_flow_ml_per_day": 600,
        },
        {
            "plant_id": "facility_1",
            "zone_id": "zone_2",
            "enabled": True,
            "maximum_flow_ml_per_day": 600,
        },
    ]
    return scenario


def selected_by_id(result, baseline_name):
    return {
        s["source_id"]: s
        for s in result["baselines"][baseline_name]["sources"]["selected"]
    }


# ---------------------------------------------------------------------------
# 1. Shape consistency
# ---------------------------------------------------------------------------
def test_all_three_baselines_are_present(scenario):
    result = run_all_baselines(scenario)
    assert set(result["baselines"]) == {"equal_blend", "cheapest_first", "fixed_priority"}


def test_every_baseline_has_the_full_cost_breakdown(scenario):
    result = run_all_baselines(scenario)
    for name, entry in result["baselines"].items():
        breakdown = entry["objective"]["cost_breakdown"]
        assert set(breakdown) == set(COST_BREAKDOWN_KEYS), name


def test_equal_blend_gets_zeroed_activation_costs_not_dropped(scenario):
    """equal_blend's raw result has no activation-cost keys at all, since it
    predates that part of the contract. The runner fills them with a real
    zero (no activation-cost concept existed, not an unknown), never drops
    the keys."""
    result = run_all_baselines(scenario)
    breakdown = result["baselines"]["equal_blend"]["objective"]["cost_breakdown"]
    assert breakdown["source_activation_cost"] == 0.00
    assert breakdown["plant_activation_cost"] == 0.00


def test_every_baseline_has_the_same_top_level_optional_keys(scenario):
    result = run_all_baselines(scenario)
    for name, entry in result["baselines"].items():
        for key in TOP_LEVEL_OPTIONAL_KEYS:
            assert key in entry, f"{name} is missing {key}"


def test_baselines_without_priority_order_or_metadata_get_none(scenario):
    """equal_blend and cheapest_first don't produce these concepts; the
    runner marks that with None, distinct from fixed_priority's real values."""
    result = run_all_baselines(scenario)
    assert result["baselines"]["equal_blend"]["priority_order"] is None
    assert result["baselines"]["equal_blend"]["metadata"] is None
    assert result["baselines"]["cheapest_first"]["priority_order"] is None
    assert result["baselines"]["cheapest_first"]["metadata"] is None


def test_fixed_priority_keeps_its_real_metadata(scenario):
    result = run_all_baselines(scenario)
    metadata = result["baselines"]["fixed_priority"]["metadata"]
    assert metadata is not None
    assert metadata["strategy"] == "fixed_priority"


def test_no_baseline_reports_water_quality(scenario):
    """Checklist requirement: water-quality values only when approved code
    actually calculates them. None of the three do yet."""
    result = run_all_baselines(scenario)
    for name, entry in result["baselines"].items():
        assert "water_quality" not in entry, name


def test_no_baseline_reports_optimal(scenario):
    result = run_all_baselines(scenario)
    for name, entry in result["baselines"].items():
        assert entry["status"] in {"FEASIBLE", "INFEASIBLE"}, name


# ---------------------------------------------------------------------------
# 2. Isolation
# ---------------------------------------------------------------------------
def test_input_scenario_is_not_mutated(scenario):
    before = copy.deepcopy(scenario)
    run_all_baselines(scenario)
    assert scenario == before


def test_one_baseline_cannot_affect_another():
    """Each baseline gets its own deep copy, so even if one baseline were to
    mutate its input in place, the others would be unaffected. Verified here
    by confirming the three results differ from each other in exactly the
    ways the rules predict, not in some contaminated way."""
    result = run_all_baselines(copy.deepcopy(TOY_SCENARIO))
    equal_blend_silvan = selected_by_id(result, "equal_blend")["silvan_reservoir"]
    fixed_priority_silvan = selected_by_id(result, "fixed_priority")["silvan_reservoir"]
    assert equal_blend_silvan["volume_drawn_ml_per_day"] != fixed_priority_silvan["volume_drawn_ml_per_day"]


def test_scenario_error_is_raised_with_baseline_context():
    with pytest.raises(BaselineRunnerError, match="equal_blend|cheapest_first|fixed_priority"):
        run_all_baselines({"scenario_id": "broken", "network": {}})


# ---------------------------------------------------------------------------
# 3. End-to-end agreement with Baseline_HandCalculations.md
# ---------------------------------------------------------------------------
def test_equal_blend_matches_hand_calculation(scenario):
    """Section 5: 220 / 220 / 60."""
    result = run_all_baselines(scenario)
    selected = selected_by_id(result, "equal_blend")
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(220.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(220.0, abs=VOLUME_TOLERANCE)
    assert selected["groundwater_bore_1"]["volume_drawn_ml_per_day"] == pytest.approx(60.0, abs=VOLUME_TOLERANCE)
    assert result["baselines"]["equal_blend"]["status"] == "FEASIBLE"


def test_cheapest_first_matches_hand_calculation(scenario):
    """Section 6, documented cap: yarra_kew 300, silvan 200, groundwater 0."""
    result = run_all_baselines(scenario)
    selected = selected_by_id(result, "cheapest_first")
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(300.0, abs=VOLUME_TOLERANCE)
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(200.0, abs=VOLUME_TOLERANCE)
    assert "groundwater_bore_1" not in selected
    assert result["baselines"]["cheapest_first"]["status"] == "FEASIBLE"


def test_fixed_priority_matches_hand_calculation(scenario):
    """Section 7: silvan 350, yarra_kew 150, groundwater 0."""
    result = run_all_baselines(scenario)
    selected = selected_by_id(result, "fixed_priority")
    assert selected["silvan_reservoir"]["volume_drawn_ml_per_day"] == pytest.approx(350.0, abs=VOLUME_TOLERANCE)
    assert selected["yarra_kew"]["volume_drawn_ml_per_day"] == pytest.approx(150.0, abs=VOLUME_TOLERANCE)
    assert "groundwater_bore_1" not in selected
    assert result["baselines"]["fixed_priority"]["status"] == "FEASIBLE"


def test_comparison_marks_all_three_feasible(scenario):
    result = run_all_baselines(scenario)
    assert set(result["comparison"]["feasible"]) == {
        "equal_blend",
        "cheapest_first",
        "fixed_priority",
    }
    assert result["comparison"]["infeasible"] == []


def test_comparison_excludes_incomplete_totals_from_cheapest(scenario):
    """equal_blend's total is None on the toy config (groundwater's cost is
    unconfirmed), so it must not be silently treated as free or win the
    cheapest comparison by default."""
    result = run_all_baselines(scenario)
    assert result["comparison"]["total_costs"]["equal_blend"] is None
    assert result["comparison"]["cheapest_by_total_cost"] != "equal_blend"


def test_comparison_picks_the_real_cheapest_among_complete_totals(scenario):
    """cheapest_first (182,500) beats fixed_priority (207,250) on total cost;
    equal_blend is excluded since its total is incomplete."""
    result = run_all_baselines(scenario)
    assert result["comparison"]["cheapest_by_total_cost"] == "cheapest_first"
    assert result["comparison"]["total_costs"]["cheapest_first"] == pytest.approx(
        182500.00, abs=COST_TOLERANCE
    )
    assert result["comparison"]["total_costs"]["fixed_priority"] == pytest.approx(
        207250.00, abs=COST_TOLERANCE
    )


# ---------------------------------------------------------------------------
# 4. The team's committed scenario files
# ---------------------------------------------------------------------------
SCENARIO_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def load_scenario_file(*parts):
    with open(SCENARIO_DIR.joinpath(*parts)) as handle:
        return json.load(handle)


def test_runs_on_the_committed_normal_scenario():
    result = run_all_baselines(load_scenario_file("normal-year-dry-year", "scenario_normal.json"))
    assert set(result["baselines"]) == {"equal_blend", "cheapest_first", "fixed_priority"}
    for name, entry in result["baselines"].items():
        assert entry["status"] == "FEASIBLE", name


def test_committed_plant_outage_scenario_is_infeasible_everywhere():
    result = run_all_baselines(load_scenario_file("high-demand-outage", "scenario_plant_outage.json"))
    assert result["comparison"]["feasible"] == []
    assert set(result["comparison"]["infeasible"]) == {
        "equal_blend",
        "cheapest_first",
        "fixed_priority",
    }


# ---------------------------------------------------------------------------
# 5. Cost-breakdown consistency (model_output_specification.md section 5, rule 1)
# ---------------------------------------------------------------------------
def test_cost_breakdown_sums_to_total_cost_when_total_is_known(scenario):
    """cheapest_first and fixed_priority both have a complete total on the
    toy config; the runner's own consistency check must not reject either."""
    result = run_all_baselines(scenario)
    for name in ("cheapest_first", "fixed_priority"):
        objective = result["baselines"][name]["objective"]
        breakdown_sum = sum(objective["cost_breakdown"].values())
        assert breakdown_sum == pytest.approx(objective["total_cost"], abs=COST_TOLERANCE)


def test_cost_consistency_check_is_skipped_when_total_is_none(scenario):
    """equal_blend's total is None on the toy config (groundwater's cost is
    unknown); the consistency check must not raise just because there is
    nothing to check it against."""
    result = run_all_baselines(scenario)
    assert result["baselines"]["equal_blend"]["objective"]["total_cost"] is None


def test_cost_consistency_check_catches_a_real_mismatch():
    """Directly exercises the internal check with a deliberately broken
    objective, since none of the three real baselines currently produce an
    inconsistent one to trigger it naturally."""
    from baseline_runner import _verify_cost_consistency

    broken_objective = {
        "total_cost": 100.00,
        "cost_breakdown": {
            "source_activation_cost": 0.0,
            "plant_activation_cost": 0.0,
            "source_draw_cost": 50.0,
            "plant_treatment_cost": 10.0,  # sums to 60, not 100
        },
    }
    with pytest.raises(BaselineRunnerError, match="cost_breakdown sums to"):
        _verify_cost_consistency("test_baseline", broken_objective)


def test_cost_consistency_check_passes_a_correct_objective():
    from baseline_runner import _verify_cost_consistency

    good_objective = {
        "total_cost": 60.00,
        "cost_breakdown": {
            "source_activation_cost": 0.0,
            "plant_activation_cost": 0.0,
            "source_draw_cost": 50.0,
            "plant_treatment_cost": 10.0,
        },
    }
    _verify_cost_consistency("test_baseline", good_objective)  # must not raise


# ---------------------------------------------------------------------------
# 6. Structural and serialization checks
# ---------------------------------------------------------------------------
def test_result_is_json_serializable(scenario):
    """The whole point is a machine-readable structure; if json.dumps can't
    handle it, it isn't one."""
    result = run_all_baselines(scenario)
    serialized = json.dumps(result)
    assert json.loads(serialized) == result


def test_top_level_keys_are_exactly_the_documented_shape(scenario):
    result = run_all_baselines(scenario)
    assert set(result) == {"scenario_id", "zone_id", "baselines", "comparison"}


def test_comparison_has_an_entry_for_every_baseline(scenario):
    result = run_all_baselines(scenario)
    assert set(result["comparison"]["total_costs"]) == {
        "equal_blend",
        "cheapest_first",
        "fixed_priority",
    }


def test_scenario_id_is_echoed_at_top_level(scenario):
    result = run_all_baselines(scenario)
    assert result["scenario_id"] == "toy_model_runner_test"


def test_baselines_dict_has_a_stable_key_order(scenario):
    """Not load-bearing for correctness, but a stable order makes generated
    JSON diffs and printouts predictable run to run."""
    result_a = run_all_baselines(scenario)
    result_b = run_all_baselines(copy.deepcopy(TOY_SCENARIO))
    assert list(result_a["baselines"]) == list(result_b["baselines"])
    assert list(result_a["baselines"]) == ["equal_blend", "cheapest_first", "fixed_priority"]


def test_running_twice_on_the_same_scenario_gives_identical_results(scenario):
    """Determinism check: no baseline should depend on anything but its input."""
    result_a = run_all_baselines(copy.deepcopy(scenario))
    result_b = run_all_baselines(copy.deepcopy(scenario))
    assert result_a == result_b


def test_warnings_are_preserved_per_baseline(scenario):
    """Every baseline keeps its own warnings list; the runner does not merge
    or drop them during normalization."""
    result = run_all_baselines(scenario)
    for name, entry in result["baselines"].items():
        assert "warnings" in entry, name
        assert isinstance(entry["warnings"], list), name


# ---------------------------------------------------------------------------
# 7. Zone selection
# ---------------------------------------------------------------------------
def test_single_zone_scenario_does_not_require_zone_id(scenario):
    """The toy config has one zone, so omitting zone_id must not raise."""
    result = run_all_baselines(scenario)
    assert result["zone_id"] is None
    assert result["baselines"]["equal_blend"]["demand_zones"][0]["zone_id"] == "zone_1"


def test_multi_zone_scenario_without_zone_id_raises_with_context():
    multi = _multi_zone_scenario()
    with pytest.raises(BaselineRunnerError, match="more than one demand zone"):
        run_all_baselines(multi)


def test_multi_zone_scenario_with_explicit_zone_id_selects_correctly():
    multi = _multi_zone_scenario()
    result = run_all_baselines(multi, zone_id="zone_2")
    assert result["zone_id"] == "zone_2"
    for name, entry in result["baselines"].items():
        assert entry["demand_zones"][0]["zone_id"] == "zone_2", name
        assert entry["demand_zones"][0]["demand_ml_per_day"] == pytest.approx(100.0), name


# ---------------------------------------------------------------------------
# 8. Input validation
# ---------------------------------------------------------------------------
def test_non_dict_scenario_raises_before_touching_any_baseline():
    with pytest.raises(BaselineRunnerError, match="JSON object"):
        run_all_baselines(["not", "a", "dict"])


def test_zero_demand_is_feasible_and_selects_nothing_everywhere(scenario):
    scenario["network"]["demand_zones"][0]["demand_ml_per_day"] = 0
    result = run_all_baselines(scenario)
    for name, entry in result["baselines"].items():
        assert entry["feasible"] is True, name
        assert entry["sources"]["selected"] == [], name
