import sys
import os
import pytest

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from results_validator import (
    validate_results,
    ValidationError,
)


def valid_results():
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


def test_valid_results_pass():
    assert validate_results(valid_results()) is True


def test_optimal_status_is_valid():
    results = valid_results()

    results["status"] = "OPTIMAL"

    assert validate_results(results) is True


def test_unbounded_status_is_valid():
    results = valid_results()

    results["status"] = "UNBOUNDED"

    assert validate_results(results) is True


def test_missing_required_field():
    results = valid_results()

    del results["objective"]

    with pytest.raises(ValidationError):
        validate_results(results)


def test_invalid_root_type():
    with pytest.raises(ValidationError):
        validate_results([])


def test_invalid_status():
    results = valid_results()

    results["status"] = "INVALID_STATUS"

    with pytest.raises(ValidationError):
        validate_results(results)


def test_invalid_sources_type():
    results = valid_results()

    results["sources"] = []

    with pytest.raises(ValidationError):
        validate_results(results)


def test_sources_requires_selected():
    results = valid_results()

    results["sources"] = {
        "unused": []
    }

    with pytest.raises(ValidationError):
        validate_results(results)


def test_sources_requires_unused():
    results = valid_results()

    results["sources"] = {
        "selected": []
    }

    with pytest.raises(ValidationError):
        validate_results(results)


def test_constraints_must_be_list():
    results = valid_results()

    results["constraints"] = {}

    with pytest.raises(ValidationError):
        validate_results(results)


def test_constraint_items_must_be_objects():
    results = valid_results()

    results["constraints"] = ["invalid"]

    with pytest.raises(ValidationError):
        validate_results(results)


def test_data_flags_sources_must_be_list():
    results = valid_results()

    results["data_flags"]["sources"] = {}

    with pytest.raises(ValidationError):
        validate_results(results)


def test_source_requires_source_id():
    results = valid_results()

    results["sources"]["selected"] = [
        {
            "source_name": "Silvan Reservoir"
        }
    ]

    with pytest.raises(ValidationError):
        validate_results(results)