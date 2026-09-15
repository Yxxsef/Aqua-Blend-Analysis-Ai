import json
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
from results_validator import validate_results

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__),
    "fixtures",
    "output_contract_v1.json",
)


def load_fixture():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_adapter_maps_top_level_fields():
    results = load_fixture()

    adapted = adapt_results(results)

    assert (
        adapted["schemaVersion"]
        == results["schema_version"]
    )

    assert adapted["runId"] is None

    assert (
        adapted["demandZones"]
        == results["demand_zones"]
    )


def test_adapter_preserves_v1_structures_unchanged():
    results = load_fixture()

    adapted = adapt_results(results)

    for field in (
        "scenario",
        "validation",
        "solver",
        "summary",
        "sources",
        "plants",
        "flows",
        "quality",
        "warnings",
    ):
        assert adapted[field] == results[field]


def test_adapter_maps_binding_constraints_summary():
    results = load_fixture()

    adapted = adapt_results(results)

    assert (
        adapted["bindingConstraintsSummary"]
        == results["binding_constraints_summary"]
    )


def test_adapter_omits_missing_optional_fields():
    results = load_fixture()

    adapted = adapt_results(results)

    assert "solvedAt" not in adapted
    assert "explanation" not in adapted
    assert "alternativeFeasibleSolutions" not in adapted
    assert "sensitivityToKeyAssumptions" not in adapted


def test_adapter_maps_task21_optional_fields_when_present():
    results = load_fixture()

    results["solved_at"] = (
        "2026-07-17T10:32:00Z"
    )

    results["explanation"] = "Test explanation."

    adapted = adapt_results(results)

    assert adapted["solvedAt"] == (
        "2026-07-17T10:32:00Z"
    )

    assert adapted["explanation"] == (
        "Test explanation."
    )


def test_adapter_missing_field():
    results = load_fixture()

    del results["solver"]

    with pytest.raises(AdapterError):
        adapt_results(results)


def test_adapter_requires_dictionary():
    with pytest.raises(AdapterError):
        adapt_results([])


def test_validate_then_adapt_round_trip():
    results = load_fixture()

    assert validate_results(results) is True

    adapted = adapt_results(results)

    assert (
        adapted["scenario"]["scenario_id"]
        == results["scenario"]["scenario_id"]
    )

    assert adapted["solver"] == results["solver"]
    assert adapted["sources"] == results["sources"]
    assert adapted["quality"] == results["quality"]
    assert adapted["flows"] == results["flows"]