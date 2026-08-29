"""Tests for AquaBlend Sprint 2 Task 20 scenario loading and validation."""

from __future__ import annotations

import json
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest


# This test file is stored in AI/scenarios/tests/.
# Add AI/scenarios/ to the Python import path so the Task 20 modules
# can be imported when pytest is run from the repository or scenario folder.
SCENARIO_DIR = Path(__file__).resolve().parent.parent

if str(SCENARIO_DIR) not in sys.path:
    sys.path.insert(0, str(SCENARIO_DIR))

from scenario_loader import ScenarioLoadError, load_scenario
from scenario_validator import ScenarioValidator


NORMAL_PATH = (
    SCENARIO_DIR
    / "normal-year-dry-year"
    / "scenario_normal.json"
)

DRY_PATH = (
    SCENARIO_DIR
    / "normal-year-dry-year"
    / "scenario_dry_year.json"
)

HIGH_PATH = (
    SCENARIO_DIR
    / "high-demand-outage"
    / "scenario_high_demand.json"
)

OUTAGE_PATH = (
    SCENARIO_DIR
    / "high-demand-outage"
    / "scenario_plant_outage.json"
)


# ---------------------------------------------------------------------------
# Shared pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def validator():
    """Return one ScenarioValidator instance for this test module."""
    return ScenarioValidator()


@pytest.fixture(scope="module")
def normal():
    """Load the normal reference scenario."""
    return load_scenario(NORMAL_PATH)


@pytest.fixture(scope="module")
def dry():
    """Load the dry-year scenario."""
    return load_scenario(DRY_PATH)


@pytest.fixture(scope="module")
def high():
    """Load the high-demand scenario."""
    return load_scenario(HIGH_PATH)


@pytest.fixture(scope="module")
def outage():
    """Load the plant-outage scenario."""
    return load_scenario(OUTAGE_PATH)


# ---------------------------------------------------------------------------
# Scenario loader tests
# ---------------------------------------------------------------------------

def test_load_valid_utf8_json():
    scenario = load_scenario(NORMAL_PATH)

    assert scenario["scenario_id"] == "toy_model_normal_year"


def test_missing_file_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_scenario(SCENARIO_DIR / "does_not_exist.json")


def test_malformed_json_raises_scenario_load_error():
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "scenario_bad.json"

        path.write_text(
            '{"scenario_id": ',
            encoding="utf-8",
        )

        with pytest.raises(ScenarioLoadError):
            load_scenario(path)


def test_non_object_top_level_is_rejected():
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "scenario_bad.json"

        path.write_text(
            "[]",
            encoding="utf-8",
        )

        with pytest.raises(ScenarioLoadError):
            load_scenario(path)


# ---------------------------------------------------------------------------
# Valid scenario tests
# ---------------------------------------------------------------------------

def test_valid_normal_scenario(
    validator,
    normal,
):
    report = validator.validate(
        normal,
        reference=normal,
        scenario_type="NORMAL",
    )

    assert report.valid, report.errors
    assert report.scenario_type == "NORMAL"

    assert (
        report.capacity_check["remaining_capacity_ml_per_day"]
        == 100
    )

    assert (
        report.capacity_check["possible_infeasible"]
        is False
    )


def test_valid_dry_year_records_all_approved_changes(
    validator,
    normal,
    dry,
):
    report = validator.validate(
        dry,
        reference=normal,
        scenario_type="DRY_YEAR",
    )

    assert report.valid, report.errors

    changed_paths = {
        change["path"]
        for change in report.changes_from_reference
    }

    assert (
        "network.source_to_plant_links["
        "source_id=silvan_reservoir,plant_id=facility_1"
        "].maximum_flow_ml_per_day"
        in changed_paths
    )

    assert (
        "network.source_to_plant_links["
        "source_id=yarra_kew,plant_id=facility_1"
        "].maximum_flow_ml_per_day"
        in changed_paths
    )

    assert (
        "network.source_to_plant_links["
        "source_id=groundwater_bore_1,plant_id=facility_1"
        "].maximum_flow_ml_per_day"
        in changed_paths
    )

    assert (
        report.capacity_check["remaining_capacity_ml_per_day"]
        == 65
    )


