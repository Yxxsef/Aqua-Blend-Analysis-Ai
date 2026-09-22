"""
confidence_flagger.py

Determines confidence level of Results JSON based on source data provenance.

Confidence levels:
- PROVISIONAL: Estimated values were used by contributing sources.
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
    provenance_sources: list[dict[str, Any]],
    selected_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Determine confidence from ALL source provenance records.

    The confirmed Results contract defines results["data_flags"]["sources"]
    as the sole provenance source. Selected/unused optimisation status must
    not affect whether an input source is estimated, measured, or unknown.

    selected_sources is retained only for API compatibility with existing
    callers; it is intentionally not used for provenance classification.
    """

    if not isinstance(provenance_sources, list):
        raise ConfidenceError(
            "Provenance sources must be a list."
        )

    if not isinstance(selected_sources, list):
        raise ConfidenceError(
            "Selected sources must be a list."
        )

    if not provenance_sources:
        return {
            "confidence": "UNKNOWN",
            "estimated_sources": [],
        }

    estimated_sources: list[str] = []
    unknown = False

    for index, source in enumerate(provenance_sources):

        if not isinstance(source, dict):
            unknown = True
            continue

        source_id = source.get("source_id")

        if (
            not isinstance(source_id, str)
            or not source_id.strip()
        ):
            unknown = True
            continue

        estimated_flag = source.get(
            "has_estimated_values"
        )

        if not isinstance(estimated_flag, bool):
            unknown = True
            continue

        provenance = source.get("provenance")

        if not isinstance(provenance, dict):
            unknown = True
            continue

        missing_fields = (
            REQUIRED_PROVENANCE_FIELDS
            - set(provenance.keys())
        )

        if missing_fields:
            unknown = True
            continue

        # A required provenance key with no actual provenance value
        # cannot confirm that source as fully measured.
        if any(
            provenance.get(field) is None
            for field in REQUIRED_PROVENANCE_FIELDS
        ):
            unknown = True

        if estimated_flag:
            estimated_sources.append(source_id)

    # Estimated data takes precedence even when another source has
    # incomplete/unknown provenance.
    if estimated_sources:
        return {
            "confidence": "PROVISIONAL",
            "estimated_sources": sorted(
                set(estimated_sources)
            ),
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

