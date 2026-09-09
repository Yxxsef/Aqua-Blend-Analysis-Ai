"""
results_adapter.py

Provides a stable internal adapter for the MILP output
contract v1 (fixture:
AI/results/tests/fixtures/output_contract_v1.json).

External MILP field names remain unchanged.
Internal naming differences are handled here.

Unresolved contract questions are recorded in
MILP_Output_Validation_Notes.md. The adapter does not
invent values or mappings that the v1 contract does
not define.
"""

from typing import Any


class AdapterError(Exception):
    """Raised when Results JSON cannot be adapted."""
    pass


REQUIRED_FIELDS = [
    "schema_version",
    "run_id",
    "scenario",
    "validation",
    "solver",
    "summary",
    "sources",
    "plants",
    "demand_zones",
    "flows",
    "quality",
    "warnings",
]


def adapt_results(
    results: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert external Results JSON into the internal format.

    The adapter:
    - preserves MILP result values;
    - converts approved external field names to internal names;
    - preserves scenario, source, plant, flow and quality structures;
    - safely handles optional fields;
    - raises AdapterError for missing required fields.
    """

    if not isinstance(results, dict):
        raise AdapterError(
            "Results must be a dictionary."
        )

    missing_fields = [
        field
        for field in REQUIRED_FIELDS
        if field not in results
    ]

    if missing_fields:
        raise AdapterError(
            "Missing required field(s): "
            + ", ".join(missing_fields)
        )

    adapted = {
        "schemaVersion": results["schema_version"],
        "runId": results["run_id"],
        "scenario": results["scenario"],
        "validation": results["validation"],
        "solver": results["solver"],
        "summary": results["summary"],
        "sources": results["sources"],
        "plants": results["plants"],
        "demandZones": results["demand_zones"],
        "flows": results["flows"],
        "quality": results["quality"],
        "warnings": results["warnings"],
    }

    # Optional fields confirmed by the Task 21 field map.
    # `binding_constraints_summary` is also present in the
    # v1 fixture. No values are invented for missing fields.
    optional_fields = {
        "solved_at": "solvedAt",
        "binding_constraints_summary": (
            "bindingConstraintsSummary"
        ),
        "alternative_feasible_solutions": (
            "alternativeFeasibleSolutions"
        ),
        "sensitivity_to_key_assumptions": (
            "sensitivityToKeyAssumptions"
        ),
        "explanation": "explanation",
    }

    for external_name, internal_name in optional_fields.items():
        if external_name in results:
            adapted[internal_name] = results[
                external_name
            ]

    return adapted