"""AquaBlend Analysis & AI pipeline entry point."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Dict


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
    _AI_DIR / "integration",
):
    module_dir_text = str(_module_dir)
    if module_dir_text not in sys.path:
        sys.path.insert(0, module_dir_text)

from app_response_adapter import (
    SOLVER_STATUSES,
    build_app_response,
    write_response_json,
)
from confidence_flagger import ConfidenceError, determine_confidence
from json_explainer import (
    ExplainerInputError,
    generate_executive_summary,
    generate_explanation,
)
from kpi_gate import evaluate
from llm_validator import ValidatorInputError, validate_llm_output
from model_runner import ModelConfig, load_model_config, rewrite_report
from prompts import PROMPT_VERSION
from results_adapter import AdapterError, adapt_results
from results_validator import ValidationError, validate_results
from visualization import build_visualization_data
from supabase_repository import (
    SupabaseError,
    extract_canonical_output,
    load_input_provenance,
    load_milp_output,
    save_ai_output as _supabase_save_ai_output,
)

# Prefix used when a push fails, so main() can set a non-zero exit status
# without re-inspecting the exception.
PUSH_FAILURE_PREFIX = "Supabase write failed: "


def load_results(path: str | Path) -> Any:
    """Load a Results JSON file from disk."""
    path = Path(path)

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _invalid_input_response(
    results: Dict, reason: str, extra_warnings: list[str] | None = None
) -> dict[str, Any]:
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
        upstream_warnings=[reason, *(extra_warnings or [])],
    )


def run_pipeline(
    results: Dict,
    model_config: ModelConfig | None = None,
    comparison: Mapping[str, Any] | None = None,
    extra_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Validate and present one MILP result without mutating its input.

    ``extra_warnings`` carries context gathered before this call (for
    example, a Supabase provenance lookup that could not be completed) so it
    is deduplicated and surfaced alongside every other warning in one place.
    """
    try:
        validate_results(results)
        adapted_results = adapt_results(results)
    except (ValidationError, AdapterError) as exc:
        return _invalid_input_response(
            results, f"Results validation failed: {exc}", extra_warnings
        )

    status = results["status"]
    if status not in SOLVER_STATUSES:
        return _invalid_input_response(
            results,
            f"Solver status {status!r} is not supported by the App response contract.",
            extra_warnings,
        )

    kpi_report, gate = evaluate(results)
    warnings: list[str] = list(extra_warnings or [])

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
        detailed_explanation = generate_explanation(adapted_results)
        deterministic_summary = generate_executive_summary(adapted_results)
    except ExplainerInputError as exc:
        return _invalid_input_response(
            results, f"Explanation input failed: {exc}", extra_warnings
        )

    llm_summary: str | None = None
    llm_summary_validated = False
    # Only the short executive summary is ever sent to the LLM. The full
    # deterministic report above (detailed_explanation) is never rewritten.
    if status == "OPTIMAL" and model_config is not None:
        rewrite = rewrite_report(deterministic_summary, model_config)
        if rewrite.fallback_used:
            warnings.append(
                "Model rewrite fell back to the deterministic summary: "
                f"{rewrite.failure_type}: {rewrite.failure_message}"
            )
        else:
            try:
                llm_validation = validate_llm_output(
                    deterministic_summary, rewrite.report_text
                )
            except ValidatorInputError as exc:
                warnings.append(f"LLM output could not be validated: {exc}")
            else:
                warnings.extend(
                    f"LLM validation warning ({warning.rule}): {warning.detail}"
                    for warning in llm_validation.warnings
                )
                if llm_validation.critical_result == "PASS":
                    llm_summary = rewrite.report_text
                    llm_summary_validated = True
                else:
                    failures = ", ".join(
                        failure.rule for failure in llm_validation.critical_failures
                    )
                    warnings.append(
                        "LLM rewrite was rejected by validation"
                        + (f": {failures}" if failures else ".")
                    )

    visualization_data = (
        build_visualization_data(results) if status == "OPTIMAL" else None
    )

    return build_app_response(
        results,
        kpis=kpi_report.as_dict(),
        gate_result=gate.overall_status,
        confidence_flag=confidence_flag,
        comparison=comparison,
        llm_summary=llm_summary,
        llm_summary_validated=llm_summary_validated,
        deterministic_summary=deterministic_summary,
        detailed_explanation=detailed_explanation,
        visualization_data=visualization_data,
        upstream_warnings=warnings,
    )


