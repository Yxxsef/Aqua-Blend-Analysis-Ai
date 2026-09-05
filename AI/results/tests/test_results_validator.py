import json
import sys
import os
import pytest

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from results_validator import (
    REQUIRED_FIELDS,
    validate_results,
    ValidationError,
)

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__),
    "fixtures",
    "output_contract_v1.json",
)


def load_fixture():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_real_v1_fixture_passes():
    assert validate_results(load_fixture()) is True


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_required_field(field):
    results = load_fixture()

    del results[field]

    with pytest.raises(ValidationError):
        validate_results(results)


def test_invalid_root_type():
    with pytest.raises(ValidationError):
        validate_results([])


def test_schema_version_must_be_string():
    results = load_fixture()

    results["schema_version"] = 1.0

    with pytest.raises(ValidationError):
        validate_results(results)


def test_scenario_must_be_object():
    results = load_fixture()

    results["scenario"] = "scenario_2026_07_17_001"

    with pytest.raises(ValidationError):
        validate_results(results)


def test_scenario_requires_scenario_id():
    results = load_fixture()

    del results["scenario"]["scenario_id"]

    with pytest.raises(ValidationError):
        validate_results(results)


def test_scenario_id_must_not_be_empty():
    results = load_fixture()

    results["scenario"]["scenario_id"] = "   "

    with pytest.raises(ValidationError):
        validate_results(results)


def test_solver_must_be_object():
    results = load_fixture()

    results["solver"] = "OPTIMAL"

    with pytest.raises(ValidationError):
        validate_results(results)


def test_solver_requires_status():
    results = load_fixture()

    del results["solver"]["status"]

    with pytest.raises(ValidationError):
        validate_results(results)


def test_solver_status_must_be_string():
    results = load_fixture()

    results["solver"]["status"] = None

    with pytest.raises(ValidationError):
        validate_results(results)


def test_sources_must_be_list():
    # Old contract shape: object with selected/unused.
    results = load_fixture()

    results["sources"] = {
        "selected": [],
        "unused": [],
    }

    with pytest.raises(ValidationError):
        validate_results(results)


def test_source_entry_must_be_object():
    results = load_fixture()

    results["sources"][0] = "silvan_reservoir"

    with pytest.raises(ValidationError):
        validate_results(results)


def test_source_entry_requires_source_id():
    results = load_fixture()

    del results["sources"][0]["source_id"]

    with pytest.raises(ValidationError):
        validate_results(results)


def test_source_id_must_not_be_empty():
    results = load_fixture()

    results["sources"][0]["source_id"] = "  "

    with pytest.raises(ValidationError):
        validate_results(results)


def test_plants_must_be_list():
    # Old contract shape: object with active/inactive.
    results = load_fixture()

    results["plants"] = {
        "active": [],
        "inactive": [],
    }

    with pytest.raises(ValidationError):
        validate_results(results)


def test_plant_entry_must_be_object():
    results = load_fixture()

    results["plants"][0] = "facility_1"

    with pytest.raises(ValidationError):
        validate_results(results)


def test_flows_must_be_object():
    results = load_fixture()

    results["flows"] = []

    with pytest.raises(ValidationError):
        validate_results(results)


def test_quality_must_be_object():
    results = load_fixture()

    results["quality"] = []

    with pytest.raises(ValidationError):
        validate_results(results)


def test_warnings_must_be_list():
    results = load_fixture()

    results["warnings"] = {}

    with pytest.raises(ValidationError):
        validate_results(results)


def test_old_task21_shape_is_rejected():
    # The pre-v1 Results JSON shape no longer satisfies
    # the v1 output contract.
    old_shape = {
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

    with pytest.raises(ValidationError):
        validate_results(old_shape)