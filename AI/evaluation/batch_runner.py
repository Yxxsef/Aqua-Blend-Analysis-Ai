"""Batch runner for AquaBlend scenarios

Runs approved scenarios through the optimiser and the three coded baselines,
applies the same KPIs and pass/fail gate to all of them, and returns one
record per scenario.

The runner does not decide anything. Every value it reports comes from the
solver, a baseline, or the KPI calculator.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AI_ROOT = Path(__file__).resolve().parents[1]
for _folder in ("scenarios", "baselines", "results", "evaluation"):
    _path = str(AI_ROOT / _folder)
    if _path not in sys.path:
        sys.path.insert(0, _path)

from scenario_loader import load_scenario  # noqa: E402
from scenario_validator import validate_scenario  # noqa: E402
from baseline_runner import run_all_baselines  # noqa: E402
from results_validator import validate_results  # noqa: E402
from results_adapter import adapt_results  # noqa: E402
from confidence_flagger import determine_confidence  # noqa: E402
from kpi_gate import evaluate  # noqa: E402

MOCK = "mock"
MILP = "milp"

DEFAULT_FIXTURE = (
    AI_ROOT / "explanations" / "llm_reporting" / "fixtures" / "model_output_example.json"
)


class OptimiserError(Exception):
    """Raised when an optimiser result cannot be produced."""


def get_optimiser_result(
    scenario: dict[str, Any],
    mode: str = MOCK,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> dict[str, Any]:
    """Return a raw Results JSON for one scenario.

    Mock mode reads a stored fixture so the pipeline runs before MILP v1
    exists. MILP mode will call the solver. Both return the same shape, so
    nothing downstream changes when v1 lands.
    """
    if mode == MOCK:
        path = Path(fixture_path)
        if not path.is_file():
            raise OptimiserError(f"Mock fixture not found: {path}")
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)

    if mode == MILP:
        raise NotImplementedError(
            "MILP v1 is not available yet. Use mode='mock' until it is wired up."
        )

    raise OptimiserError(f"Unknown mode: {mode!r}. Use {MOCK!r} or {MILP!r}.")


def _gate_as_dict(gate: Any) -> dict[str, Any]:
    """Return the gate result as a plain dict, whichever form it takes."""
    if hasattr(gate, "as_dict"):
        return gate.as_dict()
    return dict(vars(gate))


def run_scenario(
    scenario_path: str | Path,
    mode: str = MOCK,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> dict[str, Any]:
    """Run one scenario through the optimiser, the baselines, and the gate.

    The optimiser and every baseline go through the same evaluate() call, so
    the numbers being compared were produced the same way.
    """
    started = time.perf_counter()

    scenario = load_scenario(scenario_path)
    validation = validate_scenario(scenario)

    baseline_output = run_all_baselines(scenario)

    raw_results = get_optimiser_result(scenario, mode, fixture_path)
    validate_results(raw_results)
    adapted = adapt_results(raw_results)

    confidence = determine_confidence(
        raw_results.get("data_flags", {}).get("sources", []),
        raw_results.get("sources", {}).get("selected", []),
    )

    evaluations: dict[str, Any] = {}

    report, gate = evaluate(raw_results)
    evaluations["optimiser"] = {"kpis": report.as_dict(), "gate": _gate_as_dict(gate)}

    for name, result in baseline_output["baselines"].items():
        report, gate = evaluate(result)
        evaluations[name] = {"kpis": report.as_dict(), "gate": _gate_as_dict(gate)}

    return {
        "scenario_path": str(scenario_path),
        "scenario_id": scenario.get("scenario_id"),
        "mode": mode,
        "scenario_validation": validation,
        "raw_optimiser_result": raw_results,
        "adapted_optimiser_result": adapted,
        "confidence": confidence,
        "baseline_output": baseline_output,
        "evaluations": evaluations,
        "runtime_seconds": round(time.perf_counter() - started, 3),
    }

def run_batch(
    path: str | Path,
    mode: str = MOCK,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> dict[str, Any]:
    """Run one scenario file, or every scenario in a folder.

    Files run in a fixed order so two runs of the same folder do the same
    work. A scenario that fails is recorded and the batch carries on — one
    bad file must not cost the other results.
    """
    target = Path(path)
    if target.is_dir():
        scenario_files = sorted(target.rglob("*.json"))
    else:
        scenario_files = [target]

    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for scenario_file in scenario_files:
        try:
            results.append(run_scenario(scenario_file, mode, fixture_path))
        except Exception as error:
            failures.append(
                {
                    "scenario_path": str(scenario_file),
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )

    return {
        "mode": mode,
        "scenario_count": len(scenario_files),
        "succeeded": len(results),
        "failed": len(failures),
        "results": results,
        "failures": failures,
        "runtime_seconds": round(time.perf_counter() - started, 3),
    }

def _run_folder(output_root: Path) -> Path:
    """Create a timestamped folder for this run, with raw and processed inside."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(output_root) / stamp
    (run_dir / "raw").mkdir(parents=True, exist_ok=True)
    (run_dir / "processed").mkdir(parents=True, exist_ok=True)
    return run_dir


def write_run(batch: dict[str, Any], output_root: str | Path = "runs") -> Path:
    """Write a batch result to disk and return the run folder.

    Raw solver output is written untouched to raw/. Anything calculated from
    it goes to processed/. A manifest records what ran so the run can be
    repeated.
    """
    run_dir = _run_folder(output_root)

    scenarios: list[dict[str, Any]] = []

    for result in batch["results"]:
        scenario_id = result["scenario_id"] or Path(result["scenario_path"]).stem

        raw_path = run_dir / "raw" / f"{scenario_id}.json"
        with raw_path.open("w", encoding="utf-8") as handle:
            json.dump(result["raw_optimiser_result"], handle, indent=2)

        processed = {
            key: value
            for key, value in result.items()
            if key != "raw_optimiser_result"
        }
        processed_path = run_dir / "processed" / f"{scenario_id}.json"
        with processed_path.open("w", encoding="utf-8") as handle:
            json.dump(processed, handle, indent=2, default=str)

        scenarios.append(
            {
                "scenario_id": scenario_id,
                "scenario_path": result["scenario_path"],
                "status": "ok",
                "runtime_seconds": result["runtime_seconds"],
                "raw_output": str(raw_path.relative_to(run_dir)),
                "processed_output": str(processed_path.relative_to(run_dir)),
            }
        )

    for failure in batch["failures"]:
        scenarios.append(
            {
                "scenario_id": None,
                "scenario_path": failure["scenario_path"],
                "status": "failed",
                "error_type": failure["error_type"],
                "error": failure["error"],
            }
        )

    manifest = {
        "run_id": run_dir.name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": batch["mode"],
        "mock_fixture": (
            str(DEFAULT_FIXTURE.relative_to(AI_ROOT.parent))
            if batch["mode"] == MOCK
            else None
        ),
        "mock_warning": (
            "Mock mode returns the same stored optimiser result for every "
            "scenario. Optimiser values are not scenario-specific."
            if batch["mode"] == MOCK
            else None
        ),
        "scenario_count": batch["scenario_count"],
        "succeeded": batch["succeeded"],
        "failed": batch["failed"],
        "runtime_seconds": batch["runtime_seconds"],
        "scenarios": scenarios,
    }

    with (run_dir / "run_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    return run_dir