"""
confidence_flagger.py

Determines confidence level of Results JSON based on source data provenance.

Confidence levels:
- PROVISIONAL: Estimated values were used.
- MEASURED: All contributing sources are confirmed measured.
- UNKNOWN: Provenance is missing, incomplete, or invalid.
"""

from typing import Any


class ConfidenceError(Exception):
    """Raised when confidence evaluation fails."""
    pass


REQUIRED_PROVENANCE_FIELDS = {
    "storage_capacity",
    "reference_flow",
    "max_available",
    "cost",
    "alkalinity",
}


def determine_confidence(
    sources: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Determine confidence from source provenance.

    Args:
        sources: Source provenance records from data_flags.sources.

    Returns:
        {
            "confidence": "PROVISIONAL | MEASURED | UNKNOWN",
            "estimated_sources": [...]
        }
    """

    if not isinstance(sources, list):
        raise ConfidenceError("Sources must be a list.")

    if not sources:
        return {
            "confidence": "UNKNOWN",
            "estimated_sources": [],
        }

    estimated_sources = []
    unknown = False

    for index, source in enumerate(sources):

        if not isinstance(source, dict):
            raise ConfidenceError(
                f"Source at index {index} must be an object."
            )

        source_id = source.get("source_id")

        # Do not generate source_0, source_1, etc.
        if not isinstance(source_id, str) or not source_id.strip():
            unknown = True
            continue

        # has_estimated_values must be a real boolean.
        estimated_flag = source.get("has_estimated_values")

        if not isinstance(estimated_flag, bool):
            unknown = True
            continue

        # Provenance must exist.
        provenance = source.get("provenance")

        if not isinstance(provenance, dict):
            unknown = True
            continue

        # All five provenance fields are required.
        missing_fields = (
            REQUIRED_PROVENANCE_FIELDS
            - set(provenance.keys())
        )

        if missing_fields:
            unknown = True
            continue

        # Estimated values make the result provisional.
        if estimated_flag is True:
            estimated_sources.append(source_id)

    if estimated_sources:
        return {
            "confidence": "PROVISIONAL",
            "estimated_sources": estimated_sources,
        }

    if unknown:
        return {
            "confidence": "UNKNOWN",
            "estimated_sources": [],
        }

    return {
        "confidence": "MEASURED",
        "estimated_sources": [],
    }