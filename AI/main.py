"""AquaBlend Analysis & AI pipeline entry point."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


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

from app_response_adapter import SOLVER_STATUSES, build_app_response, write_response_json
from confidence_flagger import ConfidenceError, determine_confidence
from json_explainer import ExplainerInputError, generate_explanation
from kpi_gate import evaluate
from llm_validator import ValidatorInputError, validate_llm_output
from model_runner import ModelConfig, load_model_config, rewrite_report
from results_adapter import AdapterError, adapt_results
from results_validator import ValidationError, validate_results


def load_results(path: str | Path) -> Any:
    """Load a Results JSON file."""
    path = Path(path)

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _invalid_input_response(results: Any, reason: str) -> dict[str, Any]:
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
    results: Any,
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
    path: str | Path,
    model_config: ModelConfig | None = None,
    comparison: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load a Results JSON file and run the pipeline."""
    results = load_results(path)
    return run_pipeline(results, model_config=model_config, comparison=comparison)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the AquaBlend Analysis & AI pipeline."
    )

    parser.add_argument(
        "results_json",
        help="Path to a MILP or mock Results JSON file.",
    )
    parser.add_argument(
        "--model-config",
        help="Path to an OpenAI-compatible model configuration JSON file.",
    )
    parser.add_argument(
        "--output",
        help="Write the App response JSON to this path instead of stdout.",
    )

    args = parser.parse_args()

    model_config = load_model_config(args.model_config) if args.model_config else None
    response = run_from_file(args.results_json, model_config=model_config)

    if args.output:
        write_response_json(response, args.output)
    else:
        print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
