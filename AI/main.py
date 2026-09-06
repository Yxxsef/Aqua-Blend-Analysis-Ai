"""AquaBlend Analysis & AI pipeline entry point."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Dict

from supabase import create_client


# Existing Task modules are intentionally usable as standalone scripts and
# therefore use sibling imports (for example, kpi_gate imports kpi_calculator).
# Add their directories when this file is run as ``python AI/main.py`` while
# leaving their independently executable import style unchanged.
_AI_DIR = Path(__file__).resolve().parent
for _module_dir in (
    _AI_DIR / "results",
    _AI_DIR / "evaluation",
    _AI_DIR / "explanations",
    _AI_DIR / "results" / "app_response",
):
    module_dir_text = str(_module_dir)
    if module_dir_text not in sys.path:
        sys.path.insert(0, module_dir_text)

from app_response_adapter import (
    SOLVER_STATUSES,
    build_app_response,
    validate_app_response,
    write_response_json,
)
from confidence_flagger import ConfidenceError, determine_confidence
from json_explainer import ExplainerInputError, generate_explanation
from kpi_gate import evaluate
from llm_validator import ValidatorInputError, validate_llm_output
from model_runner import ModelConfig, load_model_config, rewrite_report
from prompts import PROMPT_VERSION
from results_adapter import AdapterError, adapt_results
from results_validator import ValidationError, validate_results
from env import DB_URL, DB_KEY

def _client():
    """Create a Supabase client for the AquaBlend project."""
    return create_client(supabase_url = DB_URL, supabase_key = DB_KEY)


def load_milp_output() -> Dict:
    """Load a Results JSON file from the MILP output.
        This must be loaded from the Supabase
    """
    # Return the current final row in the milp_model_output table
    output = (
        _client()
        .table("milp_model_output")
        .select("*")
        .order("run_id", desc = True)
        .limit(1)
        .single()
        .execute()
        .data
    )
    # Returns a json dictionary
    return output


def _sha256_json(payload: Any) -> str:
    """Stable SHA-256 digest of a JSON payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def save_ai_output(
    response: Mapping[str, Any],
    milp_row: Mapping[str, Any],
    model_config: ModelConfig | None = None,
    latency_ms: float | None = None,
) -> Dict:
    """Insert one App response into milp_ai_output and return the inserted row.

    The row is keyed to the MILP output it was computed from, so the foreign
    keys (scenario_id, milp_output_id, origin_run_id) are read from that row
    rather than from the response, whose scenario_id is a display string.
    """
    validate_app_response(response)

    if not isinstance(milp_row, Mapping):
        raise ValueError(
            "An App response can only be saved against a MILP output row."
        )

    missing = [key for key in ("id", "scenario_id") if milp_row.get(key) is None]
    if missing:
        raise ValueError(
            "MILP output row is missing key(s) required by milp_ai_output: "
            + ", ".join(missing)
        )

    row: dict[str, Any] = {
        "milp_output_id": milp_row["id"],
        "scenario_id": milp_row["scenario_id"],
        "origin_run_id": milp_row.get("run_id"),
        "status": (
            "failed" if response["report_mode"] == "INVALID_INPUT" else "completed"
        ),
        "ai_contract_version": response["contract_version"],
        "milp_output_hash": _sha256_json(milp_row),
        "ai_output_hash": _sha256_json(response),
        "ai_input_json": dict(milp_row),
        "raw_ai_json": dict(response),
        "decision_explanation": response["display_explanation"],
        "warnings": list(response["warnings"]),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Only a model-backed run can describe which model produced the report.
    if model_config is not None:
        row["ai_model"] = model_config.model_id
        row["prompt_version"] = PROMPT_VERSION
    if latency_ms is not None:
        row["latency_ms"] = latency_ms

    return _client().table("milp_ai_output").insert(row).execute().data


def _invalid_input_response(results: Dict, reason: str) -> dict[str, Any]:
    """Build the standard App response for unprocessable input."""
    scenario_id = (
        results.get("scenario_id")
        if isinstance(results, Mapping) and isinstance(results.get("scenario_id"), str)
        else None
    )
    return build_app_response(
        None,
        scenario_id=scenario_id,
        input_valid=False,
        upstream_warnings=[reason],
    )


def run_pipeline(
    results: Dict,
    model_config: ModelConfig | None = None,
    comparison: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and present one MILP result without mutating its input."""
    try:
        validate_results(results)
        adapted_results = adapt_results(results)
    except (ValidationError, AdapterError) as exc:
        return _invalid_input_response(results, f"Results validation failed: {exc}")

    status = results["status"]
    if status not in SOLVER_STATUSES:
        return _invalid_input_response(
            results,
            f"Solver status {status!r} is not supported by the App response contract.",
        )

    kpi_report, gate = evaluate(results)
    warnings: list[str] = []

    try:
        confidence = determine_confidence(
            results["data_flags"]["sources"],
            results["sources"]["selected"],
        )
        confidence_flag = confidence["confidence"]
    except ConfidenceError as exc:
        confidence_flag = "UNKNOWN"
        warnings.append(f"Confidence could not be determined: {exc}")

    try:
        deterministic_explanation = generate_explanation(adapted_results)
    except ExplainerInputError as exc:
        return _invalid_input_response(results, f"Explanation input failed: {exc}")

    llm_explanation: str | None = None
    llm_validated = False
    if status == "OPTIMAL" and model_config is not None:
        rewrite = rewrite_report(deterministic_explanation, model_config)
        if rewrite.fallback_used:
            warnings.append(
                "Model rewrite fell back to the deterministic explanation: "
                f"{rewrite.failure_type}: {rewrite.failure_message}"
            )
        else:
            try:
                llm_validation = validate_llm_output(
                    deterministic_explanation, rewrite.report_text
                )
            except ValidatorInputError as exc:
                warnings.append(f"LLM output could not be validated: {exc}")
            else:
                warnings.extend(
                    f"LLM validation warning ({warning.rule}): {warning.detail}"
                    for warning in llm_validation.warnings
                )
                if llm_validation.critical_result == "PASS":
                    llm_explanation = rewrite.report_text
                    llm_validated = True
                else:
                    failures = ", ".join(
                        failure.rule for failure in llm_validation.critical_failures
                    )
                    warnings.append(
                        "LLM rewrite was rejected by validation"
                        + (f": {failures}" if failures else ".")
                    )

    return build_app_response(
        results,
        kpis=kpi_report.as_dict(),
        gate_result=gate.overall_status,
        confidence_flag=confidence_flag,
        comparison=comparison,
        llm_explanation=llm_explanation,
        llm_validated=llm_validated,
        fallback_explanation=deterministic_explanation,
        upstream_warnings=warnings,
    )


def run_from_file(
    model_config: ModelConfig | None = None,
    comparison: Mapping[str, Any] | None = None,
    push: bool = False,
) -> dict[str, Any]:
    """Load the latest MILP output from Supabase and run the pipeline."""
    results = load_milp_output()

    started_at = time.perf_counter()
    response = run_pipeline(results, model_config=model_config, comparison=comparison)
    latency_ms = (time.perf_counter() - started_at) * 1000

    if push:
        save_ai_output(
            response,
            results,
            model_config=model_config,
            latency_ms=latency_ms,
        )

    return response


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the AquaBlend Analysis & AI pipeline."
    )

    parser.add_argument(
        "--model-config",
        help="Path to an OpenAI-compatible model configuration JSON file.",
    )
    parser.add_argument(
        "--output",
        help="Write the App response JSON to this path instead of stdout.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Insert the App response into the milp_ai_output table.",
    )

    args = parser.parse_args()

    model_config = load_model_config(args.model_config) if args.model_config else None
    response = run_from_file(model_config=model_config, push=args.push)

    if args.output:
        write_response_json(response, args.output)
    else:
        print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
