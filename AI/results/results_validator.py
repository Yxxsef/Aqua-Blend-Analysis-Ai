"""
results_validator.py

Validates the Results JSON produced by the MILP optimiser.

The real MILP output contract v1 fixture
(AI/results/tests/fixtures/output_contract_v1.json) is
treated as the source of truth.

Unresolved contract questions (provenance/data flags,
diagnostics, status enums, objective/cost mapping) are
recorded in MILP_Output_Validation_Notes.md and are
intentionally not validated here rather than guessed.
"""

from typing import Any


class ValidationError(Exception):
    """Raised when Results JSON fails validation."""
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


def validate_results(results: dict[str, Any]) -> bool:
    """
    Validate Results JSON against the MILP output contract v1.

    Returns:
        True if validation succeeds.

    Raises:
        ValidationError if validation fails.
    """

    if not isinstance(results, dict):
        raise ValidationError(
            "Results must be a JSON object."
        )

    missing_fields = [
        field
        for field in REQUIRED_FIELDS
        if field not in results
    ]

    if missing_fields:
        raise ValidationError(
            "Missing required fields: "
            + ", ".join(missing_fields)
        )

    # schema_version
    if not isinstance(results["schema_version"], str):
        raise ValidationError(
            "'schema_version' must be a string."
        )

    # scenario (scenario_id relocated here in v1)
    scenario = results["scenario"]

    if not isinstance(scenario, dict):
        raise ValidationError(
            "'scenario' must be an object."
        )

    if "scenario_id" not in scenario:
        raise ValidationError(
            "'scenario' must contain 'scenario_id'."
        )

    if not isinstance(scenario["scenario_id"], str):
        raise ValidationError(
            "'scenario.scenario_id' must be a string."
        )

    if not scenario["scenario_id"].strip():
        raise ValidationError(
            "'scenario.scenario_id' must not be empty."
        )

    # solver (type checks only; the v1 fixture defines
    # no status enum, so no enum is invented here)
    solver = results["solver"]

    if not isinstance(solver, dict):
        raise ValidationError(
            "'solver' must be an object."
        )

    if "status" not in solver:
        raise ValidationError(
            "'solver' must contain 'status'."
        )

    if not isinstance(solver["status"], str):
        raise ValidationError(
            "'solver.status' must be a string."
        )

    # Required object fields
    object_fields = [
        "validation",
        "summary",
        "flows",
        "quality",
    ]

    for field in object_fields:
        if not isinstance(results[field], dict):
            raise ValidationError(
                f"'{field}' must be an object."
            )

    # Required list fields
    list_fields = [
        "demand_zones",
        "warnings",
    ]

    for field in list_fields:
        if not isinstance(results[field], list):
            raise ValidationError(
                f"'{field}' must be a list."
            )

    # Validate sources structure (flat list in v1)
    sources = results["sources"]

    if not isinstance(sources, list):
        raise ValidationError(
            "'sources' must be a list."
        )

    for index, source in enumerate(sources):

        if not isinstance(source, dict):
            raise ValidationError(
                f"'sources[{index}]' must be an object."
            )

        if "source_id" not in source:
            raise ValidationError(
                f"'sources[{index}]' is missing 'source_id'."
            )

        if not isinstance(source["source_id"], str):
            raise ValidationError(
                f"'sources[{index}].source_id' "
                "must be a string."
            )

        if not source["source_id"].strip():
            raise ValidationError(
                f"'sources[{index}].source_id' "
                "must not be empty."
            )

    # Validate plants structure (flat list in v1)
    plants = results["plants"]

    if not isinstance(plants, list):
        raise ValidationError(
            "'plants' must be a list."
        )

    for index, plant in enumerate(plants):

        if not isinstance(plant, dict):
            raise ValidationError(
                f"'plants[{index}]' must be an object."
            )

    return True