def test_valid_high_demand_field_and_zero_margin(
    validator,
    normal,
    high,
):
    report = validator.validate(
        high,
        reference=normal,
        scenario_type="HIGH_DEMAND",
    )

    assert report.valid, report.errors

    assert (
        report.capacity_check["required_demand_ml_per_day"]
        == 600
    )

    assert (
        report.capacity_check["remaining_capacity_ml_per_day"]
        == 0
    )

    assert (
        report.capacity_check["possible_infeasible"]
        is False
    )


def test_valid_plant_outage_detects_capacity_and_connectivity_risk(
    validator,
    normal,
    outage,
):
    report = validator.validate(
        outage,
        reference=normal,
        scenario_type="PLANT_OUTAGE",
    )

    assert report.valid, report.errors

    assert (
        report.capacity_check["active_plant_capacity_ml_per_day"]
        == 0
    )

    assert (
        report.capacity_check["possible_infeasible"]
        is True
    )

    assert (
        report.connectivity_check[
            "all_required_zones_reachable"
        ]
        is False
    )

    assert (
        "zone_1"
        in report.connectivity_check["unreachable_zone_ids"]
    )


# ---------------------------------------------------------------------------
# Contract validation tests
# ---------------------------------------------------------------------------

def test_unknown_top_level_field_is_rejected(
    validator,
    normal,
):
    scenario = deepcopy(normal)

    scenario["invented_field"] = 123

    report = validator.validate(
        scenario,
        reference=normal,
        scenario_type="NORMAL",
    )

    assert report.valid is False

    assert any(
        "unknown field" in error.lower()
        for error in report.errors
    )


def test_unknown_nested_field_is_rejected(
    validator,
    normal,
):
    scenario = deepcopy(normal)

    scenario["network"]["plants"][0]["unexpected"] = True

    report = validator.validate(
        scenario,
        reference=normal,
        scenario_type="NORMAL",
    )

    assert report.valid is False

    assert any(
        "unexpected" in error
        for error in report.errors
    )


def test_missing_required_field_is_rejected(
    validator,
    normal,
):
    scenario = deepcopy(normal)

    del scenario["network"]

    report = validator.validate(
        scenario,
        reference=normal,
        scenario_type="NORMAL",
    )

    assert report.valid is False

    assert any(
        "network" in error
        for error in report.errors
    )


def test_wrong_type_is_rejected(
    validator,
    normal,
):
    scenario = deepcopy(normal)

    scenario["network"]["demand_zones"][0][
        "demand_ml_per_day"
    ] = "500"

    report = validator.validate(
        scenario,
        reference=normal,
        scenario_type="NORMAL",
    )

    assert report.valid is False

    assert any(
        "demand_ml_per_day" in error
        for error in report.errors
    )


def test_duplicate_source_id_is_rejected(
    validator,
    normal,
):
    scenario = deepcopy(normal)

    scenario["sources"][1]["source_id"] = (
        scenario["sources"][0]["source_id"]
    )

    report = validator.validate(
        scenario,
        reference=normal,
        scenario_type="NORMAL",
    )

    assert report.valid is False

    assert any(
        "duplicate source_id" in error.lower()
        for error in report.errors
    )


def test_unknown_link_source_is_rejected(
    validator,
    normal,
):
    scenario = deepcopy(normal)

    scenario["network"]["source_to_plant_links"][0][
        "source_id"
    ] = "unknown_source"

    report = validator.validate(
        scenario,
        reference=normal,
        scenario_type="NORMAL",
    )

    assert report.valid is False

    assert any(
        "unknown source" in error.lower()
        for error in report.errors
    )


# ---------------------------------------------------------------------------
# Output protection
# ---------------------------------------------------------------------------

def test_output_only_field_is_rejected(
    validator,
    normal,
):
    scenario = deepcopy(normal)

    scenario["objective"] = {
        "total_cost": 1,
    }

    report = validator.validate(
        scenario,
        reference=normal,
        scenario_type="NORMAL",
    )

    assert report.valid is False

    assert any(
        "output-only" in error.lower()
        for error in report.errors
    )


# ---------------------------------------------------------------------------
# Scenario-specific change validation
# ---------------------------------------------------------------------------

def test_dry_year_unapproved_demand_change_is_rejected(
    validator,
    normal,
    dry,
):
    scenario = deepcopy(dry)

    scenario["network"]["demand_zones"][0][
        "demand_ml_per_day"
    ] = 510

    report = validator.validate(
        scenario,
        reference=normal,
        scenario_type="DRY_YEAR",
    )

    assert report.valid is False

    assert any(
        "unapproved changes" in error.lower()
        for error in report.errors
    )


