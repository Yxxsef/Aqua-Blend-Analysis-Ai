"""
Aqua Blend MILP -> confirmed AI Results contract adapter.

This module bridges the current integrated MILP database/output schema to the
external Results JSON contract expected by the AI analysis pipeline.

Key rule:
    The MILP result remains the factual source of truth.

The adapter does not make optimisation decisions or invent missing analytical
results. Where the confirmed AI contract requires metadata/provenance that is
not present in milp_model_output, the matching milp_model_input row is loaded
using milp_model_output.input_id.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Mapping


AI_REQUIRED_FIELDS = {
    "scenario_id",
    "status",
    "objective",
    "demand_zones",
    "sources",
    "transfer_paths",
    "plants",
    "water_quality",
    "constraints",
    "diagnostics",
    "data_flags",
}

VALID_STATUS = {
    "OPTIMAL",
    "SUCCESS",
    "FEASIBLE",
    "INFEASIBLE",
    "UNBOUNDED",
    "ERROR",
    "TIME_LIMIT",
}


class MilpAiContractError(ValueError):
    """Raised when the integrated MILP result cannot be adapted safely."""


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    return {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        return parsed if isinstance(parsed, list) else []

    return []


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _status_for_ai(value: Any) -> str:
    status = str(value or "ERROR").strip().upper()
    status = status.replace("-", "_").replace(" ", "_")

    aliases = {
        "OPTIMAL_SOLUTION": "OPTIMAL",
        "FEASIBLE_SOLUTION": "FEASIBLE",
        "INFEASIBLE_PROBLEM": "INFEASIBLE",
        "UNBOUNDED_PROBLEM": "UNBOUNDED",
        "TIMELIMIT": "TIME_LIMIT",
        "TIMEOUT": "TIME_LIMIT",
        "FAILED": "ERROR",
        "FAILURE": "ERROR",
    }

    status = aliases.get(status, status)

    if status not in VALID_STATUS:
        raise MilpAiContractError(
            f"Unsupported solver status for AI contract: {value!r}"
        )

    return status


def _load_model_input(
    *,
    input_id: Any,
    db_url: str | None,
    db_key: str | None,
) -> dict[str, Any]:
    """
    Load the exact milp_model_input row referenced by milp_model_output.input_id.
    """

    if input_id is None:
        raise MilpAiContractError(
            "MILP output does not contain input_id, so source provenance "
            "cannot be loaded safely."
        )

    if not db_url or not db_key:
        raise MilpAiContractError(
            "DB_URL/DB_KEY are required to load the matching milp_model_input."
        )

    try:
        from supabase import create_client
    except ImportError as exc:
        raise MilpAiContractError(
            "The 'supabase' Python package is required to load milp_model_input."
        ) from exc

    try:
        client = create_client(db_url, db_key)
        response = (
            client.table("milp_model_input")
            .select("*")
            .eq("id", str(input_id))
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise MilpAiContractError(
            f"Failed to load milp_model_input {input_id}: {exc}"
        ) from exc

    rows = getattr(response, "data", None) or []

    if not rows:
        raise MilpAiContractError(
            f"No milp_model_input row found for input_id={input_id}."
        )

    row = rows[0]

    if not isinstance(row, dict):
        raise MilpAiContractError(
            "milp_model_input query returned an invalid row."
        )

    return row


def _index_by_id(
    records: Any,
    id_field: str,
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}

    for item in _as_list(records):
        if not isinstance(item, dict):
            continue

        item_id = item.get(id_field)

        if item_id is None:
            continue

        indexed[str(item_id)] = item

    return indexed


def _build_objective(
    payload: Mapping[str, Any],
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    solver = _as_dict(raw.get("solver"))
    summary = _as_dict(raw.get("summary"))
    costs = _as_dict(summary.get("costs"))

    total_cost = _first_not_none(
        costs.get("total_cost"),
        payload.get("total_cost"),
        payload.get("solver_objective_value"),
        solver.get("objective_value"),
    )

    objective: dict[str, Any] = {}

    if total_cost is not None:
        objective["total_cost"] = total_cost

    cost_breakdown: dict[str, Any] = {}

    mapping = {
        "source_activation_cost": costs.get("total_source_fixed_cost"),
        "plant_activation_cost": costs.get("total_plant_fixed_cost"),
        "source_draw_cost": costs.get("total_source_variable_cost"),
        "plant_treatment_cost": costs.get("total_plant_variable_cost"),
    }

    for key, value in mapping.items():
        if value is not None:
            cost_breakdown[key] = value

    if cost_breakdown:
        objective["cost_breakdown"] = cost_breakdown

    return objective


def _build_demand_zones(
    output_records: Any,
    input_records: Any,
) -> list[dict[str, Any]]:
    input_by_id = _index_by_id(input_records, "zone_id")
    result: list[dict[str, Any]] = []

    for output_row in _as_list(output_records):
        if not isinstance(output_row, dict):
            continue

        zone_id = output_row.get("zone_id")

        if zone_id is None:
            continue

        input_row = input_by_id.get(str(zone_id), {})

        row: dict[str, Any] = {
            "zone_id": str(zone_id),
        }

        name = input_row.get("name")
        if name is not None:
            row["zone_name"] = name

        demand = _first_not_none(
            input_row.get("demand_ml_per_day"),
            output_row.get("demand_ml_per_day"),
        )
        if demand is not None:
            row["demand_ml_per_day"] = demand

        supplied = _first_not_none(
            output_row.get("volume_supplied_ml_per_day"),
            output_row.get("delivered_ml_per_day"),
        )
        if supplied is not None:
            row["volume_supplied_ml_per_day"] = supplied

        # Preserve additional factual MILP fields.
        for key, value in output_row.items():
            row.setdefault(key, deepcopy(value))

        result.append(row)

    return result


def _build_sources(
    output_records: Any,
    source_snapshot: Any,
) -> dict[str, list[dict[str, Any]]]:
    snapshot_by_id = _index_by_id(source_snapshot, "source_id")

    selected: list[dict[str, Any]] = []
    unused: list[dict[str, Any]] = []

    for output_row in _as_list(output_records):
        if not isinstance(output_row, dict):
            continue

        source_id = output_row.get("source_id")

        if source_id is None:
            continue

        source_id = str(source_id)
        snapshot = snapshot_by_id.get(source_id, {})

        selection_status = str(
            output_row.get("selection_status", "")
        ).strip().upper()

        withdrawal = output_row.get("withdrawal_ml_per_day")
        blend_ratio = output_row.get("blend_ratio")

        row: dict[str, Any] = {
            "source_id": source_id,
        }

        if snapshot.get("name") is not None:
            row["source_name"] = snapshot["name"]

        if snapshot.get("source_type") is not None:
            row["source_type"] = snapshot["source_type"]

        is_selected = (
            selection_status == "SELECTED"
            or output_row.get("activated") is True
            or (
                isinstance(withdrawal, (int, float))
                and withdrawal > 0
            )
        )

        if is_selected:
            if withdrawal is not None:
                row["volume_drawn_ml_per_day"] = withdrawal

            if blend_ratio is not None:
                # Current integrated MILP contract uses blend_ratio as 0..1.
                # This is a unit conversion only; the optimisation decision
                # itself is not changed.
                if isinstance(blend_ratio, (int, float)) and 0 <= blend_ratio <= 1:
                    row["percent_of_blend"] = blend_ratio * 100
                else:
                    row["percent_of_blend"] = blend_ratio

            if snapshot.get("cost_per_ml") is not None:
                row["cost_per_ml"] = snapshot["cost_per_ml"]

            draw_cost = _first_not_none(
                output_row.get("total_source_cost"),
                output_row.get("variable_withdrawal_cost"),
            )
            if draw_cost is not None:
                row["draw_cost"] = draw_cost

            # Retain the current MILP evidence without renaming/removing it.
            row["milp_result"] = deepcopy(output_row)
            selected.append(row)

        else:
            reason = output_row.get("exclusion_reason_code")

            if (
                isinstance(reason, str)
                and reason.strip()
                and reason.strip().upper() not in {"N/A", "NA", "NONE"}
            ):
                row["reason"] = reason

            row["milp_result"] = deepcopy(output_row)
            unused.append(row)

    return {
        "selected": selected,
        "unused": unused,
    }


def _build_transfer_paths(raw_flows: Any) -> dict[str, list[dict[str, Any]]]:
    flows = _as_dict(raw_flows)

    result: dict[str, list[dict[str, Any]]] = {
        "source_to_plant": [],
        "plant_to_zone": [],
    }

    for key in ("source_to_plant", "plant_to_zone"):
        for item in _as_list(flows.get(key)):
            if not isinstance(item, dict):
                continue

            row = deepcopy(item)

            if "active" not in row and "activated" in row:
                row["active"] = row["activated"]

            result[key].append(row)

    return result


def _build_plants(
    output_records: Any,
    input_records: Any,
) -> dict[str, list[dict[str, Any]]]:
    input_by_id = _index_by_id(input_records, "plant_id")

    active: list[dict[str, Any]] = []
    inactive: list[dict[str, Any]] = []

    for output_row in _as_list(output_records):
        if not isinstance(output_row, dict):
            continue

        plant_id = output_row.get("plant_id")

        if plant_id is None:
            continue

        plant_id = str(plant_id)
        input_row = input_by_id.get(plant_id, {})

        row: dict[str, Any] = {
            "plant_id": plant_id,
        }

        if input_row.get("name") is not None:
            row["plant_name"] = input_row["name"]

        throughput = output_row.get("throughput_ml_per_day")
        if throughput is not None:
            row["volume_processed_ml_per_day"] = throughput

        if input_row.get("treatment_cost_per_ml") is not None:
            row["treatment_cost_per_ml"] = input_row["treatment_cost_per_ml"]

        treatment_cost = output_row.get("variable_treatment_cost")
        if treatment_cost is not None:
            row["treatment_cost"] = treatment_cost

        row["milp_result"] = deepcopy(output_row)

        if output_row.get("activated") is True:
            active.append(row)
        else:
            inactive.append(row)

    return {
        "active": active,
        "inactive": inactive,
    }


def _build_water_quality(
    raw_quality: Any,
    quality_limits: Any,
) -> dict[str, Any]:
    quality = _as_dict(raw_quality)
    limits = _as_dict(quality_limits)
    limit_parameters = _as_dict(limits.get("parameters"))

    result: dict[str, Any] = {
        "applies_to": _first_not_none(
            quality.get("applies_to"),
            limits.get("applies_to"),
        ),
        "by_plant": {},
    }

    for plant in _as_list(quality.get("plant_inflow")):
        if not isinstance(plant, dict):
            continue

        plant_id = plant.get("plant_id")
        if plant_id is None:
            continue

        parameters_out: dict[str, Any] = {}

        for parameter in _as_list(plant.get("parameters")):
            if not isinstance(parameter, dict):
                continue

            parameter_id = parameter.get("parameter_id")
            if parameter_id is None:
                continue

            parameter_id = str(parameter_id)
            contract_parameter: dict[str, Any] = {}

            value = _first_not_none(
                parameter.get("reported_value"),
                parameter.get("model_value"),
            )
            if value is not None:
                contract_parameter["value"] = value

            unit = _first_not_none(
                parameter.get("reported_unit"),
                parameter.get("model_unit"),
            )
            if unit is not None:
                contract_parameter["unit"] = unit

            limit = _as_dict(limit_parameters.get(parameter_id))

            if limit.get("min") is not None:
                contract_parameter["constraint_min"] = limit["min"]

            if limit.get("max") is not None:
                contract_parameter["constraint_max"] = limit["max"]

            within_limits = parameter.get("within_limits")
            if isinstance(within_limits, bool):
                contract_parameter["status"] = (
                    "PASS" if within_limits else "FAIL"
                )

            # Keep the exact MILP quality record as supporting factual data.
            contract_parameter["milp_result"] = deepcopy(parameter)

            parameters_out[parameter_id] = contract_parameter

        result["by_plant"][str(plant_id)] = parameters_out

    return result


def _build_constraints(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    """
    The current integrated MILP output exposes binding_constraints_summary,
    but not the confirmed contract's complete per-constraint records.

    An empty list is valid under results_validator.py and is preferable to
    fabricating detailed constraint records.
    """

    explicit_constraints = raw.get("constraints")

    if isinstance(explicit_constraints, list):
        return [
            deepcopy(item)
            for item in explicit_constraints
            if isinstance(item, dict)
        ]

    return []


def _build_diagnostics(
    payload: Mapping[str, Any],
    raw: Mapping[str, Any],
    model_input: Mapping[str, Any],
) -> dict[str, Any]:
    solver_config = _as_dict(model_input.get("solver_config_json"))
    solver = _as_dict(raw.get("solver"))
    validation = _as_dict(raw.get("validation"))

    diagnostics: dict[str, Any] = {}

    solver_name = _first_not_none(
        payload.get("solver_name"),
        solver_config.get("solver_name"),
    )

    if solver_name is not None:
        diagnostics["solver"] = solver_name

    solve_time_ms = payload.get("solve_time_ms")

    if isinstance(solve_time_ms, (int, float)):
        diagnostics["solve_time_seconds"] = solve_time_ms / 1000.0

    diagnostics["solver_status"] = solver.get("status")

    if validation:
        diagnostics["validation"] = deepcopy(validation)

    return diagnostics


def _build_data_flags(
    source_snapshot: Any,
    raw_warnings: Any,
) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []

    for source in _as_list(source_snapshot):
        if not isinstance(source, dict):
            continue

        source_id = source.get("source_id")

        if not isinstance(source_id, str) or not source_id.strip():
            raise MilpAiContractError(
                "source_data_snapshot_json contains a source without "
                "a valid source_id."
            )

        estimated = source.get("has_estimated_values")

        if not isinstance(estimated, bool):
            raise MilpAiContractError(
                f"Source {source_id} does not contain a boolean "
                "has_estimated_values value."
            )

        upstream_provenance = _as_dict(source.get("provenance"))

        provenance = {
            "storage_capacity": upstream_provenance.get("storage_capacity"),
            "reference_flow": upstream_provenance.get("reference_flow"),
            "max_available": _first_not_none(
                upstream_provenance.get("max_available"),
                upstream_provenance.get("maximum_withdrawal"),
            ),
            "cost": upstream_provenance.get("cost"),
            "alkalinity": _first_not_none(
                upstream_provenance.get("alkalinity"),
                upstream_provenance.get("quality.alkalinity"),
            ),
        }

        record: dict[str, Any] = {
            "source_id": source_id,
            "has_estimated_values": estimated,
            "provenance": provenance,
        }

        availability_origin = _first_not_none(
            source.get("availability_origin"),
            source.get("withdrawal_bounds_origin"),
        )

        if availability_origin is not None:
            record["availability_origin"] = availability_origin

        sources.append(record)

    result: dict[str, Any] = {
        "sources": sources,
    }

    warnings = _as_list(raw_warnings)
    if warnings:
        result["notes"] = deepcopy(warnings)

    return result


def adapt_milp_output_for_ai(
    payload: Mapping[str, Any],
    *,
    model_input: Mapping[str, Any] | None = None,
    db_url: str | None = None,
    db_key: str | None = None,
) -> dict[str, Any]:
    """
    Convert the current Aqua Blend integrated MILP output into the confirmed
    external Results JSON contract required by the AI pipeline.

    If payload is already in the confirmed Results contract, it is returned
    unchanged (deep-copied). This preserves compatibility with existing tests
    and legacy fixture-driven execution.
    """

    if not isinstance(payload, Mapping):
        raise MilpAiContractError(
            "MILP AI adapter expected a dictionary-like result."
        )

    original = deepcopy(dict(payload))

    if AI_REQUIRED_FIELDS.issubset(original.keys()):
        return original

    raw = _as_dict(original.get("raw_output_json"))

    if not raw:
        raise MilpAiContractError(
            "MILP output does not contain a valid raw_output_json object."
        )

    if model_input is None:
        model_input = _load_model_input(
            input_id=original.get("input_id"),
            db_url=db_url,
            db_key=db_key,
        )
    else:
        model_input = deepcopy(dict(model_input))

    source_snapshot = _as_list(
        model_input.get("source_data_snapshot_json")
    )

    input_plants = _as_list(model_input.get("plants"))
    input_demand_zones = _as_list(model_input.get("demand_zones"))
    quality_limits = _as_dict(model_input.get("quality_limits"))

    raw_solver = _as_dict(raw.get("solver"))

    scenario_id = _first_not_none(
        original.get("scenario_id"),
        model_input.get("scenario_external_id"),
    )

    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise MilpAiContractError(
            "Unable to determine a valid scenario_id for the AI contract."
        )

    status = _status_for_ai(
        _first_not_none(
            raw_solver.get("status"),
            original.get("solver_status"),
        )
    )

    output_sources = _first_not_none(
        raw.get("sources"),
        original.get("sources"),
        [],
    )

    output_plants = _first_not_none(
        raw.get("plants"),
        original.get("plants"),
        [],
    )

    output_demand_zones = _first_not_none(
        raw.get("demand_zones"),
        original.get("demand_zones"),
        [],
    )

    result: dict[str, Any] = {
        "scenario_id": scenario_id,
        "status": status,
        "objective": _build_objective(original, raw),
        "demand_zones": _build_demand_zones(
            output_demand_zones,
            input_demand_zones,
        ),
        "sources": _build_sources(
            output_sources,
            source_snapshot,
        ),
        "transfer_paths": _build_transfer_paths(
            raw.get("flows")
        ),
        "plants": _build_plants(
            output_plants,
            input_plants,
        ),
        "water_quality": _build_water_quality(
            raw.get("quality"),
            quality_limits,
        ),
        "constraints": _build_constraints(raw),
        "diagnostics": _build_diagnostics(
            original,
            raw,
            model_input,
        ),
        "data_flags": _build_data_flags(
            source_snapshot,
            raw.get("warnings"),
        ),
    }

    # Pass through factual optional fields only when they already exist.
    optional_fields = (
        "solved_at",
        "binding_constraints_summary",
        "alternative_feasible_solutions",
        "sensitivity_to_key_assumptions",
        "explanation",
    )

    for field in optional_fields:
        value = _first_not_none(
            raw.get(field),
            original.get(field),
        )
        if value is not None:
            result[field] = deepcopy(value)

    return result
