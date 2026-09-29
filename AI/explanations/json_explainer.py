"""
json_explainer.py

AquaBlend | Analysis & AI | Sprint 2 | Task 23
Upgrade the deterministic fallback explanation generator.

Reads the output of the Task 21 adapter (`AI/results/results_adapter.py`,
now merged) and produces the complete deterministic report defined by the
Task 22 reporting specification. Works entirely offline - no LLM call of
any kind (that is Task 24's job, layered on top of this module's plain-text
output).

Governing documents (Task 22, `explanations/llm_reporting/docs/`):

  LLM_Report_Scope.md          - what the deterministic template may and
                                  may not do (never invents reasons,
                                  calculations, recommendations or safety
                                  claims; is the required fallback).
  Report_Structure.md          - the fixed 12-section report order and the
                                  allowed/forbidden wording and missing-
                                  field behaviour for each section.
  Results_JSON_Field_Map.md    - the exact JSON paths of the raw, external
                                  Results JSON that `results_validator.py`
                                  validates - see the Task 21 note below for
                                  how this module's own input differs.

Note on Task 21 (`AI/results/`, now merged): `results_adapter.py` converts
the raw external Results JSON into a stable internal shape by renaming a
fixed set of TOP-LEVEL keys to camelCase (scenario_id -> scenarioId,
demand_zones -> demandZones, transfer_paths -> transferPaths,
water_quality -> waterQuality, data_flags -> dataFlags, solved_at ->
solvedAt, binding_constraints_summary -> bindingConstraintsSummary,
alternative_feasible_solutions -> alternativeFeasibleSolutions,
sensitivity_to_key_assumptions -> sensitivityToKeyAssumptions); `status`,
`objective`, `sources`, `plants`, `constraints`, `diagnostics` and
`explanation` are passed through unchanged, and the adapter never renames
anything nested inside those top-level values. This module's input `data`
is assumed to already be that adapter's OUTPUT, produced upstream (by
whatever calls this module) from `results_adapter.adapt_results()` - not
the raw Results JSON `results_validator.py` validates. Field-name constants
below use the adapted (camelCase top-level) names for that reason; nested
field names still match Results_JSON_Field_Map.md exactly, since the
adapter never touches them. This module does not call `adapt_results()`
itself: that function hard-requires every top-level field (raising
AdapterError otherwise), which is stricter than this module's own
deliberately-tolerant "only `status`/`scenarioId` are required" contract
(see "Required vs. optional input" below) - re-running that check here
would turn every optional-field gap this module is meant to handle
gracefully into a hard failure instead.

Report sections (Report_Structure.md order) and the function building each:

   1. Scenario & solver status         -> explain_scenario_and_status()
   2. Result availability warning      -> explain_result_availability()
   3. Demand-zone results              -> explain_demand_zones()
   4. Selected sources & blend ratios  -> explain_selected_sources()
   5. Unused sources                   -> explain_unused_sources()
   6. Active plants & transfer results -> explain_active_plants_and_transfers()
   7. Cost summary                     -> explain_cost_summary()
   8. Plant-inflow water quality       -> explain_water_quality()
   9. Binding constraints              -> explain_binding_constraints()
  10. Data flags & estimated values    -> explain_estimated_fields()
  11. Alternatives & sensitivity       -> explain_alternatives_and_sensitivity()
  12. Prototype disclaimer             -> PROTOTYPE_DISCLAIMER (constant)

Sections 3-11 only run for statuses in FULL_REPORT_STATUSES (currently only
`OPTIMAL`, per Report_Structure.md section 2 and the field map's non-optimal
handling rules - `TIME_LIMIT` feasible-solution handling is an open approval
question in LLM_Report_Scope.md section 13, so it is treated as status-only
for now, the same as INFEASIBLE/UNBOUNDED/ERROR). Sections 1, 2 and 12
always run, including for a status-only report.

Design note (field-name isolation)
-----------------------------------
Every JSON key this script depends on is named ONCE, in the constants near
the top of this file, and read from there everywhere else. If a field gets
renamed later, this is the only block that needs to change - the logic in
each explain_* function does not.

Required vs. optional input
----------------------------
Required (raises ExplainerInputError if missing): `status`, `scenarioId`.
Without these the report cannot even state what it is describing, so
generation stops per Report_Structure.md section 1's missing-field rule.

Everything else is optional. Missing or empty optional data never crashes
the generator; each section states plainly when a result was not provided,
per LLM_Report_Scope.md's "never invent a missing value" rule. A few gaps
(missing `bindingConstraintsSummary` on an OPTIMAL run, missing
`dataFlags`, missing `waterQuality.applies_to`) are not hard stops but do
surface as an inline validation warning within the affected section, per
Report_Structure.md's per-section missing-field rules.

Removed in this upgrade: the old source-selection "reason clause" logic
(cost ranking + capacity-binding heuristics that produced sentences like
"because it is the cheapest available source..."). Task 6 had flagged this
as "a design decision, not a guess" that needed team confirmation.
LLM_Report_Scope.md section 4 has since settled that question: the
deterministic template must not "create source-selection reasons." Selected
and unused sources are now reported as plain copied facts only.
"""

import json
import sys


# ---------------------------------------------------------------------------
# Field-name constants (see "field-name isolation" note above)
# ---------------------------------------------------------------------------

# Top-level names match results_adapter.py's adapted output (camelCase),
# not the raw external Results JSON Results_JSON_Field_Map.md documents -
# see the Task 21 module note above. Names unchanged by the adapter
# (status, objective, sources, plants) and every nested name are identical
# to the raw external contract, since the adapter never renames those.
F_SCENARIO_ID = "scenarioId"
F_SOLVED_AT = "solvedAt"
F_STATUS = "status"
F_OBJECTIVE = "objective"
F_CURRENCY = "currency"
F_UNIT = "unit"
F_COST_BREAKDOWN = "cost_breakdown"
F_SOURCES = "sources"
F_SELECTED = "selected"
F_UNUSED = "unused"
F_DEMAND_ZONES = "demandZones"
F_PLANTS = "plants"
F_ACTIVE = "active"
F_TRANSFER_PATHS = "transferPaths"
F_SOURCE_TO_PLANT = "source_to_plant"
F_PLANT_TO_ZONE = "plant_to_zone"
F_WATER_QUALITY = "waterQuality"
F_APPLIES_TO = "applies_to"
F_BY_PLANT = "by_plant"
F_BINDING_SUMMARY = "bindingConstraintsSummary"
F_ALTERNATIVES = "alternativeFeasibleSolutions"
F_SENSITIVITY = "sensitivityToKeyAssumptions"
F_DATA_FLAGS = "dataFlags"

