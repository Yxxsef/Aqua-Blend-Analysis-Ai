"""
json_explainer.py

AquaBlend | Analysis & AI | Sprint 1 | Task 9
Build and test the fallback explanation generator.

Reads a Results JSON matching the contract defined in the AquaBlend MILP
Configuration document (Section 8) and produces a complete, operator-
readable, plain-language explanation. Works entirely offline - no external
LLM API call - per Task 9's own requirement.

This file wires together three templates that were each designed and
hand-validated separately, then adds the sections Task 9 needed that
didn't exist yet:

  Task 6  Template_SourceSelection.md      -> explain_sources()
  Task 7  Template_BindingConstraints.md   -> explain_binding_constraints()
  Task 8  Template_QualityMargins.md       -> explain_quality_and_margins()
  Task 9  (new)                            -> explain_sensitivity()
                                               explain_estimated_fields()
                                               build_summary()
                                               generate_explanation() [orchestrator]

explain_sensitivity() was added after Task 13's evaluation rubric
(LLM_Evaluation_Rubric.md, Section 2, evidence table) listed
`sensitivity_to_key_assumptions[]` as an area explanations are checked
against - a JSON field none of Tasks 6/7/8/9 had covered until now.

Design note (field-name isolation)
-----------------------------------
The Sprint 1 Results JSON contract is still a draft (flagged explicitly in
the Task 8 PR: "these field names aren't finalised"). Every JSON key this
script depends on is named ONCE, in the constants near the top of this
file, and read from there everywhere else. If a field gets renamed later,
this is the only block that needs to change - the logic in each explain_*
function does not.

Required vs. optional input
----------------------------
Required (raises ExplainerInputError if missing): status, sources,
water_quality.by_plant, binding_constraints_summary. Without these
the script cannot produce a coherent explanation at all.

Optional (missing values are handled gracefully, never crash the script):
cost_per_ml on any source, data_flags.sources[].has_estimated_values,
demand_zones, plants, per-constraint slack values.

This required/optional split is a project decision made for Task 9 and
should be confirmed with the wider team, the same way Task 6 flagged its
own selected-source reason-derivation as "a design decision, not a guess."
"""

import json
import sys


# ---------------------------------------------------------------------------
# Field-name constants (see "field-name isolation" note above)
# ---------------------------------------------------------------------------

F_STATUS = "status"
F_OBJECTIVE = "objective"
F_CURRENCY = "currency"
F_SOURCES = "sources"
F_SELECTED = "selected"
F_UNUSED = "unused"
F_DEMAND_ZONES = "demand_zones"
F_PLANTS = "plants"
F_ACTIVE = "active"
F_WATER_QUALITY = "water_quality"
F_BY_PLANT = "by_plant"
F_BINDING_SUMMARY = "binding_constraints_summary"
F_SENSITIVITY = "sensitivity_to_key_assumptions"
F_DATA_FLAGS = "data_flags"

REQUIRED_TOP_LEVEL_FIELDS = [F_STATUS, F_SOURCES, F_WATER_QUALITY, F_BINDING_SUMMARY]

# Per Template_QualityMargins.md unit rules
QUALITY_UNIT_RULES = {
    "pH": None,                  # no concentration unit
    "alkalinity": "mg/L CaCO3",
    "turbidity": "NTU",
}
EXPECTED_QUALITY_PARAMETERS = list(QUALITY_UNIT_RULES.keys())

ORDINAL_WORDS = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
    6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
}


class ExplainerInputError(ValueError):
    """Raised when a required field is missing from the input JSON."""


# ---------------------------------------------------------------------------
# Validation & feasibility gate
# ---------------------------------------------------------------------------

