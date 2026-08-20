"""
results_validator.py

Validates the Results JSON produced by the MILP optimiser.

The confirmed Results JSON contract is treated as the
source of truth.
"""

from typing import Any


class ValidationError(Exception):
    """Raised when Results JSON fails validation."""
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


VALID_STATUS = {
    "OPTIMAL",
    "SUCCESS",
    "FEASIBLE",
    "INFEASIBLE",
    "ERROR",
    "TIME_LIMIT",
}


REQUIRED_PROVENANCE_FIELDS = {
    "storage_capacity",
    "reference_flow",
    "max_available",
    "cost",
    "alkalinity",
}


def validate_results(results: dict[str, Any]) -> bool:
    """
    Validate the confirmed Results JSON contract.

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

    # scenario_id
    if not isinstance(results["scenario_id"], str):
        raise ValidationError(
            "'scenario_id' must be a string."
        )

    if not results["scenario_id"].strip():
        raise ValidationError(
            "'scenario_id' must not be empty."
        )

    # status
    if not isinstance(results["status"], str):
        raise ValidationError(
            "'status' must be a string."
        )

    if results["status"] not in VALID_STATUS:
        raise ValidationError(
            f"Invalid status '{results['status']}'. "
            f"Expected one of: "
            f"{', '.join(sorted(VALID_STATUS))}"
        )

    # Required object fields
    object_fields = [
        "objective",
        "sources",
        "transfer_paths",
        "plants",
        "water_quality",
        "diagnostics",
        "data_flags",
    ]

    for field in object_fields:
        if not isinstance(results[field], dict):
            raise ValidationError(
                f"'{field}' must be an object."
            )

    # Required list fields
    list_fields = [
        "demand_zones",
        "constraints",
    ]

    for field in list_fields:
        if not isinstance(results[field], list):
            raise ValidationError(
                f"'{field}' must be a list."
            )

    # Validate sources structure
    sources = results["sources"]

    if "selected" not in sources:
        raise ValidationError(
            "'sources' must contain 'selected'."
        )

    if "unused" not in sources:
        raise ValidationError(
            "'sources' must contain 'unused'."
        )

    if not isinstance(sources["selected"], list):
        raise ValidationError(
            "'sources.selected' must be a list."
        )

    if not isinstance(sources["unused"], list):
        raise ValidationError(
            "'sources.unused' must be a list."
        )

    # Validate selected and unused source objects
    for group in ("selected", "unused"):
        for index, source in enumerate(sources[group]):

            if not isinstance(source, dict):
                raise ValidationError(
                    f"'sources.{group}[{index}]' "
                    "must be an object."
                )

            if "source_id" not in source:
                raise ValidationError(
                    f"'sources.{group}[{index}]' "
                    "is missing 'source_id'."
                )

            if not isinstance(source["source_id"], str):
                raise ValidationError(
                    f"'sources.{group}[{index}].source_id' "
                    "must be a string."
                )

            if not source["source_id"].strip():
                raise ValidationError(
                    f"'sources.{group}[{index}].source_id' "
                    "must not be empty."
                )

    # Validate constraints
    for index, constraint in enumerate(results["constraints"]):
        if not isinstance(constraint, dict):
            raise ValidationError(
                f"'constraints[{index}]' "
                "must be an object."
            )

    # Validate data_flags
    data_flags = results["data_flags"]

    if "sources" not in data_flags:
        raise ValidationError(
            "'data_flags' must contain 'sources'."
        )

    if not isinstance(data_flags["sources"], list):
        raise ValidationError(
            "'data_flags.sources' must be a list."
        )

    # Validate provenance records
    for index, source in enumerate(data_flags["sources"]):

        if not isinstance(source, dict):
            raise ValidationError(
                f"'data_flags.sources[{index}]' "
                "must be an object."
            )

        # source_id
        if "source_id" not in source:
            raise ValidationError(
                f"'data_flags.sources[{index}]' "
                "is missing 'source_id'."
            )

        if not isinstance(source["source_id"], str):
            raise ValidationError(
                f"'data_flags.sources[{index}].source_id' "
                "must be a string."
            )

        if not source["source_id"].strip():
            raise ValidationError(
                f"'data_flags.sources[{index}].source_id' "
                "must not be empty."
            )

        # has_estimated_values
        if "has_estimated_values" not in source:
            raise ValidationError(
                f"'data_flags.sources[{index}]' "
                "is missing 'has_estimated_values'."
            )

        if not isinstance(
            source["has_estimated_values"],
            bool,
        ):
            raise ValidationError(
                f"'data_flags.sources[{index}].has_estimated_values' "
                "must be a boolean."
            )

        # provenance
        if "provenance" not in source:
            raise ValidationError(
                f"'data_flags.sources[{index}]' "
                "is missing 'provenance'."
            )

        provenance = source["provenance"]

        if not isinstance(provenance, dict):
            raise ValidationError(
                f"'data_flags.sources[{index}].provenance' "
                "must be an object."
            )

        missing = REQUIRED_PROVENANCE_FIELDS - set(
            provenance.keys()
        )

        if missing:
            raise ValidationError(
                f"'data_flags.sources[{index}].provenance' "
                "is missing required field(s): "
                + ", ".join(sorted(missing))
            )

    return True