# Report_Structure.md section 1: stop and return a validation-error report
# (here, an ExplainerInputError) if either of these is missing.
REQUIRED_TOP_LEVEL_FIELDS = [F_STATUS, F_SCENARIO_ID]

# ---------------------------------------------------------------------------
# Task 91: bridge the real, current results_adapter.py output (which nests
# scenario_id under scenario.scenario_id and the solver status under
# solver.status) onto the flat scenarioId/status shape every function below
# was written against. This mirrors the same normalization pattern already
# used in supabase_repository.normalize_output_columns() for exactly this
# class of problem: old code, real nested shape, minimal-surface-area fix.
#
# "status" here has always unambiguously meant the SOLVER status
# (FULL_REPORT_STATUSES = {"OPTIMAL"}) -- never the scenario lifecycle
# status (draft/ready/solved) -- so solver.status is read, not scenario.status.
#
# A dict that already has top-level scenarioId/status (the old, pre-v1 shape
# still used by some existing fixtures/tests) is left untouched, so this is
# purely additive and does not break anything already passing.
# ---------------------------------------------------------------------------
def _normalize_v1_adapted_results(data: dict) -> dict:
    """Return a shallow copy of ``data`` with the real, current
    results_adapter.py output shape bridged onto the flat shape every
    function below was written against -- see the module note above this
    function's definition for why this normalization pattern was chosen.

    Confirmed against: (1) results_adapter.py (master) run on the real
    output_contract_v1.json fixture, and (2) real solved rows pulled
    directly from Supabase's milp_model_output table. A dict that already
    has the old flat fields is left untouched wherever those fields are
    already present, so this stays purely additive.
    """
    if not isinstance(data, dict):
        return data

    normalized = dict(data)

    # --- scenarioId / status -------------------------------------------
    if F_SCENARIO_ID not in normalized:
        scenario = data.get("scenario")
        if isinstance(scenario, dict) and "scenario_id" in scenario:
            normalized[F_SCENARIO_ID] = scenario["scenario_id"]

    if F_STATUS not in normalized:
        solver = data.get("solver")
        if isinstance(solver, dict) and "status" in solver:
            normalized[F_STATUS] = solver["status"]

    # --- objective (real: summary.costs, no currency field exists) ------
    if F_OBJECTIVE not in normalized:
        summary = data.get("summary")
        if isinstance(summary, dict) and isinstance(summary.get("costs"), dict):
            costs = summary["costs"]
            normalized[F_OBJECTIVE] = {
                "total_cost": costs.get("total_cost"),
                F_CURRENCY: None,  # confirmed: no currency field in real output
            }

    # --- demandZones (real: delivered_ml_per_day/unmet_demand_ml_per_day,
    # no demand_ml_per_day or volume_supplied_ml_per_day field exists) -----
    if F_DEMAND_ZONES in normalized and isinstance(normalized[F_DEMAND_ZONES], list):
        remapped_zones = []
        for z in normalized[F_DEMAND_ZONES]:
            if not isinstance(z, dict):
                continue
            remapped = dict(z)
            delivered = z.get("delivered_ml_per_day")
            unmet = z.get("unmet_demand_ml_per_day")
            remapped.setdefault("volume_supplied_ml_per_day", delivered)
            if "demand_ml_per_day" not in remapped and delivered is not None and unmet is not None:
                remapped["demand_ml_per_day"] = delivered + unmet
            remapped_zones.append(remapped)
        normalized[F_DEMAND_ZONES] = remapped_zones

    # --- sources.selected/unused (real: one flat list + selection_status)
    if F_SOURCES in normalized and isinstance(normalized[F_SOURCES], list):
        selected, unused = [], []
        for s in normalized[F_SOURCES]:
            if not isinstance(s, dict):
                continue
            remapped = dict(s)
            # Real per-source field names -> old field names this file reads.
            remapped.setdefault("percent_of_blend", s.get("utilisation_percent"))
            remapped.setdefault("volume_drawn_ml_per_day", s.get("withdrawal_ml_per_day"))
            remapped.setdefault("draw_cost", s.get("total_source_cost"))
            # source_name never exists in real output; every read site
            # already falls back to source_id via `or s.get("source_id")`.
            if s.get("selection_status") == "SELECTED":
                selected.append(remapped)
            else:
                unused.append(remapped)
        normalized[F_SOURCES] = {F_SELECTED: selected, F_UNUSED: unused}

    # --- plants.active/inactive (real: one flat list + activated bool) --
    if F_PLANTS in normalized and isinstance(normalized[F_PLANTS], list):
        active, inactive = [], []
        for p in normalized[F_PLANTS]:
            if not isinstance(p, dict):
                continue
            remapped = dict(p)
            remapped.setdefault("volume_processed_ml_per_day", p.get("throughput_ml_per_day"))
            remapped.setdefault("treatment_cost", p.get("total_plant_cost"))
            remapped.setdefault("treatment_cost_per_ml", None)  # not in real output
            if p.get("activated"):
                active.append(remapped)
            else:
                inactive.append(remapped)
        normalized[F_PLANTS] = {F_ACTIVE: active, "inactive": inactive}

    # --- transferPaths (real: flows.source_to_plant / .plant_to_zone) ---
    if F_TRANSFER_PATHS not in normalized:
        flows = data.get("flows")
        if isinstance(flows, dict):
            def _with_active(paths):
                out = []
                for p in paths or []:
                    p = dict(p)
                    p.setdefault("active", p.get("flow_ml_per_day", 0) not in (0, 0.0, None))
                    out.append(p)
                return out

            normalized[F_TRANSFER_PATHS] = {
                F_SOURCE_TO_PLANT: _with_active(flows.get(F_SOURCE_TO_PLANT)),
                F_PLANT_TO_ZONE: _with_active(flows.get(F_PLANT_TO_ZONE)),
            }

    # --- waterQuality (real: quality.plant_inflow, a LIST of plants each
    # with a "parameters" LIST) -> by_plant, a DICT keyed by plant_id of
    # DICTs keyed by parameter name, the shape every read site expects. ---
    if F_WATER_QUALITY not in normalized:
        quality = data.get("quality")
        if isinstance(quality, dict) and isinstance(quality.get("plant_inflow"), list):
            by_plant = {}
            for plant_entry in quality["plant_inflow"]:
                if not isinstance(plant_entry, dict):
                    continue
                plant_id = plant_entry.get("plant_id")
                params = {}
                for param in plant_entry.get("parameters") or []:
                    if not isinstance(param, dict) or not param.get("parameter_id"):
                        continue
                    params[param["parameter_id"]] = {
                        "value": param.get("reported_value"),
                        "unit": param.get("reported_unit"),
                        "constraint_min": param.get("model_min"),
                        "constraint_max": param.get("model_max"),
                        "safety_margin_percent": param.get("safety_margin_percent"),
                        "status": (
                            "PASS" if param.get("within_limits") is True
                            else "FAIL" if param.get("within_limits") is False
                            else None
                        ),
                    }
                if plant_id:
                    by_plant[plant_id] = params
            normalized[F_WATER_QUALITY] = {
                F_APPLIES_TO: quality.get("applies_to"),
                F_BY_PLANT: by_plant,
            }

    return normalized

