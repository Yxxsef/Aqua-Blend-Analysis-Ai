"""AquaBlend Analysis & AI pipeline entry point."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Dict

import httpx
from postgrest.exceptions import APIError
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

# Prefix used when a push fails, so main() can set a non-zero exit status
# without re-inspecting the exception.
PUSH_FAILURE_PREFIX = "Supabase write failed: "


class SupabaseError(RuntimeError):
    """A Supabase read or write could not be completed."""


def _client():
    """Create a Supabase client for the AquaBlend project."""
    return create_client(supabase_url = DB_URL, supabase_key = DB_KEY)


def load_results(path: str | Path) -> Any:
    """Load a Results JSON file from disk."""
    path = Path(path)

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_milp_output(
    run_id: int | None = None,
    scenario_db_id: int | None = None,
    scenario: str | None = None,
) -> Dict:
    """Load one row from the MILP output table in Supabase.

    With no selector the newest row by ``created_at`` is returned. Each
    selector names the real column it filters: ``origin_run_id``,
    ``scenario_db_id`` (both nullable integers) and ``scenario_id`` (the
    varchar display string, for example "SCN-008").

    Raises:
        SupabaseError: the table could not be reached, or no row matched.
    """
    # limit(1) rather than single(): single() raises on an empty result, which
    # is a normal state to report rather than a transport failure.
    try:
        query = _client().table("milp_model_output").select("*")

        if run_id is not None:
            query = query.eq("origin_run_id", run_id)
        if scenario_db_id is not None:
            query = query.eq("scenario_db_id", scenario_db_id)
        if scenario is not None:
            query = query.eq("scenario_id", scenario)

        rows = (
            query
            .order("created_at", desc = True)
            .limit(1)
            .execute()
            .data
        )
    except APIError as exc:
        raise SupabaseError(f"milp_model_output query rejected: {exc}") from exc
    except httpx.HTTPError as exc:
        raise SupabaseError(f"Could not reach Supabase: {exc}") from exc
    except Exception as exc:  # Safe boundary around the client runtime.
        raise SupabaseError(f"Unexpected Supabase failure: {exc}") from exc

    if not rows:
        selectors = {
            "origin_run_id": run_id,
            "scenario_db_id": scenario_db_id,
            "scenario_id": scenario,
        }
        asked = ", ".join(
            f"{name}={value!r}"
            for name, value in selectors.items()
            if value is not None
        )
        raise SupabaseError(
            f"No milp_model_output row matched {asked}."
            if asked
            else "milp_model_output contains no rows to analyse."
        )

    # Returns a json dictionary
    return rows[0]


def _sha256_json(payload: Any) -> str:
    """Stable SHA-256 digest of a JSON payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def save_ai_output(
    response: Mapping[str, Any],
    milp_row: Mapping[str, Any],
    model_config: ModelConfig | None = None,
    latency_ms: float | None = None,
    started_at: datetime | None = None,
) -> Dict:
    """Insert one App response into milp_ai_output and return the inserted row.

    The row is keyed to the MILP output it was computed from, so the foreign
    keys are read from that row rather than from the response. The MILP row
    carries two scenario identifiers: ``scenario_id`` is the display string
    ("SCN-005") and ``scenario_db_id`` is the integer that milp_ai_output's
    foreign key into Scenarios("Id") requires.

    Raises:
        SupabaseError: the MILP row cannot key a milp_ai_output row, or the
            insert failed.
    """
    validate_app_response(response)

    if not isinstance(milp_row, Mapping):
        raise SupabaseError(
            "An App response can only be saved against a MILP output row."
        )

    missing = [key for key in ("id", "scenario_db_id") if milp_row.get(key) is None]
    if missing:
        raise SupabaseError(
            "MILP output row is missing key(s) required by milp_ai_output: "
            + ", ".join(missing)
        )

    failed = response["report_mode"] == "INVALID_INPUT"

    row: dict[str, Any] = {
        "milp_output_id": milp_row["id"],
        "scenario_id": milp_row["scenario_db_id"],
        "origin_run_id": milp_row.get("origin_run_id"),
        "status": "failed" if failed else "completed",
        "ai_contract_version": response["contract_version"],
        # MILP publishes its own digest; both tables are indexed on their
        # hashes so an AI row can be matched back to the output it analysed.
        # Fall back to our own only when the column is null.
        "milp_output_hash": milp_row.get("output_hash") or _sha256_json(milp_row),
        "ai_output_hash": _sha256_json(response),
        "ai_input_json": dict(milp_row),
        "raw_ai_json": dict(response),
        "decision_explanation": response["display_explanation"],
        "warnings": list(response["warnings"]),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    if started_at is not None:
        row["started_at"] = started_at.isoformat()

    # A failure belongs in the dedicated columns, not only in the warnings
    # payload, so it can be queried without unpacking jsonb.
    if failed:
        row["error_code"] = response["report_mode"]
        row["error_message"] = next(iter(response["warnings"]), None)

    # Only a model-backed run can describe which model produced the report.
    if model_config is not None:
        row["ai_model"] = model_config.model_id
        row["prompt_version"] = PROMPT_VERSION
    if latency_ms is not None:
        row["latency_ms"] = latency_ms

    try:
        return _client().table("milp_ai_output").insert(row).execute().data
    except APIError as exc:
        raise SupabaseError(f"milp_ai_output insert rejected: {exc}") from exc
    except httpx.HTTPError as exc:
        raise SupabaseError(f"Could not reach Supabase: {exc}") from exc
    except Exception as exc:  # Safe boundary around the client runtime.
        raise SupabaseError(f"Unexpected Supabase failure: {exc}") from exc


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
    """
    try:
        if path is not None:
            results = load_results(path)
        else:
            results = load_milp_output(
                run_id=run_id,
                scenario_db_id=scenario_db_id,
                scenario=scenario,
            )
    except SupabaseError as exc:
        return _invalid_input_response(None, f"Supabase read failed: {exc}")
    except (OSError, json.JSONDecodeError) as exc:
        return _invalid_input_response(None, f"Results file could not be read: {exc}")

    started_at = datetime.now(timezone.utc)
    started_counter = time.perf_counter()
    response = run_pipeline(results, model_config=model_config, comparison=comparison)
    latency_ms = (time.perf_counter() - started_counter) * 1000

    if push:
        try:
            save_ai_output(
                response,
                results,
                model_config=model_config,
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
