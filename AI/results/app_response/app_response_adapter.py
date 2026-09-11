"""Task 27 - App & Delivery response adapter for AquaBlend [SECOND DRAFT].

This second draft incorporates review feedback from the initial implementation.
The adapter converts upstream analysis outputs into one predictable,
display oriented response without mutating the raw MILP result.

Task 27 is intentionally kept separate from the upstream owners:
- Task 19 owns KPI and pass/fail gate calculation.
- Task 21 owns result validation and confidence flagging.
- Tasks 23/25 own fallback and validated LLM reporting.
- Task 26 owns scenario/baseline comparison output.

Until those contracts are final, this module treats their payloads as
inputs and normalises only the outer App & Delivery response shape.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping


# Bumped for the executive_summary/detailed_explanation/visualization_data
# fields (AquaBlend final AI integration): the response shape gained new
# required fields, so this is not a purely additive change to 0.1-draft.
CONTRACT_VERSION = "0.2-draft"

SOLVER_STATUSES = {
    "OPTIMAL",
    "INFEASIBLE",
    "UNBOUNDED",
    "TIME_LIMIT",
    "ERROR",
}

REPORT_MODES = {
    "LLM_VALIDATED",
    "TEMPLATE_FALLBACK",
    "STATUS_ONLY",
    "INVALID_INPUT",
}

_REQUIRED_RESPONSE_FIELDS = {
    "contract_version",
    "scenario_id",
    "solver_status",
    "kpis",
    "gate_result",
    "confidence_flag",
    "comparison",
    "report_mode",
    "executive_summary",
    "detailed_explanation",
    "visualization_data",
    "display_explanation",
    "warnings",
}

def _non_empty_text(value: Any) -> str | None:
    """Return trimmed text, or None when the value is absent/blank."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None

def _dedupe(messages: Iterable[str]) -> list[str]:  
    """De-duplicate warning strings while preserving their order."""
    seen: set[str] = set()
    result: list[str] = []
    for message in messages:
        if not isinstance(message, str):
            continue
        cleaned = message.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _contract_warnings(milp_result: Mapping[str, Any] | None) -> list[str]:
    """Build display warnings that are directly supported by the MILP contract.

    These warnings are deliberately conservative. They do not replace the
    warning/confidence logic owned by upstream tasks; they surface known model
    caveats already present in the supplied MILP result contract.

    Currently, the adapter checks for three contract-supported warning types:
    1. Estimated source values are present in the MILP result.
    2. Source activation cost is structurally reported as 0.00 because the
       current model input path does not provide this cost.
    3. Water-quality values apply to the blend at plant inflow and should not
       be interpreted as post-treatment regulatory water quality.
    """
    if not milp_result:
        return []

    warnings: list[str] = []

    data_flags = milp_result.get("data_flags")
    if isinstance(data_flags, Mapping):
        source_flags = data_flags.get("sources")
        if isinstance(source_flags, list) and any(
            isinstance(source, Mapping)
            and source.get("has_estimated_values") is True
            for source in source_flags
        ):
            warnings.append(
                "One or more source inputs contain estimated values; "
                "interpret the result and confidence flag accordingly."
            )

        notes = data_flags.get("notes")
        if isinstance(notes, list) and any(
            isinstance(note, str)
            and "source_activation_cost is structurally 0.00" in note
            for note in notes
        ):
            warnings.append(
                "Source activation cost is currently structurally zero in the "
                "model input path and should not be interpreted as a confirmed "
                "real-world zero cost."
            )

    water_quality = milp_result.get("water_quality")
    if isinstance(water_quality, Mapping) and (
        water_quality.get("applies_to") == "blend_at_plant_inflow"
    ):
        warnings.append(
            "Water-quality values apply to the blend at plant inflow, not to "
            "post-treatment regulatory water quality."
        )

    return warnings


