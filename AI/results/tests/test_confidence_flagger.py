from types import SimpleNamespace
import os
import sys

import pytest

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from confidence_flagger import ConfidenceError, determine_confidence

# case study sources from base_scenarios_v1.json
CASE_SOURCE_1 = "225103"  # Thomson Reservoir
CASE_SOURCE_2 = "229421"  # O'Shannassy Reservoir
CASE_SOURCE_3 = "233217"  # Barwon River at Geelong


def complete_provenance(label="verified_dataset"):
    return {
        "storage_capacity": label,
        "reference_flow": label,
        "minimum_withdrawal": label,
        "maximum_withdrawal": label,
        "cost": label,
        "quality.pH": label,
        "quality.alkalinity": label,
        "quality.turbidity": label,
    }


def scenario_source(source_id, *, estimated=False, provenance=None):
    """SourceInput-like object using the current ScenarioData field names."""
    return SimpleNamespace(
        source_id=source_id,
        has_estimated_values=estimated,
        provenance=(
            complete_provenance() if provenance is None else provenance
        ),
    )


def milp_source(
    source_id,
    *,
    selection_status="SELECTED",
    activated=True,
    withdrawal=100.0,
):
    """Representative MILP Output JSON v1 source record."""
    return {
        "source_id": source_id,
        "model_included": True,
        "activated": activated,
        "withdrawal_ml_per_day": withdrawal,
        "selection_status": selection_status,
    }


def test_provisional_when_contributing_source_uses_estimated_values():
    scenario_sources = [
        scenario_source(CASE_SOURCE_1, estimated=True),
        scenario_source(CASE_SOURCE_2, estimated=False),
    ]
    milp_sources = [
        milp_source(CASE_SOURCE_1, withdrawal=700.0),
        milp_source(CASE_SOURCE_2, withdrawal=500.0),
    ]

    result = determine_confidence(scenario_sources, milp_sources)

    assert result == {
        "confidence": "PROVISIONAL",
        "estimated_sources": [CASE_SOURCE_1],
    }


def test_measured_when_all_contributing_sources_are_complete_and_not_estimated():
    scenario_sources = [
        scenario_source(CASE_SOURCE_1),
        scenario_source(CASE_SOURCE_2),
    ]
    milp_sources = [
        milp_source(CASE_SOURCE_1, withdrawal=700.0),
        milp_source(CASE_SOURCE_2, withdrawal=500.0),
    ]

    result = determine_confidence(scenario_sources, milp_sources)

    assert result == {
        "confidence": "MEASURED",
        "estimated_sources": [],
    }


def test_unused_estimated_source_does_not_reduce_confidence():
    scenario_sources = [
        scenario_source(CASE_SOURCE_1),
        scenario_source(CASE_SOURCE_2),
        scenario_source(CASE_SOURCE_3, estimated=True),
    ]
    milp_sources = [
        milp_source(CASE_SOURCE_1, withdrawal=700.0),
        milp_source(CASE_SOURCE_2, withdrawal=500.0),
        milp_source(
            CASE_SOURCE_3,
            selection_status="UNUSED",
            activated=False,
            withdrawal=0.0,
        ),
    ]

    result = determine_confidence(scenario_sources, milp_sources)

    assert result["confidence"] == "MEASURED"
    assert result["estimated_sources"] == []


def test_unknown_when_contributing_source_provenance_is_incomplete():
    incomplete = complete_provenance()
    incomplete["quality.turbidity"] = None

    scenario_sources = [
        scenario_source(CASE_SOURCE_1, provenance=incomplete),
    ]
    milp_sources = [milp_source(CASE_SOURCE_1)]

    result = determine_confidence(scenario_sources, milp_sources)

    assert result == {
        "confidence": "UNKNOWN",
        "estimated_sources": [],
    }


def test_unknown_when_contributing_source_is_missing_from_scenario_data():
    scenario_sources = [scenario_source(CASE_SOURCE_1)]
    milp_sources = [milp_source(CASE_SOURCE_2)]

    result = determine_confidence(scenario_sources, milp_sources)

    assert result["confidence"] == "UNKNOWN"


def test_provisional_takes_precedence_over_other_unknown_provenance():
    incomplete = complete_provenance()
    incomplete["cost"] = None

    scenario_sources = [
        scenario_source(CASE_SOURCE_1, estimated=True),
        scenario_source(CASE_SOURCE_2, estimated=False, provenance=incomplete),
    ]
    milp_sources = [
        milp_source(CASE_SOURCE_1),
        milp_source(CASE_SOURCE_2),
    ]

    result = determine_confidence(scenario_sources, milp_sources)

    assert result == {
        "confidence": "PROVISIONAL",
        "estimated_sources": [CASE_SOURCE_1],
    }


def test_unsolved_v1_pending_sources_return_unknown_without_raising():
    """Mirrors the Task 56 v1 fixture, which is NOT_SOLVED/PENDING."""
    scenario_sources = [
        scenario_source(CASE_SOURCE_1),
        scenario_source(CASE_SOURCE_2),
        scenario_source(CASE_SOURCE_3),
    ]
    milp_sources = [
        {
            "source_id": CASE_SOURCE_1,
            "model_included": None,
            "activated": None,
            "withdrawal_ml_per_day": None,
            "selection_status": "PENDING",
        },
        {
            "source_id": CASE_SOURCE_2,
            "model_included": None,
            "activated": None,
            "withdrawal_ml_per_day": None,
            "selection_status": "PENDING",
        },
        {
            "source_id": CASE_SOURCE_3,
            "model_included": None,
            "activated": None,
            "withdrawal_ml_per_day": None,
            "selection_status": "PENDING",
        },
    ]

    result = determine_confidence(scenario_sources, milp_sources)

    assert result == {
        "confidence": "UNKNOWN",
        "estimated_sources": [],
    }


def test_withdrawal_is_preferred_as_contribution_evidence():
    scenario_sources = [scenario_source(CASE_SOURCE_1)]
    milp_sources = [
        {
            "source_id": CASE_SOURCE_1,
            "activated": True,
            "withdrawal_ml_per_day": 0.0,
            "selection_status": "SELECTED",
        }
    ]

    result = determine_confidence(scenario_sources, milp_sources)

    # Zero solved withdrawal means the source did not contribute, even if a contradictory status flag says SELECTED.  
    # The safest confidence is UNKNOWN because there are no confirmed contributing sources.
    assert result["confidence"] == "UNKNOWN"


def test_legacy_task21_selected_source_shape_remains_supported():
    provenance_sources = [
        {
            "source_id": CASE_SOURCE_1,
            "has_estimated_values": True,
            "provenance": complete_provenance(),
        }
    ]
    selected_sources = [{"source_id": CASE_SOURCE_1}]

    result = determine_confidence(provenance_sources, selected_sources)

    assert result == {
        "confidence": "PROVISIONAL",
        "estimated_sources": [CASE_SOURCE_1],
    }


def test_invalid_top_level_container_raises_clear_error():
    with pytest.raises(ConfidenceError):
        determine_confidence("not-a-source-sequence", [])

    with pytest.raises(ConfidenceError):
        determine_confidence([], "not-a-milp-source-sequence")
