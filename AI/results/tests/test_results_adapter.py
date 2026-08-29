import sys
import os
import pytest

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from results_adapter import (
    adapt_results,
    AdapterError,
)


def sample_results():
    return {
        "scenario_id": "scenario_2026_07_17_001",
        "status": "OPTIMAL",
        "objective": {
            "total_cost": 184150.00,
            "currency": "AUD",
        },
        "demand_zones": [],
        "sources": {
            "selected": [],
            "unused": [],
        },
        "transfer_paths": {},
        "plants": {},
        "water_quality": {},
        "constraints": [],
        "diagnostics": {},
        "data_flags": {
            "sources": []
        },
    }


def test_adapter_converts_fields():
    result = adapt_results(sample_results())

    assert (
        result["scenarioId"]
        == "scenario_2026_07_17_001"
    )

    assert result["status"] == "OPTIMAL"
    assert result["demandZones"] == []
    assert result["waterQuality"] == {}

    # The adapter preserves the complete data_flags
    # structure, even when sources is empty.
    assert result["dataFlags"] == {
        "sources": []
    }


def test_adapter_preserves_additional_data_flags_fields():
    results = sample_results()

    results["data_flags"]["notes"] = [
        "Estimated demand data"
    ]

    result = adapt_results(results)

    assert result["dataFlags"] == {
        "sources": [],
        "notes": [
            "Estimated demand data"
        ],
    }


def test_adapter_preserves_sources():
    results = sample_results()

    results["sources"]["selected"].append(
        {
            "source_id": "silvan_reservoir"
        }
    )

    result = adapt_results(results)

    assert (
        result["sources"]["selected"][0]["source_id"]
        == "silvan_reservoir"
    )


def test_adapter_preserves_constraints():
    results = sample_results()

    results["constraints"].append(
        {
            "name": "demand_satisfaction_zone_1",
            "status": "PASS",
        }
    )

    result = adapt_results(results)

    assert len(result["constraints"]) == 1
    assert (
        result["constraints"][0]["status"]
        == "PASS"
    )


def test_adapter_optional_fields():
    results = sample_results()

    results["solved_at"] = (
        "2026-07-17T10:32:00Z"
    )

    results["binding_constraints_summary"] = [
        "demand_satisfaction_zone_1"
    ]

    results["explanation"] = "Test explanation."

    result = adapt_results(results)

    assert result["solvedAt"] == (
        "2026-07-17T10:32:00Z"
    )

    assert result["bindingConstraintsSummary"] == [
        "demand_satisfaction_zone_1"
    ]

    assert result["explanation"] == (
        "Test explanation."
    )


def test_adapter_missing_field():
    results = sample_results()

    del results["status"]

    with pytest.raises(AdapterError):
        adapt_results(results)


def test_adapter_requires_dictionary():
    with pytest.raises(AdapterError):
        adapt_results([])