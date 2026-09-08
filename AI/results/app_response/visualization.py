"""Deterministic chart-ready data for the App & Delivery response.

Values here are read straight from the validated MILP Results JSON contract
(see ``AI/results/Results_JSON_Field_Map.md``) - never from LLM wording, and
never recalculated. This module does not render charts; the App team turns
``visualization_data`` into graphs on their side.

A value that is genuinely unknown is omitted (or, where the shape requires
the key to be present, set to ``null``) rather than replaced with ``0``,
since a fabricated zero would be indistinguishable from a real zero to a
consumer of this data.
"""

from __future__ import annotations

from typing import Any, Mapping


def _num(value: Any) -> float | int | None:
    """Pass through a genuine numeric value; anything else is unknown."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _blend_ratios(sources: Mapping[str, Any]) -> list[dict[str, Any]]:
    selected = sources.get("selected")
    if not isinstance(selected, list):
        return []

    ratios = []
    for source in selected:
        if not isinstance(source, Mapping):
            continue
        name = source.get("source_name") or source.get("source_id")
        if not name:
            continue
        ratios.append({
            "source": name,
            "volume_ml_day": _num(source.get("volume_drawn_ml_per_day")),
            "share_pct": _num(source.get("percent_of_blend")),
        })
    return ratios


# Matches the labels already used by explain_cost_summary() in
# json_explainer.py, so the deterministic report and the chart data never
# describe the same cost component with two different names.
_COST_BREAKDOWN_LABELS = (
    ("source_activation_cost", "Source activation cost"),
    ("plant_activation_cost", "Plant activation cost"),
    ("source_draw_cost", "Source draw cost"),
    ("plant_treatment_cost", "Plant treatment cost"),
)


def _cost_breakdown(objective: Mapping[str, Any]) -> list[dict[str, Any]]:
    breakdown = objective.get("cost_breakdown")
    if not isinstance(breakdown, Mapping):
        return []

    entries = []
    for key, label in _COST_BREAKDOWN_LABELS:
        if key not in breakdown:
            continue  # omit rather than invent a category that wasn't reported
        amount = _num(breakdown.get(key))
        if amount is None:
            continue
        entries.append({"category": label, "amount_aud": amount})
    return entries


def _quality_margins(water_quality: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_plant = water_quality.get("by_plant")
    if not isinstance(by_plant, Mapping):
        return []

    margins = []
    for plant_id, parameters in sorted(by_plant.items()):
        if not isinstance(parameters, Mapping):
            continue
        for parameter, detail in sorted(parameters.items()):
            if not isinstance(detail, Mapping):
                continue
            margins.append({
                "plant_id": plant_id,
                "parameter": parameter,
                "value": _num(detail.get("value")),
                "limit_min": _num(detail.get("constraint_min")),
                "limit_max": _num(detail.get("constraint_max")),
                "margin_pct": _num(detail.get("safety_margin_percent")),
                "status": detail.get("status") if isinstance(detail.get("status"), str) else None,
            })
    return margins


def _solution_costs(objective: Mapping[str, Any], results: Mapping[str, Any]) -> list[dict[str, Any]]:
    costs = []
    optimal_cost = _num(objective.get("total_cost"))
    if optimal_cost is not None:
        costs.append({"solution": "Optimal", "amount_aud": optimal_cost})

    alternatives = results.get("alternative_feasible_solutions")
    if isinstance(alternatives, list):
        for alt in alternatives:
            if not isinstance(alt, Mapping):
                continue
            amount = _num(alt.get("total_cost"))
            if amount is None:
                continue
            label = alt.get("description")
            label = label if isinstance(label, str) and label.strip() else "Alternative"
            costs.append({"solution": label, "amount_aud": amount})
    return costs


def build_visualization_data(results: Mapping[str, Any]) -> dict[str, Any] | None:
    """Build deterministic chart-ready data from a validated Results JSON.

    Returns ``None`` when ``results`` carries none of the source data this
    function knows how to chart (for example, a non-optimal result), so the
    caller can omit ``visualization_data`` entirely rather than emit an
    all-empty shell.
    """
    if not isinstance(results, Mapping):
        return None

    sources = results.get("sources") if isinstance(results.get("sources"), Mapping) else {}
    objective = results.get("objective") if isinstance(results.get("objective"), Mapping) else {}
    water_quality = (
        results.get("water_quality") if isinstance(results.get("water_quality"), Mapping) else {}
    )

    blend_ratios = _blend_ratios(sources)
    cost_breakdown = _cost_breakdown(objective)
    quality_margins = _quality_margins(water_quality)
    solution_costs = _solution_costs(objective, results)

    if not (blend_ratios or cost_breakdown or quality_margins or solution_costs):
        return None

    return {
        "blend_ratios": blend_ratios,
        "cost_breakdown": cost_breakdown,
        "quality_margins": quality_margins,
        "solution_costs": solution_costs,
    }
