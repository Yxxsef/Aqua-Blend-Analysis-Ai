"""
kpi_gate.py — Task 19 (Sprint 2)

Applies the pass/fail rules from KPI_Set.md §2 ("General evaluation rules")
on top of kpi_calculator.py's per-KPI results, and returns exactly one of:

    PASS               — feasible, 100% demand satisfaction, zero quality
                          violations, all confirmed (not just present).
    FAIL               — confirmed infeasible/invalid, OR demand satisfaction
                          is confirmed below 100%, OR at least one confirmed
                          quality violation.
    UNABLE_TO_EVALUATE — feasibility or a gating KPI could not be confirmed
                          (missing, incomplete, or unknown data), so neither
                          PASS nor FAIL can be honestly claimed.

Cost (KPI 3) and the chemical KPI (KPI 6) are NEVER gating criteria — per
KPI_Set.md §4 KPI 3/6, their "required target" is comparative ("lowest among
otherwise valid results"), not a fixed pass/fail threshold. They are carried
through in the report for visibility, but do not affect the gate.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from kpi_calculator import KPIReport, is_confirmed_feasible, calculate_kpis


@dataclass
class GateResult:
    overall_status: str  # "PASS" | "FAIL" | "UNABLE_TO_EVALUATE"
    reasons: list

    def as_dict(self) -> dict:
        return {"overall_status": self.overall_status, "reasons": self.reasons}


def evaluate_gate(report: KPIReport) -> GateResult:
    reasons: list[str] = []

    # --- Gate 1: feasibility (KPI_Set.md §2 rule 1: "feasibility is the
    # first gate") ---
    feas = report.feasibility
    if feas.status == "UNKNOWN":
        return GateResult(
            "UNABLE_TO_EVALUATE",
            [f"Feasibility could not be confirmed: {feas.detail}"],
        )
    if feas.value == "INFEASIBLE":
        return GateResult("FAIL", ["Result is INFEASIBLE."])
    if feas.value in ("UNBOUNDED", "ERROR"):
        return GateResult("FAIL", [f"Solver status '{feas.value}' is not a valid result."])
    if not is_confirmed_feasible(feas):
        # Covers TIME_LIMIT-without-incumbent and any other non-feasible,
        # non-error status that still isn't a confirmed feasible result.
        # (A verified TIME_LIMIT incumbent passes is_confirmed_feasible()
        # and falls through to the demand/quality gates below, instead of
        # being incorrectly reported as UNABLE_TO_EVALUATE.)
        return GateResult(
            "UNABLE_TO_EVALUATE",
            [f"Status '{feas.value}' does not confirm feasibility."],
        )

    # --- Gate 2: demand satisfaction (KPI_Set.md §2 rule 2: "must supply
    # 100% of required demand") ---
    demand = report.demand_satisfaction
    if demand.status == "N/A":
        return GateResult(
            "UNABLE_TO_EVALUATE",
            [f"Demand satisfaction could not be calculated: {demand.detail}"],
        )
    if demand.value < 100.0:
        reasons.append(f"Demand satisfaction is {demand.value}%, below the required 100%.")

    # --- Gate 3: quality violations (KPI_Set.md §2 rule 2: "zero quality
    # violations") ---
    violations = report.quality_violations
    if violations.status == "N/A":
        return GateResult(
            "UNABLE_TO_EVALUATE",
            [f"Quality violations could not be counted: {violations.detail}"],
        )
    if violations.status == "INCOMPLETE":
        return GateResult(
            "UNABLE_TO_EVALUATE",
            [
                f"Quality violation count ({violations.value}) is based on "
                "incomplete data and cannot be confirmed as zero."
            ],
        )
    if violations.value > 0:
        reasons.append(f"{violations.value} quality violation(s) detected.")

    if reasons:
        return GateResult("FAIL", reasons)

    return GateResult("PASS", ["Feasible, 100% demand satisfaction, zero quality violations."])


def evaluate(results: dict) -> tuple[KPIReport, GateResult]:
    """Convenience entry point: calculate KPIs and evaluate the gate in one call."""
    report = calculate_kpis(results)
    gate = evaluate_gate(report)
    return report, gate
