"""Tests for the Task 26 batch runner and comparison report."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "AI" / "evaluation"))

from batch_runner import (  # noqa: E402
    MOCK,
    MILP,
    INGEST,
    find_output_file,
    SCHEMA_TOY,
    SCHEMA_V1,
    V1_FIXTURE,
    detect_schema,
    OptimiserError,
    get_optimiser_result,
    run_batch,
    run_scenario,
    write_run,
)
from comparison_report import (  # noqa: E402
    NO_QUALITY_REASON,
    build_comparison,
    compare_scenario,
    write_comparison,
)

SCENARIO_DIR = REPO_ROOT / "AI" / "scenarios"
NORMAL = SCENARIO_DIR / "normal-year-dry-year" / "scenario_normal.json"
OUTAGE = SCENARIO_DIR / "high-demand-outage" / "scenario_plant_outage.json"


# --- the optimiser seam ---------------------------------------------------

def test_mock_mode_returns_a_results_json():
    result = get_optimiser_result({}, MOCK)
    assert result["scenario_id"]
    assert result["status"]


def test_milp_mode_is_not_wired_up_yet():
    with pytest.raises(NotImplementedError):
        get_optimiser_result({}, MILP)


def test_unknown_mode_is_rejected():
    with pytest.raises(OptimiserError):
        get_optimiser_result({}, "nonsense")


def test_missing_fixture_is_reported_clearly():
    with pytest.raises(OptimiserError):
        get_optimiser_result({}, MOCK, Path("does/not/exist.json"))


# --- one scenario ---------------------------------------------------------

def test_scenario_runs_optimiser_and_all_three_baselines():
    result = run_scenario(NORMAL)
    assert set(result["evaluations"]) == {
        "optimiser",
        "equal_blend",
        "cheapest_first",
        "fixed_priority",
    }


def test_scenario_records_runtime_and_validation():
    result = run_scenario(NORMAL)
    assert result["runtime_seconds"] >= 0
    assert result["scenario_validation"]["valid"] is True


# --- the batch ------------------------------------------------------------

def test_batch_runs_every_scenario_in_a_folder():
    batch = run_batch(SCENARIO_DIR)
    assert batch["scenario_count"] >= 2
    assert batch["failed"] == 0


def test_batch_order_is_the_same_every_run():
    first = [r["scenario_path"] for r in run_batch(SCENARIO_DIR)["results"]]
    second = [r["scenario_path"] for r in run_batch(SCENARIO_DIR)["results"]]
    assert first == second


def test_one_broken_file_does_not_stop_the_batch(tmp_path):
    (tmp_path / "scenario_ok.json").write_text(NORMAL.read_text(), encoding="utf-8")
    (tmp_path / "scenario_broken.json").write_text("{ not json", encoding="utf-8")

    batch = run_batch(tmp_path)

    assert batch["succeeded"] == 1
    assert batch["failed"] == 1
    assert batch["failures"][0]["error_type"]


# --- infeasible baselines -------------------------------------------------

def test_plant_outage_makes_every_baseline_infeasible():
    result = run_scenario(OUTAGE)
    for name, evaluation in result["evaluations"].items():
        if name == "optimiser":
            continue
        assert evaluation["gate"]["overall_status"] == "FAIL"


def test_infeasible_baseline_still_appears_in_the_comparison():
    comparison = compare_scenario(run_scenario(OUTAGE))
    runs = {row["run"] for row in comparison["rows"]}
    assert "equal_blend" in runs


# --- the comparison -------------------------------------------------------

def test_baseline_margin_carries_a_reason_not_a_blank():
    comparison = compare_scenario(run_scenario(NORMAL))
    for row in comparison["rows"]:
        if row["is_baseline"]:
            margin = row["minimum_safety_margin"]
            assert margin["value"] is None
            assert margin["reason"] == NO_QUALITY_REASON


def test_comparison_records_the_quality_stage():
    comparison = compare_scenario(run_scenario(NORMAL))
    assert comparison["quality_stage"]


def test_missing_optimiser_makes_the_scenario_not_comparable():
    result = run_scenario(NORMAL)
    del result["evaluations"]["optimiser"]
    comparison = compare_scenario(result)
    assert comparison["comparable"] is False
    assert comparison["rows"] == []


# --- writing to disk ------------------------------------------------------

def test_run_writes_raw_processed_and_manifest(tmp_path):
    run_dir = write_run(run_batch(NORMAL), tmp_path)

    assert (run_dir / "raw").is_dir()
    assert (run_dir / "processed").is_dir()

    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == MOCK
    assert manifest["mock_warning"]
    assert manifest["scenarios"]


def test_comparison_csv_has_a_row_for_every_run(tmp_path):
    batch = run_batch(SCENARIO_DIR)
    paths = write_comparison(build_comparison(batch), write_run(batch, tmp_path))

    with paths["csv"].open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == batch["succeeded"] * 4

def test_csv_row_width_matches_header_when_not_comparable(tmp_path):
    """An incomparable scenario writes a full-width row, not a short one."""
    comparison = {
        "comparisons": [
            {
                "scenario_id": "s1",
                "comparable": False,
                "reason": "no optimiser result — baselines cannot be compared against it",
                "rows": [],
            }
        ]
    }

    paths = write_comparison(comparison, tmp_path)

    with paths["csv"].open(encoding="utf-8", newline="") as handle:
        header, row = list(csv.reader(handle))

    assert len(row) == len(header)
    assert row[header.index("scenario_reason")] == comparison["comparisons"][0]["reason"]
    assert row[header.index("gate")] == ""

# --- schema detection -----------------------------------------------------

def test_v1_fixture_is_detected_as_milp_v1():
    result = get_optimiser_result({}, MOCK, V1_FIXTURE)
    assert detect_schema(result) == SCHEMA_V1


def test_toy_fixture_is_detected_as_toy():
    result = get_optimiser_result({}, MOCK)
    assert detect_schema(result) == SCHEMA_TOY


def test_v1_fixture_is_a_solved_run():
    """The v1 fixture must be solved, or it cannot test value-level behaviour."""
    result = get_optimiser_result({}, MOCK, V1_FIXTURE)
    assert result["solver"]["status"] == "OPTIMAL"
    assert result["solver"]["objective_value"] is not None


# --- v1 payloads must not take the run down --------------------------------

def test_v1_scenario_still_returns_a_result():
    """A schema the KPI layer cannot read yet must not raise out of run_scenario."""
    result = run_scenario(NORMAL, MOCK, V1_FIXTURE)
    assert result["schema"] == SCHEMA_V1
    assert result["scenario_id"]


def test_v1_run_survives_an_optimiser_that_cannot_be_evaluated():
    """The three baselines stay comparable even when the optimiser entry fails."""
    result = run_scenario(NORMAL, MOCK, V1_FIXTURE)
    evaluations = result["evaluations"]

    assert set(evaluations) == {
        "optimiser",
        "equal_blend",
        "cheapest_first",
        "fixed_priority",
    }
    for name in ("equal_blend", "cheapest_first", "fixed_priority"):
        assert evaluations[name]["gate"] is not None


def test_v1_failure_is_recorded_not_swallowed():
    """A failure must name what broke, so the owning task can act on it."""
    result = run_scenario(NORMAL, MOCK, V1_FIXTURE)
    assert result["unsupported"]
    assert any("56" in note for note in result["unsupported"])


def test_toy_path_still_validates_and_adapts():
    """The toy schema keeps its full pipeline — nothing was skipped for it."""
    result = run_scenario(NORMAL, MOCK)
    assert result["schema"] == SCHEMA_TOY
    assert result["adapted_optimiser_result"] is not None
    assert result["confidence"] is not None
    assert result["unsupported"] == []


# --- scenario context ------------------------------------------------------

def test_scenario_context_carries_the_capacities_v1_dropped():
    result = run_scenario(NORMAL, MOCK, V1_FIXTURE)
    context = result["scenario_context"]
    assert context["source_to_plant_capacity"]["yarra_kew->facility_1"] == 300
    assert context["plants"]["facility_1"]["maximum_processing_capacity_ml_per_day"] == 600
    assert context["demand"]["zone_1"] == 500


def test_scenario_context_names_what_it_cannot_supply():
    """Source bounds and costs live in Supabase — the gap must be stated, not implied."""
    result = run_scenario(NORMAL, MOCK, V1_FIXTURE)
    assert result["scenario_context"]["unavailable"]


# --- ingest mode -----------------------------------------------------------

def _drop_output(directory, scenario_id, filename="milp_run_output.json"):
    """Write the solved v1 fixture into directory, under the given scenario id."""
    payload = json.loads(Path(V1_FIXTURE).read_text())
    payload["scenario"]["scenario_id"] = scenario_id
    target = Path(directory) / filename
    target.write_text(json.dumps(payload, indent=2))
    return target


def test_ingest_reads_the_real_output_file(tmp_path):
    _drop_output(tmp_path, "toy_model_normal_year")
    result = run_scenario(NORMAL, INGEST, ingest_dir=tmp_path)

    assert result["schema"] == SCHEMA_V1
    assert result["raw_optimiser_result"]["solver"]["status"] == "OPTIMAL"


def test_ingest_records_which_file_it_read(tmp_path):
    """The manifest has to say where a number came from, not just what it was."""
    dropped = _drop_output(tmp_path, "toy_model_normal_year")
    result = run_scenario(NORMAL, INGEST, ingest_dir=tmp_path)

    assert result["raw_optimiser_result"]["_ingested_from"] == str(dropped)


def test_ingest_matches_on_scenario_id_not_filename(tmp_path):
    """Optimisation names its own files, so the join is on scenario_id."""
    _drop_output(tmp_path, "toy_model_normal_year", filename="whatever_they_called_it.json")
    found = find_output_file("toy_model_normal_year", tmp_path)

    assert found.name == "whatever_they_called_it.json"


def test_ingest_prefers_a_file_named_after_the_scenario(tmp_path):
    _drop_output(tmp_path, "toy_model_normal_year", filename="toy_model_normal_year.json")
    _drop_output(tmp_path, "toy_model_normal_year", filename="another_run.json")
    found = find_output_file("toy_model_normal_year", tmp_path)

    assert found.name == "toy_model_normal_year.json"


def test_ingest_says_which_scenario_had_no_output(tmp_path):
    """A silent skip would look like a passing run with nothing in it."""
    _drop_output(tmp_path, "some_other_scenario")

    with pytest.raises(OptimiserError) as error:
        find_output_file("toy_model_normal_year", tmp_path)
    assert "toy_model_normal_year" in str(error.value)


def test_ingest_reports_a_missing_directory(tmp_path):
    with pytest.raises(OptimiserError):
        find_output_file("toy_model_normal_year", tmp_path / "not_there")


def test_ingest_ignores_unreadable_files(tmp_path):
    """A stray or half-written file must not stop the real one being found."""
    (tmp_path / "broken.json").write_text("{ not json")
    _drop_output(tmp_path, "toy_model_normal_year")

    found = find_output_file("toy_model_normal_year", tmp_path)
    assert found.name == "milp_run_output.json"


def test_solver_mode_points_at_ingest(tmp_path):
    """The harness ingests output files; it does not run the solver."""
    with pytest.raises(NotImplementedError) as error:
        get_optimiser_result({}, MILP)
    assert "ingest" in str(error.value)
