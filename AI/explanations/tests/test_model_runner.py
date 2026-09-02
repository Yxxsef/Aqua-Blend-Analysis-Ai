"""Mocked tests for the AquaBlend LLM model runner."""

from __future__ import annotations

import json
from pathlib import Path
import socket
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


def test_socket_timeout_also_returns_timeout_not_model_error() -> None:
    """Regression test for a real bug found on a genuine live run (Task 62),
    not a synthetic case: on Python < 3.10, urllib's real network timeout
    raises socket.timeout, a class SEPARATE from the builtin TimeoutError -
    they were only unified as the same class starting in Python 3.10.
    Catching TimeoutError alone let a genuine timeout on Python 3.9 fall
    through to the generic Exception handler and be mis-labelled
    MODEL_ERROR instead of TIMEOUT - reproduced directly against a real
    endpoint: a call that ran out of time returned failure_type=MODEL_ERROR
    with runtime_ms almost exactly equal to timeout_seconds, the signature
    of a timeout being mis-categorised, not a genuine model error.

    test_timeout_returns_template_fallback above only ever exercised the
    builtin TimeoutError directly, never socket.timeout - which is exactly
    why this bug was never caught by the existing suite; only a real
    network call was ever going to hit the class that mattered."""
    def socket_timeout_request(*_args, **_kwargs):
        raise socket.timeout("timed out")

    result = rewrite_report(
        TEMPLATE_REPORT,
        ModelConfig(model_id="test-model"),
        request_fn=socket_timeout_request,
    )

    assert result.report_text == TEMPLATE_REPORT.strip()
    assert result.report_mode == "TEMPLATE_FALLBACK"
    assert result.fallback_used is True
    assert result.failure_type == "TIMEOUT"
    assert result.failure_type != "MODEL_ERROR"


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


def test_frequency_penalty_is_omitted_from_payload_by_default() -> None:
    """frequency_penalty defaults to None and must not appear in the request
    at all unless explicitly set - it's not guaranteed to do anything for
    every model (see model_runner.py's comment on this field), so it should
    never be silently sent with a made-up default value."""
    captured: dict = {}

    def fake_request(url, headers, payload, timeout_seconds):
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "Some output."}}]}

    rewrite_report(
        TEMPLATE_REPORT,
        ModelConfig(model_id="test-model"),
        request_fn=fake_request,
    )

    assert "frequency_penalty" not in captured["payload"]


def test_frequency_penalty_is_included_when_set() -> None:
    """Regression test for a real live-run finding (Task 62): a genuine run
    fell into a repetition loop with no penalty configured at all.
    frequency_penalty is opt-in via model_config.json - when set, it must
    actually reach the request payload."""
    captured: dict = {}

    def fake_request(url, headers, payload, timeout_seconds):
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "Some output."}}]}

    rewrite_report(
        TEMPLATE_REPORT,
        ModelConfig(model_id="test-model", frequency_penalty=0.4),
        request_fn=fake_request,
    )

    assert captured["payload"]["frequency_penalty"] == 0.4


@pytest.mark.parametrize("bad_value", [-2.1, 2.1])
def test_out_of_range_frequency_penalty_is_rejected(bad_value: float) -> None:
    with pytest.raises(ValueError, match="frequency_penalty"):
        ModelConfig(model_id="test-model", frequency_penalty=bad_value).validate()

