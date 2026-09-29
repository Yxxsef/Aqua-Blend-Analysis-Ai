"""Build a solved MILP v1.0 fixture from the frozen contract template.

The solved values are the same solution already stored in the Sprint 2 toy
fixture (model_output_example.json), re-expressed in the v1.0 schema. Keeping
one solution in two shapes means the adapter can be tested: both fixtures must
produce the same internal representation.
"""

import json
from pathlib import Path

CONTRACT = Path("contract_v1.json")

# The frozen contract template, pinned to the commit it was reviewed at. It is
# the MILP team's file, so it is not committed here — fetch it when needed.
CONTRACT_URL = (
    "https://raw.githubusercontent.com/ksuraev/Aqua-Blend-MILP-Team/"
    "ef29b89c62ad46e88227482cb0dbd621bc69af88/MILP/json_contracts/"
    "output_contract_v1.json"
)
OUT = Path("fixtures/milp_v1_solved_example.json")

# Solved solution, taken from the Sprint 2 toy fixture.
WITHDRAWALS = {"silvan_reservoir": 210.0, "yarra_kew": 290.0, "groundwater_bore_1": 0.0}
UNIT_COST = {"silvan_reservoir": 400.0, "yarra_kew": 235.0}  # groundwater cost lives in Supabase, not the repo
# Only yarra_kew's withdrawal bound is derivable (toy fixture shows it binding at 290).
BINDING_UPPER = {"silvan_reservoir": False, "yarra_kew": True, "groundwater_bore_1": False}
LINK_CAPACITY = {"silvan_reservoir": 350.0, "yarra_kew": 300.0, "groundwater_bore_1": 60.0}
PLANT_CAPACITY = 600.0
TREATMENT_COST_PER_ML = 64.0
DEMAND = 500.0

# Blend quality at plant inflow, from the toy fixture.
PH_REPORTED = 7.11
ALKALINITY = 38.04
TURBIDITY = 5.28


def ph_to_nmol(ph):
    """Convert pH to hydrogen-ion concentration in nmol/L."""
    return 10 ** (-ph) * 1e9


def pass_all(block):
    """Mark a validation block as run and passing."""
    block["status"] = "PASS"
    for check in block.get("checks", []):
        check["passed"] = True
    return block


