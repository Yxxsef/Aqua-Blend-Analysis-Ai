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