"""Task 27 App response adapter structural test. """

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from app_response_adapter import (
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


class AppResponseAdapterTests(unittest.TestCase):
    def test_success_response_has_required_structure(self) -> None:
        response = build_app_response(
            SAMPLE_OPTIMAL_RESULT,
            kpis=MOCK_KPIS,
            gate_result="PASS",
            confidence_flag="UNKNOWN",
            llm_explanation="Validated explanation.",
            llm_validated=True,
        )

        validate_app_response(response)
        self.assertEqual(response["report_mode"], "LLM_VALIDATED")
        self.assertEqual(response["solver_status"], "OPTIMAL")
        self.assertEqual(response["scenario_id"], "scenario_2026_07_17_001")
        self.assertIsInstance(response["warnings"], list)

    def test_fallback_mode_is_used_when_llm_is_unavailable(self) -> None:
        response = build_app_response(
            SAMPLE_OPTIMAL_RESULT,
            kpis=MOCK_KPIS,
            gate_result="PASS",
            confidence_flag="UNKNOWN",
            fallback_explanation="Deterministic fallback explanation.",
        )

        self.assertEqual(response["report_mode"], "TEMPLATE_FALLBACK")
        self.assertTrue(
            any("template fallback" in warning.lower() for warning in response["warnings"])
        )

    def test_non_optimal_result_is_status_only(self) -> None:
        response = build_app_response(
            {
                "scenario_id": "scenario_2026_07_17_001",
                "status": "INFEASIBLE",
            },
            # Stale solution data must be discarded by the adapter.
            kpis=MOCK_KPIS,
            gate_result="FAIL",
            confidence_flag="UNKNOWN",
            comparison={"baseline_id": "mock"},
        )

        self.assertEqual(response["report_mode"], "STATUS_ONLY")
        self.assertEqual(response["solver_status"], "INFEASIBLE")
        self.assertIsNone(response["kpis"])
        self.assertIsNone(response["comparison"])

    def test_invalid_input_response_does_not_claim_solver_output(self) -> None:
        response = build_app_response(
            None,
            scenario_id="scenario_2026_07_17_001",
            input_valid=False,
        )

        self.assertEqual(response["report_mode"], "INVALID_INPUT")
        self.assertIsNone(response["solver_status"])
        self.assertIsNone(response["kpis"])
        self.assertIsNone(response["comparison"])

    def test_raw_milp_result_is_not_mutated(self) -> None:
        raw = deepcopy(SAMPLE_OPTIMAL_RESULT)
        before = deepcopy(raw)

        response = build_app_response(
            raw,
            kpis=MOCK_KPIS,
            gate_result="PASS",
            confidence_flag="UNKNOWN",
            fallback_explanation="Fallback.",
        )

        self.assertEqual(raw, before)

        # Also ensure returned nested objects do not alias the caller's KPI data.
        response["kpis"]["total_cost"] = 0
        self.assertEqual(MOCK_KPIS["total_cost"], 184150.0)

    def test_invalid_report_mode_is_rejected(self) -> None:
        response = build_app_response(
            SAMPLE_OPTIMAL_RESULT,
            fallback_explanation="Fallback.",
        )
        response["report_mode"] = "NOT_A_MODE"
        with self.assertRaises(ValueError):
            validate_app_response(response)

    def test_all_required_report_modes_are_documented_in_code(self) -> None:
        self.assertEqual(
            REPORT_MODES,
            {
                "LLM_VALIDATED",
                "TEMPLATE_FALLBACK",
                "STATUS_ONLY",
                "INVALID_INPUT",
            },
        )

    def test_mock_json_examples_pass_structural_validation(self) -> None:
        examples_dir = Path(__file__).parent / "examples"
        for name in (
            "success_response.json",
            "fallback_response.json",
            "error_response.json",
            "invalid_input_response.json",
        ):
            with self.subTest(name=name):
                payload = json.loads((examples_dir / name).read_text(encoding="utf-8"))
                validate_app_response(payload)


if __name__ == "__main__":
    unittest.main()
