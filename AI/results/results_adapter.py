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

    # Ensure the input is a dictionary.
    if not isinstance(results, dict):
        raise AdapterError(
            "Results must be a dictionary."
        )

    # Check all required fields before accessing them.
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

    # Convert the confirmed external field names
    # into the stable internal representation.
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
    }

    # data_flags is required externally.
    #
    # Preserve the complete data_flags structure exactly as
    # provided by the external Results JSON contract. An empty
    # sources list does not imply that other metadata (for
    # example notes or future fields) should be discarded.
    data_flags = results["data_flags"]

    if not isinstance(data_flags, dict):
        raise AdapterError(
            "data_flags must be a dictionary."
        )

    adapted["dataFlags"] = data_flags

    # Optional fields are copied only when supplied.
    # Missing optional fields are not invented.
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