def run_from_source(
    path: str | Path | None = None,
    model_config: ModelConfig | None = None,
    comparison: Mapping[str, Any] | None = None,
    push: bool = False,
    run_id: int | None = None,
    scenario_db_id: int | None = None,
    scenario: str | None = None,
) -> dict[str, Any]:
    """Run the pipeline over one MILP result, from a file or from Supabase.

    ``path`` reads a Results JSON file; otherwise the row is selected from
    Supabase. A database that cannot be read is reported through the App
    response contract as unprocessable input. A failed write is recorded as a
    warning on an otherwise complete response, so a computed result is never
    lost just because it could not be stored.

    When reading from Supabase, ``raw_output_json`` is used as the canonical
    analysis payload when it is complete; otherwise a documented, best-effort
    normalization of the flat ``milp_model_output`` columns is used instead
    (see ``supabase_repository.normalize_output_columns``). The linked
    ``milp_model_input`` row is also fetched for provenance context; if either
    step is incomplete, a warning is added rather than failing the analysis.
    """
    output_row: Dict[str, Any] | None = None
    extra_warnings: list[str] = []

    try:
        if path is not None:
            results = load_results(path)
        else:
            output_row = load_milp_output(
                run_id=run_id,
                scenario_db_id=scenario_db_id,
                scenario=scenario,
            )
            results, canonical_warnings = extract_canonical_output(output_row)
            extra_warnings.extend(canonical_warnings)
            _, provenance_warnings = load_input_provenance(output_row)
            extra_warnings.extend(provenance_warnings)
    except SupabaseError as exc:
        return _invalid_input_response(None, f"Supabase read failed: {exc}")
    except (OSError, json.JSONDecodeError) as exc:
        return _invalid_input_response(None, f"Results file could not be read: {exc}")

    started_at = datetime.now(timezone.utc)
    started_counter = time.perf_counter()
    response = run_pipeline(
        results,
        model_config=model_config,
        comparison=comparison,
        extra_warnings=extra_warnings,
    )
    latency_ms = (time.perf_counter() - started_counter) * 1000

    if push:
        try:
            _supabase_save_ai_output(
                response,
                output_row if output_row is not None else results,
                model_config=model_config,
                prompt_version=PROMPT_VERSION if model_config is not None else None,
                latency_ms=latency_ms,
                started_at=started_at,
            )
        except SupabaseError as exc:
            response["warnings"].append(f"{PUSH_FAILURE_PREFIX}{exc}")

    return response


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the AquaBlend Analysis & AI pipeline."
    )

    # Input is either a file or one Supabase row; the selectors below name the
    # milp_model_output columns they filter, so they cannot be confused with
    # the response's own scenario_id, which is a display string.
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "results_json",
        nargs="?",
        help="Path to a Results JSON file. Omit to read from Supabase.",
    )
    source.add_argument(
        "--run-id",
        type=int,
        help="Select the newest row with this origin_run_id.",
    )
    source.add_argument(
        "--scenario-db-id",
        type=int,
        help="Select the newest row with this scenario_db_id.",
    )
    source.add_argument(
        "--scenario",
        help="Select the newest row with this scenario_id, e.g. SCN-008.",
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

    # A file fixture carries no id or scenario_db_id, so it can never key a
    # milp_ai_output row. Reject the combination here rather than at the insert.
    if args.push and args.results_json:
        parser.error("--push needs a Supabase row; it cannot be used with a file.")

    model_config = load_model_config(args.model_config) if args.model_config else None
    response = run_from_source(
        args.results_json,
        model_config=model_config,
        push=args.push,
        run_id=args.run_id,
        scenario_db_id=args.scenario_db_id,
        scenario=args.scenario,
    )

    if args.output:
        write_response_json(response, args.output)
    else:
        print(json.dumps(response, indent=2))

    # The response is emitted either way; a failed write still exits non-zero
    # so a caller is never told the row was stored when it was not.
    push_failures = [
        warning
        for warning in response["warnings"]
        if warning.startswith(PUSH_FAILURE_PREFIX)
    ]
    if push_failures:
        print(push_failures[0], file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
