"""Task 61 integration tests for the Analysis & AI pipeline entry point."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest


AI_DIR = Path(__file__).resolve().parents[1]
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

import main
from model_runner import ModelConfig, rewrite_report


FIXTURE_PATH = (
    AI_DIR
    / "explanations"
    / "llm_reporting"
    / "fixtures"
    / "model_output_example.json"
)
PROTOTYPE_DISCLAIMER = "AquaBlend is a public-data decision-support proof-of-concept."


@pytest.fixture
def valid_results() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_optimal_result_uses_deterministic_fallback_without_model(
    valid_results: dict,
) -> None:
    original_results = copy.deepcopy(valid_results)

    response = main.run_pipeline(valid_results)

    assert response["scenario_id"] == "scenario_2026_07_17_001"
    assert response["solver_status"] == "OPTIMAL"
    assert response["kpis"]["demand_satisfaction"]["value"] == 100.0
    assert response["gate_result"] == "PASS"
    assert response["confidence_flag"] == "PROVISIONAL"
    assert response["report_mode"] == "TEMPLATE_FALLBACK"
    assert PROTOTYPE_DISCLAIMER in response["display_explanation"]
    assert valid_results == original_results


def test_incomplete_dictionary_returns_invalid_input() -> None:
    response = main.run_pipeline({"scenario_id": "partial-scenario"})

    assert response["report_mode"] == "INVALID_INPUT"
    assert response["scenario_id"] == "partial-scenario"
    assert response["solver_status"] is None
    assert response["kpis"] is None
    assert any("Missing required fields" in warning for warning in response["warnings"])


def test_non_object_input_returns_invalid_input() -> None:
    response = main.run_pipeline(["not", "a", "JSON object"])

    assert response["report_mode"] == "INVALID_INPUT"
    assert response["scenario_id"] is None
    assert any("Results must be a JSON object" in warning for warning in response["warnings"])


def test_unsupported_feasible_status_returns_invalid_input(valid_results: dict) -> None:
    results = copy.deepcopy(valid_results)
    results["status"] = "FEASIBLE"

    response = main.run_pipeline(results)

    assert response["report_mode"] == "INVALID_INPUT"
    assert any("not supported by the App response contract" in warning for warning in response["warnings"])


def test_unbounded_result_returns_status_only_response(valid_results: dict) -> None:
    results = copy.deepcopy(valid_results)
    results["status"] = "UNBOUNDED"

    response = main.run_pipeline(results)

    assert response["solver_status"] == "UNBOUNDED"
    assert response["report_mode"] == "STATUS_ONLY"
    assert response["kpis"] is None
    assert response["comparison"] is None
    assert response["report_mode"] != "INVALID_INPUT"


def test_accepted_llm_rewrite_is_displayed(
    valid_results: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_request(_url, _headers, payload, _timeout_seconds):
        prompt = payload["messages"][1]["content"]
        report = prompt.split("<deterministic_report>\n", 1)[1].rsplit(
            "\n</deterministic_report>", 1
        )[0]
        return {"choices": [{"message": {"content": report}}]}

    def rewrite_with_fake_request(deterministic_report, config):
        return rewrite_report(
            deterministic_report,
            config,
            request_fn=fake_request,
        )

    monkeypatch.setattr(main, "rewrite_report", rewrite_with_fake_request)

    response = main.run_pipeline(
        valid_results,
        model_config=ModelConfig(model_id="test-model"),
    )

    assert response["report_mode"] == "LLM_VALIDATED"


def test_rejected_llm_rewrite_uses_deterministic_fallback(
    valid_results: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_request(*_args, **_kwargs):
        return {
            "choices": [
                {"message": {"content": "The result is completely safe and costs $1."}}
            ]
        }

    def rewrite_with_fake_request(deterministic_report, config):
        return rewrite_report(
            deterministic_report,
            config,
            request_fn=fake_request,
        )

    monkeypatch.setattr(main, "rewrite_report", rewrite_with_fake_request)

    response = main.run_pipeline(
        valid_results,
        model_config=ModelConfig(model_id="test-model"),
    )

    assert response["report_mode"] == "TEMPLATE_FALLBACK"
    assert PROTOTYPE_DISCLAIMER in response["display_explanation"]
    assert any("LLM rewrite was rejected by validation" in warning for warning in response["warnings"])