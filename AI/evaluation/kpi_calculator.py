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
#
# Sprint 4 finding (Task 87): KPI_Set.md itself always hedged this - "FEASIBLE:
# feasible, if this status is officially supported by the MILP contract." That
# condition is now resolved, and the answer is no. AI/results/Results_JSON_
# Field_Map.md (the actual confirmed contract doc) states explicitly:
# "FEASIBLE must not be used unless it exists in the confirmed contract" - and
# it does not appear anywhere in the confirmed status enumeration. This module
# previously included "FEASIBLE" here anyway; that was a bug now fixed to
# match the confirmed contract exactly. See also: results_validator.py's
# VALID_STATUS still includes "FEASIBLE" and "SUCCESS", which contradicts this
# same confirmed doc - flagged separately to the team, not fixed here, since
# that file isn't in this module's scope.
FEASIBLE_STATUSES = {"OPTIMAL"}
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
            "Feasible and optimal",
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
        # Sprint 4 (Task 87): the real milp_model_output.demand_zones jsonb
        # (confirmed against an actual captured row) does not use
        # demand_ml_per_day/volume_supplied_ml_per_day at all. It reports
        # delivered_ml_per_day and unmet_demand_ml_per_day instead, with no
        # direct "required" field. Required demand is derived as
        # delivered + unmet, which is exactly what "required" means. Both
        # field-name sets are supported so this still works against the
        # older toy-model reference data used throughout Sprint 1-3.
        if "demand_ml_per_day" in zone or "volume_supplied_ml_per_day" in zone:
            required = zone.get("demand_ml_per_day")
            supplied = zone.get("volume_supplied_ml_per_day")
        else:
            delivered = zone.get("delivered_ml_per_day")
            unmet = zone.get("unmet_demand_ml_per_day")
            supplied = delivered
            required = (
                delivered + unmet
                if _is_number(delivered) and _is_number(unmet)
                else None
            )

        if not _is_number(required) or not _is_number(supplied):
            return KPIResult(
                "demand_satisfaction", "N/A", None, "%",
                f"Zone '{zone.get('zone_id', '?')}' is missing the fields "
                "needed to determine required and supplied demand. "
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
# Shared helper for KPI 4 and KPI 5 — both read water-quality data.
# ---------------------------------------------------------------------------
def _margin_percent(value, lo, hi):
    """KPI_Set.md's margin formula: min(value-min, max-value)/(max-min)*100."""
    if not (_is_number(value) and _is_number(lo) and _is_number(hi)) or hi == lo:
        return None
    return round(min(value - lo, hi - value) / (hi - lo) * 100, 1)


def _active_plant_ids(results: dict):
    """Returns the set of active plant IDs, handling both plant shapes.

    Old canonical shape: plants = {"active": [...], "inactive": [...]}.
    Real v1 shape (confirmed against a captured milp_model_output row,
    Sprint 4 / Task 87): plants is a flat list, each entry has an
    "activated" boolean rather than being split into two arrays.

    Sprint 4 finding (Task 87): normalize_output_columns() has a second bug
    alongside the quality double-wrap - it puts every plant into "active"
    regardless of its real "activated" value (confirmed against a captured
    row: a plant with activated=false still ended up in the "active" list,
    with "inactive" always empty). Flagged to the team, not fixed in that
    shared file. Re-checking each entry's own "activated" field here even
    when it arrives pre-split, so this module isn't silently wrong because
    of it.
    """
    plants = results.get("plants")
    if isinstance(plants, dict):
        candidates = plants.get("active", [])
    elif isinstance(plants, list):
        candidates = plants
    else:
        return set()

    return {
        p.get("plant_id") for p in candidates
        if isinstance(p, dict) and p.get("activated", True) is not False
    }


def _collect_quality_entries(results: dict):
    """Returns (entries, incomplete_flag).

    entries: list of (plant_id, parameter, entry_dict) for every
    plant/parameter pair actually present. entry_dict is always normalised
    to this module's internal shape — {"status": "PASS"/"FAIL"/None,
    "safety_margin_percent": float or None} — regardless of which real
    shape the data came from.
    incomplete_flag: True if any *active* plant is missing entirely, or is
    missing one of EXPECTED_QUALITY_PARAMETERS.
    """
    quality = results.get("water_quality", {})
    entries = []
    plants_seen = {}

    if isinstance(quality, dict) and isinstance(quality.get("by_plant"), dict):
        by_plant = quality["by_plant"]
        # Old canonical shape: by_plant = {plant_id: {param_name: {...}}}.
        # Guard against the case where "by_plant" itself isn't really a
        # per-plant mapping (e.g. it was accidentally given the real v1
        # quality blob directly, which also happens to have top-level keys
        # like "applies_to"/"plant_inflow" - those are not plant IDs).
        if "plant_inflow" not in by_plant:
            for plant_id, params in by_plant.items():
                if not isinstance(params, dict):
                    continue
                plants_seen[plant_id] = set(params.keys())
                for param_name, entry in params.items():
                    if isinstance(entry, dict):
                        entries.append((plant_id, param_name, entry))

    plant_inflow = None
    if isinstance(quality, dict) and isinstance(quality.get("plant_inflow"), list):
        plant_inflow = quality["plant_inflow"]
    elif (
        isinstance(quality, dict)
        and isinstance(quality.get("by_plant"), dict)
        and isinstance(quality["by_plant"].get("plant_inflow"), list)
    ):
        # normalize_output_columns() double-wraps the real quality blob
        # under an extra "by_plant" key rather than replacing it (Sprint 4
        # finding, Task 87 - flagged to the team as a bug in that shared
        # function, not fixed here since it isn't this module's file).
        # Recovering the real structure from underneath that wrapping
        # rather than failing, since the actual data is still right there.
        plant_inflow = quality["by_plant"]["plant_inflow"]

    if plant_inflow is not None:
        # Real v1 shape (confirmed against a captured milp_model_output
        # row): quality.plant_inflow[] = [{plant_id, parameters: [{
        # parameter_id, model_value, model_min, model_max, within_limits,
        # binding_lower, binding_upper, reported_value, reported_unit,
        # ...}]}]. No safety_margin_percent or PASS/FAIL status field
        # exists directly - both are derived here.
        #
        # Margin is computed in "model" units (model_value/model_min/
        # model_max), not "reported" units, because that is the space the
        # constraint is actually enforced in - confirmed against the real
        # pH entry, where reported_value is pH but model_value is the
        # transformed hydrogen-ion concentration the solver linearises on.
        # For an identity-transform parameter (e.g. turbidity, alkalinity)
        # model and reported units coincide, so this makes no difference.
        # Flagging this choice for team confirmation since KPI_Set.md's
        # margin formula predates this model/reported distinction.
        for plant in plant_inflow:
            if not isinstance(plant, dict):
                continue
            plant_id = plant.get("plant_id")
            params = plant.get("parameters", [])
            if not isinstance(params, list):
                continue
            seen_params = set()
            for param in params:
                if not isinstance(param, dict):
                    continue
                param_id = param.get("parameter_id")
                seen_params.add(param_id)
                within_limits = param.get("within_limits")
                status = (
                    "PASS" if within_limits is True
                    else "FAIL" if within_limits is False
                    else None
                )
                margin = _margin_percent(
                    param.get("model_value"), param.get("model_min"), param.get("model_max")
                )
                entries.append((plant_id, param_id, {
                    "status": status,
                    "safety_margin_percent": margin,
                }))
            plants_seen[plant_id] = seen_params

    active_plant_ids = _active_plant_ids(results)
    incomplete = False
    for plant_id in active_plant_ids:
        seen_params = plants_seen.get(plant_id)
        if seen_params is None:
            incomplete = True
            continue
        if not EXPECTED_QUALITY_PARAMETERS.issubset(seen_params):
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
