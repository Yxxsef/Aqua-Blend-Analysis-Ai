"""
baseline_runner.py

AquaBlend | Analysis & AI | Sprint 2 | Task 18

Runs all three coded baselines — equal_blend (Task 15), cheapest_first
(Task 16), fixed_priority (Task 17) — against the same scenario, normalizes
their results into one consistent shape, and produces a side-by-side
comparison. Depends on all three of those modules being importable from this
folder.

Why normalization is needed, not optional
------------------------------------------
The three baselines were built at different points as the MILP output
contract evolved. equal_blend predates the activation-cost fields, so its
`objective.cost_breakdown` carries only two keys
(`source_draw_cost`, `plant_treatment_cost`); cheapest_first and
fixed_priority carry all four. fixed_priority also returns two extra
top-level fields (`priority_order`, `metadata`) that the other two do not,
since its own approved rule specifically requires storing a heuristic label
and justification.

None of this is a bug in any of the three files — each is correct against
the contract as it stood when it was written, and none of it should be
"fixed" by editing someone else's baseline. This runner is the place that
resolves it: every normalized result carries the full set of
`cost_breakdown` keys (missing ones filled with 0.00, since no activation-cost
concept existed yet for that baseline, not because a real cost is unknown),
and the full set of top-level keys (missing ones filled with `None`, which is
distinguishable from a real value of any kind).

Each baseline runs against its own deep copy of the input scenario, so none
can affect another even if a baseline were ever to mutate its input.

No baseline currently computes water quality. The runner treats a
`water_quality` key appearing on any baseline's result as an error, not
something to pass through, since no baseline is approved to make that claim.

Each normalized result is also checked against
`model_output_specification.md` section 5, rule 1: `cost_breakdown` must sum
to `total_cost`. This is checked only when `total_cost` is present -- a
baseline with an incomplete cost (some source's price unknown) has no total
to check against, and that incompleteness is already visible via
`cost_is_complete`.

`Baseline_Validation_Notes.md` records the differences this file's
normalization step is papering over, and compares Sprint 2's coded output
against the Sprint 1 hand calculations.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from baseline_equal_blend import run_equal_blend  # noqa: E402
from baseline_cheapest_first import run_cheapest_first  # noqa: E402
from baseline_fixed_priority import run_fixed_priority  # noqa: E402

BASELINE_RUNNERS: dict[str, Callable[..., dict]] = {
    "equal_blend": run_equal_blend,
    "cheapest_first": run_cheapest_first,
    "fixed_priority": run_fixed_priority,
}

# The full set of cost_breakdown keys across all three baselines, in the
# order the MILP Results JSON contract defines them.
COST_BREAKDOWN_KEYS = [
    "source_activation_cost",
    "plant_activation_cost",
    "source_draw_cost",
    "plant_treatment_cost",
]

# Top-level keys not every baseline produces. Normalized to None, not
# omitted, so every baseline's result has an identical key set and a
# consumer can check "is this None" rather than "is this key present".
TOP_LEVEL_OPTIONAL_KEYS = ["priority_order", "metadata"]


class BaselineRunnerError(ValueError):
    """Raised when a baseline cannot be run, or returns something the runner
    is not willing to normalize (e.g. an unapproved water_quality field)."""


def _normalize_cost_breakdown(objective: dict) -> dict:
    breakdown = dict(objective.get("cost_breakdown") or {})
    for key in COST_BREAKDOWN_KEYS:
        breakdown.setdefault(key, 0.00)
    # Keep key order stable and predictable for anyone reading the JSON by eye.
    return {key: breakdown[key] for key in COST_BREAKDOWN_KEYS}


def _verify_cost_consistency(baseline_name: str, objective: dict) -> None:
    """model_output_specification.md section 5, rule 1: cost_breakdown must
    sum to total_cost. Only checked when total_cost is present -- an
    incomplete cost (some component unknown) has no total to check against,
    and that incompleteness is already surfaced via cost_is_complete."""
    total = objective.get("total_cost")
    if total is None:
        return
    breakdown_sum = sum(objective["cost_breakdown"].values())
    if abs(breakdown_sum - total) > 0.01:
        raise BaselineRunnerError(
            f"{baseline_name}: cost_breakdown sums to {breakdown_sum:.2f}, but "
            f"total_cost is {total:.2f}. These must match (spec section 5, rule 1)."
        )


def _normalize_result(baseline_name: str, result: dict) -> dict:
    if "water_quality" in result:
        raise BaselineRunnerError(
            f"{baseline_name} returned a water_quality field, which no "
            "approved baseline is meant to compute; refusing to normalize it "
            "as if it were routine."
        )

    normalized = dict(result)
    objective = dict(normalized.get("objective") or {})
    objective["cost_breakdown"] = _normalize_cost_breakdown(objective)
    _verify_cost_consistency(baseline_name, objective)
    normalized["objective"] = objective

    for key in TOP_LEVEL_OPTIONAL_KEYS:
        normalized.setdefault(key, None)

    return normalized


def run_all_baselines(scenario: dict, zone_id: str | None = None) -> dict:
    """
    Runs equal_blend, cheapest_first, and fixed_priority against the same
    scenario and zone. Each baseline receives its own deep copy of the
    scenario dict, so the same demand, sources, capacities, and costs reach
    every baseline, and no baseline can affect what another one sees.

    Returns
    -------
    {
        "scenario_id": ...,
        "zone_id": ...,
        "baselines": {
            "equal_blend": <normalized result>,
            "cheapest_first": <normalized result>,
            "fixed_priority": <normalized result>,
        },
        "comparison": {
            "feasible": [names...],
            "infeasible": [names...],
            "total_costs": {name: total_cost or None, ...},
            "cheapest_by_total_cost": name or None,
        },
    }

    A baseline whose total_cost is None (an incomplete cost, per that
    baseline's own rules) is excluded from `cheapest_by_total_cost` rather
    than treated as free or infinite — silently picking either would invent
    a ranking the data does not support.
    """
    if not isinstance(scenario, dict):
        raise BaselineRunnerError("scenario must be a JSON object (Python dict).")

    baselines: dict[str, dict] = {}
    for name, runner in BASELINE_RUNNERS.items():
        scenario_copy = copy.deepcopy(scenario)
        try:
            raw_result = runner(scenario_copy, zone_id)
        except Exception as error:  # noqa: BLE001 - re-raised with baseline context
            raise BaselineRunnerError(f"{name} failed to run: {error}") from error
        baselines[name] = _normalize_result(name, raw_result)

    feasible = [name for name, r in baselines.items() if r["feasible"]]
    infeasible = [name for name, r in baselines.items() if not r["feasible"]]

    total_costs = {
        name: r["objective"]["total_cost"] for name, r in baselines.items()
    }
    known_totals = {
        name: cost for name, cost in total_costs.items() if cost is not None
    }
    cheapest = min(known_totals, key=known_totals.get) if known_totals else None

    return {
        "scenario_id": scenario.get("scenario_id"),
        "zone_id": zone_id,
        "baselines": baselines,
        "comparison": {
            "feasible": feasible,
            "infeasible": infeasible,
            "total_costs": total_costs,
            "cheapest_by_total_cost": cheapest,
        },
    }


def main() -> None:
    if not 2 <= len(sys.argv) <= 3:
        print("Usage: python3 baseline_runner.py <scenario.json> [zone_id]")
        raise SystemExit(1)
    with open(sys.argv[1]) as handle:
        scenario = json.load(handle)
    zone_id = sys.argv[2] if len(sys.argv) == 3 else None
    try:
        print(json.dumps(run_all_baselines(scenario, zone_id), indent=2))
    except BaselineRunnerError as error:
        print(f"Runner error: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
