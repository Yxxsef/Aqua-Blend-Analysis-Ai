"""
baseline_equal_blend.py

AquaBlend | Analysis & AI | Sprint 2

The equal-blend baseline: divide a demand zone's requirement equally across
every active, connected source, cap any source whose share exceeds its
capacity, redistribute the remainder across the sources still under their cap,
and repeat until demand is met or capacity is exhausted. The rule is defined in
`Baseline_EqualBlend.md` and hand-validated in `Baseline_HandCalculations.md`.

This is a deliberately non-optimised reference point for comparing the MILP
optimiser against. It solves nothing and claims nothing about optimality, so it
reports FEASIBLE or INFEASIBLE and never OPTIMAL.

Input is one scenario dictionary in the MILP scenario-input shape documented in
`MILP/docs/data_loader.md`. Fields the baseline does not need are ignored.
Scenarios whose `data_source.type` is `supabase` carry no source rows offline;
the baseline still runs on them, taking capacity from the link limits alone and
reporting cost as unavailable rather than inventing it.

`Baseline_EqualBlend_Implementation.md` lists every field read and returned.
"""

from __future__ import annotations

import json
import sys
from typing import Any

BASELINE_NAME = "equal_blend"
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
# The rule itself (Baseline_EqualBlend.md section 2)
# ---------------------------------------------------------------------------


def allocate_equal_blend(
    capacities: dict[str, float],
    demand_ml_per_day: float,
) -> tuple[dict[str, float], float]:
    """Split ``demand_ml_per_day`` equally across ``capacities``, capping and
    redistributing until demand is met or every source sits at its cap.

    Returns the unrounded allocation and the unmet volume, which is 0.0 when
    demand is fully met. The iteration order of ``capacities`` fixes the order
    of the result but not its values: capping every violator in one round is
    equivalent to capping them one at a time, because removing a capped source
    raises the share for those that remain.
    """
    if demand_ml_per_day < 0:
        raise BaselineInputError("Zone demand cannot be negative.")

    allocation = {source_id: 0.0 for source_id in capacities}
    uncapped = list(capacities)
    remaining = float(demand_ml_per_day)

    while uncapped and remaining > _EPSILON:
        share = remaining / len(uncapped)
        violators = [
            source_id
            for source_id in uncapped
            if capacities[source_id] < share - _EPSILON
        ]

        if not violators:
            for source_id in uncapped:
                allocation[source_id] = share
            remaining = 0.0
            break

        for source_id in violators:
            allocation[source_id] = capacities[source_id]
            remaining -= capacities[source_id]
            uncapped.remove(source_id)

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


def _select_zone(scenario: dict, zone_id: str | None) -> dict:
    zones = (scenario.get("network") or {}).get("demand_zones") or []
    if not zones:
        raise BaselineInputError("The scenario contains no demand zones.")
    if zone_id is None:
        if len(zones) > 1:
            raise BaselineInputError(
                "The scenario has more than one demand zone; pass zone_id to "
                "choose which one the equal-blend baseline applies to."
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
# Contract checks the equal-blend rule does not itself cover
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
            "maximum_processing_capacity_ml_per_day",
        )
        if maximum is not None and supplied > maximum + _EPSILON:
            warnings.append(
                f"Plant {plant['plant_id']} would process {supplied:g} ML/day, above its "
                f"maximum of {maximum:g} ML/day."
            )
        minimum = (
            _as_float(
                plant.get("minimum_processing_capacity_ml_per_day"),
                "minimum_processing_capacity_ml_per_day",
            )
            or 0.0
        )
        if supplied > _EPSILON and supplied < minimum - _EPSILON:
            warnings.append(
                f"Plant {plant['plant_id']} would process {supplied:g} ML/day, below its "
                f"minimum of {minimum:g} ML/day."
            )

    return warnings


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_equal_blend(scenario: dict, zone_id: str | None = None) -> dict:
    """Apply the equal-blend baseline to one demand zone of ``scenario``.

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
    capacities = {
        source["source_id"]: source["capacity_ml_per_day"] for source in usable
    }
    allocation, unmet = allocate_equal_blend(capacities, demand)
    supplied = float(sum(allocation.values()))

    plants = _plants_serving(scenario, resolved_zone_id)
    warnings.extend(_contract_warnings(usable, allocation, supplied, plants))

    selected: list[dict] = []
    unused: list[dict] = list(excluded)
    missing_cost: list[str] = []
    known_draw_cost = 0.0

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

    # Treatment is charged per ML processed whatever the source, so it is only
    # attributable when one plant serves the zone. Splitting flow between
    # several is a routing decision this baseline does not make.
    treatment_cost: float | None = None
    if len(plants) == 1:
        rate = _as_float(
            plants[0].get("treatment_cost_per_ml"), "treatment_cost_per_ml"
        )
        if rate is not None:
            treatment_cost = round(supplied * rate, COST_DECIMALS)
    elif len(plants) > 1:
        warnings.append(
            f"Zone {resolved_zone_id} is served by {len(plants)} plants, so treatment "
            "cost is not attributable by this baseline."
        )

    # A total may not be reconstructed from partial cost fields, so an
    # incomplete one reads as None and the known part is offered as a lower
    # bound instead.
    cost_is_complete = not missing_cost and treatment_cost is not None
    lower_bound = round(known_draw_cost + (treatment_cost or 0.0), COST_DECIMALS)
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
                "source_draw_cost": source_draw_cost,
                "plant_treatment_cost": treatment_cost,
            },
        },
        "warnings": warnings,
    }


def main() -> None:
    if not 2 <= len(sys.argv) <= 3:
        print("Usage: python3 baseline_equal_blend.py <scenario.json> [zone_id]")
        raise SystemExit(1)
    with open(sys.argv[1]) as handle:
        scenario = json.load(handle)
    zone_id = sys.argv[2] if len(sys.argv) == 3 else None
    try:
        print(json.dumps(run_equal_blend(scenario, zone_id), indent=2))
    except BaselineInputError as error:
        print(f"Input error: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
