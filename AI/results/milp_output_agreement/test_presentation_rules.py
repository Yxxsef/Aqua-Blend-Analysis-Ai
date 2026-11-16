"""
Tests for the Task 45 agreement.

The first two tests are drift checks: if the MILP team adds, renames or
removes an output field, they fail and name the field, so the agreement has
to be updated on purpose rather than silently going stale.
"""

import json
from pathlib import Path

import pytest

from presentation_gate import (
    INVALID_OUTPUT,
    NO_SOLUTION,
    VALID,
    gate_mode,
    leaf_paths,
    load_rules,
    presentable_values,
)

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"
# The contract template is optional here; point CONTRACT_PATH at your clone to include it.
CONTRACT_PATH = HERE / "fixtures" / "output_contract_v1.json"

RULES = load_rules()


def _load(name):
    with (FIXTURES / name).open(encoding="utf-8") as handle:
        return json.load(handle)


FEASIBLE = _load("feasible.json")
INFEASIBLE = _load("infeasible.json")
DOCUMENTS = [FEASIBLE, INFEASIBLE] + (
    [json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))] if CONTRACT_PATH.exists() else []
)


def _paths(document):
    return {path for path, _, _ in leaf_paths(document)}


def test_every_output_field_is_classified():
    seen = set().union(*(_paths(doc) for doc in DOCUMENTS))
    unclassified = sorted(seen - set(RULES["fields"]))
    assert not unclassified, f"Fields with no presentation rule: {unclassified}"


def test_no_rule_for_a_field_that_does_not_exist():
    seen = set().union(*(_paths(doc) for doc in DOCUMENTS))
    stale = sorted(set(RULES["fields"]) - seen)
    assert not stale, f"Rules for fields not present in any output: {stale}"


def test_rule_values_are_from_the_allowed_sets():
    for path, rule in RULES["fields"].items():
        assert rule["use"] in RULES["categories"], path
        assert rule["when"] in {"always", "valid"}, path


def test_gate_modes_on_real_outputs():
    assert gate_mode(FEASIBLE) == VALID
    assert gate_mode(INFEASIBLE) == NO_SOLUTION


def test_feasible_but_inconsistent_output_is_not_valid():
    broken = json.loads(json.dumps(FEASIBLE))
    broken["validation"]["output_consistency"]["status"] = "FAILED"
    assert gate_mode(broken) == INVALID_OUTPUT
    assert ("summary.costs.total_cost", 533000.0) not in presentable_values(broken, RULES)


def test_infeasible_run_hides_zero_filled_figures():
    allowed = dict(presentable_values(INFEASIBLE, RULES))
    # Postprocessing fills these with 0.0 / full demand on an infeasible run.
    assert INFEASIBLE["summary"]["costs"]["total_cost"] == 0.0
    assert INFEASIBLE["demand_zones"][0]["unmet_demand_ml_per_day"] == 1200.0
    for path in (
        "summary.costs.total_cost",
        "summary.total_delivered_ml_per_day",
        "sources[].withdrawal_ml_per_day",
        "demand_zones[].unmet_demand_ml_per_day",
        "demand_zones[].demand_satisfied",
    ):
        assert path not in allowed, path
    assert allowed["solver.status"] == "infeasible"
    assert allowed["summary.total_demand_ml_per_day"] == 1200.0


def test_feasible_run_allows_reported_quality_but_not_ph_model_limits():
    allowed = presentable_values(FEASIBLE, RULES)
    paths = [path for path, _ in allowed]
    assert ("summary.costs.total_cost", 533000.0) in allowed
    assert "quality.plant_inflow[].parameters[].reported_value" in paths
    model_max_values = [
        value for path, value in allowed
        if path == "quality.plant_inflow[].parameters[].model_max"
    ]
    # Alkalinity and turbidity limits are allowed; the pH (hydrogen-ion) one is not.
    ph = next(
        p for p in FEASIBLE["quality"]["plant_inflow"][0]["parameters"]
        if p["transform"] == "ph_to_hydrogen_ion"
    )
    assert ph["model_max"] not in model_max_values
    assert len(model_max_values) == 2


@pytest.mark.parametrize("path", ["sources[].decision_evidence.unit_cost_rank", "schema_version"])
def test_evidence_and_internal_fields_are_never_presentable(path):
    assert path not in {p for p, _ in presentable_values(FEASIBLE, RULES)}
