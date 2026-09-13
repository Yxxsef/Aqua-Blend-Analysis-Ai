"""
Adapter between Aqua Blend's current MILP database/output contract
and the Results contract expected by the AI analysis pipeline.

The adapter is intentionally non-destructive:
- all existing database fields are preserved;
- raw_output_json is preserved;
- the legacy/AI-facing fields are added;
- already-compatible AI Results payloads pass through unchanged.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


AI_REQUIRED_FIELDS = {
    "status",
    "objective",
    "transfer_paths",
    "water_quality",
    "constraints",
    "diagnostics",
    "data_flags",
}


class MilpAiContractError(ValueError):
    """Raised when a MILP result cannot be converted for AI analysis."""


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _index_records(
    value: Any,
    id_field: str,
) -> dict[str, dict]:
    """
    Convert a MILP entity collection into the object form expected
    by the AI Results contract.

    Example:
        [{"source_id": "SRC_001", ...}]
    becomes:
        {"SRC_001": {"source_id": "SRC_001", ...}}
    """

    if isinstance(value, dict):
        return deepcopy(value)

    if not isinstance(value, list):
        return {}

    indexed: dict[str, dict] = {}

    for item in value:
        if not isinstance(item, dict):
            continue

        record_id = item.get(id_field)

        if record_id is None:
            continue

        indexed[str(record_id)] = deepcopy(item)

    return indexed


def _build_transfer_paths(
    source_to_plant: list,
    plant_to_zone: list,
) -> list:
    """
    Flatten both MILP flow families into a common transfer-path list.

    Original fields are deliberately retained so downstream AI code can
    still access source_id / plant_id / zone_id / flow_ml_per_day.
    """

    paths: list[dict] = []

    for flow in source_to_plant:
        if not isinstance(flow, dict):
            continue

        path = deepcopy(flow)
        path["path_type"] = "source_to_plant"

        path.setdefault("from_id", flow.get("source_id"))
        path.setdefault("to_id", flow.get("plant_id"))

        paths.append(path)

    for flow in plant_to_zone:
        if not isinstance(flow, dict):
            continue

        path = deepcopy(flow)
        path["path_type"] = "plant_to_zone"

        path.setdefault("from_id", flow.get("plant_id"))
        path.setdefault("to_id", flow.get("zone_id"))

        paths.append(path)

    return paths


def adapt_milp_output_for_ai(payload: Mapping[str, Any]) -> dict:
    """
    Convert the current Aqua Blend MILP output into the contract required
    by the AI analysis pipeline.

    Current MILP raw_output_json:
        solver
        summary
        flows
        quality
        binding_constraints_summary
        validation
        warnings

    AI pipeline requires:
        status
        objective
        transfer_paths
        water_quality
        constraints
        diagnostics
        data_flags
    """

    if not isinstance(payload, Mapping):
        raise MilpAiContractError(
            "MILP AI adapter expected a mapping/dictionary payload."
        )

    output = deepcopy(dict(payload))

    # If the payload is already in the AI Results contract, do nothing.
    if AI_REQUIRED_FIELDS.issubset(output.keys()):
        return output

    raw = output.get("raw_output_json")

    if raw is None:
        raw = {}

    if not isinstance(raw, dict):
        raise MilpAiContractError(
            "raw_output_json must be a JSON object/dictionary."
        )

    solver = _as_dict(raw.get("solver"))
    summary = _as_dict(raw.get("summary"))
    costs = _as_dict(summary.get("costs"))
    flows = _as_dict(raw.get("flows"))
    validation = _as_dict(raw.get("validation"))

    source_to_plant = _as_list(
        _first_not_none(
            flows.get("source_to_plant"),
            output.get("flows_source_to_plant"),
        )
    )

    plant_to_zone = _as_list(
        _first_not_none(
            flows.get("plant_to_zone"),
            output.get("flows_plant_to_zone"),
        )
    )

    quality = _first_not_none(
        raw.get("quality"),
        output.get("quality"),
        {},
    )

    binding_constraints = _first_not_none(
        raw.get("binding_constraints_summary"),
        output.get("binding_constraints_summary"),
        [],
    )

    warnings = _first_not_none(
        raw.get("warnings"),
        output.get("warnings"),
        [],
    )

    if not isinstance(warnings, list):
        warnings = [warnings]

    status = _first_not_none(
        solver.get("status"),
        output.get("solver_status"),
        "unknown",
    )

    # The AI Results contract uses canonical uppercase solver states.
    # Current MILP output stores values such as "optimal".
    status = (
        str(status)
        .strip()
        .upper()
        .replace("-", "_")
        .replace(" ", "_")
    )

    objective_value = _first_not_none(
        solver.get("objective_value"),
        output.get("solver_objective_value"),
        output.get("total_cost"),
        costs.get("total_cost"),
    )

    total_cost = _first_not_none(
        costs.get("total_cost"),
        output.get("total_cost"),
        objective_value,
    )

    transfer_paths = _build_transfer_paths(
        source_to_plant,
        plant_to_zone,
    )

    # ------------------------------------------------------------------
    # Normalise MILP entity collections.
    #
    # Current MILP output stores these as JSON arrays.
    # The AI Results contract expects keyed JSON objects.
    # ------------------------------------------------------------------

    source_records = _first_not_none(
        raw.get("sources"),
        output.get("sources"),
        [],
    )

    plant_records = _first_not_none(
        raw.get("plants"),
        output.get("plants"),
        [],
    )

    demand_zone_records = _first_not_none(
        raw.get("demand_zones"),
        output.get("demand_zones"),
        [],
    )

    output["sources"] = _index_records(
        source_records,
        "source_id",
    )

    output["plants"] = _index_records(
        plant_records,
        "plant_id",
    )

    output["demand_zones"] = _index_records(
        demand_zone_records,
        "zone_id",
    )

    # ------------------------------------------------------------------
    # Add the AI Results contract.
    # ------------------------------------------------------------------

    output["status"] = status

    output["objective"] = {
        "value": objective_value,
        "total_cost": total_cost,
        "sense": "minimize",
        "costs": deepcopy(costs),
    }

    # The AI contract expects transfer_paths to be an object,
    # while the MILP output stores the two path families as arrays.
    output["transfer_paths"] = {
        "source_to_plant": deepcopy(source_to_plant),
        "plant_to_zone": deepcopy(plant_to_zone),
        "all_paths": deepcopy(transfer_paths),
    }

    output["water_quality"] = deepcopy(quality)

    # The current MILP output stores binding constraints as an array.
    # Wrap them in an object for the AI Results contract.
    if isinstance(binding_constraints, dict):
        output["constraints"] = deepcopy(binding_constraints)
    else:
        output["constraints"] = {
            "binding_constraints": deepcopy(
                binding_constraints
                if isinstance(binding_constraints, list)
                else []
            )
        }

    output["diagnostics"] = deepcopy(validation)

    output["data_flags"] = {
        "warnings": deepcopy(warnings),
        "has_warnings": bool(warnings),

        "allow_estimated_values": output.get(
            "allow_estimated_values"
        ),

        "loader_status": (
            _as_dict(validation.get("loader")).get("status")
            or output.get("loader_status")
        ),

        "preprocessing_status": (
            _as_dict(validation.get("preprocessing")).get("status")
            or output.get("preprocessing_status")
        ),

        "output_consistency_status": (
            _as_dict(
                validation.get("output_consistency")
            ).get("status")
            or output.get("output_consistency_status")
        ),

        "solver_is_feasible": _first_not_none(
            solver.get("is_feasible"),
            output.get("solver_is_feasible"),
        ),

        "solver_is_optimal": _first_not_none(
            solver.get("is_optimal"),
            output.get("solver_is_optimal"),
        ),
    }

    # Keep useful aliases for analysis/debugging.
    output["ai_contract_adapter"] = {
        "version": "1.0",
        "source_contract": "aqua_blend_milp_output",
        "target_contract": "aqua_blend_ai_results",
    }

    missing = [
        field
        for field in AI_REQUIRED_FIELDS
        if field not in output
    ]

    if missing:
        raise MilpAiContractError(
            "MILP → AI adaptation failed. Missing AI fields: "
            + ", ".join(sorted(missing))
        )

    return output
