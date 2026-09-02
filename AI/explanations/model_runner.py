"""Configurable OpenAI-compatible model runner for AquaBlend report rewrites.

Normal CI does not require a live model. Tests inject a mocked request function.
The output from this module is intentionally marked as unvalidated until the
Task 25 factual and safety validator accepts it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import socket
import time
from typing import Any, Callable, Mapping
from urllib import error, request

try:
    from .prompts import (
        PROMPT_VERSION,
        REWRITE_FAILURE_SENTINEL,
        build_rewrite_messages,
    )
except ImportError:  # Allows direct execution during simple local testing.
    from prompts import (  # type: ignore
        PROMPT_VERSION,
        REWRITE_FAILURE_SENTINEL,
        build_rewrite_messages,
    )

JsonMapping = Mapping[str, Any]
RequestFunction = Callable[[str, Mapping[str, str], JsonMapping, float], JsonMapping]


@dataclass(frozen=True)
class ModelConfig:
    """Runtime configuration for an OpenAI-compatible chat endpoint."""

    model_id: str
    base_url: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 1200
    timeout_seconds: float = 30.0
    seed: int | None = 0

    def validate(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id must not be empty")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0 and 2")
        if not 0.0 < self.top_p <= 1.0:
            raise ValueError("top_p must be greater than 0 and at most 1")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class RewriteResult:
    """Result returned by the model runner.

    report_mode is LLM_UNVALIDATED after a successful model call. Task 25 must
    validate it before any downstream component may label it LLM_VALIDATED.
    """

    report_text: str
    report_mode: str
    model_id: str
    prompt_version: str
    runtime_ms: int
    fallback_used: bool
    failure_type: str | None = None
    failure_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_model_config(path: str | Path) -> ModelConfig:
    """Load and validate a model configuration JSON file."""
    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Model config not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in model config: {config_path}") from exc

    if not isinstance(raw, dict):
        raise ValueError("Model config JSON must contain an object")

    try:
        config = ModelConfig(**raw)
    except TypeError as exc:
        raise ValueError(f"Unsupported or missing model config field: {exc}") from exc

    config.validate()
    return config


def _default_request(
    url: str,
    headers: Mapping[str, str],
    payload: JsonMapping,
    timeout_seconds: float,
) -> JsonMapping:
    """POST JSON to an OpenAI-compatible endpoint using the Python stdlib."""
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=dict(headers), method="POST")

    with request.urlopen(req, timeout=timeout_seconds) as response:
        response_body = response.read().decode("utf-8")

    parsed = json.loads(response_body)
    if not isinstance(parsed, dict):
        raise ValueError("Model endpoint returned a non-object JSON response")
    return parsed


def _extract_content(response_json: JsonMapping) -> str:
    """Extract text from an OpenAI-compatible chat-completions response."""
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Model response is missing choices[0]")

    first = choices[0]
    if not isinstance(first, Mapping):
        raise ValueError("Model response choices[0] is invalid")

    message = first.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("Model response is missing choices[0].message")

    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("Model response content is not a string")

    return content.strip()


def _fallback(
    deterministic_report: str,
    config: ModelConfig,
    started_at: float,
    failure_type: str,
    failure_message: str,
) -> RewriteResult:
    return RewriteResult(
        report_text=deterministic_report,
        report_mode="TEMPLATE_FALLBACK",
        model_id=config.model_id,
        prompt_version=PROMPT_VERSION,
        runtime_ms=round((time.perf_counter() - started_at) * 1000),
        fallback_used=True,
        failure_type=failure_type,
        failure_message=failure_message,
    )


def rewrite_report(
    deterministic_report: str,
    config: ModelConfig,
    request_fn: RequestFunction | None = None,
) -> RewriteResult:
    """Rewrite a deterministic report or safely return the original report.

    The successful LLM text is not yet trusted. It must pass Task 25 validation
    before display. Timeouts, endpoint failures, malformed responses, empty
    output, and an explicit model failure sentinel all trigger fallback.
    """
    config.validate()
    messages = build_rewrite_messages(deterministic_report)
    original_report = deterministic_report.strip()
    started_at = time.perf_counter()

    endpoint = f"{config.base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    payload: dict[str, Any] = {
        "model": config.model_id,
        "messages": messages,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "max_tokens": config.max_tokens,
        "stream": False,
    }
    if config.seed is not None:
        payload["seed"] = config.seed

    sender = request_fn or _default_request

    try:
        response_json = sender(
            endpoint,
            headers,
            payload,
            config.timeout_seconds,
        )
        output_text = _extract_content(response_json)
    except (TimeoutError, socket.timeout) as exc:
        # Found from a genuine live model run (Task 62), not a synthetic test: on
        # Python < 3.10, urllib raises socket.timeout on a real network timeout,
        # which is a SEPARATE class from the builtin TimeoutError (they were only
        # unified as the same class starting in Python 3.10). Catching TimeoutError
        # alone let a genuine timeout fall through to the generic Exception handler
        # below and be mis-labelled MODEL_ERROR instead of TIMEOUT - reproduced
        # directly: a real call that ran out of time on Python 3.9 returned
        # failure_type="MODEL_ERROR" with runtime_ms almost exactly equal to
        # timeout_seconds, the signature of a timeout, not a genuine model error.
        # Catching both classes explicitly is correct and safe on every Python
        # version: on 3.10+, socket.timeout is already an alias for TimeoutError,
        # so this only ever catches the same thing twice, never something new.
        return _fallback(
            original_report,
            config,
            started_at,
            "TIMEOUT",
            str(exc) or "Model request timed out",
        )
    except error.URLError as exc:
        return _fallback(
            original_report,
            config,
            started_at,
            "MODEL_UNAVAILABLE",
            str(exc.reason),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return _fallback(
            original_report,
            config,
            started_at,
            "INVALID_RESPONSE",
            str(exc),
        )
    except Exception as exc:  # Safe boundary around third-party runtimes.
        return _fallback(
            original_report,
            config,
            started_at,
            "MODEL_ERROR",
            str(exc),
        )

    if not output_text:
        return _fallback(
            original_report,
            config,
            started_at,
            "EMPTY_OUTPUT",
            "Model returned empty output",
        )

    if output_text == REWRITE_FAILURE_SENTINEL:
        return _fallback(
            original_report,
            config,
            started_at,
            "MODEL_DECLINED",
            "Model reported that it could not perform a faithful rewrite",
        )

    return RewriteResult(
        report_text=output_text,
        report_mode="LLM_UNVALIDATED",
        model_id=config.model_id,
        prompt_version=PROMPT_VERSION,
        runtime_ms=round((time.perf_counter() - started_at) * 1000),
        fallback_used=False,
    )
