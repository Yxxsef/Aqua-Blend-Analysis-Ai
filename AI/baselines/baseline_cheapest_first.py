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

Ordering: `cost_per_ml` ascending, ties broken by `source_id` ascending. The
approved rule also described a placeholder ordering by source type, to be used
until real costs arrived. Real costs have since been confirmed for the sources
that carry them, and ranking by source type would invent a cost order rather
than read one, so it is not implemented here. Sources with no `cost_per_ml`
cannot be ranked and are drawn last, which a warning discloses.

Scenarios use the MILP scenario-input shape; `baseline_common.py` reads them.
`Baseline_CheapestFirst_Implementation.md` lists every field read and returned.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence

from baseline_common import (
    EPSILON,
    BaselineInputError,
    ScenarioView,
    build_result,
    read_scenario,
)

BASELINE_NAME = "cheapest_first"


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
        if remaining <= EPSILON:
            break
        drawn = min(source["capacity_ml_per_day"], remaining)
        allocation[source["source_id"]] = drawn
        remaining -= drawn

    return allocation, max(remaining, 0.0)


def _ranking_warnings(view: ScenarioView) -> list[str]:
    unranked = [s["source_id"] for s in view.usable if s.get("cost_per_ml") is None]
    if not unranked:
        return []
    return [
        f"Sources {', '.join(unranked)} have no cost_per_ml and cannot be ranked "
        "by cost; they are drawn last."
    ]


def run_cheapest_first(scenario: dict, zone_id: str | None = None) -> dict:
    """Apply the cheapest-first baseline to one demand zone of ``scenario``.

    ``zone_id`` may be omitted when the scenario has exactly one demand zone.
    """
    view = read_scenario(scenario, zone_id)
    view.warnings.extend(_ranking_warnings(view))
    allocation, unmet = allocate_cheapest_first(view.usable, view.demand_ml_per_day)
    return build_result(BASELINE_NAME, scenario, view, allocation, unmet)


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
