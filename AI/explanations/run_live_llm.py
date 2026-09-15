"""
run_live_llm.py

AquaBlend | Analysis & AI | Sprint 3 | Task 62
Runs the deterministic report from Task 23 through the real, live Task 24
model runner (a genuine local Ollama endpoint, not a mock or hand-built
stand-in), then validates the result through Task 25's llm_validator.py.

Two calls are made on purpose:
  1. A normal call against the real running model - the accepted-rewrite case.
  2. A call against a deliberately wrong port - the fallback case, demonstrating
     TEMPLATE_FALLBACK triggers correctly when the model is unavailable.

This script is meant to be run locally, once model_config.json points at a
real running Ollama endpoint (see LLM_Runner_README.md and the Task 62 setup
notes). It is NOT run in CI and does not belong in any automated test suite -
it makes a real network call to localhost.

Usage:
    python run_live_llm.py
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from json_explainer import generate_explanation
from model_runner import ModelConfig, load_model_config, rewrite_report
from llm_validator import validate_llm_output
from test_json_explainer import REFERENCE_JSON

# Each run gets its own timestamped subfolder so repeat runs never
# overwrite an earlier one - every real call is separate evidence.
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUTPUT_DIR = Path("live_run_output") / RUN_ID


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Run ID: {RUN_ID}")
    print(f"Output folder: {OUTPUT_DIR}")
    print()

    # ---------------------------------------------------------------
    # Step 1: the deterministic report - real Task 23 code, real fixture.
    # ---------------------------------------------------------------
    print("=" * 70)
    print("STEP 1: Generating the deterministic report (Task 23)")
    print("=" * 70)
    deterministic_report = generate_explanation(REFERENCE_JSON)
    (OUTPUT_DIR / "deterministic_report.txt").write_text(deterministic_report)
    print(f"Generated {len(deterministic_report)} characters.")
    print(f"Saved to {OUTPUT_DIR / 'deterministic_report.txt'}")
    print()

    # ---------------------------------------------------------------
    # Step 2: load the real local model config.
    # ---------------------------------------------------------------
    config = load_model_config("model_config.json")
    print(f"Loaded config: model_id={config.model_id}, base_url={config.base_url}")
    print()

    # ---------------------------------------------------------------
    # Step 3: the real, live call - the accepted-rewrite case.
    # ---------------------------------------------------------------
    print("=" * 70)
    print("STEP 2: Calling the real live model (accepted-rewrite case)")
    print("=" * 70)
    started = time.time()
    result = rewrite_report(deterministic_report, config)  # no request_fn override - real HTTP call
    wall_clock_ms = round((time.time() - started) * 1000)

    print(f"report_mode:    {result.report_mode}")
    print(f"model_id:       {result.model_id}")
    print(f"prompt_version: {result.prompt_version}")
    print(f"runtime_ms:     {result.runtime_ms}  (wall clock: {wall_clock_ms} ms)")
    print(f"fallback_used:  {result.fallback_used}")
    print(f"failure_type:   {result.failure_type}")
    print()
    print("--- Model output (first 500 chars) ---")
    print(result.report_text[:500])
    print()

    (OUTPUT_DIR / "live_rewrite_success.txt").write_text(result.report_text)
    (OUTPUT_DIR / "live_rewrite_success_metadata.json").write_text(
        json.dumps(result.to_dict(), indent=2)
    )

    # ---------------------------------------------------------------
    # Step 4: validate the real output - Task 25's validator, for real.
    # ---------------------------------------------------------------
    print("=" * 70)
    print("STEP 3: Validating the live output (Task 25)")
    print("=" * 70)
    validation = validate_llm_output(deterministic_report, result.report_text)
    print(f"critical_result: {validation.critical_result}")
    for f in validation.critical_failures:
        print(f"  FAIL: {f.rule} - {f.detail}")
    for w in validation.warnings:
        print(f"  WARN: {w.rule} - {w.detail}")
    print()

    (OUTPUT_DIR / "live_rewrite_validation.json").write_text(
        json.dumps(validation.to_dict(), indent=2)
    )

    # ---------------------------------------------------------------
    # Step 5: force a fallback - point at a port nothing is listening on.
    # ---------------------------------------------------------------
    print("=" * 70)
    print("STEP 4: Forcing a fallback (model unavailable case)")
    print("=" * 70)
    broken_config = ModelConfig(
        model_id=config.model_id,
        base_url="http://localhost:11499/v1",  # deliberately wrong port
        api_key=config.api_key,
        temperature=config.temperature,
        top_p=config.top_p,
        max_tokens=config.max_tokens,
        timeout_seconds=5.0,
        seed=config.seed,
    )
    fallback_result = rewrite_report(deterministic_report, broken_config)

    print(f"report_mode:   {fallback_result.report_mode}")
    print(f"fallback_used: {fallback_result.fallback_used}")
    print(f"failure_type:  {fallback_result.failure_type}")
    print(f"failure_msg:   {fallback_result.failure_message}")
    print()

    (OUTPUT_DIR / "live_rewrite_fallback_metadata.json").write_text(
        json.dumps(fallback_result.to_dict(), indent=2)
    )

    # Sanity check: fallback text must equal the deterministic report exactly.
    assert fallback_result.report_text == deterministic_report.strip(), (
        "Fallback text should be the deterministic report, unchanged."
    )
    print("Confirmed: fallback text matches the deterministic report exactly.")
    print()

    print("=" * 70)
    print("DONE. All output saved to:", OUTPUT_DIR.resolve())
    print("=" * 70)


if __name__ == "__main__":
    main()
