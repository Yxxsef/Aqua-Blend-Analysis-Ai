"""
Regenerate the real MILP output fixtures used by the Task 45 agreement.

Builds the base scenario (config/scenarios/base_scenarios_v1.json) the same way
as MILP/tests/mock_pipeline.py, solves it with Pyomo/HiGHS, and writes the
serialised SolvedScenario (pipeline.solved_scenario_to_json, the same function
the worker uses) for two cases:

- feasible.json:   the base scenario as configured
- infeasible.json: the same scenario with the turbidity upper limit lowered to
                   0.5 NTU, so no blend can satisfy it (quality pre-check skipped)

Difference from mock_pipeline.py: source quality keys use "ph" to match the
scenario's quality_limits. mock_pipeline.py uses "pH" and currently fails
preprocessing on master (gap G13).

Run from the MILP folder:
    PYTHONPATH=. python3 path/to/make_fixtures.py path/to/fixtures
"""

import json

from src.contracts import (
    DemandZoneInput,
    PlantInput,
    ScenarioData,
    SourceInput,
    SourcePlantLinkInput,
    PlantZoneLinkInput,
    InputValidationPolicy,
    LoaderValidation,
)
from src.preprocessing import preprocess_scenario
from src.model import solve
from src.postprocessing import postprocess_solution, print_solution_summary

# Illustrative-only quality/cost values (the real scenario sources this from
# Supabase; the JSON file only carries withdrawal overrides).
SOURCE_INFO = {
    "225103": dict(name="Thomson Reservoir", cost=450.0, pH=7.2, alkalinity=45.0, turbidity=1.2),
    "229421": dict(name="O'Shannassy Reservoir", cost=380.0, pH=6.8, alkalinity=30.0, turbidity=0.8),
    "233217": dict(name="Barwon River at Geelong", cost=520.0, pH=7.6, alkalinity=85.0, turbidity=2.5),
}

with open("config/scenarios/base_scenarios_v1.json") as f:
    raw = json.load(f)

sources = tuple(
    SourceInput(
        source_id=s["source_id"],
        name=s["name"],
        source_type="reservoir",
        enabled=s["enabled"],
        forced_inactive=s["forced_inactive"],
        minimum_withdrawal_ml_per_day=s["minimum_withdrawal_ml_per_day_override"],
        maximum_withdrawal_ml_per_day=s["max_available_ml_per_day_override"],
        withdrawal_bounds_origin="scenario_override",
        fixed_activation_cost=s["fixed_activation_cost"],
        cost_per_ml=SOURCE_INFO[s["source_id"]]["cost"],
        quality={
            "ph": SOURCE_INFO[s["source_id"]]["pH"],
            "alkalinity": SOURCE_INFO[s["source_id"]]["alkalinity"],
            "turbidity": SOURCE_INFO[s["source_id"]]["turbidity"],
        },
        has_estimated_values=False,
        database_model_ready=True,
        availability_status="available",
        provenance={},
    )
    for s in raw["sources"]
)

plants = tuple(
    PlantInput(
        plant_id=p["plant_id"],
        name=p["name"],
        enabled=p["enabled"],
        minimum_processing_capacity_ml_per_day=p["minimum_processing_capacity_ml_per_day"],
        maximum_processing_capacity_ml_per_day=p["maximum_processing_capacity_ml_per_day"],
        fixed_activation_cost=p["fixed_activation_cost"],
        treatment_cost_per_ml=p["treatment_cost_per_ml"],
    )
    for p in raw["network"]["plants"]
)

demand_zones = tuple(
    DemandZoneInput(
        zone_id=z["zone_id"],
        name=z["name"],
        demand_ml_per_day=z["demand_ml_per_day"],
    )
    for z in raw["network"]["demand_zones"]
)

source_links = tuple(
    SourcePlantLinkInput(
        source_id=l["source_id"],
        plant_id=l["plant_id"],
        enabled=l["enabled"],
        maximum_flow_ml_per_day=l["maximum_flow_ml_per_day"],
    )
    for l in raw["network"]["source_to_plant_links"]
)

zone_links = tuple(
    PlantZoneLinkInput(
        plant_id=l["plant_id"],
        zone_id=l["zone_id"],
        enabled=l["enabled"],
        maximum_flow_ml_per_day=l["maximum_flow_ml_per_day"],
    )
    for l in raw["network"]["plant_to_zone_links"]
)

scenario = ScenarioData(
    scenario_id=raw["scenario_id"],
    scenario_name=raw["scenario_name"],
    status=raw["status"],
    description=raw["description"],
    sources=sources,
    plants=plants,
    demand_zones=demand_zones,
    source_to_plant_links=source_links,
    plant_to_zone_links=zone_links,
    quality_limits=raw["quality_limits"],
    validation_issues=(),
    input_validation_policy=InputValidationPolicy(
        fail_if_source_missing_from_database=True,
        fail_if_daily_availability_missing=True,
        fail_if_required_quality_value_missing=True,
        fail_if_demand_missing=True
    ),
   loader_validation=LoaderValidation(
        status="PASSED",
        scenario_ready=True,
        validation_issues=(),
        checks=(),
    )
)

import copy, sys
from dataclasses import replace
from src.pipeline import solved_scenario_to_json
OUT = sys.argv[1] if len(sys.argv) > 1 else "."

def run(sc, name, **kw):
    p = preprocess_scenario(sc, run_id=f"demo-{name}", **kw)
    m, r = solve(p)
    s = postprocess_solution(sc, p, m, r)
    open(f"{OUT}/{name}.json", "w").write(solved_scenario_to_json(s, indent=2))
    print(name, s.solver.status, s.solver.is_feasible, s.solver.objective_value)

run(scenario, "feasible")
ql = copy.deepcopy(scenario.quality_limits)
ql["parameters"]["turbidity"]["max"] = 0.5
run(replace(scenario, quality_limits=ql), "infeasible", validate_quality_feasibility=False)
