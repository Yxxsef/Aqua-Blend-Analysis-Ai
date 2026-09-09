"""
AquaBlend | Analysis & AI | Sprint 3 | Task 73
AI run metadata and traceability.

This module provides a small, machine-readable metadata structure for an
AquaBlend AI execution.

It does not generate scenario_id or run_id. Those identifiers are owned by
the upstream orchestration/backend layer and are recorded here only when
supplied.

The module is intentionally independent of the AI orchestration entry point
so it can be connected to the final integration pipeline without changing
existing Results, LLM runner, validator, or App response contracts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AIRunMetadata:
    """Traceability information for one AI execution."""

    scenario_id: str | None = None
    run_id: str | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    runtime_ms: int | None = None
    validator_result: str | None = None
    fallback_used: bool | None = None
    fallback_reason: str | None = None
    confidence: str | None = None
    module_version: str = "task-73-v1"

    def to_dict(self) -> dict[str, Any]:
        """Return metadata as a machine-readable dictionary."""
        return asdict(self)


def build_ai_run_metadata(
    *,
    scenario_id: str | None = None,
    run_id: str | None = None,
    model_id: str | None = None,
    prompt_version: str | None = None,
    runtime_ms: int | None = None,
    validator_result: str | None = None,
    fallback_used: bool | None = None,
    fallback_reason: str | None = None,
    confidence: str | None = None,
    module_version: str = "task-73-v1",
) -> AIRunMetadata:
    """Build traceability metadata from values supplied by the AI pipeline.

    This function does not invent missing identifiers or execution facts.
    Optional values remain None when the relevant upstream component did
    not supply them.
    """
    return AIRunMetadata(
        scenario_id=scenario_id,
        run_id=run_id,
        model_id=model_id,
        prompt_version=prompt_version,
        runtime_ms=runtime_ms,
        validator_result=validator_result,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        confidence=confidence,
        module_version=module_version,
    )
