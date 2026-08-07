"""
results_adapter.py

Provides a stable internal adapter for Results JSON.

The external MILP/Results JSON field names must remain unchanged.
Internal application names are handled here.
"""


class AdapterError(Exception):
    """
    Raised when Results JSON cannot be adapted.
    """
    pass


def adapt_results(results):
    """
    Convert external Results JSON into internal format.

    Args:
        results (dict):
            Validated Results JSON.

    Returns:
        dict:
            Internal AquaBlend representation.
    """

    if not isinstance(results, dict):
        raise AdapterError(
            "Results must be a dictionary."
        )

    try:
        adapted = {

            # Keep scenario information
            "scenario": results["scenario"],

            # Solver status
            "status": results["status"],

            # Source allocation details
            "sources": results["sources"],

            # Demand information
            "demand": results["demand"],

            # Cost information
            "cost": results["cost"],

            # Constraint information
            "constraints": results["constraints"],

            # Quality information
            "qualityStage": results["quality_stage"],

            # Diagnostic information
            "diagnostics": results["diagnostics"],
        }

    except KeyError as error:
        raise AdapterError(
            f"Missing required field: {error.args[0]}"
        )

    return adapted