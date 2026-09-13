"""Task 28 sensitivity and value-of-data ranking support.

Task 90 updates this module for the latest confirmed ``milp_model_output``
contract. Source records are now read from the top-level ``sources`` JSONB
column instead of the removed ``data_flags.sources`` structure.

The internal provenance/estimation shape of ``sources`` has not yet been
confirmed from a real database row, and the current SQL contract does not
expose a dedicated ``sensitivity_to_key_assumptions`` column. The module
therefore handles missing evidence as ``INSUFFICIENT_DATA`` and does not
invent field mappings, impact scores, or rankings.
"""

from __future__ import annotations

from typing import Any


STATUS_RANKED = "RANKED"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STATUS_INVALID_INPUT = "INVALID_INPUT"

# Existing Task 28 aliases are retained only to interpret sensitivity wording.
# They are not converted into scores or used to invent a ranking.
FIELD_ALIASES = {
    "storage_capacity": "storage_capacity",
    "reference_flow": "reference_flow",
    "max_available_ml_per_day": "max_available",
    "max_available": "max_available",
    "cost_per_ml": "cost",
    "cost": "cost",
    "alkalinity": "alkalinity",
}


def _invalid(reason: str) -> dict[str, Any]:
    return {
        "status": STATUS_INVALID_INPUT,
        "ranking": [],
        "verified_entries": [],
        "reason": reason,
    }


def _insufficient(
    reason: str,
    verified_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "status": STATUS_INSUFFICIENT_DATA,
        "ranking": [],
        "verified_entries": verified_entries or [],
        "reason": reason,
    }


def _validate_sources(results: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    """Validate the confirmed top-level ``milp_model_output.sources`` field."""
    if "sources" not in results:
        return None, _invalid(
            "sources must be present in the current MILP output."
        )

    sources = results["sources"]
    if not isinstance(sources, list):
        return None, _invalid("sources must be a list.")

    if not sources:
        return None, _insufficient(
            "No source records are available in milp_model_output.sources."
        )

    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            return None, _invalid(f"sources[{index}] must be an object.")

        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            return None, _invalid(
                f"sources[{index}].source_id must be a non-empty string."
            )

    return sources, None


def _find_source_id(
    assumption: str,
    sources: list[dict[str, Any]],
) -> str | None:
    """Return one source_id mentioned in the assumption, or None."""
    assumption_lower = assumption.lower()
    matches = [
        source["source_id"]
        for source in sources
        if isinstance(source.get("source_id"), str)
        and source["source_id"].lower() in assumption_lower
    ]
    return matches[0] if len(matches) == 1 else None


def _find_provenance_field(assumption: str) -> str | None:
    """Map assumption wording to one existing Task 28 provenance field."""
    assumption_lower = assumption.lower()
    for alias in sorted(FIELD_ALIASES, key=len, reverse=True):
        if alias in assumption_lower:
            return FIELD_ALIASES[alias]
    return None


def _estimated_state(
    source: dict[str, Any],
    provenance_field: str,
) -> bool | None:
    """Return True/False when provenance is usable, otherwise None.

    The latest SQL contract confirms only that ``sources`` is JSONB. The
    ``has_estimated_values`` and ``provenance`` names are therefore treated as
    usable only when they are actually present in a supplied source record.
    Missing or differently shaped provenance is not treated as invalid input.
    """
    has_estimated_values = source.get("has_estimated_values")
    if not isinstance(has_estimated_values, bool):
        return None

    if has_estimated_values is False:
        return False

    provenance = source.get("provenance")
    if not isinstance(provenance, dict):
        return None

    value = provenance.get(provenance_field)
    if not isinstance(value, str):
        return None

    return value.lower() == "estimate"


def rank_sensitivities(results: dict[str, Any]) -> dict[str, Any]:
    """Evaluate sensitivity entries without inventing unsupported rankings.

    Confirmed Task 90 contract behaviour:
    - source records are read from top-level ``sources``;
    - ``data_flags.sources`` is no longer required or read;
    - missing/unconfirmed provenance is handled as insufficient evidence;
    - free-text impacts are never converted into an invented priority score.

    The current source of ``sensitivity_to_key_assumptions`` is still pending
    confirmation. If it is not supplied, the function returns
    ``INSUFFICIENT_DATA`` rather than assuming another location.
    """
    if not isinstance(results, dict):
        return _invalid("Results must be a JSON object.")

    sources, source_error = _validate_sources(results)
    if source_error is not None:
        return source_error
    assert sources is not None

    if "sensitivity_to_key_assumptions" not in results:
        return _insufficient(
            "No confirmed sensitivity_to_key_assumptions data is available "
            "in the current MILP output contract."
        )

    sensitivities = results["sensitivity_to_key_assumptions"]
    if not isinstance(sensitivities, list):
        return _invalid("sensitivity_to_key_assumptions must be a list.")

    if not sensitivities:
        return _insufficient("No sensitivity entries are available.")

    verified_entries: list[dict[str, Any]] = []
    provenance_unconfirmed = False

    for index, entry in enumerate(sensitivities):
        if not isinstance(entry, dict):
            return _invalid(
                f"sensitivity_to_key_assumptions[{index}] must be an object."
            )

        assumption = entry.get("assumption")
        impact = entry.get("impact")

        if not isinstance(assumption, str) or not assumption.strip():
            return _invalid(
                f"sensitivity_to_key_assumptions[{index}].assumption must "
                "be a non-empty string."
            )

        if not isinstance(impact, str) or not impact.strip():
            return _invalid(
                f"sensitivity_to_key_assumptions[{index}].impact must "
                "be a non-empty string."
            )

        source_id = _find_source_id(assumption, sources)
        provenance_field = _find_provenance_field(assumption)

        if source_id is None or provenance_field is None:
            continue

        source = next(
            source for source in sources if source["source_id"] == source_id
        )
        estimated = _estimated_state(source, provenance_field)

        if estimated is None:
            provenance_unconfirmed = True
            continue

        if estimated:
            verified_entries.append(
                {
                    "assumption": assumption,
                    "impact": impact,
                    "source_id": source_id,
                    "provenance_field": provenance_field,
                }
            )

    if not verified_entries:
        if provenance_unconfirmed:
            return _insufficient(
                "Sensitivity entries are available, but the provenance/"
                "estimation shape inside milp_model_output.sources has not "
                "been confirmed or is not available in these source records."
            )

        return _insufficient(
            "Sensitivity entries could not be verified against confirmed "
            "estimated source provenance."
        )

    return _insufficient(
        "Verified sensitivity entries are available, but the current "
        "sensitivity impacts are free text and no agreed structured "
        "comparison value exists, so a fair ranking is unsupported.",
        verified_entries,
    )