def validate_input(data: dict) -> None:
    """Raise ExplainerInputError with a clear message if a required field
    is missing. Called once, before any explain_* function runs."""
    if not isinstance(data, dict):
        raise ExplainerInputError("Input must be a JSON object (Python dict).")

    missing = [f for f in REQUIRED_TOP_LEVEL_FIELDS if f not in data]
    if missing:
        raise ExplainerInputError(
            f"Missing required field(s): {', '.join(missing)}. "
            "Cannot generate an explanation without these."
        )

    if F_BY_PLANT not in data.get(F_WATER_QUALITY, {}):
        raise ExplainerInputError(
            f"Missing required field: {F_WATER_QUALITY}.{F_BY_PLANT}."
        )


def check_feasibility(data: dict):
    """Global feasibility gate (extends Task 6's per-section gate to the
    whole explanation, per Task 9 design discussion). Returns a message
    string if the scenario is not OPTIMAL, else None."""
    status = data.get(F_STATUS)
    if status != "OPTIMAL":
        return f"No blend could be recommended for this scenario ({status})."
    return None


# ---------------------------------------------------------------------------
# Task 6 - Source-selection explanation (Template_SourceSelection.md)
# ---------------------------------------------------------------------------

def _ordinal(n: int) -> str:
    return ORDINAL_WORDS.get(n, f"{n}th")


def _cost_ranking(all_sources: list) -> list:
    """Rank every source with a numeric cost_per_ml, ascending. Sources
    with no cost_per_ml are excluded from ranking (Section 7 of the
    template)."""
    costed = [s for s in all_sources if s.get("cost_per_ml") is not None]
    costed_sorted = sorted(costed, key=lambda s: s["cost_per_ml"])
    return [s["source_id"] for s in costed_sorted]


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


def explain_sources(data: dict) -> str:
    sources = data.get(F_SOURCES, {}) or {}
    selected = sources.get(F_SELECTED, []) or []
    unused = sources.get(F_UNUSED, []) or []
    binding = data.get(F_BINDING_SUMMARY, []) or []
    source_flags = _source_data_flags(data)
    # cost_per_ml has no currency field of its own anywhere in the contract -
    # objective.currency is the only currency the JSON actually states, so it's
    # applied here too rather than assuming AUD. Per rubric C7 ("cost uses AUD"),
    # every dollar figure in the explanation must carry a currency, not just the
    # summary total.
    currency = (data.get(F_OBJECTIVE, {}) or {}).get(F_CURRENCY)

    # Section 7: zero selected sources (e.g. zero demand)
    if not selected and not unused:
        return "No sources were required for this scenario."

    ranking = _cost_ranking(selected + unused)
    lines = []

    if not selected:
        lines.append("No sources were required for this scenario.")
    else:
        ordered = sorted(selected, key=lambda s: s.get("percent_of_blend", 0), reverse=True)
        for s in ordered:
            source_id = s.get("source_id")
            name = s.get("source_name", source_id)
            pct = s.get("percent_of_blend")
            vol = round(s.get("volume_drawn_ml_per_day", 0))
            cost = s.get("cost_per_ml")
            capacity_binding = f"source_capacity_{source_id}" in binding

            if cost is None:
                # Section 7: missing cost_per_ml on a selected source
                reason_clause = ("it was included in the optimal blend to help meet "
                                  "demand at minimum total cost")
                sentence = f"{name} supplied {pct}% of the blend ({vol} ML), because {reason_clause}."
            else:
                rank = ranking.index(source_id) + 1 if source_id in ranking else None
                if rank == 1 and capacity_binding:
                    reason_clause = ("it is the cheapest available source and was used "
                                      "at its full available capacity")
                elif capacity_binding:
                    reason_clause = "it was used at its full available capacity for this scenario"
                elif rank == 1:
                    reason_clause = ("it is the cheapest available source for this scenario, "
                                      "with capacity remaining")
                elif rank is not None:
                    reason_clause = (f"it supplemented the blend, at the {_ordinal(rank)} lowest "
                                      "cost, to meet remaining demand after lower-cost sources "
                                      "reached capacity")
                else:
                    reason_clause = ("it was included in the optimal blend to help meet demand "
                                      "at minimum total cost")

                has_estimated = bool(source_flags.get(source_id, {}).get("has_estimated_values"))
                estimated_tag = " (estimated)" if has_estimated else ""
                currency_str = f" {currency}" if currency else ""
                sentence = (f"{name} supplied {pct}% of the blend ({vol} ML) at "
                            f"${cost:.2f}{currency_str}/ML{estimated_tag}, because {reason_clause}.")
            lines.append(sentence)

    for s in unused:
        name = s.get("source_name", s.get("source_id"))
        reason = s.get("reason")
        if not reason:
            # Section 7: missing reason on an unused source
            lines.append(f"{name} was not selected (no reason provided in the solver output).")
        else:
            lines.append(f"{name} was not selected because {reason}.")

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


