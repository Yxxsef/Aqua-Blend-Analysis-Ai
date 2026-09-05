"""Task 57 - confidence flagging using the current MILP and ScenarioData.

The current MILP output no longer includes source provenance information.
Confidence is therefore determined by matching:

- source decisions from the MILP output; and
- provenance information stored in ScenarioData.

The two data sources are joined using source_id.

Only sources that actually contributed water to the solution affect the
confidence result.

Confidence results:
- PROVISIONAL: at least one contributing source used estimated or overridden data.
- MEASURED: all contributing sources are confirmed as non-estimated and have
  complete provenance information.
- UNKNOWN: contribution or provenance cannot be confirmed.

UNKNOWN is treated as a valid confidence state and does not stop the rest of
the analysis pipeline.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class ConfidenceError(Exception):
    """Raised when the function is given an invalid top-level input."""


# Used to distinguish between a missing field and a field that contains None.
_MISSING = object()


# Main provenance fields currently created by data_loader.py.
# Quality provenance is handled separately because the configured quality
# parameters may change in future versions.
REQUIRED_BASE_PROVENANCE_FIELDS = {
    "storage_capacity",
    "reference_flow",
    "minimum_withdrawal",
    "maximum_withdrawal",
    "cost",
}


# Provenance fields used by the earlier Sprint 2 Task 21 implementation.
# Support is retained so previous confidence inputs and tests remain compatible.
LEGACY_REQUIRED_PROVENANCE_FIELDS = {
    "storage_capacity",
    "reference_flow",
    "max_available",
    "cost",
    "alkalinity",
}


def _field(record: Any, name: str, default: Any = _MISSING) -> Any:
    """Read a field from either a dictionary or a ScenarioData-style object."""

    # Test fixtures may use dictionaries, while real ScenarioData uses objects.
    if isinstance(record, Mapping):
        return record.get(name, default)

    return getattr(record, name, default)


def _valid_source_id(value: Any) -> str | None:
    """Return a cleaned source ID when the value is valid."""

    if isinstance(value, str) and value.strip():
        return value.strip()

    return None


def _is_number(value: Any) -> bool:
    """Check for a numeric value without treating booleans as numbers."""

    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _contribution_state(source: Any) -> bool | None:
    """Determine whether a source contributed to the MILP result.

    Returns:
        True when the source contributed.
        False when the source did not contribute.
        None when the available solver information is unclear.
    """

    # Withdrawal is the strongest indication that a source actually supplied water.
    withdrawal = _field(source, "withdrawal_ml_per_day")

    if _is_number(withdrawal):
        return float(withdrawal) > 0.0

    # If withdrawal is unavailable, use the solver selection status.
    selection_status = _field(source, "selection_status")

    if isinstance(selection_status, str):
        status = selection_status.strip().upper()

        if status == "SELECTED":
            return True

        if status in {"UNUSED", "EXCLUDED"}:
            return False

        # PENDING indicates that the source decision has not been confirmed yet.
        if status == "PENDING":
            return None

    # Activation can also indicate whether the source was used.
    activated = _field(source, "activated")

    if isinstance(activated, bool):
        return activated

    # Sprint 2 inputs already contained only selected sources.
    # If the newer MILP decision fields are missing, treat the source as contributing to maintain compatibility with the older format.
    decision_fields = {
        "withdrawal_ml_per_day",
        "selection_status",
        "activated",
        "model_included",
    }

    if isinstance(source, Mapping) and not decision_fields.intersection(source):
        return True

    return None


def _complete_provenance(provenance: Any) -> bool:
    """Check whether the provenance information is complete enough for MEASURED."""

    # Missing or empty provenance cannot confirm measured confidence.
    if not isinstance(provenance, Mapping) or not provenance:
        return False

    # Check the current Sprint 3 ScenarioData provenance structure.
    if REQUIRED_BASE_PROVENANCE_FIELDS.issubset(provenance.keys()):

        # Quality provenance is stored using quality.<parameter_id> keys.
        # These are detected dynamically so the function does not depend on a fixed set of quality parameters.
        quality_keys = [
            key
            for key in provenance
            if isinstance(key, str) and key.startswith("quality.")
        ]

        # At least one quality provenance entry is required.
        if not quality_keys:
            return False

        keys_to_check = set(REQUIRED_BASE_PROVENANCE_FIELDS).union(
            quality_keys
        )

    # Also support the earlier Sprint 2 provenance structure.
    elif LEGACY_REQUIRED_PROVENANCE_FIELDS.issubset(provenance.keys()):
        keys_to_check = set(LEGACY_REQUIRED_PROVENANCE_FIELDS)

    else:
        return False

    # Every required provenance field must contain a non-empty string value.
    for key in keys_to_check:
        value = provenance.get(key)

        if not isinstance(value, str) or not value.strip():
            return False

    return True


def determine_confidence(
    scenario_sources: Sequence[Any],
    milp_sources: Sequence[Any],
) -> dict[str, Any]:
    """Determine confidence for the sources that contributed to the MILP result.

    Args:
        scenario_sources:
            ScenarioData source records containing provenance information.

        milp_sources:
            MILP output source records containing solver decision information.

    Returns:
        A dictionary containing the confidence state and any estimated sources.
    """

    # Validate the ScenarioData source collection.
    if isinstance(scenario_sources, (str, bytes)) or not isinstance(
        scenario_sources, Sequence
    ):
        raise ConfidenceError(
            "ScenarioData sources must be a sequence."
        )

    # Validate the MILP source collection.
    if isinstance(milp_sources, (str, bytes)) or not isinstance(
        milp_sources, Sequence
    ):
        raise ConfidenceError(
            "MILP sources must be a sequence."
        )

    # Build a lookup so MILP source IDs can be matched to ScenarioData records.
    scenario_by_id: dict[str, Any] = {}
    duplicate_scenario_id = False

    for source in scenario_sources:
        source_id = _valid_source_id(
            _field(source, "source_id")
        )

        # Missing IDs create uncertainty but should not stop the pipeline.
        if source_id is None:
            continue

        if source_id in scenario_by_id:
            duplicate_scenario_id = True

        scenario_by_id[source_id] = source

    # Identify which MILP sources actually contributed to the solution.
    contributing_ids: set[str] = set()
    contribution_unknown = False

    for source in milp_sources:
        source_id = _valid_source_id(
            _field(source, "source_id")
        )

        if source_id is None:
            contribution_unknown = True
            continue

        state = _contribution_state(source)

        if state is True:
            contributing_ids.add(source_id)

        elif state is None:
            contribution_unknown = True

    # Without any confirmed contributing sources, confidence cannot be safely reported as MEASURED.
    if not contributing_ids:
        return {
            "confidence": "UNKNOWN",
            "estimated_sources": [],
        }

    estimated_sources: list[str] = []

    # Any duplicate source IDs or unclear contribution decisions introduce uncertainty into the final confidence result.
    provenance_unknown = (
        duplicate_scenario_id or contribution_unknown
    )

    # Check provenance only for the sources that contributed to the result.
    for source_id in sorted(contributing_ids):

        source = scenario_by_id.get(source_id)

        # A contributing MILP source must have a matching ScenarioData record.
        if source is None:
            provenance_unknown = True
            continue

        estimated_flag = _field(
            source,
            "has_estimated_values",
        )

        # The estimated flag must be a real boolean.
        if not isinstance(estimated_flag, bool):
            provenance_unknown = True
            continue

        provenance = _field(
            source,
            "provenance",
        )

        provenance_complete = _complete_provenance(
            provenance
        )

        if estimated_flag:
            # Any confirmed estimated contributing source makes the overall confidence PROVISIONAL.
            estimated_sources.append(source_id)
            continue

        # A non-estimated source still requires complete provenance before it can contribute to a MEASURED result.
        if not provenance_complete:
            provenance_unknown = True

    # Confirmed estimated data takes priority over other uncertainty.
    if estimated_sources:
        return {
            "confidence": "PROVISIONAL",
            "estimated_sources": sorted(
                estimated_sources
            ),
        }

    # Missing or unclear provenance results in UNKNOWN.
    if provenance_unknown:
        return {
            "confidence": "UNKNOWN",
            "estimated_sources": [],
        }

    # All contributing sources are non-estimated and have complete provenance.
    return {
        "confidence": "MEASURED",
        "estimated_sources": [],
    }