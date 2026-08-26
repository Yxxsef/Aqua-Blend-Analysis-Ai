"""
kpi_calculator.py — Task 19 (Sprint 2)

Calculates the six KPIs defined in AI/evaluation/KPI_Set.md against a MILP
Results JSON object (model_output_contract.json shape). Works on optimiser
output and coded-baseline output alike, as long as the input follows the
same field names (model_output_specification.md, "Naming follows the
data_loader.py").

This module ONLY calculates KPI values. It does not decide pass/fail —
that is kpi_gate.py's job (KPI_Set.md §2, rule 3: "cost and chemical KPIs
are compared only between valid results", which is a gating concern, not
a calculation concern).

Design note on "missing" vs "incomplete" (KPI_Set.md §2 rule 4):
Missing values are never estimated. Every KPI result carries an explicit
`status` field: "OK", "N/A", "INCOMPLETE", or "UNKNOWN" — never a silently
substituted number.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


# KPI_Set.md §4, KPI 1: interpretation rule.
FEASIBLE_STATUSES = {"OPTIMAL", "FEASIBLE"}
INVALID_STATUSES = {"UNBOUNDED", "ERROR"}
# INFEASIBLE and TIME_LIMIT are handled explicitly, not via a set membership
# check, because they each need their own message (see calculate_feasibility).

# The full set of feasibility.value outcomes that mean "safe to treat this
# result as feasible" — used by anything downstream that needs a single
# feasible/not-feasible decision (calculate_total_cost, evaluate_gate).
# Deliberately NOT the same as checking feasibility.status == "OK": that
# field means "we have a confirmed, definitive answer", which is also true
# for INFEASIBLE, UNBOUNDED, and ERROR. Confusing the two would make cost
# and the gate treat an infeasible result as usable.
CONFIRMED_FEASIBLE_VALUES = FEASIBLE_STATUSES | {"TIME_LIMIT_FEASIBLE_INCUMBENT"}


def is_confirmed_feasible(feasibility: "KPIResult") -> bool:
    """True only for a feasibility result the rest of the pipeline can treat
    as a usable, feasible solution: OPTIMAL, FEASIBLE, or a TIME_LIMIT result
    with a verified feasible incumbent. Everything else (INFEASIBLE,
    UNBOUNDED, ERROR, UNKNOWN, an unconfirmed TIME_LIMIT) is False.
    """
    return feasibility.status == "OK" and feasibility.value in CONFIRMED_FEASIBLE_VALUES

# KPI_Set.md §3.7 / the input contract's quality_limits.parameters: the three
# parameters the current toy configuration checks. This is used only to
# detect *incompleteness* in KPI 4/5 (a plant reporting fewer than the
# expected parameters). If the parameter set changes, update this constant —
# it is intentionally not hardcoded any deeper than this one place.
EXPECTED_QUALITY_PARAMETERS = {"pH", "alkalinity", "turbidity"}


@dataclass
class KPIResult:
    """One KPI's calculated value plus how confident we are in it.

    status:
      "OK"         — value is a genuine, complete calculation.
      "N/A"        — required data was absent; do not compare or gate on this.
      "INCOMPLETE" — a partial value could be computed, but it should not be
                      treated as authoritative (e.g. minimum-of-available
                      rather than true minimum).
      "UNKNOWN"    — feasibility specifically could not be determined at all.
    """

    name: str
    status: str
    value: Optional[Any] = None
    unit: Optional[str] = None
    detail: str = ""


@dataclass
class KPIReport:
    scenario_id: Optional[str]
    feasibility: KPIResult
    demand_satisfaction: KPIResult
    total_cost: KPIResult
    minimum_safety_margin: KPIResult
    quality_violations: KPIResult
    chemical_kpi: KPIResult

    def as_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "feasibility": vars(self.feasibility),
            "demand_satisfaction": vars(self.demand_satisfaction),
            "total_cost": vars(self.total_cost),
            "minimum_safety_margin": vars(self.minimum_safety_margin),
            "quality_violations": vars(self.quality_violations),
            "chemical_kpi": vars(self.chemical_kpi),
        }


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


# ---------------------------------------------------------------------------
# KPI 1 — Feasibility status (KPI_Set.md §4, KPI 1)
# ---------------------------------------------------------------------------
def calculate_feasibility(results: dict) -> KPIResult:
    status = results.get("status")

    if status is None:
        return KPIResult(
            "feasibility", "UNKNOWN", None, "status",
            "No `status` field present in the Results JSON.",
        )

    if status in FEASIBLE_STATUSES:
        return KPIResult(
            "feasibility", "OK", status, "status",
            "Feasible" + (" and optimal" if status == "OPTIMAL" else ""),
        )

    if status == "INFEASIBLE":
        return KPIResult(
            "feasibility", "OK", "INFEASIBLE", "status",
            "No feasible solution was found. Other KPIs must not be treated "
            "as a successful result even if their source data is complete.",
        )

    if status == "TIME_LIMIT":
        # KPI_Set.md §4, KPI 1: "feasibility is not confirmed unless the MILP
        # output explicitly verifies a feasible incumbent solution. The
        # current reference JSON has no separate incumbent-feasibility
        # field." We check for one defensively in case it is added later,
        # but today this branch always falls through to UNKNOWN.
        if results.get("incumbent_feasible") is True:
            return KPIResult(
                "feasibility", "OK", "TIME_LIMIT_FEASIBLE_INCUMBENT",
                "status",
                "Solver hit the time limit but reported a verified feasible "
                "incumbent solution.",
            )
        return KPIResult(
            "feasibility", "UNKNOWN", "TIME_LIMIT", "status",
            "Solver hit the time limit and no incumbent-feasibility field "
            "is present in this contract version. Feasibility cannot be "
            "confirmed; do not treat this result as gateable.",
        )

    if status in INVALID_STATUSES:
        return KPIResult(
            "feasibility", "OK", status, "status",
            "Not a valid result for KPI comparison.",
        )

    # Any other/unrecognised status string.
    return KPIResult(
        "feasibility", "UNKNOWN", status, "status",
        f"Unrecognised status value '{status}'.",
    )


# ---------------------------------------------------------------------------
# KPI 2 — Demand satisfaction (KPI_Set.md §4, KPI 2)
# ---------------------------------------------------------------------------
def calculate_demand_satisfaction(results: dict) -> KPIResult:
    zones = results.get("demand_zones")
    if not zones:
        return KPIResult(
            "demand_satisfaction", "N/A", None, "%",
            "No `demand_zones` present.",
        )

    total_required = 0.0
    total_supplied = 0.0
    for zone in zones:
        required = zone.get("demand_ml_per_day")
        supplied = zone.get("volume_supplied_ml_per_day")
        if not _is_number(required) or not _is_number(supplied):
            return KPIResult(
                "demand_satisfaction", "N/A", None, "%",
                f"Zone '{zone.get('zone_id', '?')}' is missing "
                "demand_ml_per_day or volume_supplied_ml_per_day. "
                "Not assuming a missing value is zero.",
            )
        total_required += required
        total_supplied += supplied

    if total_required == 0:
        return KPIResult(
            "demand_satisfaction", "N/A", None, "%",
            "Total required demand is zero; percentage is undefined.",
        )

    pct = (total_supplied / total_required) * 100
    return KPIResult("demand_satisfaction", "OK", round(pct, 1), "%")


# ---------------------------------------------------------------------------
# KPI 3 — Total cost (KPI_Set.md §4, KPI 3)
# ---------------------------------------------------------------------------
def calculate_total_cost(results: dict, feasibility: KPIResult) -> KPIResult:
    # "If the result is infeasible: report N/A for comparison purposes, even
    # if the solver output contains a temporary objective value." — so this
    # checks confirmed feasibility FIRST, not just field presence. Uses
    # is_confirmed_feasible() rather than a raw value-in-set check so a
    # verified TIME_LIMIT incumbent is correctly included (see that
    # function's docstring for why feasibility.status == "OK" alone is not
    # the right test here).
    if not is_confirmed_feasible(feasibility):
        return KPIResult(
            "total_cost", "N/A", None, None,
            "Result is not confirmed feasible; total cost is not valid for "
            "comparison even if a value is present in the output.",
        )

    objective = results.get("objective")
    if not isinstance(objective, dict) or not _is_number(objective.get("total_cost")):
        return KPIResult(
            "total_cost", "N/A", None, None,
            "`objective.total_cost` missing or not numeric.",
        )

    currency = objective.get("currency", "?")
    return KPIResult(
        "total_cost", "OK", objective["total_cost"], currency,
    )


# ---------------------------------------------------------------------------
# Shared helper for KPI 4 and KPI 5 — both read water_quality.by_plant.
# ---------------------------------------------------------------------------
def _collect_quality_entries(results: dict):
    """Returns (entries, incomplete_flag).

    entries: list of (plant_id, parameter, entry_dict) for every
    plant/parameter pair actually present.
    incomplete_flag: True if any *active* plant is missing from
    water_quality.by_plant entirely, or is missing one of
    EXPECTED_QUALITY_PARAMETERS.
    """
    wq = results.get("water_quality", {})
    by_plant = wq.get("by_plant", {}) if isinstance(wq, dict) else {}

    entries = []
    for plant_id, params in by_plant.items():
        if not isinstance(params, dict):
            continue
        for param_name, entry in params.items():
            if isinstance(entry, dict):
                entries.append((plant_id, param_name, entry))

    # Incompleteness check against active plants (model_output_specification.md
    # §3.7: "A plant with zero inflow has no defined blend and is omitted" —
    # so we only expect entries for plants actually reported as active).
    active_plants = results.get("plants", {}).get("active", [])
    incomplete = False
    for plant in active_plants:
        plant_id = plant.get("plant_id")
        plant_params = by_plant.get(plant_id)
        if not isinstance(plant_params, dict):
            incomplete = True
            continue
        if not EXPECTED_QUALITY_PARAMETERS.issubset(plant_params.keys()):
            incomplete = True

    return entries, incomplete


# ---------------------------------------------------------------------------
# KPI 4 — Minimum safety margin (KPI_Set.md §4, KPI 4)
# ---------------------------------------------------------------------------
def calculate_minimum_safety_margin(results: dict) -> KPIResult:
    entries, incomplete = _collect_quality_entries(results)

    margins = [
        e["safety_margin_percent"]
        for (_, _, e) in entries
        if _is_number(e.get("safety_margin_percent"))
    ]

    if not margins:
        return KPIResult(
            "minimum_safety_margin", "N/A", None, "%",
            "No verified safety_margin_percent values are available.",
        )

    min_margin = round(min(margins), 1)
    if incomplete:
        return KPIResult(
            "minimum_safety_margin", "INCOMPLETE", min_margin, "%",
            "Some expected plant/parameter entries are missing; this is the "
            "minimum of available values, not confirmed as the true overall "
            "minimum.",
        )
    return KPIResult("minimum_safety_margin", "OK", min_margin, "%")


# ---------------------------------------------------------------------------
# KPI 5 — Quality violations (KPI_Set.md §4, KPI 5)
# ---------------------------------------------------------------------------
def calculate_quality_violations(results: dict) -> KPIResult:
    entries, incomplete = _collect_quality_entries(results)

    if not entries:
        return KPIResult(
            "quality_violations", "N/A", None, "count",
            "No water-quality entries are available.",
        )

    violations = 0
    for (_plant_id, _param, entry) in entries:
        status = entry.get("status")
        if status == "FAIL":
            violations += 1
        elif status is None:
            margin = entry.get("safety_margin_percent")
            if _is_number(margin) and margin < 0:
                violations += 1

    if incomplete:
        return KPIResult(
            "quality_violations", "INCOMPLETE", violations, "count",
            "Some expected plant/parameter entries are missing; this count "
            "may understate the true number of violations.",
        )
    return KPIResult("quality_violations", "OK", violations, "count")


# ---------------------------------------------------------------------------
# KPI 6 — Chemical cost or use (KPI_Set.md §4, KPI 6)
# ---------------------------------------------------------------------------
# No field is approved in the current output contract. This whitelist is
# deliberately empty; extend it only once a field is officially added to
# model_output_contract.json / model_output_specification.md. Per KPI_Set.md:
# "Never create a chemical value from treatment cost or another unrelated
# field" — so this must never fall back to plant_treatment_cost.
APPROVED_CHEMICAL_FIELDS: tuple[str, ...] = ()


def calculate_chemical_kpi(results: dict) -> KPIResult:
    for field_path in APPROVED_CHEMICAL_FIELDS:
        # Reserved for when a field is approved; deliberately unreachable today.
        pass  # pragma: no cover

    return KPIResult(
        "chemical_kpi", "N/A", None, None,
        "No approved chemical cost/use field exists in the current "
        "model_output_contract.json.",
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def calculate_kpis(results: dict) -> KPIReport:
    """Calculate all six KPIs for one Results JSON object.

    `results` should already have passed schema validation (Task 21);
    this function still degrades safely on missing/malformed data rather
    than raising, per KPI_Set.md's missing-data rules.
    """
    feasibility = calculate_feasibility(results)
    return KPIReport(
        scenario_id=results.get("scenario_id"),
        feasibility=feasibility,
        demand_satisfaction=calculate_demand_satisfaction(results),
        total_cost=calculate_total_cost(results, feasibility),
        minimum_safety_margin=calculate_minimum_safety_margin(results),
        quality_violations=calculate_quality_violations(results),
        chemical_kpi=calculate_chemical_kpi(results),
    )
