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
    Determine confidence from source provenance.

    Args:
        provenance_sources:
            Source provenance records from
            results["data_flags"]["sources"].

        selected_sources:
            Selected/contributing sources from
            results["sources"]["selected"].

    Returns:
        {
            "confidence": "PROVISIONAL | MEASURED | UNKNOWN",
            "estimated_sources": [...]
        }
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

    # Build the set of contributing source IDs.
    selected_ids = set()

    for index, source in enumerate(selected_sources):

        if not isinstance(source, dict):
            raise ConfidenceError(
                f"Selected source at index {index} "
                "must be an object."
            )

        source_id = source.get("source_id")

        if (
            not isinstance(source_id, str)
            or not source_id.strip()
        ):
            raise ConfidenceError(
                f"Selected source at index {index} "
                "has an invalid source_id."
            )

        selected_ids.add(source_id)

    if not selected_ids:
        return {
            "confidence": "UNKNOWN",
            "estimated_sources": [],
        }

    estimated_sources = []
    unknown = False
    matched_selected_sources = set()

    for index, source in enumerate(provenance_sources):

        if not isinstance(source, dict):
            raise ConfidenceError(
                f"Source at index {index} "
                "must be an object."
            )

        source_id = source.get("source_id")

        if (
            not isinstance(source_id, str)
            or not source_id.strip()
        ):
            unknown = True
            continue

        # Ignore provenance for sources that did not
        # contribute to the optimisation result.
        if source_id not in selected_ids:
            continue

        matched_selected_sources.add(source_id)

        estimated_flag = source.get(
            "has_estimated_values"
        )

        if not isinstance(
            estimated_flag,
            bool,
        ):
            unknown = True
            continue

        provenance = source.get(
            "provenance"
        )

        if not isinstance(
            provenance,
            dict,
        ):
            unknown = True
            continue

        missing_fields = (
            REQUIRED_PROVENANCE_FIELDS
            - set(provenance.keys())
        )

        if missing_fields:
            unknown = True
            continue

        if estimated_flag:
            estimated_sources.append(source_id)

    # Every selected source should have provenance.
    if matched_selected_sources != selected_ids:
        unknown = True

    if estimated_sources:
        return {
            "confidence": "PROVISIONAL",
            "estimated_sources": sorted(
                estimated_sources
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