# Report_Structure.md section 2 / Results_JSON_Field_Map.md "Non-optimal
# runs": only OPTIMAL currently permits the full 12-section report.
FULL_REPORT_STATUSES = {"OPTIMAL"}

# Per Template_QualityMargins.md unit rules
QUALITY_UNIT_RULES = {
    "pH": None,                  # no concentration unit
    "alkalinity": "mg/L CaCO3",
    "turbidity": "NTU",
}
EXPECTED_QUALITY_PARAMETERS = list(QUALITY_UNIT_RULES.keys())

# Report_Structure.md, "Plant-inflow water-quality results" - mandatory
# every time water_quality is reported.
WATER_QUALITY_STAGE_NOTE = (
    "These quality results describe the blend arriving at plant inflow. They "
    "were checked against the modelled plant-inflow constraints and are not "
    "final post-treatment drinking-water results."
)

# Report_Structure.md, "Prototype disclaimer" - always present, section 12.
PROTOTYPE_DISCLAIMER = (
    "AquaBlend is a public-data decision-support proof-of-concept. This "
    "report does not replace qualified operators, engineers, regulators, or "
    "health authorities."
)


class ExplainerInputError(ValueError):
    """Raised when a required field is missing from the input JSON."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_input(data: dict) -> None:
    """Raise ExplainerInputError with a clear message if a required field
    is missing. Called once, before any explain_* function runs. Per
    Report_Structure.md section 1, `status` and `scenarioId` are the only
    fields whose absence stops report generation outright."""
    if not isinstance(data, dict):
        raise ExplainerInputError("Input must be a JSON object (Python dict).")

    missing = [f for f in REQUIRED_TOP_LEVEL_FIELDS if f not in data]
    if missing:
        raise ExplainerInputError(
            f"Missing required field(s): {', '.join(missing)}. "
            "Cannot generate a report without these."
        )


def _format_money(value, currency) -> str:
    """Format a numeric amount with a thousands separator and its currency,
    when a currency is given. Never guesses a currency (Results_JSON_Field_Map.md
    lists objective.currency as the only currency source in the contract),
    and never forces a decimal precision the JSON didn't actually report -
    `{:,.2f}` would round 235.456 to 235.46 and pad a plain 400 into 400.00,
    both of which invent digits that aren't in the exact structured value."""
    suffix = f" {currency}" if currency else ""
    return f"${value:,}{suffix}"


def _source_data_flags(data: dict) -> dict:
    """Maps source_id -> its data_flags.sources[] entry, per the confirmed
    output contract (Section 3.11). Provenance is echoed straight from the
    database view per source, so 'is this estimated' is now a direct
    boolean lookup rather than the old free-text substring matching this
    script used against a flat estimated_fields[] list - that approach was
    flagged as an over-broad hack (see the old 'all sources' open item) and
    is retired now that a clean per-source signal exists."""
    entries = data.get(F_DATA_FLAGS, {}).get(F_SOURCES, []) or []
    return {e.get("source_id"): e for e in entries if e.get("source_id")}


def explain_scenario_and_status(data: dict) -> str:
    """Report_Structure.md section 1. scenario_id and status are always
    present here (validate_input already enforced that); solved_at is
    included only when present."""
    scenario_id = data.get(F_SCENARIO_ID)
    status = data.get(F_STATUS)
    lines = [f"Scenario: {scenario_id}.", f"Solver status: {status}."]
    solved_at = data.get(F_SOLVED_AT)
    if solved_at:
        lines.append(f"Solved at: {solved_at}.")
    return " ".join(lines)


def explain_result_availability(data: dict) -> str:
    """Report_Structure.md section 2. Only OPTIMAL is currently confirmed
    usable for a full recommendation (see FULL_REPORT_STATUSES note)."""
    status = data.get(F_STATUS)
    if not status:
        return "The result state is unknown because no solver status was reported."
    if status == "OPTIMAL":
        return (
            "The solver produced a confirmed optimal solution under the "
            "current model and input assumptions."
        )
    return (
        f"Solver status is {status}. This result is not confirmed as usable "
        "for a final recommendation."
    )


def explain_demand_zones(data: dict) -> str:
    """Report_Structure.md section 3."""
    zones = data.get(F_DEMAND_ZONES) or []
    if not zones:
        return "No demand-zone result was provided."

    lines = []
    for zone in zones:
        zone_id = zone.get("zone_id")
        name = zone.get("zone_name") or zone_id
        demand = zone.get("demand_ml_per_day")
        supplied = zone.get("volume_supplied_ml_per_day")
        demand_clause = f"required demand {demand} ML/day" if demand is not None else "required demand not reported"
        supplied_clause = f"supplied volume {supplied} ML/day" if supplied is not None else "supplied volume not reported"
        lines.append(f"{name}: {demand_clause}, {supplied_clause}.")
    return "\n\n".join(lines)


def explain_selected_sources(data: dict) -> str:
    """Report_Structure.md section 4. Copies facts only - no reason clause
    (LLM_Report_Scope.md section 4 forbids the template from "creating
    source-selection reasons")."""
    selected = (data.get(F_SOURCES) or {}).get(F_SELECTED) or []
    if not selected:
        return "No selected-source result was provided."

    currency = (data.get(F_OBJECTIVE) or {}).get(F_CURRENCY)
    source_flags = _source_data_flags(data)
    # Ordering by blend share is a presentation choice only, not a claim
    # about why a source was chosen.
    ordered = sorted(selected, key=lambda s: s.get("percent_of_blend", 0), reverse=True)

    lines = []
    for s in ordered:
        source_id = s.get("source_id")
        name = s.get("source_name") or source_id
        pct = s.get("percent_of_blend")
        vol = s.get("volume_drawn_ml_per_day")
        cost = s.get("cost_per_ml")
        draw_cost = s.get("draw_cost")

        pct_clause = f"{pct}% of the blend" if pct is not None else "an unreported share of the blend"
        vol_clause = f"{vol} ML/day" if vol is not None else "an unreported volume"
        parts = [f"{name} supplied {vol_clause}, {pct_clause}."]

        if cost is not None:
            has_estimated = bool(source_flags.get(source_id, {}).get("has_estimated_values"))
            estimated_tag = " (estimated)" if has_estimated else ""
            parts.append(f"Cost per ML: {_format_money(cost, currency)}{estimated_tag}.")
        if draw_cost is not None:
            parts.append(f"Draw cost: {_format_money(draw_cost, currency)}.")

        lines.append(" ".join(parts))

    return "\n\n".join(lines)


