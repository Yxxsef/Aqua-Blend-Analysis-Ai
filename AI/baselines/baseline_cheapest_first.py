"""
baseline_cheapest_first.py

AquaBlend | Analysis & AI | Sprint 2

The cheapest-first baseline: rank active, connected sources by `cost_per_ml`
ascending and draw from each in turn, taking the smaller of its capacity and
the demand still unmet, until demand is met or every source is exhausted. The
rule is defined in `Baseline_CheapestFirst.md` and hand-validated in
`Baseline_HandCalculations.md`.

This is a cost-only heuristic. It does not evaluate water quality and makes no
claim to satisfy quality limits: a cheapest-first blend may or may not pass
them. It solves nothing and claims nothing about optimality, so it reports
FEASIBLE or INFEASIBLE and never OPTIMAL.

Ordering is `cost_per_ml` ascending, ties broken by `source_id` ascending. The
approved rule also described a placeholder ordering by source type, to be used
until real costs arrived. Real costs have since been confirmed for the sources
that carry them, and ranking by source type would invent a cost order rather
than read one, so it is not implemented here. Sources with no `cost_per_ml`
cannot be ranked and are drawn last, which a warning discloses.

Input is one scenario dictionary in the MILP scenario-input shape documented in
`MILP/docs/data_loader.md`. Fields the baseline does not need are ignored.
Scenarios whose `data_source.type` is `supabase` carry no source rows offline;
the baseline still runs on them, taking capacity from the link limits alone and
reporting cost as unavailable rather than inventing it.

`Baseline_CheapestFirst_Implementation.md` lists every field read and returned.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import Any

BASELINE_NAME = "cheapest_first"
CURRENCY = "AUD"
COST_UNIT = "cost for one representative day"

# Allocation runs at full precision; these apply once, on output.
VOLUME_DECIMALS = 1
PERCENT_DECIMALS = 1
COST_DECIMALS = 2

# Guards float comparisons. Volumes are ML/day, far above this.
_EPSILON = 1e-9


class BaselineInputError(ValueError):
    """Raised when the scenario cannot supply what the baseline needs."""


# ---------------------------------------------------------------------------
# The rule itself (Baseline_CheapestFirst.md section 2)
# ---------------------------------------------------------------------------


def cost_rank(source: dict) -> tuple[bool, float, str]:
    """Sort key implementing the approved ordering: `cost_per_ml` ascending,
    ties broken by `source_id` ascending. A source with no cost sorts last,
    since claiming it is cheap would not be supported by the data."""
    cost = source.get("cost_per_ml")
    return (cost is None, cost if cost is not None else 0.0, source["source_id"])


def allocate_cheapest_first(
    sources: Sequence[dict],
    demand_ml_per_day: float,
) -> tuple[dict[str, float], float]:
    """Draw from the cheapest source first, then the next, until demand is met.

    Each source is a mapping with `source_id`, `capacity_ml_per_day` and
    `cost_per_ml`. Returns the unrounded allocation and the unmet volume, which
    is 0.0 when demand is fully met. Ordering is fully determined by
    ``cost_rank``, so the result does not depend on input order.
    """
    if demand_ml_per_day < 0:
        raise BaselineInputError("Zone demand cannot be negative.")

    allocation = {source["source_id"]: 0.0 for source in sources}
    remaining = float(demand_ml_per_day)

    for source in sorted(sources, key=cost_rank):
        if remaining <= _EPSILON:
            break
        drawn = min(source["capacity_ml_per_day"], remaining)
        allocation[source["source_id"]] = drawn
        remaining -= drawn

    return allocation, max(remaining, 0.0)


# ---------------------------------------------------------------------------
# Reading the MILP scenario contract
# ---------------------------------------------------------------------------


def _as_float(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BaselineInputError(f"{label} must be a number, got {value!r}.")
    return float(value)


def _as_bool(value: Any, label: str, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise BaselineInputError(f"{label} must be true or false, got {value!r}.")
    return value


def _source_rows(scenario: dict) -> dict[str, dict]:
    """Inline source rows keyed by source_id. `rows` is the loader's documented
    alias for `source_rows`."""
    data_source = scenario.get("data_source") or {}
    rows = data_source.get("source_rows")
    if rows is None:
        rows = data_source.get("rows") or []
    return {row["source_id"]: row for row in rows if row.get("source_id")}


def _withdrawal_limit(entry: dict, row: dict | None, bound: str) -> float | None:
    """Resolve W_upper_s or W_lower_s using the loader's override precedence
    (MILP/docs/data_loader.md section 3.1). An explicit null counts as absent,
    exactly as the loader treats it."""
    canonical = f"{bound}_withdrawal_ml_per_day"
    value = entry.get(f"{canonical}_override")
    if value is None and canonical in entry:
        value = entry.get(canonical)
    if value is None and bound == "maximum":
        value = entry.get("max_available_ml_per_day_override")  # legacy alias
    if value is not None:
        return _as_float(value, f"sources[].{canonical}_override")

    if row is None:
        return None
    row_field = (
        "max_available_ml_per_day"
        if bound == "maximum"
        else "minimum_withdrawal_ml_per_day"
    )
    return _as_float(row.get(row_field), f"source row {row_field}")


def _plant_minimum(plant: dict) -> float:
    """Minimum throughput, accepting the `minimum_operating_flow_ml_per_day`
    alias the loader also accepts."""
    value = plant.get("minimum_processing_capacity_ml_per_day")
    if value is None and "minimum_operating_flow_ml_per_day" in plant:
        value = plant.get("minimum_operating_flow_ml_per_day")
    return _as_float(value, "plants[].minimum_processing_capacity_ml_per_day") or 0.0


def _select_zone(scenario: dict, zone_id: str | None) -> dict:
    zones = (scenario.get("network") or {}).get("demand_zones") or []
    if not zones:
        raise BaselineInputError("The scenario contains no demand zones.")
    if zone_id is None:
        if len(zones) > 1:
            raise BaselineInputError(
                "The scenario has more than one demand zone; pass zone_id to "
                "choose which one the cheapest-first baseline applies to."
            )
        return zones[0]
    for zone in zones:
        if zone.get("zone_id") == zone_id:
            return zone
    raise BaselineInputError(f"Demand zone {zone_id!r} is not in the scenario.")


def _plants_serving(scenario: dict, zone_id: str) -> list[dict]:
    """Enabled plants with an enabled link into this zone."""
    network = scenario.get("network") or {}
    enabled = {
        plant["plant_id"]: plant
        for plant in network.get("plants") or []
        if _as_bool(plant.get("enabled"), "plants[].enabled", default=True)
    }
    serving_ids = {
        link["plant_id"]
        for link in network.get("plant_to_zone_links") or []
        if link.get("zone_id") == zone_id
        and link.get("plant_id") in enabled
        and _as_bool(link.get("enabled"), "plant_to_zone_links[].enabled", default=True)
    }
    return [enabled[plant_id] for plant_id in enabled if plant_id in serving_ids]


def _excluded(record: dict, reason: str, capacity: float | None = None) -> dict:
    return {**record, "capacity_ml_per_day": capacity, "reason": reason}


def _resolve_sources(
    scenario: dict,
    zone_id: str,
    warnings: list[str],
) -> tuple[list[dict], list[dict]]:
    """Split the scenario's sources into those usable for this zone and those
    excluded, each with the reason it was left out."""
    rows = _source_rows(scenario)
    network = scenario.get("network") or {}
    serving_plant_ids = {
        plant["plant_id"] for plant in _plants_serving(scenario, zone_id)
    }

    usable: list[dict] = []
    excluded: list[dict] = []

    for index, entry in enumerate(scenario.get("sources") or []):
        source_id = entry.get("source_id")
        if not source_id:
            raise BaselineInputError(f"sources[{index}] has no source_id.")
        row = rows.get(source_id)
        record = {
            "source_id": source_id,
            "source_name": (row or {}).get("source_name")
            or entry.get("name")
            or source_id,
            "source_type": (row or {}).get("source_type"),
            "cost_per_ml": _as_float((row or {}).get("cost_per_ml"), "cost_per_ml"),
            "fixed_activation_cost": _as_float(
                entry.get("fixed_activation_cost"), "sources[].fixed_activation_cost"
            )
            or 0.0,
            "minimum_withdrawal_ml_per_day": _withdrawal_limit(entry, row, "minimum")
            or 0.0,
        }

        if not _as_bool(entry.get("enabled"), "sources[].enabled", default=True):
            excluded.append(_excluded(record, "it is disabled in this scenario"))
            continue
        if _as_bool(
            entry.get("forced_inactive"), "sources[].forced_inactive", default=False
        ):
            excluded.append(_excluded(record, "it is forced inactive in this scenario"))
            continue
        if row is not None and not _as_bool(
            row.get("is_active"), "source row is_active", default=True
        ):
            excluded.append(_excluded(record, "it is not active in the source data"))
            continue

        link_limit = 0.0
        connected = False
        for link in network.get("source_to_plant_links") or []:
            if (
                link.get("source_id") != source_id
                or link.get("plant_id") not in serving_plant_ids
            ):
                continue
            if not _as_bool(
                link.get("enabled"), "source_to_plant_links[].enabled", default=True
            ):
                continue
            connected = True
            limit = _as_float(
                link.get("maximum_flow_ml_per_day"), "maximum_flow_ml_per_day"
            )
            if limit is None:
                warnings.append(
                    f"Link {source_id} -> {link.get('plant_id')} has no "
                    "maximum_flow_ml_per_day; the MILP loader requires one, so this "
                    "link contributes no capacity here."
                )
                continue
            link_limit += limit

        if not connected:
            excluded.append(_excluded(record, f"it has no enabled route to {zone_id}"))
            continue

        # The formulation caps a source twice, on its withdrawal and on its arcs,
        # so what it can actually deliver is the tighter of the two.
        withdrawal_limit = _withdrawal_limit(entry, row, "maximum")
        if withdrawal_limit is None:
            warnings.append(
                f"Source {source_id} has no maximum_withdrawal_ml_per_day; capacity "
                "falls back to its link limits alone."
            )
            capacity = link_limit
        else:
            capacity = min(withdrawal_limit, link_limit)

        if capacity <= _EPSILON:
            excluded.append(
                _excluded(record, "it has no usable capacity in this scenario", 0.0)
            )
            continue

        usable.append({**record, "capacity_ml_per_day": capacity})

    return usable, excluded


# ---------------------------------------------------------------------------
# Contract checks the cheapest-first rule does not itself cover
# ---------------------------------------------------------------------------


def _contract_warnings(
    usable: list[dict],
    allocation: dict[str, float],
    supplied: float,
    plants: list[dict],
) -> list[str]:
    """The approved rule reasons only about upper capacity, but the MILP also
    treats the source minimum withdrawal and the plant throughput band as hard
    constraints. Breaches are reported rather than corrected, since correcting
    them would change the rule."""
    warnings: list[str] = []

    for source in usable:
        drawn = allocation[source["source_id"]]
        minimum = source["minimum_withdrawal_ml_per_day"]
        if drawn > _EPSILON and drawn < minimum - _EPSILON:
            warnings.append(
                f"Source {source['source_id']} is drawn at {drawn:g} ML/day, below its "
                f"minimum withdrawal of {minimum:g} ML/day. The MILP would reject this draw."
            )

    for plant in plants:
        maximum = _as_float(
            plant.get("maximum_processing_capacity_ml_per_day"),
            "plants[].maximum_processing_capacity_ml_per_day",
        )
        if maximum is not None and supplied > maximum + _EPSILON:
            warnings.append(
                f"Plant {plant['plant_id']} would process {supplied:g} ML/day, above its "
                f"maximum of {maximum:g} ML/day."
            )
        minimum = _plant_minimum(plant)
        if supplied > _EPSILON and supplied < minimum - _EPSILON:
            warnings.append(
                f"Plant {plant['plant_id']} would process {supplied:g} ML/day, below its "
                f"minimum of {minimum:g} ML/day."
            )

    return warnings


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_cheapest_first(scenario: dict, zone_id: str | None = None) -> dict:
    """Apply the cheapest-first baseline to one demand zone of ``scenario``.

    ``zone_id`` may be omitted when the scenario has exactly one demand zone.
    """
    if not isinstance(scenario, dict):
        raise BaselineInputError("scenario must be a JSON object (Python dict).")

    warnings: list[str] = []
    zone = _select_zone(scenario, zone_id)
    resolved_zone_id = zone.get("zone_id")
    demand = _as_float(
        zone.get("demand_ml_per_day"), "demand_zones[].demand_ml_per_day"
    )
    if demand is None:
        raise BaselineInputError(
            f"Demand zone {resolved_zone_id!r} has no demand_ml_per_day; the baseline "
            "will not assume a value for it."
        )

    usable, excluded = _resolve_sources(scenario, resolved_zone_id, warnings)

    unranked = [s["source_id"] for s in usable if s["cost_per_ml"] is None]
    if unranked:
        warnings.append(
            f"Sources {', '.join(unranked)} have no cost_per_ml and cannot be ranked "
            "by cost; they are drawn last."
        )

    allocation, unmet = allocate_cheapest_first(usable, demand)
    supplied = float(sum(allocation.values()))

    plants = _plants_serving(scenario, resolved_zone_id)
    warnings.extend(_contract_warnings(usable, allocation, supplied, plants))

    selected: list[dict] = []
    unused: list[dict] = list(excluded)
    missing_cost: list[str] = []
    known_draw_cost = 0.0
    source_activation_cost = 0.0

    for source in usable:
        drawn = allocation[source["source_id"]]
        capacity = source["capacity_ml_per_day"]
        if drawn <= _EPSILON:
            unused.append(
                {
                    **{
                        k: source[k]
                        for k in ("source_id", "source_name", "source_type")
                    },
                    "capacity_ml_per_day": round(capacity, VOLUME_DECIMALS),
                    "reason": "no volume was required from it for this scenario",
                }
            )
            continue

        source_activation_cost += source["fixed_activation_cost"]
        cost_per_ml = source["cost_per_ml"]
        if cost_per_ml is None:
            missing_cost.append(source["source_id"])
            draw_cost = None
        else:
            draw_cost = round(drawn * cost_per_ml, COST_DECIMALS)
            known_draw_cost += drawn * cost_per_ml

        selected.append(
            {
                "source_id": source["source_id"],
                "source_name": source["source_name"],
                "source_type": source["source_type"],
                "volume_drawn_ml_per_day": round(drawn, VOLUME_DECIMALS),
                "percent_of_blend": round(
                    (drawn / supplied * 100.0) if supplied > _EPSILON else 0.0,
                    PERCENT_DECIMALS,
                ),
                "capacity_ml_per_day": round(capacity, VOLUME_DECIMALS),
                "capacity_usage_percent": round(
                    drawn / capacity * 100.0, PERCENT_DECIMALS
                ),
                "cost_per_ml": cost_per_ml,
                "draw_cost": draw_cost,
            }
        )

    # Treatment is charged per ML processed whatever the source, so it and the
    # plant activation cost are only attributable when one plant serves the
    # zone. Splitting flow between several is a routing decision this baseline
    # does not make.
    treatment_cost: float | None = None
    plant_activation_cost = 0.0
    if len(plants) == 1:
        rate = _as_float(
            plants[0].get("treatment_cost_per_ml"), "treatment_cost_per_ml"
        )
        if rate is not None:
            treatment_cost = round(supplied * rate, COST_DECIMALS)
        if supplied > _EPSILON:
            plant_activation_cost = (
                _as_float(
                    plants[0].get("fixed_activation_cost"),
                    "plants[].fixed_activation_cost",
                )
                or 0.0
            )
    elif len(plants) > 1:
        warnings.append(
            f"Zone {resolved_zone_id} is served by {len(plants)} plants, so treatment "
            "cost is not attributable by this baseline."
        )

    # A total may not be reconstructed from partial cost fields, so an
    # incomplete one reads as None and the known part is offered as a lower
    # bound instead.
    cost_is_complete = not missing_cost and treatment_cost is not None
    lower_bound = round(
        known_draw_cost
        + (treatment_cost or 0.0)
        + source_activation_cost
        + plant_activation_cost,
        COST_DECIMALS,
    )
    total_cost = lower_bound if cost_is_complete else None
    source_draw_cost = (
        round(known_draw_cost, COST_DECIMALS) if not missing_cost else None
    )

    feasible = unmet <= _EPSILON
    return {
        "baseline": BASELINE_NAME,
        "scenario_id": scenario.get("scenario_id"),
        "status": "FEASIBLE" if feasible else "INFEASIBLE",
        "feasible": feasible,
        "demand_zones": [
            {
                "zone_id": resolved_zone_id,
                "zone_name": zone.get("name"),
                "demand_ml_per_day": round(demand, VOLUME_DECIMALS),
                "volume_supplied_ml_per_day": round(supplied, VOLUME_DECIMALS),
            }
        ],
        "unmet_demand_ml_per_day": round(unmet, VOLUME_DECIMALS),
        "sources": {"selected": selected, "unused": unused},
        "objective": {
            "total_cost": total_cost,
            "total_cost_lower_bound": lower_bound,
            "currency": CURRENCY,
            "unit": COST_UNIT,
            "cost_is_complete": cost_is_complete,
            "sources_missing_cost": missing_cost,
            "cost_breakdown": {
                "source_activation_cost": round(source_activation_cost, COST_DECIMALS),
                "plant_activation_cost": round(plant_activation_cost, COST_DECIMALS),
                "source_draw_cost": source_draw_cost,
                "plant_treatment_cost": treatment_cost,
            },
        },
        "warnings": warnings,
    }


def main() -> None:
    if not 2 <= len(sys.argv) <= 3:
        print("Usage: python3 baseline_cheapest_first.py <scenario.json> [zone_id]")
        raise SystemExit(1)
    with open(sys.argv[1]) as handle:
        scenario = json.load(handle)
    zone_id = sys.argv[2] if len(sys.argv) == 3 else None
    try:
        print(json.dumps(run_cheapest_first(scenario, zone_id), indent=2))
    except BaselineInputError as error:
        print(f"Input error: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