def build_app_response(
    milp_result: Mapping[str, Any] | None,
    *,
    scenario_id: str | None = None,
    input_valid: bool = True,
    kpis: Mapping[str, Any] | None = None,
    gate_result: str | None = None,
    confidence_flag: str | None = None,
    comparison: Mapping[str, Any] | None = None,
    llm_summary: str | None = None,
    llm_summary_validated: bool = False,
    deterministic_summary: str | None = None,
    detailed_explanation: str | None = None,
    visualization_data: Mapping[str, Any] | None = None,
    upstream_warnings: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return the App & Delivery response shape defined by the current draft contract.

    Parameters supplied by unfinished upstream tasks are passed into this
    function rather than recalculated here. The adapter selects a report mode,
    applies safe display behaviour for invalid/non-optimal cases, and returns
    fresh data structures so the raw MILP result is never overwritten.

    ``scenario_id`` is primarily useful for INVALID_INPUT responses, where a
    solver output may not exist. Otherwise the value is read from the MILP
    result.

    Only ``deterministic_summary`` (a short, operator-readable summary) may be
    replaced by a validated LLM rewrite (``llm_summary``/``llm_summary_validated``).
    ``detailed_explanation`` is always the complete deterministic technical
    report and is never rewritten by an LLM. ``executive_summary`` (and
    ``display_explanation``, kept for backward compatibility) reflect whichever
    summary source was actually used.
    """
    milp_copy: dict[str, Any] | None = (
        deepcopy(dict(milp_result)) if milp_result is not None else None
    )

    supplied_scenario_id = _non_empty_text(scenario_id)
    output_scenario_id = (
        _non_empty_text(milp_copy.get("scenario_id")) if milp_copy else None
    )
    response_scenario_id = supplied_scenario_id or output_scenario_id

    warnings = list(upstream_warnings or [])

    # INVALID_INPUT means the scenario did not reach a trustworthy solve.
    if not input_valid:
        warnings.append(
            "Scenario input validation failed; the solver result is not "
            "available for display."
        )
        summary = "The scenario could not be processed because the input was invalid."
        response = {
            "contract_version": CONTRACT_VERSION,
            "scenario_id": response_scenario_id,
            "solver_status": None,
            "kpis": None,
            "gate_result": None,
            "confidence_flag": None,
            "comparison": None,
            "report_mode": "INVALID_INPUT",
            "executive_summary": summary,
            "detailed_explanation": None,
            "visualization_data": None,
            "display_explanation": summary,
            "warnings": _dedupe(warnings),
        }
        validate_app_response(response)
        return response

    if milp_copy is None:
        raise ValueError("milp_result is required when input_valid=True")

    solver_status = _non_empty_text(milp_copy.get("status"))
    if solver_status not in SOLVER_STATUSES:
        raise ValueError(
            "MILP result contains an undocumented solver status: "
            f"{solver_status!r}"
        )

    warnings.extend(_contract_warnings(milp_copy))
    detailed_text = _non_empty_text(detailed_explanation)

    # The MILP output contract states that solution blocks are not meaningful
    # unless the solver status is OPTIMAL. Do not forward KPIs/comparisons in
    # this branch, even if stale values were supplied by a caller.
    if solver_status != "OPTIMAL":
        warnings.append(
            f"Solver status is {solver_status}; optimal-solution metrics and "
            "comparisons are not displayed."
        )
        summary = (
            f"The solver returned {solver_status}. No optimal solution is "
            "available for display."
        )
        response = {
            "contract_version": CONTRACT_VERSION,
            "scenario_id": response_scenario_id,
            "solver_status": solver_status,
            "kpis": None,
            "gate_result": _non_empty_text(gate_result),
            "confidence_flag": _non_empty_text(confidence_flag),
            "comparison": None,
            "report_mode": "STATUS_ONLY",
            "executive_summary": summary,
            "detailed_explanation": detailed_text,
            "visualization_data": None,
            "display_explanation": summary,
            "warnings": _dedupe(warnings),
        }
        validate_app_response(response)
        return response

    llm_text = _non_empty_text(llm_summary)
    fallback_text = _non_empty_text(deterministic_summary)

    if llm_summary_validated and llm_text:
        report_mode = "LLM_VALIDATED"
        summary = llm_text
    elif fallback_text:
        report_mode = "TEMPLATE_FALLBACK"
        summary = fallback_text
        warnings.append(
            "Validated LLM explanation was unavailable; a deterministic "
            "template fallback is being displayed."
        )
    else:
        report_mode = "STATUS_ONLY"
        summary = (
            "An optimal solution was found, but no validated display "
            "explanation is currently available."
        )
        warnings.append(
            "No validated LLM explanation or deterministic fallback was "
            "provided to the response adapter."
        )

    response = {
        "contract_version": CONTRACT_VERSION,
        "scenario_id": response_scenario_id,
        "solver_status": solver_status,
        "kpis": deepcopy(dict(kpis)) if kpis is not None else None,
        "gate_result": _non_empty_text(gate_result),
        "confidence_flag": _non_empty_text(confidence_flag),
        "comparison": (
            deepcopy(dict(comparison)) if comparison is not None else None
        ),
        "report_mode": report_mode,
        "executive_summary": summary,
        "detailed_explanation": detailed_text,
        "visualization_data": (
            deepcopy(dict(visualization_data)) if visualization_data is not None else None
        ),
        "display_explanation": summary,
        "warnings": _dedupe(warnings),
    }

    validate_app_response(response)
    return response


def validate_app_response(response: Mapping[str, Any]) -> None:
    """Perform dependency-free structural validation of an app response.

    Raises:
        ValueError: when the response does not follow the draft Task 27 shape.
    """
    missing = _REQUIRED_RESPONSE_FIELDS.difference(response.keys())
    if missing:
        raise ValueError(f"Response is missing required fields: {sorted(missing)}")

    if response["contract_version"] != CONTRACT_VERSION:
        raise ValueError(
            f"contract_version must be {CONTRACT_VERSION!r} in this draft"
        )

    scenario_id = response["scenario_id"]
    if scenario_id is not None and not _non_empty_text(scenario_id):
        raise ValueError("scenario_id must be a non-empty string or null")

    solver_status = response["solver_status"]
    if solver_status is not None and solver_status not in SOLVER_STATUSES:
        raise ValueError(f"Unsupported solver_status: {solver_status!r}")

    report_mode = response["report_mode"]
    if report_mode not in REPORT_MODES:
        raise ValueError(f"Unsupported report_mode: {report_mode!r}")

    if response["kpis"] is not None and not isinstance(response["kpis"], Mapping):
        raise ValueError("kpis must be an object or null")

    for field in ("gate_result", "confidence_flag"):
        value = response[field]
        if value is not None and not _non_empty_text(value):
            raise ValueError(f"{field} must be a non-empty string or null")

    if response["comparison"] is not None and not isinstance(
        response["comparison"], Mapping
    ):
        raise ValueError("comparison must be an object or null")

    executive_summary = response["executive_summary"]
    if not _non_empty_text(executive_summary):
        raise ValueError("executive_summary must be a non-empty string")

    explanation = response["display_explanation"]
    if not _non_empty_text(explanation):
        raise ValueError("display_explanation must be a non-empty string")

    if explanation != executive_summary:
        raise ValueError(
            "display_explanation must equal executive_summary (kept only for "
            "backward compatibility)"
        )

    detailed_explanation = response["detailed_explanation"]
    if detailed_explanation is not None and not _non_empty_text(detailed_explanation):
        raise ValueError("detailed_explanation must be a non-empty string or null")

    if response["visualization_data"] is not None and not isinstance(
        response["visualization_data"], Mapping
    ):
        raise ValueError("visualization_data must be an object or null")

    warnings = response["warnings"]
    if not isinstance(warnings, list) or not all(
        isinstance(item, str) and item.strip() for item in warnings
    ):
        raise ValueError("warnings must be a list of non-empty strings")

    # Cross-field safety rules.
    if report_mode == "INVALID_INPUT":
        if solver_status is not None:
            raise ValueError("INVALID_INPUT responses must have solver_status=null")
        if response["kpis"] is not None or response["comparison"] is not None:
            raise ValueError(
                "INVALID_INPUT responses must not expose solution KPIs/comparison"
            )
        if detailed_explanation is not None or response["visualization_data"] is not None:
            raise ValueError(
                "INVALID_INPUT responses must not expose a detailed explanation or "
                "visualization data"
            )

    if solver_status is not None and solver_status != "OPTIMAL":
        if response["kpis"] is not None or response["comparison"] is not None:
            raise ValueError(
                "Non-optimal solver responses must not expose solution KPIs/comparison"
            )

    if report_mode in {"LLM_VALIDATED", "TEMPLATE_FALLBACK"} and (
        solver_status != "OPTIMAL"
    ):
        raise ValueError(
            f"{report_mode} is only valid for an OPTIMAL solver result"
        )


def write_response_json(response: Mapping[str, Any], path: str | Path) -> None:
    """Validate and write a response as UTF-8 JSON."""
    validate_app_response(response)
    Path(path).write_text(
        json.dumps(dict(response), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