def explain_unused_sources(data: dict) -> str:
    """Report_Structure.md section 5. `sources.unused[].reason` ownership is
    unconfirmed (LLM_Report_Scope.md section 10), so it is never rendered -
    only that the source was not selected."""
    unused = (data.get(F_SOURCES) or {}).get(F_UNUSED) or []
    if not unused:
        return "No unused-source result was provided."

    lines = []
    for s in unused:
        name = s.get("source_name") or s.get("source_id")
        lines.append(f"{name} was not selected.")
    return "\n\n".join(lines)


def explain_active_plants_and_transfers(data: dict) -> str:
    """Report_Structure.md section 6."""
    plants = (data.get(F_PLANTS) or {}).get(F_ACTIVE) or []
    currency = (data.get(F_OBJECTIVE) or {}).get(F_CURRENCY)

    if not plants:
        plant_lines = ["No active-plant result was provided."]
    else:
        plant_lines = []
        for p in plants:
            name = p.get("plant_name") or p.get("plant_id")
            vol = p.get("volume_processed_ml_per_day")
            vol_clause = f"{vol} ML/day" if vol is not None else "an unreported volume"
            parts = [f"{name} processed {vol_clause}."]
            cost_per_ml = p.get("treatment_cost_per_ml")
            treatment_cost = p.get("treatment_cost")
            if cost_per_ml is not None:
                parts.append(f"Treatment cost per ML: {_format_money(cost_per_ml, currency)}.")
            if treatment_cost is not None:
                parts.append(f"Total treatment cost: {_format_money(treatment_cost, currency)}.")
            plant_lines.append(" ".join(parts))

    # Transfer detail is a subpart of this section - omitted entirely (not
    # even a fallback line) when transfer_paths is missing, per
    # Report_Structure.md's missing-field rule for this section.
    transfer_paths = data.get(F_TRANSFER_PATHS)
    transfer_lines = []
    if transfer_paths:
        selected = {s.get("source_id"): s for s in (data.get(F_SOURCES) or {}).get(F_SELECTED) or []}
        unused = {s.get("source_id"): s for s in (data.get(F_SOURCES) or {}).get(F_UNUSED) or []}
        plant_index = {p.get("plant_id"): p for p in plants}
        zone_index = {z.get("zone_id"): z for z in data.get(F_DEMAND_ZONES) or []}

        for path in transfer_paths.get(F_SOURCE_TO_PLANT) or []:
            s = selected.get(path.get("source_id")) or unused.get(path.get("source_id"))
            from_name = (s.get("source_name") if s else None) or path.get("source_id")
            p = plant_index.get(path.get("plant_id"))
            to_name = (p.get("plant_name") if p else None) or path.get("plant_id")
            flow = path.get("flow_ml_per_day")
            active = path.get("active")
            transfer_lines.append(f"{from_name} to {to_name}: {flow} ML/day ({'active' if active else 'inactive'}).")

        for path in transfer_paths.get(F_PLANT_TO_ZONE) or []:
            p = plant_index.get(path.get("plant_id"))
            from_name = (p.get("plant_name") if p else None) or path.get("plant_id")
            z = zone_index.get(path.get("zone_id"))
            to_name = (z.get("zone_name") if z else None) or path.get("zone_id")
            flow = path.get("flow_ml_per_day")
            active = path.get("active")
            transfer_lines.append(f"{from_name} to {to_name}: {flow} ML/day ({'active' if active else 'inactive'}).")

    lines = list(plant_lines)
    if transfer_lines:
        lines.append("Transfer results:\n\n" + "\n\n".join(transfer_lines))
    return "\n\n".join(lines)


def explain_cost_summary(data: dict) -> str:
    """Report_Structure.md section 7. Only called for statuses in
    FULL_REPORT_STATUSES; never recalculates a total, only copies the
    objective block."""
    objective = data.get(F_OBJECTIVE)
    if not objective or objective.get("total_cost") is None:
        return "Cost summary is unavailable."

    currency = objective.get(F_CURRENCY)
    unit = objective.get(F_UNIT)
    total_clause = _format_money(objective["total_cost"], currency)
    lines = [f"Total cost: {total_clause}" + (f" ({unit})." if unit else ".")]

    breakdown = objective.get(F_COST_BREAKDOWN) or {}
    breakdown_labels = [
        ("source_activation_cost", "Source activation cost"),
        ("plant_activation_cost", "Plant activation cost"),
        ("source_draw_cost", "Source draw cost"),
        ("plant_treatment_cost", "Plant treatment cost"),
    ]
    breakdown_parts = [
        f"{label}: {_format_money(breakdown[key], currency)}."
        for key, label in breakdown_labels
        if breakdown.get(key) is not None
    ]
    if breakdown_parts:
        lines.append("Cost breakdown: " + " ".join(breakdown_parts))

    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Task 7 - Binding constraints explanation (Template_BindingConstraints.md)
#
# Rebuilt against the confirmed model_output_contract.json (Section 3.8):
#   - Constraint names are now prefix-based, not suffix-based, e.g.
#     source_capacity_yarra_kew (was yarra_kew_capacity), plant_capacity_
#     facility_1 (was facility_1_batch_capacity), quality_range_pH_facility_1
#     (was pH_range - now carries a plant id, since quality is reported
#     per-plant under water_quality.by_plant).
#   - treatment_facilities became plants; facility_id/facility_name became
#     plant_id/plant_name; there is no batch count anymore (the confirmed
#     formulation has zero integer variables, per diagnostics.
#     num_integer_variables), so all "N batches" wording is removed.
#   - Estimated-value disclosure no longer reads a flat estimated_fields[]
#     string list. Per the output spec's "known gaps" (Section 6), only
#     source fields carry a provenance mechanism (data_flags.sources[]);
#     demand, plant capacity, link capacity, and quality limits are defined
#     in the scenario file and have none. So only source_capacity lines can
#     honestly disclose "(estimated)" here; the demand/plant_capacity/
#     water_quality categories no longer attempt to guess at this.
# ---------------------------------------------------------------------------

CATEGORY_ORDER = [
    "demand", "source_capacity", "plant_capacity", "link_capacity", "water_quality",
]


