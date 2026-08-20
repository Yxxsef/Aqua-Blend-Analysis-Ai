from copy import deepcopy

import pytest

from AI.results.sensitivity_ranking import (
    STATUS_INSUFFICIENT_DATA,
    STATUS_INVALID_INPUT,
    rank_sensitivities,
)


@pytest.fixture
def sample_results():
    return {
        "scenario_id": "scenario_2026_07_17_001",
        "status": "OPTIMAL",
        "data_flags": {
            "sources": [
                {
                    "source_id": "groundwater_bore_1",
                    "has_estimated_values": True,
                    "provenance": {
                        "storage_capacity": "estimate",
                        "reference_flow": "estimate",
                        "max_available": "estimate",
                        "cost": "estimate",
                        "alkalinity": "estimate",
                    },
                },
                {
                    "source_id": "yarra_kew",
                    "has_estimated_values": True,
                    "provenance": {
                        "storage_capacity": "estimate",
                        "reference_flow": "estimate",
                        "max_available": "estimate",
                        "cost": "estimate",
                        "alkalinity": "estimate",
                    },
                },
            ]
        },
        "sensitivity_to_key_assumptions": [
            {
                "assumption": (
                    "cost_per_ml for groundwater_bore_1 "
                    "(flagged estimated in the source view)"
                ),
                "impact": (
                    "If actual groundwater cost is 20 percent lower than "
                    "estimated, groundwater_bore_1 would likely enter the "
                    "optimal blend instead of remaining unused"
                ),
            },
            {
                "assumption": (
                    "max_available_ml_per_day for yarra_kew "
                    "(flagged estimated in the source view)"
                ),
                "impact": (
                    "This constraint is currently binding; if real availability "
                    "is lower than assumed, the model may become infeasible at "
                    "this demand level"
                ),
            },
        ],
    }


def test_valid_current_contract_returns_insufficient_data(sample_results):
    result = rank_sensitivities(sample_results)

    assert result["status"] == STATUS_INSUFFICIENT_DATA
    assert result["ranking"] == []
    assert len(result["verified_entries"]) == 2
    assert result["verified_entries"][0]["source_id"] == "groundwater_bore_1"
    assert result["verified_entries"][0]["provenance_field"] == "cost"
    assert result["verified_entries"][1]["source_id"] == "yarra_kew"
    assert result["verified_entries"][1]["provenance_field"] == "max_available"


def test_missing_sensitivity_returns_insufficient_data(sample_results):
    del sample_results["sensitivity_to_key_assumptions"]

    result = rank_sensitivities(sample_results)

    assert result["status"] == STATUS_INSUFFICIENT_DATA
    assert result["ranking"] == []
    assert result["verified_entries"] == []


def test_empty_sensitivity_returns_insufficient_data(sample_results):
    sample_results["sensitivity_to_key_assumptions"] = []

    result = rank_sensitivities(sample_results)

    assert result["status"] == STATUS_INSUFFICIENT_DATA


@pytest.mark.parametrize(
    "invalid_sensitivity",
    [
        {},
        ["bad-entry"],
    ],
)
def test_malformed_sensitivity_returns_invalid_input(
    sample_results,
    invalid_sensitivity,
):
    sample_results["sensitivity_to_key_assumptions"] = invalid_sensitivity

    result = rank_sensitivities(sample_results)

    assert result["status"] == STATUS_INVALID_INPUT
    assert result["ranking"] == []


def test_missing_impact_returns_invalid_input(sample_results):
    del sample_results["sensitivity_to_key_assumptions"][0]["impact"]

    result = rank_sensitivities(sample_results)

    assert result["status"] == STATUS_INVALID_INPUT


def test_unverified_provenance_is_not_ranked(sample_results):
    results = deepcopy(sample_results)

    results["data_flags"]["sources"][0]["provenance"]["cost"] = "measured"
    results["data_flags"]["sources"][1]["provenance"][
        "max_available"
    ] = "measured"

    result = rank_sensitivities(results)

    assert result["status"] == STATUS_INSUFFICIENT_DATA
    assert result["verified_entries"] == []
