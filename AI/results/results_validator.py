"""
results_validator.py

Validates the Results JSON produced by the MILP optimiser.

Task 21:
- Validate required Results JSON fields
- Detect missing fields
- Validate basic data structures
- Provide clear validation errors
"""

from typing import Dict, List


class ValidationError(Exception):
    """
    Raised when the Results JSON fails validation.
    """
    pass


# Required top-level fields from the Results JSON contract
REQUIRED_FIELDS = [
    "scenario",
    "status",
    "sources",
    "demand",
    "cost",
    "constraints",
    "quality_stage",
    "diagnostics",
]


# Accepted solver/result statuses
VALID_STATUS = {
    "SUCCESS",
    "FEASIBLE",
    "INFEASIBLE",
    "ERROR",
    "TIME_LIMIT",
}


def validate_results(results: Dict) -> bool:
    """
    Validate the Results JSON structure.

    Args:
        results:
            Parsed Results JSON as a Python dictionary.

    Returns:
        True if validation succeeds.

    Raises:
        ValidationError:
            If the Results JSON is missing required fields
            or contains invalid structures.
    """

    # Check root object
    if not isinstance(results, dict):
        raise ValidationError(
            "Results must be a JSON object."
        )

    # Check required fields
    missing_fields: List[str] = [
        field
        for field in REQUIRED_FIELDS
        if field not in results
    ]

    if missing_fields:
        raise ValidationError(
            "Missing required fields: "
            + ", ".join(missing_fields)
        )

    # Validate status
    if not isinstance(results["status"], str):
        raise ValidationError(
            "'status' must be a string."
        )

    if results["status"] not in VALID_STATUS:
        raise ValidationError(
            f"Invalid status '{results['status']}'. "
            f"Expected one of: {', '.join(VALID_STATUS)}"
        )

    # Validate scenario
    if not isinstance(results["scenario"], dict):
        raise ValidationError(
            "'scenario' must be an object."
        )

    # Validate sources
    if not isinstance(results["sources"], list):
        raise ValidationError(
            "'sources' must be a list."
        )

    # Validate each source object
    for index, source in enumerate(results["sources"]):

        if not isinstance(source, dict):
            raise ValidationError(
                f"Source at index {index} must be an object."
            )

    # Validate demand
    if not isinstance(results["demand"], dict):
        raise ValidationError(
            "'demand' must be an object."
        )

    # Validate cost
    if not isinstance(results["cost"], dict):
        raise ValidationError(
            "'cost' must be an object."
        )

    # Validate constraints
    if not isinstance(results["constraints"], dict):
        raise ValidationError(
            "'constraints' must be an object."
        )

    # Validate quality stage
    if not isinstance(results["quality_stage"], (dict, str)):
        raise ValidationError(
            "'quality_stage' must be an object or string."
        )

    # Validate diagnostics
    if not isinstance(results["diagnostics"], dict):
        raise ValidationError(
            "'diagnostics' must be an object."
        )

    return True