"""Mocked tests for the AquaBlend LLM model runner."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

EXPLANATIONS_DIR = Path(__file__).resolve().parents[1]
if str(EXPLANATIONS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPLANATIONS_DIR))

from model_runner import ModelConfig, load_model_config, rewrite_report
from prompts import PROMPT_VERSION, REWRITE_FAILURE_SENTINEL, build_rewrite_messages


TEMPLATE_REPORT = """Scenario: normal_year
Solver status: OPTIMAL
Total cost: 1250 AUD
Warning: Water quality applies to plant inflow, not final drinking water.
Prototype disclaimer: Public-data proof-of-concept only.
"""


def test_prompt_contains_report_and_strict_rules() -> None:
    messages = build_rewrite_messages(TEMPLATE_REPORT)

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "Preserve every fact" in messages[0]["content"]
    assert "Do not create reasons" in messages[0]["content"]
    assert "plant-inflow quality" in messages[0]["content"]
    assert TEMPLATE_REPORT.strip() in messages[1]["content"]


def test_success_records_metadata_and_marks_output_unvalidated() -> None:
    captured: dict = {}

    def fake_request(url, headers, payload, timeout_seconds):
        captured.update(
            url=url,
            headers=headers,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        return {
            "choices": [
                {
                    "message": {
                        "content": "Scenario normal_year completed with status OPTIMAL."
                    }
                }
            ]
        }

    config = ModelConfig(model_id="test-model", timeout_seconds=5)
    result = rewrite_report(TEMPLATE_REPORT, config, request_fn=fake_request)

    assert result.report_mode == "LLM_UNVALIDATED"
    assert result.fallback_used is False
    assert result.model_id == "test-model"
    assert result.prompt_version == PROMPT_VERSION
    assert result.failure_type is None
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["payload"]["temperature"] == 0.0
    assert captured["payload"]["seed"] == 0


def test_timeout_returns_template_fallback() -> None:
    def timeout_request(*_args, **_kwargs):
        raise TimeoutError("request exceeded 1 second")

    result = rewrite_report(
        TEMPLATE_REPORT,
        ModelConfig(model_id="test-model"),
        request_fn=timeout_request,
    )

    assert result.report_text == TEMPLATE_REPORT.strip()
    assert result.report_mode == "TEMPLATE_FALLBACK"
    assert result.fallback_used is True
    assert result.failure_type == "TIMEOUT"


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {"content": None}}]},
    ],
)
def test_malformed_response_returns_template_fallback(response: dict) -> None:
    def malformed_request(*_args, **_kwargs):
        return response

    result = rewrite_report(
        TEMPLATE_REPORT,
        ModelConfig(model_id="test-model"),
        request_fn=malformed_request,
    )

    assert result.report_mode == "TEMPLATE_FALLBACK"
    assert result.failure_type == "INVALID_RESPONSE"


def test_empty_output_returns_template_fallback() -> None:
    def empty_request(*_args, **_kwargs):
        return {"choices": [{"message": {"content": "   "}}]}

    result = rewrite_report(
        TEMPLATE_REPORT,
        ModelConfig(model_id="test-model"),
        request_fn=empty_request,
    )

    assert result.report_mode == "TEMPLATE_FALLBACK"
    assert result.failure_type == "EMPTY_OUTPUT"


def test_failure_sentinel_returns_template_fallback() -> None:
    def declined_request(*_args, **_kwargs):
        return {"choices": [{"message": {"content": REWRITE_FAILURE_SENTINEL}}]}

    result = rewrite_report(
        TEMPLATE_REPORT,
        ModelConfig(model_id="test-model"),
        request_fn=declined_request,
    )

    assert result.report_mode == "TEMPLATE_FALLBACK"
    assert result.failure_type == "MODEL_DECLINED"


def test_load_model_config(tmp_path: Path) -> None:
    path = tmp_path / "model_config.json"
    path.write_text(
        json.dumps(
            {
                "model_id": "Qwen/Qwen3-4B-Instruct-2507",
                "temperature": 0.0,
                "timeout_seconds": 10
            }
        ),
        encoding="utf-8",
    )

    config = load_model_config(path)

    assert config.model_id == "Qwen/Qwen3-4B-Instruct-2507"
    assert config.temperature == 0.0
    assert config.timeout_seconds == 10


def test_invalid_config_is_rejected() -> None:
    with pytest.raises(ValueError, match="model_id"):
        ModelConfig(model_id=" ").validate()
