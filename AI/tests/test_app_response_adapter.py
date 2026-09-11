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
        llm_summary="Validated summary.",
        llm_summary_validated=True,
        detailed_explanation="Full deterministic report text.",
        visualization_data={"blend_ratios": []},
    )

    validate_app_response(response)
    assert response["report_mode"] == "LLM_VALIDATED"
    assert response["solver_status"] == "OPTIMAL"
    assert response["scenario_id"] == "scenario_2026_07_17_001"
    assert response["gate_result"] == "PASS"
    assert response["confidence_flag"] == "UNKNOWN"
    assert response["kpis"] == MOCK_KPIS
    assert response["executive_summary"] == "Validated summary."
    assert response["display_explanation"] == response["executive_summary"]
    assert response["detailed_explanation"] == "Full deterministic report text."
    assert response["visualization_data"] == {"blend_ratios": []}
    assert isinstance(response["warnings"], list)


def test_fallback_mode_is_used_when_llm_is_unavailable() -> None:
    """An optimal result should use the deterministic fallback when supplied."""
    response = build_app_response(
        SAMPLE_OPTIMAL_RESULT,
        kpis=MOCK_KPIS,
        gate_result="PASS",
        confidence_flag="UNKNOWN",
        deterministic_summary="Deterministic fallback summary.",
    )

    assert response["report_mode"] == "TEMPLATE_FALLBACK"
    assert response["display_explanation"] == "Deterministic fallback summary."
    assert response["executive_summary"] == "Deterministic fallback summary."
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
    caller_visualization = {"blend_ratios": [{"source": "A", "volume_ml_day": 1, "share_pct": 100}]}

    response = build_app_response(
        raw,
        kpis=MOCK_KPIS,
        gate_result="PASS",
        confidence_flag="UNKNOWN",
        deterministic_summary="Fallback.",
        visualization_data=caller_visualization,
    )

    assert raw == before

    # Returned nested values must not alias the caller's objects either.
    response["kpis"]["total_cost"] = 0
    assert MOCK_KPIS["total_cost"] == 184150.0

    response["visualization_data"]["blend_ratios"].append({"source": "mutated"})
    assert len(caller_visualization["blend_ratios"]) == 1


