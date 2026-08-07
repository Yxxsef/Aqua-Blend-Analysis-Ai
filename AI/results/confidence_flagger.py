"""
confidence_flagger.py

Determines confidence level of Results JSON based on
source data provenance.

Confidence levels:
- PROVISIONAL: Estimated values were used
- MEASURED: All contributing sources are confirmed measured
- UNKNOWN: Provenance information is missing
"""


class ConfidenceError(Exception):
    """Raised when confidence evaluation fails."""
    pass


def determine_confidence(sources):
    """
    Determine confidence flag from contributing sources.

    Args:
        sources (list):
            List of source dictionaries.

    Returns:
        dict:
            {
                "confidence": "PROVISIONAL | MEASURED | UNKNOWN",
                "estimated_sources": []
            }

    """

    if not isinstance(sources, list):
        raise ConfidenceError(
            "Sources must be a list."
        )

    estimated_sources = []
    missing_provenance = []

    for index, source in enumerate(sources):

        if not isinstance(source, dict):
            raise ConfidenceError(
                f"Source at index {index} must be an object."
            )

        source_id = source.get(
            "source_id",
            f"source_{index}"
        )

        # Missing provenance
        if "has_estimated_values" not in source:
            missing_provenance.append(source_id)
            continue

        # Estimated data detected
        if source["has_estimated_values"] is True:
            estimated_sources.append(source_id)


    # Estimated values always make result provisional
    if estimated_sources:
        return {
            "confidence": "PROVISIONAL",
            "estimated_sources": estimated_sources
        }


    # Missing provenance means we cannot confirm measurement
    if missing_provenance:
        return {
            "confidence": "UNKNOWN",
            "estimated_sources": missing_provenance
        }


    # All sources confirmed measured
    return {
        "confidence": "MEASURED",
        "estimated_sources": []
    }