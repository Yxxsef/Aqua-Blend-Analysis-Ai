"""Pytest coverage for the Task 27 App & Delivery response adapter."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from results.app_response.app_response_adapter import (
    REPORT_MODES,
    build_app_response,
    validate_app_response,
)


SAMPLE_OPTIMAL_RESULT = {
    "scenario_id": "scenario_2026_07_17_001",
    "status": "OPTIMAL",
    "objective": {
        "total_cost": 184150.0,
        "currency": "AUD",
    },
    "water_quality": {
        "applies_to": "blend_at_plant_inflow",
    },
    "data_flags": {
        "sources": [
            {
                "source_id": "silvan_reservoir",
                "has_estimated_values": True,
            }
        ],
        "notes": [
            "source_activation_cost is structurally 0.00: draft model note"
        ],
    },
}

MOCK_KPIS = {
    "total_cost": 184150.0,
    "currency": "AUD",
    "demand_required_ml_per_day": 500,
    "demand_supplied_ml_per_day": 500,
    "demand_met_percent": 100.0,
}


def test_success_response_has_required_structure() -> None:
    """An optimal validated result should produce an LLM_VALIDATED response."""
    response = build_app_response(
        SAMPLE_OPTIMAL_RESULT,
        kpis=MOCK_KPIS,
        gate_result="PASS",
        confidence_flag="UNKNOWN",
        llm_explanation="Validated explanation.",
        llm_validated=True,
    )

    validate_app_response(response)
    assert response["report_mode"] == "LLM_VALIDATED"
    assert response["solver_status"] == "OPTIMAL"
    assert response["scenario_id"] == "scenario_2026_07_17_001"
    assert response["gate_result"] == "PASS"
    assert response["confidence_flag"] == "UNKNOWN"
    assert response["kpis"] == MOCK_KPIS
    assert isinstance(response["warnings"], list)


def test_fallback_mode_is_used_when_llm_is_unavailable() -> None:
    """An optimal result should use the deterministic fallback when supplied."""
    response = build_app_response(
        SAMPLE_OPTIMAL_RESULT,
        kpis=MOCK_KPIS,
        gate_result="PASS",
        confidence_flag="UNKNOWN",
        fallback_explanation="Deterministic fallback explanation.",
    )

    assert response["report_mode"] == "TEMPLATE_FALLBACK"
    assert response["display_explanation"] == "Deterministic fallback explanation."
    assert any("template fallback" in warning.lower() for warning in response["warnings"])


def test_non_optimal_result_is_status_only() -> None:
    """Non-optimal responses must discard stale solution-only data."""
    response = build_app_response(
        {
            "scenario_id": "scenario_2026_07_17_001",
            "status": "INFEASIBLE",
        },
        kpis=MOCK_KPIS,
        gate_result="FAIL",
        confidence_flag="UNKNOWN",
        comparison={"baseline_id": "mock"},
    )

    assert response["report_mode"] == "STATUS_ONLY"
    assert response["solver_status"] == "INFEASIBLE"
    assert response["kpis"] is None
    assert response["comparison"] is None
    assert response["gate_result"] == "FAIL"
    assert response["confidence_flag"] == "UNKNOWN"


def test_non_optimal_gate_and_confidence_are_sanitised() -> None:
    """STATUS_ONLY should sanitise text fields exactly like the OPTIMAL branch."""
    response = build_app_response(
        {
            "scenario_id": "scenario_2026_07_17_001",
            "status": "INFEASIBLE",
        },
        gate_result="  FAIL  ",
        confidence_flag="  UNKNOWN  ",
    )

    assert response["gate_result"] == "FAIL"
    assert response["confidence_flag"] == "UNKNOWN"

    blank_response = build_app_response(
        {
            "scenario_id": "scenario_2026_07_17_001",
            "status": "ERROR",
        },
        gate_result="   ",
        confidence_flag="   ",
    )

    assert blank_response["gate_result"] is None
    assert blank_response["confidence_flag"] is None


def test_invalid_input_response_does_not_claim_solver_output() -> None:
    """Invalid input must not expose solver or solution data."""
    response = build_app_response(
        None,
        scenario_id="scenario_2026_07_17_001",
        input_valid=False,
    )

    assert response["report_mode"] == "INVALID_INPUT"
    assert response["solver_status"] is None
    assert response["kpis"] is None
    assert response["gate_result"] is None
    assert response["confidence_flag"] is None
    assert response["comparison"] is None


def test_raw_milp_result_is_not_mutated() -> None:
    """Building a display response must not mutate upstream input data."""
    raw = deepcopy(SAMPLE_OPTIMAL_RESULT)
    before = deepcopy(raw)

    response = build_app_response(
        raw,
        kpis=MOCK_KPIS,
        gate_result="PASS",
        confidence_flag="UNKNOWN",
        fallback_explanation="Fallback.",
    )

    assert raw == before

    # Returned nested values must not alias the caller's KPI object either.
    response["kpis"]["total_cost"] = 0
    assert MOCK_KPIS["total_cost"] == 184150.0


def test_invalid_report_mode_is_rejected() -> None:
    """Structural validation should reject undocumented report modes."""
    response = build_app_response(
        SAMPLE_OPTIMAL_RESULT,
        fallback_explanation="Fallback.",
    )
    response["report_mode"] = "NOT_A_MODE"

    with pytest.raises(ValueError):
        validate_app_response(response)


def test_all_required_report_modes_are_documented_in_code() -> None:
    """The adapter should expose exactly the four Task 27 report modes."""
    assert REPORT_MODES == {
        "LLM_VALIDATED",
        "TEMPLATE_FALLBACK",
        "STATUS_ONLY",
        "INVALID_INPUT",
    }


def test_example_adapter_outputs_pass_structural_validation() -> None:
    """Stored example adapter outputs should remain valid against the contract."""
    examples_dir = (
        Path(__file__).parents[1] / "results" / "app_response" / "examples"
    )

    for name in (
        "success_response.json",
        "fallback_response.json",
        "error_response.json",
        "invalid_input_response.json",
    ):
        payload = json.loads((examples_dir / name).read_text(encoding="utf-8"))
        validate_app_response(payload)