def _classify_constraint(name: str) -> str:
    """Returns the category a constraint NAME belongs to, by pattern alone -
    independent of whether a matching entry actually exists. Classification
    drives Output-composition ordering; lookup success is decided separately
    when rendering (No-matching-entry case). Matches the confirmed contract's
    prefix-based naming (Section 3.8)."""
    if name.startswith("demand_satisfaction_"):
        return "demand"
    if name.startswith("source_capacity_"):
        return "source_capacity"
    if name.startswith("plant_capacity_"):
        return "plant_capacity"
    if name.startswith("link_capacity_"):
        return "link_capacity"
    if name.startswith("quality_range_"):
        return "water_quality"
    return "unknown"


def _split_quality_name(name: str) -> tuple:
    """quality_range_<parameter>_<plant_id> - parameter is one of the three
    known quality parameters, so split on the first match rather than
    guessing where the parameter ends and the plant id begins."""
    remainder = name[len("quality_range_"):]
    for param in EXPECTED_QUALITY_PARAMETERS:
        prefix = f"{param}_"
        if remainder.startswith(prefix):
            return param, remainder[len(prefix):]
        if remainder == param:
            return param, None
    return None, None


def _render_constraint(category, name, selected, unused, demand_zones,
                        plants, links, quality_by_plant, source_flags) -> str:
    """Renders one binding-constraint sentence. Falls back to the Unknown
    wording if the id encoded in `name` has no matching entry at all
    (No-matching-entry case); drops individual detail clauses, rather than
    the whole sentence, when an entry IS found but missing a field
    (Missing-field case)."""

    unknown_wording = f"The solution was limited by {name} (no plain-language mapping available)."

    if category == "demand":
        zone_id = name[len("demand_satisfaction_"):]
        zone = demand_zones.get(zone_id)
        if not zone:
            return unknown_wording
        vol = zone.get("demand_ml_per_day")
        if vol is None:
            return (
                f"The solution was limited by the water demand for {zone_id}: the full "
                f"volume needed by {zone_id} had to be delivered, leaving no room to "
                "supply any less."
            )
        return (
            f"The solution was limited by the water demand for {zone_id}: the full "
            f"{vol} ML/day needed by {zone_id} had to be delivered, "
            "leaving no room to supply any less."
        )

    if category == "source_capacity":
        # Names the specific other selected source(s), rather than a vague
        # "additional water had to come from other sources" clause - a real
        # LLM rewrite inverted that wording into "no extra water could come
        # from other sources" (the opposite meaning). Stating who supplied
        # the remainder removes the ambiguity that inversion exploited.
        source_id = name[len("source_capacity_"):]
        s = selected.get(source_id)
        if not s:
            return unknown_wording
        source_name = s.get("source_name") or source_id
        vol = s.get("volume_drawn_ml_per_day")
        binding_label = f"the available capacity of {source_name}"

        other_names = [
            sel.get("source_name") or sid
            for sid, sel in selected.items()
            if sid != source_id
        ]
        if len(other_names) == 1:
            other_clause = (
                f"The remaining demand was supplied by the other selected "
                f"source, {other_names[0]}."
            )
        elif len(other_names) > 1:
            other_clause = (
                "The remaining demand was supplied by the other selected "
                "sources: " + ", ".join(other_names) + "."
            )
        else:
            other_clause = (
                "No other selected source was available to supply the "
                "remaining demand."
            )

        if vol is None:
            return (
                f"The solution was limited by {binding_label}: {source_name} "
                f"reached its maximum available capacity. {other_clause}"
            )
        has_estimated = bool(source_flags.get(source_id, {}).get("has_estimated_values"))
        tag = ", estimated" if has_estimated else ""
        return (
            f"The solution was limited by {binding_label}: {source_name} "
            f"reached its maximum available capacity ({vol} ML/day{tag}). "
            f"{other_clause}"
        )

    if category == "plant_capacity":
        plant_id = name[len("plant_capacity_"):]
        p = plants.get(plant_id)
        if not p:
            return unknown_wording
        plant_name = p.get("plant_name") or plant_id
        vol = p.get("volume_processed_ml_per_day")
        binding_label = f"the processing capacity of {plant_name}"
        if vol is None:
            return (
                f"The solution was limited by {binding_label}: {plant_name} was "
                "already treating as much as it can handle, leaving no spare capacity."
            )
        return (
            f"The solution was limited by {binding_label}: {plant_name} was "
            f"already treating as much as it can handle ({vol} ML/day), leaving no "
            "spare capacity."
        )

    if category == "link_capacity":
        # link_capacity_<from>_to_<to> - the id portion is exactly the
        # matching entry's own path_id (per the input spec's own naming
        # convention: path_id is "<from>_to_<to>"), so no from/to parsing
        # is needed, just a direct lookup. The output contract does not
        # echo a link's own maximum_flow_ml_per_day (that's input-only),
        # so this can report the flow that was reached, not a specific cap.
        path_id = name[len("link_capacity_"):]
        entry = links.get(path_id)
        if not entry:
            return unknown_wording
        layer, path = entry
        vol = path.get("flow_ml_per_day")
        if layer == "source_to_plant":
            source_id = path.get("source_id")
            plant_id = path.get("plant_id")
            s = selected.get(source_id) or unused.get(source_id)
            from_name = (s.get("source_name") if s else None) or source_id
            p = plants.get(plant_id)
            to_name = (p.get("plant_name") if p else None) or plant_id
        else:
            plant_id = path.get("plant_id")
            zone_id = path.get("zone_id")
            p = plants.get(plant_id)
            from_name = (p.get("plant_name") if p else None) or plant_id
            z = demand_zones.get(zone_id)
            to_name = (z.get("zone_name") if z else None) or zone_id
        binding_label = f"the connection from {from_name} to {to_name}"
        if vol is None:
            return (
                f"The solution was limited by {binding_label}: this link was carrying "
                "as much flow as it can handle, so any additional water had to route "
                "another way."
            )
        return (
            f"The solution was limited by {binding_label}: this link was carrying as "
            f"much flow as it can handle ({vol} ML/day), so any additional water had to "
            "route another way."
        )

    if category == "water_quality":
        parameter, plant_id = _split_quality_name(name)
        if parameter is None or plant_id is None:
            return unknown_wording
        q = quality_by_plant.get(plant_id, {}).get(parameter)
        if not q:
            return unknown_wording
        cmin, cmax, unit = q.get("constraint_min"), q.get("constraint_max"), q.get("unit")
        binding_label = f"the {parameter} limit at {plant_id}"
        if cmin is None or cmax is None or unit is None:
            return (
                f"The solution was limited by {binding_label}: {parameter} sat right "
                "at the edge of its modelled constraint range, so the blend could not "
                "be pushed any further."
            )
        return (
            f"The solution was limited by {binding_label}: {parameter} sat right at "
            f"the edge of its modelled constraint range ({cmin}\u2013{cmax} {unit}), "
            "so the blend could not be pushed any further."
        )

    return unknown_wording  # true Unknown (name matches no pattern at all)