def test_invalid_report_mode_is_rejected() -> None:
    """Structural validation should reject undocumented report modes."""
    response = build_app_response(
        SAMPLE_OPTIMAL_RESULT,
        deterministic_summary="Fallback.",
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


# ---------------------------------------------------------------------------
# Task 88: prove the adapter works against the REAL milp_model_output flat
# schema (via supabase_repository.normalize_output_columns()), not just on
# SAMPLE_OPTIMAL_RESULT above, which is a hand-built canonical dict that
# could silently drift from what normalization actually produces.
# ---------------------------------------------------------------------------

from integration.supabase_repository import normalize_output_columns
from results.app_response.app_response_adapter import SOLVER_STATUSES


def _real_optimal_row() -> dict:
    """A row shaped exactly like a real milp_model_output table row (flat
    columns, per milp_model_output.sql), for the confirmed toy-model
    OPTIMAL scenario used throughout this project's fixtures."""
    return {
        "id": "6f1d2c3b-0000-4000-8000-000000000001",
        "schema_version": "1.0",
        "scenario_id": "scenario_2026_07_17_001",
        "scenario_status": "solved",
        "loader_status": "NOT_RUN",
        "preprocessing_status": "NOT_RUN",
        "solver_status": "OPTIMAL",
        "solver_is_feasible": True,
        "solver_is_optimal": True,
        "solver_objective_value": 184150.0,
        "total_cost": 184150.0,
        "total_demand_ml_per_day": 500.0,
        "total_delivered_ml_per_day": 500.0,
        "sources": [
            {
                "source_id": "yarra_kew",
                "source_name": "Yarra River, Kew",
                "volume_drawn_ml_per_day": 290.0,
                "percent_of_blend": 58.0,
                "selected": True,
            },
            {
                "source_id": "silvan_reservoir",
                "source_name": "Silvan Reservoir",
                "volume_drawn_ml_per_day": 210.0,
                "percent_of_blend": 42.0,
                "selected": True,
            },
            {
                "source_id": "groundwater_bore_1",
                "source_name": "Groundwater Bore 1",
                "volume_drawn_ml_per_day": 0.0,
                "selected": False,
            },
        ],
        "plants": [
            {"plant_id": "facility_1", "plant_name": "Treatment Facility 1", "active": True},
        ],
        "demand_zones": [
            {
                "zone_id": "zone_1",
                "zone_name": "Zone 1",
                "demand_ml_per_day": 500.0,
                "volume_supplied_ml_per_day": 500.0,
            },
        ],
        "flows_source_to_plant": [],
        "flows_plant_to_zone": [],
        "quality": {
            "by_plant": {
                "facility_1": {
                    "alkalinity": {
                        "value": 38.04,
                        "constraint_min": 20,
                        "constraint_max": 100,
                        "status": "PASS",
                        "safety_margin_percent": 22.6,
                    },
                },
            },
        },
        "binding_constraints_summary": ["source_capacity_yarra_kew"],
        "warnings": [
            "One or more source inputs contain estimated values; interpret "
            "the result and confidence flag accordingly.",
        ],
        "output_hash": None,
        "input_id": None,
        "origin_run_id": 7,
        "scenario_db_id": 42,
    }


def _real_infeasible_row() -> dict:
    row = _real_optimal_row()
    row.update(
        {
            "solver_status": "INFEASIBLE",
            "solver_is_feasible": False,
            "solver_is_optimal": None,
            "solver_objective_value": None,
            "total_cost": None,
        }
    )
    return row


def test_solver_status_vocabulary_is_a_subset_of_solver_statuses() -> None:
    """Locks in which of milp_model_output's three status columns
    (loader_status, preprocessing_status, solver_status) is the correct one
    for the adapter to read - a structural fact about vocabularies never
    overlapping, not a preference."""
    row = _real_optimal_row()
    assert row["solver_status"] in SOLVER_STATUSES


def test_loader_and_preprocessing_status_vocabulary_never_matches() -> None:
    """NOT_RUN (and any other loader/preprocessing-stage value) is
    structurally incompatible with SOLVER_STATUSES - this is why those two
    columns are never the right ones to read here."""
    row = _real_optimal_row()
    assert row["loader_status"] not in SOLVER_STATUSES
    assert row["preprocessing_status"] not in SOLVER_STATUSES


def test_real_optimal_row_normalizes_and_builds_a_valid_response() -> None:
    canonical = normalize_output_columns(_real_optimal_row())
    response = build_app_response(
        canonical,
        kpis={"total_cost": 184150.0, "demand_met_percent": 100.0},
        gate_result="PASS",
        confidence_flag="UNKNOWN",
        deterministic_summary="Deterministic summary text.",
        detailed_explanation="Full deterministic report text.",
    )
    validate_app_response(response)
    assert response["solver_status"] == "OPTIMAL"
    assert response["scenario_id"] == "scenario_2026_07_17_001"
    assert response["report_mode"] == "TEMPLATE_FALLBACK"


def test_real_infeasible_row_normalizes_and_builds_a_status_only_response() -> None:
    canonical = normalize_output_columns(_real_infeasible_row())
    response = build_app_response(canonical)
    validate_app_response(response)
    assert response["solver_status"] == "INFEASIBLE"
    assert response["report_mode"] == "STATUS_ONLY"
    assert response["kpis"] is None
    assert response["comparison"] is None


def test_real_selected_sources_survive_normalization_into_the_response() -> None:
    canonical = normalize_output_columns(_real_optimal_row())
    selected_ids = {s["source_id"] for s in canonical["sources"]["selected"]}
    unused_ids = {s["source_id"] for s in canonical["sources"]["unused"]}
    assert selected_ids == {"yarra_kew", "silvan_reservoir"}
    assert unused_ids == {"groundwater_bore_1"}


def test_passing_a_raw_row_directly_fails_with_a_clear_message() -> None:
    """Regression for the defensive guard added to build_app_response(): a
    raw milp_model_output row (never normalized) must fail loudly and
    specifically, not with the generic 'undocumented solver status: None'
    message that 'status' simply being absent would otherwise produce."""
    with pytest.raises(ValueError, match="raw milp_model_output row"):
        build_app_response(_real_optimal_row())
