from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

# Ensure the adapter module in AI/scenarios is importable when tests run
SCENARIOS_DIR = Path(__file__).resolve().parents[1]
if str(SCENARIOS_DIR) not in sys.path:
    sys.path.insert(0, str(SCENARIOS_DIR))

from scenario_context_adapter import ScenarioContextAdapter


def test_build_context_maps_core_fields_and_excludes_solver_outputs():
    scenario = SimpleNamespace(
        scenario_id="scenario_001",
        run_id="run_001",
        scenario_name="High Demand Summer Case",
        description="Tests increased summer demand.",
        status="ready",
        is_ready=True,
        validation_issues=[],
        sources=[
            SimpleNamespace(
                source_id="SRC_001",
                name="Source A",
                enabled=True,
                forced_inactive=False,
                minimum_withdrawal_ml_per_day=0,
                maximum_withdrawal_ml_per_day=70,
                availability_status="available",
                objective_value=999.0,
            )
        ],
        plants=[
            {
                "plant_id": "PLANT_001",
                "name": "Plant 1",
                "enabled": True,
                "minimum_processing_capacity_ml_per_day": 10,
                "maximum_processing_capacity_ml_per_day": 100,
                "availability_status": "available",
            }
        ],
        demand_zones=[
            {
                "zone_id": "ZONE_001",
                "name": "North Zone",
                "demand_ml_per_day": 120,
            }
        ],
        source_to_plant_links=[
            {
                "source_id": "SRC_001",
                "plant_id": "PLANT_001",
                "enabled": True,
                "maximum_flow_ml_per_day": 60,
            }
        ],
        plant_to_zone_links=[
            {
                "plant_id": "PLANT_001",
                "zone_id": "ZONE_001",
                "enabled": True,
                "maximum_flow_ml_per_day": 100,
            }
        ],
        quality_limits=[
            {
                "parameter_id": "TDS",
                "name": "Total Dissolved Solids",
                "maximum": 500,
                "unit": "mg/L",
                "profile_id": "STANDARD_001",
            }
        ],
        objective_value=1234.5,
        source_allocations=[{"source_id": "SRC_001", "volume": 70}],
        flows=[{"from": "SRC_001", "to": "PLANT_001", "value": 60}],
    )

    adapter = ScenarioContextAdapter()
    context = adapter.build(scenario)
    payload = context.to_dict()

    assert payload["scenario_id"] == "scenario_001"
    assert payload["run_id"] == "run_001"
    assert payload["scenario_name"] == "High Demand Summer Case"
    assert payload["description"] == "Tests increased summer demand."
    assert payload["status"] == "ready"
    assert payload["is_ready"] is True
    assert payload["validation_issues"] == []

    assert payload["sources"][0]["source_id"] == "SRC_001"
    assert payload["plants"][0]["plant_id"] == "PLANT_001"
    assert payload["demand_zones"][0]["zone_id"] == "ZONE_001"
    assert payload["quality_limits"][0]["parameter_id"] == "TDS"

    assert "objective_value" not in payload
    assert "source_allocations" not in payload
    assert "flows" not in payload


def test_build_context_handles_missing_optional_fields_safely():
    scenario = {
        "scenario_id": "scenario_002",
        "scenario_name": "Minimal Scenario",
        "sources": None,
        "plants": None,
        "demand_zones": [],
        "source_to_plant_links": None,
        "plant_to_zone_links": None,
        "quality_limits": None,
        "validation_issues": None,
    }

    adapter = ScenarioContextAdapter()
    context = adapter.build(scenario)
    payload = context.to_dict()

    assert payload["scenario_id"] == "scenario_002"
    assert payload["scenario_name"] == "Minimal Scenario"
    assert payload["validation_issues"] == []
    assert payload["sources"] == []
    assert payload["plants"] == []
    assert payload["demand_zones"] == []
    assert payload["source_to_plant_links"] == []
    assert payload["plant_to_zone_links"] == []
    assert payload["quality_limits"] == []


def test_build_context_preserves_link_ids_and_overrides():
    scenario = {
        "scenario_id": "scenario_003",
        "scenario_name": "Outage Test",
        "source_to_plant_links": [
            {
                "source_id": "SRC_010",
                "plant_id": "PLANT_020",
                "enabled": False,
                "maximum_flow_ml_per_day": 40,
                "override": {"reason": "simulate outage"},
            }
        ],
        "plant_to_zone_links": [
            {
                "plant_id": "PLANT_020",
                "zone_id": "ZONE_030",
                "enabled": True,
                "maximum_flow_ml_per_day": 90,
                "override": {"reason": "capacity reduction"},
            }
        ],
    }

    adapter = ScenarioContextAdapter()
    context = adapter.build(scenario)
    payload = context.to_dict()

    assert payload["source_to_plant_links"][0]["source_id"] == "SRC_010"
    assert payload["source_to_plant_links"][0]["plant_id"] == "PLANT_020"
    assert payload["source_to_plant_links"][0]["enabled"] is False
    assert (
        payload["source_to_plant_links"][0]["override"]["reason"]
        == "simulate outage"
    )

    assert payload["plant_to_zone_links"][0]["plant_id"] == "PLANT_020"
    assert payload["plant_to_zone_links"][0]["zone_id"] == "ZONE_030"
    assert (
        payload["plant_to_zone_links"][0]["override"]["reason"]
        == "capacity reduction"
    )


def test_build_context_prefers_explicit_run_id_argument():
    """
    Explicit run_id argument should take precedence over any run_id
    present in the scenario object.
    """
    scenario = {
        "scenario_id": "scenario_004",
        "run_id": "scenario_run_id",
        "scenario_name": "Run ID Override Test",
    }

    adapter = ScenarioContextAdapter()

    context = adapter.build(
        scenario,
        run_id="explicit_run_id",
    )

    payload = context.to_dict()

    assert payload["scenario_id"] == "scenario_004"
    assert payload["run_id"] == "explicit_run_id"
    assert payload["scenario_name"] == "Run ID Override Test"