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
INGEST = "ingest"

# Where the Optimisation team's real v1.0 output files are read from. The
# harness ingests those files; it does not run the solver, because the v1.0
# contract exposes no execution hooks. Confirmed with Yousef, 07/09/26.
DEFAULT_INGEST_DIR = Path(__file__).resolve().parent / "milp_outputs"

DEFAULT_FIXTURE = (
    AI_ROOT / "explanations" / "llm_reporting" / "fixtures" / "model_output_example.json"
)

V1_FIXTURE = AI_ROOT / "evaluation" / "fixtures" / "milp_v1_solved_example.json"

SCHEMA_TOY = "toy"
SCHEMA_V1 = "milp_v1"


def detect_schema(results: dict[str, Any]) -> str:
    """Return which Results JSON schema this payload uses.

    The harness cannot assume a shape: once real MILP output arrives it will
    receive whatever the optimiser sends. v1.0 is identified by its own
    schema_version marker rather than by where the file came from.
    """
    if "schema_version" in results:
        return SCHEMA_V1
    return SCHEMA_TOY


def _read_json_or_none(path: Path) -> Any:
    """Read a JSON file, returning None if it cannot be read or parsed."""
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def _declared_scenario_id(payload: Any) -> Any:
    """Return the scenario_id a Results payload declares about itself."""
    if not isinstance(payload, dict):
        return None
    scenario = payload.get("scenario")
    if not isinstance(scenario, dict):
        return None
    return scenario.get("scenario_id")


def find_output_file(scenario_id: str, ingest_dir: Path) -> Path:
    """Find the real MILP output file for one scenario.

    The filename is a hint, never the decision. A file is accepted only when
    its own scenario.scenario_id matches, so an output saved under the wrong
    name is not silently attached to the wrong scenario. <scenario_id>.json is
    checked first because it is the common case, then every other file.
    """
    directory = Path(ingest_dir)
    if not directory.is_dir():
        raise OptimiserError(f"Ingest directory not found: {directory}")

    rejected: list[str] = []

    direct = directory / f"{scenario_id}.json"
    if direct.is_file():
        declared = _declared_scenario_id(_read_json_or_none(direct))
        if declared == scenario_id:
            return direct
        rejected.append(f"{direct.name} declares scenario_id {declared!r}")

    for candidate in sorted(directory.glob("*.json")):
        if candidate == direct:
            continue
        if _declared_scenario_id(_read_json_or_none(candidate)) == scenario_id:
            return candidate

    detail = f" ({'; '.join(rejected)})" if rejected else ""
    raise OptimiserError(
        f"No MILP output found for scenario {scenario_id!r} in {directory}"
        + detail
    )


class OptimiserError(Exception):
    """Raised when an optimiser result cannot be produced."""


def get_optimiser_result(
    scenario: dict[str, Any],
    mode: str = MOCK,
    fixture_path: Path = DEFAULT_FIXTURE,
    ingest_dir: Path = DEFAULT_INGEST_DIR,
) -> dict[str, Any]:
    """Return a raw Results JSON for one scenario.

    Ingest mode reads the real output file the Optimisation team produced for
    this scenario. Mock mode reads a stored fixture and stays available as a
    testing fallback. Both return whatever shape the file holds — the caller
    detects the schema rather than assuming one.
    """
    if mode == MOCK:
        path = Path(fixture_path)
        if not path.is_file():
            raise OptimiserError(f"Mock fixture not found: {path}")
        with path.open(encoding="utf-8") as handle:
            return json.load(handle), None

    if mode == INGEST:
        scenario_id = scenario.get("scenario_id")
        if not scenario_id:
            raise OptimiserError("Cannot ingest: scenario has no scenario_id.")
        path = find_output_file(scenario_id, ingest_dir)
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        # The payload is returned exactly as written by Optimisation. The
        # source path travels beside it so raw/ stays an untouched copy.
        return payload, str(path)

    if mode == MILP:
        raise NotImplementedError(
            "The harness does not run the solver. v1.0 has no execution hooks, "
            "so use mode='ingest' to read Optimisation's output files."
        )

    raise OptimiserError(
        f"Unknown mode: {mode!r}. Use {MOCK!r}, {INGEST!r} or {MILP!r}."
    )


def _gate_as_dict(gate: Any) -> dict[str, Any]:
    """Return the gate result as a plain dict, whichever form it takes."""
    if hasattr(gate, "as_dict"):
        return gate.as_dict()
    return dict(vars(gate))


