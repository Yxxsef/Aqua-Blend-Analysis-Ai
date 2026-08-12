"""Task 28 sensitivity and value-of-data ranking support.

The current Results JSON contract exposes sensitivity entries as free-text
``assumption`` and ``impact`` values.  The team has not agreed on a fixed
priority rule or numerical impact score.  This module therefore verifies that
sensitivity entries refer to estimated source data, but refuses to invent a
ranking when the available data does not support a fair comparison.
"""

from __future__ import annotations

from typing import Any


STATUS_RANKED = "RANKED"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STATUS_INVALID_INPUT = "INVALID_INPUT"

# Confirmed Task 21 provenance fields and common wording used by the current
# MILP sensitivity examples.  Aliases are used only to verify an uncertainty;
# they are never converted into a score.
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


def _find_source_id(
    assumption: str,
    sources: list[dict[str, Any]],
) -> str | None:
    """Return one real source_id mentioned in the assumption, or None."""
    assumption_lower = assumption.lower()
    matches = [
        source["source_id"]
        for source in sources
        if isinstance(source.get("source_id"), str)
        and source["source_id"].lower() in assumption_lower
    ]
    return matches[0] if len(matches) == 1 else None


def _find_provenance_field(assumption: str) -> str | None:
    """Map assumption wording to one confirmed Task 21 provenance field."""
    assumption_lower = assumption.lower()
    for alias in sorted(FIELD_ALIASES, key=len, reverse=True):
        if alias in assumption_lower:
            return FIELD_ALIASES[alias]
    return None


def _is_verified_uncertain(
    source: dict[str, Any],
    provenance_field: str,
) -> bool:
    """Return True only when provenance confirms that field is estimated."""
    if source.get("has_estimated_values") is not True:
        return False

    provenance = source.get("provenance")
    if not isinstance(provenance, dict):
        return False

    value = provenance.get(provenance_field)
    return isinstance(value, str) and value.lower() == "estimate"


def rank_sensitivities(results: dict[str, Any]) -> dict[str, Any]:
    """Evaluate sensitivity entries and rank only when comparison is supported.

    With the current contract, sensitivity impacts are free text.  Free text is
    not converted into a numerical or categorical priority because that would
    invent a ranking rule.  Valid sensitivity entries are instead verified
    against ``data_flags.sources`` and reported in ``verified_entries``.

    Args:
        results: One validated external MILP Results JSON object.

    Returns:
        A dictionary containing ``status``, ``ranking``, ``verified_entries``
        and ``reason``.
    """
    if not isinstance(results, dict):
        return _invalid("Results must be a JSON object.")

    data_flags = results.get("data_flags")
    if not isinstance(data_flags, dict):
        return _invalid("data_flags must be an object.")

    sources = data_flags.get("sources")
    if not isinstance(sources, list):
        return _invalid("data_flags.sources must be a list.")

    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            return _invalid(
                f"data_flags.sources[{index}] must be an object."
            )
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            return _invalid(
                f"data_flags.sources[{index}].source_id must be a "
                "non-empty string."
            )

    if "sensitivity_to_key_assumptions" not in results:
        return _insufficient(
            "No sensitivity_to_key_assumptions field is available."
        )

    sensitivities = results["sensitivity_to_key_assumptions"]
    if not isinstance(sensitivities, list):
        return _invalid("sensitivity_to_key_assumptions must be a list.")

    if not sensitivities:
        return _insufficient("No sensitivity entries are available.")

    verified_entries: list[dict[str, Any]] = []

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
                f"sensitivity_to_key_assumptions[{index}].impact must be "
                "a non-empty string."
            )

        source_id = _find_source_id(assumption, sources)
        provenance_field = _find_provenance_field(assumption)

        if source_id is None or provenance_field is None:
            continue

        source = next(
            source for source in sources if source["source_id"] == source_id
        )

        if _is_verified_uncertain(source, provenance_field):
            verified_entries.append(
                {
                    "assumption": assumption,
                    "impact": impact,
                    "source_id": source_id,
                    "provenance_field": provenance_field,
                }
            )

    if not verified_entries:
        return _insufficient(
            "Sensitivity entries could not be verified against estimated "
            "source provenance in data_flags.sources."
        )

    return _insufficient(
        "Verified sensitivity entries are available, but the current Results "
        "JSON provides only free-text impact descriptions. No agreed or "
        "structured comparison value exists, so a fair ranking is unsupported.",
        verified_entries,
    )