def _round_ml(value):
    """Whole ML per the template's rounding rule. None stays None -
    Missing-field handling decides what to do with an absent figure."""
    return round(value) if value is not None else None


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
        vol = _round_ml(zone.get("demand_ml_per_day"))
        if vol is None:
            return (
                f"The solution was limited by the water demand for {zone_id}: the full "
                f"volume needed by {zone_id} had to be delivered, leaving no room to "
                "supply any less."
            )
        return (
            f"The solution was limited by the water demand for {zone_id}: the full "
            f"{vol} ML needed by {zone_id} had to be delivered, "
            "leaving no room to supply any less."
        )

    if category == "source_capacity":
        source_id = name[len("source_capacity_"):]
        s = selected.get(source_id)
        if not s:
            return unknown_wording
        source_name = s.get("source_name") or source_id
        vol = _round_ml(s.get("volume_drawn_ml_per_day"))
        binding_label = f"the available capacity of {source_name}"
        if vol is None:
            return (
                f"The solution was limited by {binding_label}: {source_name} was "
                "drawn up to the most its capacity allows, so any additional water "
                "had to come from other sources."
            )
        has_estimated = bool(source_flags.get(source_id, {}).get("has_estimated_values"))
        tag = ", estimated" if has_estimated else ""
        return (
            f"The solution was limited by {binding_label}: {source_name} was drawn "
            f"up to the most its capacity allows ({vol} ML{tag}), so any additional "
            "water had to come from other sources."
        )

    if category == "plant_capacity":
        plant_id = name[len("plant_capacity_"):]
        p = plants.get(plant_id)
        if not p:
            return unknown_wording
        plant_name = p.get("plant_name") or plant_id
        vol = _round_ml(p.get("volume_processed_ml_per_day"))
        binding_label = f"the processing capacity of {plant_name}"
        if vol is None:
            return (
                f"The solution was limited by {binding_label}: {plant_name} was "
                "already treating as much as it can handle, leaving no spare capacity."
            )
        return (
            f"The solution was limited by {binding_label}: {plant_name} was "
            f"already treating as much as it can handle ({vol} ML), leaving no "
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
        vol = _round_ml(path.get("flow_ml_per_day"))
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
            f"much flow as it can handle ({vol} ML), so any additional water had to "
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
                "at the edge of its safe range, so the blend could not be pushed any "
                "further."
            )
        return (
            f"The solution was limited by {binding_label}: {parameter} sat right at "
            f"the edge of its safe range ({cmin}\u2013{cmax} {unit}), so the "
            "blend could not be pushed any further."
        )

    return unknown_wording  # true Unknown (name matches no pattern at all)