def build_scenario_context(scenario: dict[str, Any]) -> dict[str, Any]:
    """Collect the scenario inputs that Results JSON v1.0 no longer echoes.

    v1.0 deliberately dropped bounds, capacities and cost rates from the output
    (see its section 5): they are inputs, and echoing them created two sources
    of truth. That is defensible, but it means a consumer holding only a results
    file cannot check utilisation, verify a bound, or compute a margin. The
    harness therefore carries the scenario side alongside the result.

    Nothing here is calculated. Every value is copied from the scenario file,
    keyed so it can be joined back to a result by ID. Arc keys are written as
    "source->plant" strings rather than tuples so the context stays JSON
    serialisable for the run manifest.
    """
    network = scenario.get("network", {})

    unavailable = [
        "source withdrawal bounds — held in the Supabase source view, not the "
        "scenario file",
        "source cost_per_ml — same",
    ]

    return {
        "scenario_id": scenario.get("scenario_id"),
        "source_to_plant_capacity": {
            f"{link.get('source_id')}->{link.get('plant_id')}": link.get("maximum_flow_ml_per_day")
            for link in network.get("source_to_plant_links", [])
        },
        "plant_to_zone_capacity": {
            f"{link.get('plant_id')}->{link.get('zone_id')}": link.get("maximum_flow_ml_per_day")
            for link in network.get("plant_to_zone_links", [])
        },
        "plants": {
            plant.get("plant_id"): {
                "minimum_operating_flow_ml_per_day": plant.get("minimum_operating_flow_ml_per_day"),
                "maximum_processing_capacity_ml_per_day": plant.get("maximum_processing_capacity_ml_per_day"),
                "fixed_activation_cost": plant.get("fixed_activation_cost"),
                "treatment_cost_per_ml": plant.get("treatment_cost_per_ml"),
            }
            for plant in network.get("plants", [])
        },
        "demand": {
            zone.get("zone_id"): zone.get("demand_ml_per_day")
            for zone in network.get("demand_zones", [])
        },
        "quality_limits": scenario.get("quality_limits", {}),
        "unavailable": unavailable,
    }


def _evaluate_one(result: dict[str, Any]) -> dict[str, Any]:
    """Run the KPIs and gate for one result, recording failure rather than raising.

    Each run is isolated so a schema the KPI layer cannot read yet costs one
    entry, not the whole scenario. The baselines stay comparable even when the
    optimiser result cannot be evaluated.
    """
    try:
        report, gate = evaluate(result)
    except Exception as error:
        return {
            "kpis": None,
            "gate": None,
            "error": f"{type(error).__name__}: {error}",
        }
    return {"kpis": report.as_dict(), "gate": _gate_as_dict(gate)}


def run_scenario(
    scenario_path: str | Path,
    mode: str = MOCK,
    fixture_path: Path = DEFAULT_FIXTURE,
    ingest_dir: Path = DEFAULT_INGEST_DIR,
) -> dict[str, Any]:
    """Run one scenario through the optimiser, the baselines, and the gate.

    The optimiser and every baseline go through the same evaluate() call, so
    the numbers being compared were produced the same way.
    """
    started = time.perf_counter()

    scenario = load_scenario(scenario_path)
    validation = validate_scenario(scenario)
    context = build_scenario_context(scenario)

    baseline_output = run_all_baselines(scenario)

    raw_results, optimiser_source = get_optimiser_result(
        scenario, mode, fixture_path, ingest_dir
    )
    schema = detect_schema(raw_results)
    unsupported: list[str] = []

    # Task 56 moved the validator and adapter to v1.0; the confidence flagger
    # still reads the toy provenance fields (Task 57, PR #54, not merged). So
    # the components are chosen one at a time rather than as a schema pair.
    if schema == SCHEMA_V1:
        validate_results(raw_results)
        adapted = adapt_results(raw_results)
        confidence = None
        unsupported.append(
            f"{schema}: confidence flagger skipped — it reads "
            "data_flags.sources, which v1.0 does not carry "
            "(Task 56 note 1; Task 57 pending)"
        )
    else:
        adapted = None
        confidence = determine_confidence(
            raw_results.get("data_flags", {}).get("sources", []),
            raw_results.get("sources", {}).get("selected", []),
        )
        unsupported.append(
            f"{schema}: validator and adapter skipped — Task 56 moved both "
            "to the v1.0 contract and no toy path remains"
        )

    evaluations: dict[str, Any] = {}

    for name, result in [("optimiser", raw_results), *baseline_output["baselines"].items()]:
        evaluations[name] = _evaluate_one(result)
        if "error" in evaluations[name]:
            unsupported.append(f"{name}: {evaluations[name]['error']}")

    return {
        "scenario_path": str(scenario_path),
        "scenario_id": scenario.get("scenario_id"),
        "mode": mode,
        "schema": schema,
        "scenario_validation": validation,
        "scenario_context": context,
        "raw_optimiser_result": raw_results,
        # Where the raw result came from, held beside the payload rather than
        # inside it. None for modes that do not read a per-scenario file.
        "optimiser_source": optimiser_source,
        "adapted_optimiser_result": adapted,
        "confidence": confidence,
        "baseline_output": baseline_output,
        "evaluations": evaluations,
        "unsupported": unsupported,
        "runtime_seconds": round(time.perf_counter() - started, 3),
    }

def run_batch(
    path: str | Path,
    mode: str = MOCK,
    fixture_path: Path = DEFAULT_FIXTURE,
    ingest_dir: Path = DEFAULT_INGEST_DIR,
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
            results.append(
                run_scenario(scenario_file, mode, fixture_path, ingest_dir)
            )
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
        # What this run actually read, so the manifest can record it rather
        # than assuming the default.
        "fixture_path": str(fixture_path),
        "ingest_dir": str(ingest_dir),
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
                "schema": result.get("schema"),
                "source": result.get("optimiser_source"),
                "unsupported": result.get("unsupported", []),
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
        "mock_fixture": batch.get("fixture_path") if batch["mode"] == MOCK else None,
        "ingest_dir": batch.get("ingest_dir") if batch["mode"] == INGEST else None,
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