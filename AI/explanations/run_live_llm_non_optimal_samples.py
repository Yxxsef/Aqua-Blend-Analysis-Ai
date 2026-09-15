"""
run_live_llm_non_optimal_samples.py

AquaBlend | Analysis & AI | Sprint 3 | Task 62
Runs the two remaining genuine Task 23 deterministic samples - Sample 2
(INFEASIBLE) and Sample 3 (TIME_LIMIT), both from the actual merged
sample_explanations_sprint2.txt, not hand-written - through the real,
live Task 24 model runner, then validates each result through Task 25's
llm_validator.py.

Companion to run_live_llm.py, which covers Sample 1 (OPTIMAL). Together
the two scripts cover every sample type Task 23's deliverables actually
produced, closing the "run existing deterministic explanation samples"
checklist item in the plural sense it's written in.

No fallback demonstration here - that's already covered by run_live_llm.py
and does not need repeating for every sample type.

Usage:
    python run_live_llm_non_optimal_samples.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from model_runner import load_model_config, rewrite_report
from llm_validator import validate_llm_output

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUTPUT_DIR = Path("live_run_output") / f"{RUN_ID}_non_optimal_samples"

# Verbatim from AI/explanations/sample_explanations_sprint2.txt, Sample 2 -
# Task 23's own genuine output, not hand-written.
SAMPLE_2_INFEASIBLE = """## Scenario & Solver Status

Scenario: scenario_2026_07_17_001. Solver status: INFEASIBLE. Solved at: 2026-07-17T10:32:00Z.

## Result Availability

Solver status is INFEASIBLE. This result is not confirmed as usable for a final recommendation.

## Prototype Disclaimer

AquaBlend is a public-data decision-support proof-of-concept. This report does not replace qualified operators, engineers, regulators, or health authorities."""

# Verbatim from the same file, Sample 3.
SAMPLE_3_TIME_LIMIT = """## Scenario & Solver Status

Scenario: scenario_2026_07_17_001. Solver status: TIME_LIMIT. Solved at: 2026-07-17T10:32:00Z.

## Result Availability

Solver status is TIME_LIMIT. This result is not confirmed as usable for a final recommendation.

## Prototype Disclaimer

AquaBlend is a public-data decision-support proof-of-concept. This report does not replace qualified operators, engineers, regulators, or health authorities."""


def run_one(name: str, deterministic_report: str, config) -> None:
    sample_dir = OUTPUT_DIR / name
    sample_dir.mkdir(parents=True, exist_ok=True)

    (sample_dir / "deterministic_report.txt").write_text(deterministic_report)

    print("=" * 70)
    print(f"Running: {name}")
    print("=" * 70)

    result = rewrite_report(deterministic_report, config)  # real HTTP call, no mocking

    print(f"report_mode:    {result.report_mode}")
    print(f"model_id:       {result.model_id}")
    print(f"prompt_version: {result.prompt_version}")
    print(f"runtime_ms:     {result.runtime_ms}")
    print(f"fallback_used:  {result.fallback_used}")
    print(f"failure_type:   {result.failure_type}")
    print()
    print("--- Model output ---")
    print(result.report_text)
    print()

    (sample_dir / "live_rewrite.txt").write_text(result.report_text)
    (sample_dir / "live_rewrite_metadata.json").write_text(
        json.dumps(result.to_dict(), indent=2)
    )

    validation = validate_llm_output(deterministic_report, result.report_text)
    print(f"critical_result: {validation.critical_result}")
    for f in validation.critical_failures:
        print(f"  FAIL: {f.rule} - {f.detail}")
    for w in validation.warnings:
        print(f"  WARN: {w.rule} - {w.detail}")
    print()

    (sample_dir / "live_rewrite_validation.json").write_text(
        json.dumps(validation.to_dict(), indent=2)
    )


def main() -> None:
    config = load_model_config("model_config.json")
    print(f"Run ID: {RUN_ID}")
    print(f"Output folder: {OUTPUT_DIR}")
    print(f"Model config: model_id={config.model_id}, base_url={config.base_url}")
    print()

    run_one("sample_2_infeasible", SAMPLE_2_INFEASIBLE, config)
    run_one("sample_3_time_limit", SAMPLE_3_TIME_LIMIT, config)

    print("=" * 70)
    print("DONE. All output saved to:", OUTPUT_DIR.resolve())
    print("=" * 70)


if __name__ == "__main__":
    main()
