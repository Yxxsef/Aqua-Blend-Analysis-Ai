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