def explain_binding_constraints(data: dict) -> str:
    """Report_Structure.md section 9. Only called for statuses in
    FULL_REPORT_STATUSES, so a missing binding_constraints_summary here
    always means missing-from-an-OPTIMAL-result, per the field's own
    missing-field rule."""
    missing_field = F_BINDING_SUMMARY not in data
    binding = data.get(F_BINDING_SUMMARY) or []

    if not binding:
        body = "No binding inequality or ranged constraint was reported for this scenario."
        if missing_field:
            return (
                "Validation warning: bindingConstraintsSummary is missing from an "
                "OPTIMAL result.\n\n" + body
            )
        return body

    sources = data.get(F_SOURCES, {}) or {}
    selected = {s["source_id"]: s for s in sources.get(F_SELECTED, []) or []}
    unused = {s["source_id"]: s for s in sources.get(F_UNUSED, []) or []}
    demand_zones = {z["zone_id"]: z for z in data.get(F_DEMAND_ZONES, []) or []}
    plants = {
        p["plant_id"]: p
        for p in data.get(F_PLANTS, {}).get(F_ACTIVE, []) or []
    }
    transfer_paths = data.get(F_TRANSFER_PATHS, {}) or {}
    links = {}
    for path in transfer_paths.get(F_SOURCE_TO_PLANT, []) or []:
        if path.get("path_id"):
            links[path["path_id"]] = (F_SOURCE_TO_PLANT, path)
    for path in transfer_paths.get(F_PLANT_TO_ZONE, []) or []:
        if path.get("path_id"):
            links[path["path_id"]] = (F_PLANT_TO_ZONE, path)
    quality_by_plant = data.get(F_WATER_QUALITY, {}).get(F_BY_PLANT, {}) or {}
    source_flags = _source_data_flags(data)

    # Output composition: group by fixed category order; within a category,
    # keep the order names appear in binding_constraints_summary. Names that
    # match no category pattern at all (true Unknown) go last, in list order.
    buckets = {cat: [] for cat in CATEGORY_ORDER}
    unknown_bucket = []
    for name in binding:
        category = _classify_constraint(name)
        (unknown_bucket if category == "unknown" else buckets[category]).append(name)

    lines = []
    for category in CATEGORY_ORDER:
        for name in buckets[category]:
            lines.append(_render_constraint(
                category, name, selected, unused, demand_zones,
                plants, links, quality_by_plant, source_flags
            ))
    for name in unknown_bucket:
        lines.append(f"The solution was limited by {name} (no plain-language mapping available).")

    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Task 8 - Water-quality & safety-margin explanation (Template_QualityMargins.md)
# ---------------------------------------------------------------------------

def explain_water_quality(data: dict) -> str:
    """Report_Structure.md section 8. Every render path that reports actual
    parameter values ends with WATER_QUALITY_STAGE_NOTE - the mandatory
    plant-inflow-not-final-drinking-water disclosure."""
    wq = data.get(F_WATER_QUALITY) or {}
    by_plant = wq.get(F_BY_PLANT) or {}

    if not by_plant:
        return "No water-quality result was provided."

    applies_to = wq.get(F_APPLIES_TO)
    if not applies_to:
        return (
            "Validation warning: waterQuality.applies_to is missing, so these "
            "quality results cannot be safely interpreted and are not reported."
        )

    lines = [f"These quality results apply to: {applies_to}."]
    # Sorted, not insertion-order: report order must never depend on
    # whatever order an upstream producer happened to serialise plants in.
    for plant_id, after in sorted(by_plant.items()):
        after = after or {}

        # Missing parameters - never assume a pass
        for p in EXPECTED_QUALITY_PARAMETERS:
            if p not in after:
                lines.append(f"{p} at {plant_id} was not reported in the results and could not be assessed.")

        # Unit validation
        for param, q in after.items():
            if param not in QUALITY_UNIT_RULES:
                continue
            expected_unit = QUALITY_UNIT_RULES[param]
            actual_unit = q.get("unit")
            if expected_unit is None:
                if actual_unit not in (None, "pH", ""):
                    lines.append(
                        f"Note: unit mismatch for {param} at {plant_id} - expected no "
                        f"concentration unit, got '{actual_unit}'."
                    )
            elif actual_unit != expected_unit:
                lines.append(
                    f"Note: unit mismatch for {param} at {plant_id} - expected "
                    f"'{expected_unit}', got '{actual_unit}'."
                )

        passing, violations = [], []
        for param, q in after.items():
            status = q.get("status")
            margin = q.get("safety_margin_percent")
            is_violation = status == "FAIL" or (margin is not None and margin < 0)
            (violations if is_violation else passing).append((param, q))

        if violations:
            for param, q in violations:
                lines.append(
                    f"Not all plant-inflow blend quality parameters passed at {plant_id}. "
                    f"{param} breached its allowed range: {q.get('value')} {q.get('unit')} "
                    f"against a permitted {q.get('constraint_min')}-{q.get('constraint_max')} "
                    f"{q.get('unit')} (safety margin {q.get('safety_margin_percent')}%). This is "
                    "recorded as a FAIL against the modelled plant-inflow constraint range."
                )
        elif passing:
            tightest = min(passing, key=lambda pq: pq[1].get("safety_margin_percent", float("inf")))
            widest = max(passing, key=lambda pq: pq[1].get("safety_margin_percent", float("-inf")))
            t_name, t_q = tightest
            lines.append(
                f"All tested plant-inflow blend quality parameters passed at {plant_id}. "
                f"{t_name} was closest to its limit, with a safety margin of "
                f"{t_q.get('safety_margin_percent')}%."
            )
            if widest[0] != tightest[0]:
                w_name, w_q = widest
                lines.append(f"The widest margin at {plant_id} was on {w_name} at {w_q.get('safety_margin_percent')}%.")

    lines.append(WATER_QUALITY_STAGE_NOTE)
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Task 9 - New sections (not covered by Tasks 6/7/8)
# ---------------------------------------------------------------------------

