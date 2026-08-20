"""
results_adapter.py

Provides a stable internal adapter for the confirmed
Results JSON contract.

External MILP field names remain unchanged.
Internal naming differences are handled here.
"""

from typing import Any


class AdapterError(Exception):
    """Raised when Results JSON cannot be adapted."""
    pass


REQUIRED_FIELDS = [
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
]


def adapt_results(
    results: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert external Results JSON into the internal format.

    The adapter:
    - preserves MILP result values;
    - converts approved external field names to internal names;
    - preserves source, constraint, plant, transfer and quality structures;
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

    data_flags = results["data_flags"]

    if not isinstance(data_flags, dict):
        raise AdapterError(
            "'data_flags' must be a dictionary."
        )

    if "sources" not in data_flags:
        raise AdapterError(
            "'data_flags' must contain 'sources'."
        )

    if not isinstance(data_flags["sources"], list):
        raise AdapterError(
            "'data_flags.sources' must be a list."
        )

    adapted = {
        "scenarioId": results["scenario_id"],
        "status": results["status"],
        "objective": results["objective"],
        "demandZones": results["demand_zones"],
        "sources": results["sources"],
        "transferPaths": results["transfer_paths"],
        "plants": results["plants"],
        "waterQuality": results["water_quality"],
        "constraints": results["constraints"],
        "diagnostics": results["diagnostics"],

        # Preserve the complete provenance metadata exactly as
        # supplied by the confirmed Results JSON contract.
        "dataFlags": data_flags,
    }

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