def explain_binding_constraints(data: dict) -> str:
    binding = data.get(F_BINDING_SUMMARY, []) or []
    if not binding:
        return "No constraint was binding; the solution stayed within every limit."

    sources = data.get(F_SOURCES, {}) or {}
    selected = {s["source_id"]: s for s in sources.get(F_SELECTED, []) or []}
    unused = {s["source_id"]: s for s in sources.get(F_UNUSED, []) or []}
    demand_zones = {z["zone_id"]: z for z in data.get(F_DEMAND_ZONES, []) or []}
    plants = {
        p["plant_id"]: p
        for p in data.get(F_PLANTS, {}).get(F_ACTIVE, []) or []
    }
    transfer_paths = data.get("transfer_paths", {}) or {}
    links = {}
    for path in transfer_paths.get("source_to_plant", []) or []:
        if path.get("path_id"):
            links[path["path_id"]] = ("source_to_plant", path)
    for path in transfer_paths.get("plant_to_zone", []) or []:
        if path.get("path_id"):
            links[path["path_id"]] = ("plant_to_zone", path)
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

def explain_quality_and_margins(data: dict) -> str:
    by_plant = data.get(F_WATER_QUALITY, {}).get(F_BY_PLANT, {}) or {}

    if not by_plant:
        return "No plant-inflow blend quality was reported for this scenario."

    lines = []
    for plant_id, after in by_plant.items():
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
                    f"{q.get('unit')} (safety margin {q.get('safety_margin_percent')}%). This "
                    "is treated as a violation and must be resolved before the blend is "
                    "acceptable."
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


def explain_estimated_fields(data: dict) -> str:
    """Standalone aggregate list of every source with estimated values,
    plus any free-text notes. Rebuilt against the confirmed output
    contract (Section 3.11): data_flags is now data_flags.sources[]
    (per-source has_estimated_values + provenance) and data_flags.notes[],
    not a flat estimated_fields[] string list."""
    flags = data.get(F_DATA_FLAGS, {}) or {}
    source_entries = flags.get(F_SOURCES, []) or []
    notes = flags.get("notes", []) or []

    estimated_sources = [e for e in source_entries if e.get("has_estimated_values")]

    if not estimated_sources and not notes:
        return "No fields in this result were flagged as estimated."

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


def build_summary(data: dict) -> str:
    status = data.get(F_STATUS)
    objective = data.get(F_OBJECTIVE, {}) or {}
    total_cost = objective.get("total_cost")
    currency = objective.get(F_CURRENCY, "")
    sources = data.get(F_SOURCES, {}) or {}
    n_selected = len(sources.get(F_SELECTED, []) or [])
    n_unused = len(sources.get(F_UNUSED, []) or [])
    by_plant = data.get(F_WATER_QUALITY, {}).get(F_BY_PLANT, {}) or {}

    overall_quality = "PASS"
    for plant_quality in by_plant.values():
        for q in (plant_quality or {}).values():
            margin = q.get("safety_margin_percent")
            if q.get("status") == "FAIL" or (margin is not None and margin < 0):
                overall_quality = "FAIL"
                break
        if overall_quality == "FAIL":
            break

    cost_clause = f"${total_cost:,.2f} {currency}".strip() if total_cost is not None else "not reported"
    return (
        f"This scenario is {status}. Total cost: {cost_clause}. "
        f"{n_selected} source(s) selected, {n_unused} unused. "
        f"Plant-inflow blend quality: {overall_quality}."
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_explanation(data: dict) -> str:
    """Build the complete operator-readable explanation. Accepts a Python
    dict already parsed from JSON. See generate_explanation_from_file for
    reading directly from a file."""
    validate_input(data)

    infeasible_message = check_feasibility(data)
    if infeasible_message:
        return infeasible_message

    sections = [
        ("Selected & Unused Sources", explain_sources(data)),
        ("Binding Constraints", explain_binding_constraints(data)),
        ("Water Quality & Safety Margins", explain_quality_and_margins(data)),
        ("Sensitivity to Key Assumptions", explain_sensitivity(data)),
        ("Estimated Fields / Data Limitations", explain_estimated_fields(data)),
        ("Summary", build_summary(data)),
    ]

    return "\n\n".join(f"## {title}\n\n{body}" for title, body in sections if body)


def generate_explanation_from_file(path: str) -> str:
    """Script accepts a JSON file per Task 9's checklist."""
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