def explain_sensitivity(data: dict) -> str:
    """Reports sensitivity_to_key_assumptions[]. Added after Task 13's
    evaluation rubric (evidence table, Section 2) listed this field as
    something explanations are checked against - it wasn't covered by
    Task 6, 7, 8, or the original Task 9 output.

    Optional field: absence or malformed entries are handled gracefully,
    never invented (per rubric criterion C5, no invented reasons)."""
    items = data.get(F_SENSITIVITY, []) or []
    lines = []
    for item in items:
        assumption = item.get("assumption")
        impact = item.get("impact")
        if not assumption or not impact:
            # Don't fabricate a missing half of the pair - skip rather than guess.
            continue
        lines.append(f"This result is sensitive to {assumption}: {impact}.")

    if not lines:
        return "No sensitivity information was reported for this scenario."
    return "\n\n".join(lines)


def explain_estimated_fields(data: dict):
    """Report_Structure.md section 10. Returns None when the section must be
    omitted entirely (data_flags present but carries nothing to disclose);
    returns a validation-warning string when data_flags is missing entirely,
    since estimate/provenance disclosures then cannot be checked at all."""
    if F_DATA_FLAGS not in data or data.get(F_DATA_FLAGS) is None:
        return (
            "Validation warning: dataFlags is missing, so estimated-value "
            "and provenance disclosures could not be checked."
        )

    flags = data.get(F_DATA_FLAGS) or {}
    source_entries = flags.get(F_SOURCES) or []
    notes = flags.get("notes") or []

    estimated_sources = [e for e in source_entries if e.get("has_estimated_values")]

    if not estimated_sources and not notes:
        return None

    lines = []
    if estimated_sources:
        bullets = []
        for e in estimated_sources:
            source_id = e.get("source_id", "unknown source")
            provenance = e.get("provenance", {}) or {}
            estimated_fields = [k for k, v in provenance.items() if v == "estimate"]
            if estimated_fields:
                bullets.append(f"- {source_id}: {', '.join(estimated_fields)}")
            else:
                bullets.append(f"- {source_id}")
        lines.append(
            "The following sources have one or more estimated fields, and should be "
            "treated as provisional:\n" + "\n".join(bullets)
        )

    if notes:
        note_bullets = "\n".join(f"- {n}" for n in notes)
        lines.append(f"Additional notes on data provenance:\n{note_bullets}")

    return "\n\n".join(lines)


def explain_alternatives_and_sensitivity(data: dict):
    """Report_Structure.md section 11. Returns None when both arrays are
    missing or empty, since this subsection must be omitted entirely (unlike
    most other sections, which show a "not provided" fallback line)."""
    alternatives = data.get(F_ALTERNATIVES) or []
    sensitivity_items = [
        item for item in (data.get(F_SENSITIVITY) or [])
        if item.get("assumption") and item.get("impact")
    ]

    if not alternatives and not sensitivity_items:
        return None

    lines = []
    if alternatives:
        alt_lines = []
        for alt in alternatives:
            description = alt.get("description")
            if not description:
                continue
            parts = [f"{description}."]
            total_cost = alt.get("total_cost")
            diff = alt.get("cost_difference_from_optimal")
            notes = alt.get("notes")
            if total_cost is not None:
                parts.append(f"Total cost: {total_cost}.")
            if diff is not None:
                parts.append(f"Cost difference from optimal: {diff}.")
            if notes:
                parts.append(f"{notes}.")
            alt_lines.append(" ".join(parts))
        if alt_lines:
            lines.append("Alternative feasible solutions:\n\n" + "\n\n".join(alt_lines))

    if sensitivity_items:
        lines.append(explain_sensitivity(data))

    if not lines:
        return None
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Executive summary (AquaBlend final AI integration)
#
# A short, deterministic, operator-readable summary - distinct from the full
# 12-section report generate_explanation() builds. This is the ONLY text an
# LLM rewrite may ever touch; the full report is always deterministic. Never
# invents a figure that isn't in `data`; a missing value is stated as
# "not reported", never guessed or defaulted to zero. Written as short,
# complete sentences (not one comma-chained line): a status word directly
# followed by ", <number>" was found to false-positive-match
# llm_validator's Title-Case identifier pattern (e.g. "OPTIMAL, 500" reads
# as a two-word proper noun) - see Validation_Rules.md-style reasoning in
# llm_validator.py's _TITLE_CASE_IDENTIFIER_PATTERN. Ending each fact with
# a period rather than a comma avoids that class of false positive.
# ---------------------------------------------------------------------------

def _short_binding_constraint_label(data: dict, name: str) -> str | None:
    """A brief, few-word mention of one binding constraint - NOT the full
    sentence explain_binding_constraints() renders. Returns None when the
    id encoded in `name` has no matching entry (the No-matching-entry case
    also used by _render_constraint)."""
    category = _classify_constraint(name)
    selected = {
        s.get("source_id"): s
        for s in (data.get(F_SOURCES) or {}).get(F_SELECTED) or []
    }
    plants = {
        p.get("plant_id"): p
        for p in (data.get(F_PLANTS) or {}).get(F_ACTIVE) or []
    }
    demand_zones = {z.get("zone_id"): z for z in data.get(F_DEMAND_ZONES) or []}

    if category == "demand":
        zone_id = name[len("demand_satisfaction_"):]
        zone = demand_zones.get(zone_id)
        if not zone:
            return None
        return f"demand for {zone.get('zone_name') or zone_id}"
    if category == "source_capacity":
        source_id = name[len("source_capacity_"):]
        s = selected.get(source_id)
        if not s:
            return None
        return f"{s.get('source_name') or source_id}'s available capacity"
    if category == "plant_capacity":
        plant_id = name[len("plant_capacity_"):]
        p = plants.get(plant_id)
        if not p:
            return None
        return f"{p.get('plant_name') or plant_id}'s processing capacity"
    if category == "link_capacity":
        return "a source-to-plant or plant-to-zone connection"
    if category == "water_quality":
        parameter, plant_id = _split_quality_name(name)
        if parameter is None:
            return None
        return f"the {parameter} limit at {plant_id}"
    return None


def _closest_quality_margin(data: dict) -> tuple[str, str, float] | None:
    """(plant_id, parameter, safety_margin_percent) for the tightest
    reported plant-inflow quality margin, or None when no numeric margin
    was reported anywhere."""
    by_plant = (data.get(F_WATER_QUALITY) or {}).get(F_BY_PLANT) or {}
    tightest: tuple[str, str, float] | None = None
    for plant_id, parameters in sorted(by_plant.items()):
        for parameter, detail in (parameters or {}).items():
            margin = (detail or {}).get("safety_margin_percent")
            if not isinstance(margin, (int, float)):
                continue
            if tightest is None or margin < tightest[2]:
                tightest = (plant_id, parameter, margin)
    return tightest


