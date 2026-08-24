"""Comparison report for AquaBlend.

Compares the optimiser against every coded baseline on the four measures the
task sheet asks for: feasibility, total cost, demand satisfaction, and the
minimum safety margin.

This module reports. It does not rank, score, or recommend. Every value comes
from the KPI calculator; nothing here is calculated.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

MEASURES = (
    "feasibility",
    "total_cost",
    "demand_satisfaction",
    "minimum_safety_margin",
)

NO_QUALITY_REASON = "baselines do not compute water quality"

QUALITY_STAGE_KEY = "applies_to"

def _measure(kpis: dict[str, Any], name: str, is_baseline: bool) -> dict[str, Any]:
    """Return one measure, with a reason when there is no value."""
    entry = kpis.get(name, {})
    value = entry.get("value")
    status = entry.get("status")

    cell: dict[str, Any] = {"value": value, "status": status}

    if value is None:
        if is_baseline and name == "minimum_safety_margin":
            cell["reason"] = NO_QUALITY_REASON
        else:
            cell["reason"] = entry.get("reason") or "not reported"

    return cell


def compare_scenario(result: dict[str, Any]) -> dict[str, Any]:
    """Build the comparison for one scenario result from run_scenario()."""
    evaluations = result.get("evaluations", {})

    if "optimiser" not in evaluations:
        return {
            "scenario_id": result.get("scenario_id"),
            "comparable": False,
            "reason": "no optimiser result — baselines cannot be compared against it",
            "rows": [],
        }

    quality_stage = (
        result.get("raw_optimiser_result", {})
        .get("water_quality", {})
        .get(QUALITY_STAGE_KEY)
    )

    rows = []
    for name, evaluation in evaluations.items():
        kpis = evaluation.get("kpis", {})
        is_baseline = name != "optimiser"
        row = {
            "run": name,
            "is_baseline": is_baseline,
            "gate": evaluation.get("gate", {}).get("overall_status"),
        }
        for measure in MEASURES:
            row[measure] = _measure(kpis, measure, is_baseline)
        rows.append(row)

    return {
        "scenario_id": result.get("scenario_id"),
        "comparable": True,
        "quality_stage": quality_stage,
        "rows": rows,
    }


def build_comparison(batch: dict[str, Any]) -> dict[str, Any]:
    """Build the comparison across every scenario in a batch."""
    return {
        "mode": batch.get("mode"),
        "scenario_count": batch.get("scenario_count"),
        "comparisons": [compare_scenario(r) for r in batch.get("results", [])],
        "failed_scenarios": [
            {"scenario_path": f["scenario_path"], "error_type": f["error_type"]}
            for f in batch.get("failures", [])
        ],
    }


def write_comparison(comparison: dict[str, Any], run_dir: str | Path) -> dict[str, Path]:
    """Write the comparison as JSON and as a flat CSV."""
    run_dir = Path(run_dir)

    json_path = run_dir / "comparison.json"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(comparison, handle, indent=2)

    csv_path = run_dir / "comparison.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["scenario_id", "quality_stage", "run", "gate"]
            + [f"{m}_{part}" for m in MEASURES for part in ("value", "reason")]
        )
        for scenario in comparison["comparisons"]:
            if not scenario["comparable"]:
                writer.writerow([scenario["scenario_id"], scenario.get("quality_stage"), "", scenario["reason"]])
                continue
            for row in scenario["rows"]:
                cells: list[Any] = [scenario["scenario_id"], scenario.get("quality_stage"), row["run"], row["gate"]]
                for measure in MEASURES:
                    cells.append(row[measure]["value"])
                    cells.append(row[measure].get("reason", ""))
                writer.writerow(cells)

    return {"json": json_path, "csv": csv_path}