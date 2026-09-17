"""Task 28 sensitivity and value-of-data ranking support.

Task 90 aligns this module with the latest inspected ``milp_model_output``
example. The current raw MILP output exposes source decisions through the
confirmed top-level ``sources`` JSONB field. It does not expose the removed
``data_flags.sources`` structure.

Inspection of ``milp_model_output_example.json`` also confirms that the source
records contain solved decision/result fields, but no per-source provenance or
``has_estimated_values`` fields. The example does not contain a
``sensitivity_to_key_assumptions`` field either.

Because Task 28 needs sensitivity evidence plus provenance/estimation evidence
to support a value-of-data ranking, the current raw MILP output alone is
insufficient. This module therefore validates the confirmed source structure
and returns ``INSUFFICIENT_DATA`` rather than inventing provenance, sensitivity
values, or a ranking.
"""

from __future__ import annotations

from typing import Any


STATUS_RANKED = "RANKED"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STATUS_INVALID_INPUT = "INVALID_INPUT"


# These are the source fields observed in the inspected current MILP output
# example. Only source_id is required by this module; the remaining names are
# documented here so Task 90 does not silently rely on old source structures.
CONFIRMED_SOURCE_FIELDS = {
    "source_id",
    "activated",
    "blend_ratio",
    "model_included",
    "selection_status",
    "decision_evidence",
    "total_source_cost",
    "utilisation_percent",
    "exclusion_reason_code",
    "withdrawal_ml_per_day",
    "variable_withdrawal_cost",
}


def _invalid(reason: str) -> dict[str, Any]:
    return {
        "status": STATUS_INVALID_INPUT,
        "ranking": [],
        "verified_entries": [],
        "reason": reason,
    }


def _insufficient(reason: str) -> dict[str, Any]:
    return {
        "status": STATUS_INSUFFICIENT_DATA,
        "ranking": [],
        "verified_entries": [],
        "reason": reason,
    }


def _validate_sources(
    results: dict[str, Any],
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
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


def rank_sensitivities(results: dict[str, Any]) -> dict[str, Any]:
    """Check whether the current MILP output can support sensitivity ranking.

    Confirmed Task 90 behaviour after inspecting the current output example:
    - source records are read from top-level ``sources``;
    - ``data_flags.sources`` is not read;
    - ``allow_estimated_values`` is a policy flag and is not treated as proof
      that a particular source value was estimated;
    - the inspected source objects do not contain per-source provenance;
    - the inspected output does not contain sensitivity-to-assumption data;
    - without both provenance and sensitivity evidence, no supported ranking
      can be produced.
    """
    if not isinstance(results, dict):
        return _invalid("Results must be a JSON object.")

    sources, source_error = _validate_sources(results)
    if source_error is not None:
        return source_error
    assert sources is not None

    # The current milp_model_output example confirms solved source decision
    # fields, but not the provenance/estimation evidence required by Task 28.
    # Do not infer source provenance from the top-level allow_estimated_values
    # policy flag or from source activation/withdrawal values.
    return _insufficient(
        "The current milp_model_output.sources records do not provide "
        "confirmed per-source provenance/estimation data, and the inspected "
        "MILP output does not provide sensitivity_to_key_assumptions. "
        "A supported sensitivity/value-of-data ranking cannot be produced "
        "from the raw MILP output alone."
    )