def generate_executive_summary(data: dict) -> str:
    """Build a short, plain-language executive summary suitable for an LLM
    to lightly reword (see AI/explanations/prompts.py). Requires the same
    minimum fields as generate_explanation(): `status` and `scenarioId`.

    For an OPTIMAL result this reports, only when the underlying data is
    present (never guessed): the scenario id and solver status; whether
    demand was fully met; total cost; each selected source's blend share;
    the closest plant-inflow water-quality margin; one binding constraint;
    a provisional/estimated-data note; and one alternative or sensitivity
    finding. Targets roughly 80-150 words and never exceeds ~180."""
    data = _normalize_v1_adapted_results(data)
    validate_input(data)

    scenario_id = data.get(F_SCENARIO_ID)
    status = data.get(F_STATUS)

    if status not in FULL_REPORT_STATUSES:
        return (
            f"Scenario {scenario_id}: solver status {status}. No optimal "
            "solution is available to summarise."
        )

    paragraphs: list[str] = []

    # Scenario, status, demand, cost.
    zones = data.get(F_DEMAND_ZONES) or []
    demand = sum(z.get("demand_ml_per_day") or 0 for z in zones) or None
    supplied = sum(z.get("volume_supplied_ml_per_day") or 0 for z in zones) or None
    if demand is not None and supplied is not None:
        demand_sentence = (
            f"Demand was fully met: {supplied} ML/day supplied against "
            f"{demand} ML/day required."
            if supplied >= demand
            else (
                f"Demand was only partially met: {supplied} ML/day "
                f"supplied against {demand} ML/day required."
            )
        )
    else:
        demand_sentence = "Demand satisfaction was not reported."

    objective = data.get(F_OBJECTIVE) or {}
    currency = objective.get(F_CURRENCY)
    total_cost = objective.get("total_cost")
    cost_sentence = (
        f"Total cost was {_format_money(total_cost, currency)}."
        if total_cost is not None
        else "Total cost was not reported."
    )

    paragraphs.append(
        f"Scenario {scenario_id} reached solver status {status}. "
        f"{demand_sentence} {cost_sentence}"
    )

    # Selected sources and blend shares.
    selected = (data.get(F_SOURCES) or {}).get(F_SELECTED) or []
    ordered = sorted(selected, key=lambda s: s.get("percent_of_blend", 0), reverse=True)
    if ordered:
        parts = [
            f"{s.get('source_name') or s.get('source_id')}"
            + (f" at {s['percent_of_blend']}%" if s.get("percent_of_blend") is not None else "")
            for s in ordered
        ]
        if len(parts) == 1:
            source_clause = parts[0]
        else:
            source_clause = ", ".join(parts[:-1]) + f", and {parts[-1]}"
        paragraphs.append(f"The blend was supplied by {source_clause} of the total.")
    else:
        paragraphs.append("No selected-source result was provided.")

    # Closest plant-inflow water-quality margin, and one binding constraint.
    fact_sentences: list[str] = []
    margin = _closest_quality_margin(data)
    if margin is not None:
        plant_id, parameter, percent = margin
        fact_sentences.append(
            f"The closest water-quality safety margin was on {parameter} at "
            f"{plant_id}, with {percent}% margin at plant inflow."
        )

    binding = data.get(F_BINDING_SUMMARY) or []
    non_demand = [name for name in binding if _classify_constraint(name) != "demand"]
    for name in non_demand + binding:
        label = _short_binding_constraint_label(data, name)
        if label is not None:
            fact_sentences.append(f"A binding constraint was {label}.")
            break
    if fact_sentences:
        paragraphs.append(" ".join(fact_sentences))

    # Provisional / estimated-data note.
    source_entries = (data.get(F_DATA_FLAGS) or {}).get(F_SOURCES) or []
    if any(e.get("has_estimated_values") for e in source_entries):
        paragraphs.append(
            "Some source data is estimated, so this result is provisional."
        )

    # One alternative or sensitivity finding.
    alternatives = data.get(F_ALTERNATIVES) or []
    if alternatives:
        alt = alternatives[0]
        alt_cost = alt.get("total_cost")
        alt_diff = alt.get("cost_difference_from_optimal")
        if alt_cost is not None or alt_diff is not None:
            sentence = "An alternative solution"
            if alt_cost is not None:
                sentence += f" would cost {_format_money(alt_cost, currency)}"
            if alt_diff is not None:
                sentence += (
                    f", a difference of {_format_money(alt_diff, currency)} "
                    "from the optimal result"
                )
            paragraphs.append(sentence + ".")
    else:
        sensitivity_items = [
            item for item in (data.get(F_SENSITIVITY) or [])
            if item.get("assumption") and item.get("impact")
        ]
        if sensitivity_items:
            item = sensitivity_items[0]
            paragraphs.append(
                f"This result is sensitive to {item['assumption']}: {item['impact']}."
            )

    return " ".join(paragraphs)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_explanation(data: dict) -> str:
    """Build the complete deterministic report, per Report_Structure.md's
    fixed 12-section order. Accepts a Python dict already parsed from JSON.
    See generate_explanation_from_file for reading directly from a file."""
    data = _normalize_v1_adapted_results(data)
    validate_input(data)
    status = data.get(F_STATUS)

    sections = [
        ("Scenario & Solver Status", explain_scenario_and_status(data)),
        ("Result Availability", explain_result_availability(data)),
    ]

    if status in FULL_REPORT_STATUSES:
        sections.append(("Demand-Zone Results", explain_demand_zones(data)))
        sections.append(("Selected Sources & Blend Ratios", explain_selected_sources(data)))
        sections.append(("Unused Sources", explain_unused_sources(data)))
        sections.append(("Active Plants & Transfer Results", explain_active_plants_and_transfers(data)))
        sections.append(("Cost Summary", explain_cost_summary(data)))
        sections.append(("Plant-Inflow Water Quality", explain_water_quality(data)))
        sections.append(("Binding Constraints", explain_binding_constraints(data)))

        estimated_body = explain_estimated_fields(data)
        if estimated_body is not None:
            sections.append(("Data Flags & Estimated Values", estimated_body))

        alternatives_body = explain_alternatives_and_sensitivity(data)
        if alternatives_body is not None:
            sections.append(("Alternatives & Sensitivity", alternatives_body))

    sections.append(("Prototype Disclaimer", PROTOTYPE_DISCLAIMER))

    return "\n\n".join(f"## {title}\n\n{body}" for title, body in sections if body)


def generate_explanation_from_file(path: str) -> str:
    """Script accepts a JSON file per Task 9's original checklist."""
    with open(path, "r") as f:
        data = json.load(f)
    return generate_explanation(data)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python json_explainer.py <path-to-results.json>")
        sys.exit(1)
    try:
        print(generate_explanation_from_file(sys.argv[1]))
    except ExplainerInputError as e:
        print(f"Input error: {e}")
        sys.exit(1)