def main():
    if not CONTRACT.is_file():
        raise SystemExit(
            f"{CONTRACT} not found. Fetch the frozen contract first:\n\n"
            f"    curl -sfL -o {CONTRACT} \\\n      {CONTRACT_URL}\n"
        )

    doc = json.loads(CONTRACT.read_text())

    total_withdrawal = sum(WITHDRAWALS.values())
    source_variable_cost = sum(WITHDRAWALS[s] * UNIT_COST.get(s, 0.0) for s in WITHDRAWALS)
    plant_variable_cost = total_withdrawal * TREATMENT_COST_PER_ML
    total_cost = source_variable_cost + plant_variable_cost

    doc["run_id"] = "fixture_milp_v1_solved_001"

    for name in ("loader", "preprocessing", "output_consistency"):
        pass_all(doc["validation"][name])
    doc["validation"]["loader"]["scenario_ready"] = True

    doc["solver"].update(
        {
            "status": "OPTIMAL",
            "is_feasible": True,
            "is_optimal": True,
            "objective_value": total_cost,
        }
    )

    doc["summary"].update(
        {
            "total_withdrawal_ml_per_day": total_withdrawal,
            "total_treated_ml_per_day": total_withdrawal,
            "total_delivered_ml_per_day": total_withdrawal,
            "selected_source_count": sum(1 for v in WITHDRAWALS.values() if v > 0),
            "active_plant_count": 1,
        }
    )
    doc["summary"]["costs"].update(
        {
            "total_source_fixed_cost": 0.0,
            "total_source_variable_cost": source_variable_cost,
            "total_plant_fixed_cost": 0.0,
            "total_plant_variable_cost": plant_variable_cost,
            "reconstructed_total_cost": total_cost,
            "total_cost": total_cost,
            "cost_reconciles": True,
        }
    )

    # Cheapest source gets rank 1.
    ranked = sorted(UNIT_COST, key=UNIT_COST.get)
    cost_rank = {sid: i + 1 for i, sid in enumerate(ranked)}  # groundwater omitted -> null

    for record in doc["sources"]:
        sid = record["source_id"]
        drawn = WITHDRAWALS[sid]
        record.update(
            {
                "model_included": True,
                "activated": drawn > 0,
                "withdrawal_ml_per_day": drawn,
                # Source withdrawal bounds are not in the repo, so this cannot be computed.
                "utilisation_percent": None,
                "blend_ratio": round(drawn / total_withdrawal, 4) if drawn > 0 else None,
                "variable_withdrawal_cost": drawn * UNIT_COST.get(sid, 0.0),
                "total_source_cost": drawn * UNIT_COST.get(sid, 0.0),
                "selection_status": "SELECTED" if drawn > 0 else "UNUSED",
                "exclusion_reason_code": None,
            }
        )
        record["decision_evidence"].update(
            {
                "unit_cost_rank": cost_rank.get(sid),
                "binding_lower": False,
                "binding_upper": BINDING_UPPER[sid],
            }
        )

    plant = doc["plants"][0]
    plant.update(
        {
            "activated": True,
            "throughput_ml_per_day": total_withdrawal,
            "utilisation_percent": round(total_withdrawal / PLANT_CAPACITY * 100, 2),
            "variable_treatment_cost": plant_variable_cost,
            "total_plant_cost": plant_variable_cost,
        }
    )

    zone = doc["demand_zones"][0]
    zone.update(
        {
            "delivered_ml_per_day": total_withdrawal,
            "surplus_ml_per_day": max(0.0, total_withdrawal - DEMAND),
            "demand_satisfied": total_withdrawal >= DEMAND,
            "unmet_demand_ml_per_day": max(0.0, DEMAND - total_withdrawal),
        }
    )

    for link in doc["flows"]["source_to_plant"]:
        sid = link["source_id"]
        flow = WITHDRAWALS[sid]
        link.update(
            {
                "activated": flow > 0,
                "flow_ml_per_day": flow,
                "utilisation_percent": round(flow / LINK_CAPACITY[sid] * 100, 2),
            }
        )

    for link in doc["flows"]["plant_to_zone"]:
        link.update(
            {
                "activated": True,
                "flow_ml_per_day": total_withdrawal,
                "utilisation_percent": round(total_withdrawal / PLANT_CAPACITY * 100, 2),
            }
        )

    inflow = doc["quality"]["plant_inflow"][0]
    inflow["flow_ml_per_day"] = total_withdrawal

    measured = {
        "pH": (ph_to_nmol(PH_REPORTED), PH_REPORTED),
        "alkalinity": (ALKALINITY, ALKALINITY),
        "turbidity": (TURBIDITY, TURBIDITY),
    }

    for param in inflow["parameters"]:
        model_value, reported = measured[param["parameter_id"]]
        lo, hi = param["model_min"], param["model_max"]
        param.update(
            {
                "model_value": round(model_value, 4),
                "reported_value": reported,
                "within_limits": lo <= model_value <= hi,
                "binding_lower": abs(model_value - lo) < 1e-6,
                "binding_upper": abs(model_value - hi) < 1e-6,
            }
        )

    doc["binding_constraints_summary"] = [
        "Source yarra_kew is operating at its maximum withdrawal bound.",
        "Source groundwater_bore_1 is not activated.",
    ]
    doc["warnings"] = [
        "Fixture derived from the frozen v1.0 contract template. Solved values "
        "reproduce the Sprint 2 toy fixture solution; they are not from a real solve.",
        "sources[].utilisation_percent is null: source withdrawal bounds are not "
        "available in this repo. v1.0 no longer echoes them, so they must come from "
        "ScenarioData/ModelParameters.",
        "groundwater_bore_1 unit_cost_rank is null: its cost_per_ml is not published "
        "in the toy fixture or the scenario file.",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