def test_high_demand_wrong_value_is_rejected(
    validator,
    normal,
    high,
):
    scenario = deepcopy(high)

    scenario["network"]["demand_zones"][0][
        "demand_ml_per_day"
    ] = 590

    report = validator.validate(
        scenario,
        reference=normal,
        scenario_type="HIGH_DEMAND",
    )

    assert report.valid is False

    assert any(
        "must be 600" in error
        for error in report.errors
    )


def test_plant_outage_extra_change_is_rejected(
    validator,
    normal,
    outage,
):
    scenario = deepcopy(outage)

    scenario["network"]["plants"][0][
        "maximum_processing_capacity_ml_per_day"
    ] = 0

    report = validator.validate(
        scenario,
        reference=normal,
        scenario_type="PLANT_OUTAGE",
    )

    assert report.valid is False

    assert any(
        "unapproved changes" in error.lower()
        for error in report.errors
    )


# ---------------------------------------------------------------------------
# Capacity screening
# ---------------------------------------------------------------------------

def test_capacity_shortfall_is_warning_not_fake_solver_status(
    validator,
    high,
):
    scenario = deepcopy(high)

    scenario["network"]["demand_zones"][0][
        "demand_ml_per_day"
    ] = 650

    capacity = validator.check_capacity(scenario)

    assert capacity["possible_infeasible"] is True

    assert (
        capacity["effective_capacity_ml_per_day"]
        < capacity["required_demand_ml_per_day"]
    )

    serialised = json.dumps(capacity)

    assert "OPTIMAL" not in serialised
    assert "INFEASIBLE" not in serialised


# ---------------------------------------------------------------------------
# Current MILP input-contract regression tests
# ---------------------------------------------------------------------------

def test_current_minimum_processing_capacity_field_is_accepted(
    validator,
    normal,
):
    scenario = deepcopy(normal)

    plant = scenario["network"]["plants"][0]

    # Replace the legacy field with the current MILP input-contract field.
    plant["minimum_processing_capacity_ml_per_day"] = plant.pop(
        "minimum_operating_flow_ml_per_day",
        0,
    )

    report = validator.validate(
        scenario,
        reference=scenario,
        scenario_type="NORMAL",
    )

    assert report.valid, report.errors


def test_legacy_minimum_plant_field_is_accepted_with_warning(
    validator,
    normal,
):
    scenario = deepcopy(normal)

    plant = scenario["network"]["plants"][0]

    # Ensure the legacy field exists so compatibility behaviour is tested.
    if "minimum_operating_flow_ml_per_day" not in plant:
        plant["minimum_operating_flow_ml_per_day"] = plant.pop(
            "minimum_processing_capacity_ml_per_day",
            0,
        )

    report = validator.validate(
        scenario,
        reference=scenario,
        scenario_type="NORMAL",
    )

    assert report.valid, report.errors

    assert any(
        "minimum_operating_flow_ml_per_day" in warning
        for warning in report.warnings
    )


def test_minimum_withdrawal_field_is_accepted(
    validator,
    normal,
):
    scenario = deepcopy(normal)

    scenario["sources"][0][
        "minimum_withdrawal_ml_per_day"
    ] = 0

    report = validator.validate(
        scenario,
        reference=scenario,
        scenario_type="NORMAL",
    )

    assert report.valid, report.errors


# ---------------------------------------------------------------------------
# ID-based comparison regression tests
# ---------------------------------------------------------------------------

def test_source_order_does_not_create_false_changes(
    validator,
    normal,
):
    scenario = deepcopy(normal)

    # Reorder the source array without changing any source data.
    scenario["sources"] = list(
        reversed(scenario["sources"])
    )

    report = validator.validate(
        scenario,
        reference=normal,
        scenario_type="NORMAL",
    )

    assert report.valid, report.errors

    changed_paths = {
        change["path"]
        for change in report.changes_from_reference
    }

    assert not any(
        path.startswith("sources[")
        for path in changed_paths
    )


def test_dry_year_link_order_does_not_affect_validation(
    validator,
    normal,
    dry,
):
    scenario = deepcopy(dry)

    # Reorder links without changing their IDs or values.
    scenario["network"]["source_to_plant_links"] = list(
        reversed(
            scenario["network"]["source_to_plant_links"]
        )
    )

    report = validator.validate(
        scenario,
        reference=normal,
        scenario_type="DRY_YEAR",
    )

    assert report.valid, report.errors