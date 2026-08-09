# Cheapest-First Baseline: Implementation

| File | |
|---|---|
| [`baseline_cheapest_first.py`](baseline_cheapest_first.py) | the implementation |
| [`Baseline_CheapestFirst.md`](Baseline_CheapestFirst.md) | the approved rule it codes |
| [`../tests/test_baseline_cheapest_first.py`](../tests/test_baseline_cheapest_first.py) | 36 tests |

## Run

```bash
python3 baseline_cheapest_first.py <scenario.json> [zone_id]
python3 -m pytest AI/tests/test_baseline_cheapest_first.py -v
```

```python
from baseline_cheapest_first import run_cheapest_first
result = run_cheapest_first(scenario_dict)
```

`zone_id` is needed only for multi-zone scenarios. `allocate_cheapest_first(sources, demand)` exposes the rule on its own, and `cost_rank(source)` is the sort key.

## Sort order and tie-break

Sources are ordered by `cost_per_ml` ascending. Ties are broken by `source_id` ascending, so the result is reproducible whatever order the scenario lists sources in. `cost_rank()` is the single place this is decided:

```text
(cost_per_ml is None, cost_per_ml, source_id)
```

**Sources with no `cost_per_ml` sort last.** They cannot be ranked, and treating an unknown cost as cheap would not be supported by the data. A warning names them. The only evidence available points the same way: the reference solve excludes `groundwater_bore_1` because its cost exceeds both selected sources.

**The placeholder source-type tiering is not implemented.** `Baseline_CheapestFirst.md` section 2.2 defined an ordering by source type (reservoir, then river, then groundwater) to use until real costs arrived, which produces 350 / 150 / 0. `Baseline_HandCalculations.md` section 6 supersedes it with the confirmed costs, notes that the real order is different, and records it rather than editing the older document. Ranking by source type would invent a cost order instead of reading one, so this module ranks on the cost field alone and reproduces the hand-calculated numbers.

This is a cost-only heuristic. It does not evaluate water quality and emits no quality result, so a cheapest-first blend may or may not pass quality limits.

## Inputs

A scenario dict in the MILP scenario-input shape (`MILP/docs/data_loader.md`). Required: `demand_zones[].zone_id`, `demand_zones[].demand_ml_per_day`, `sources[].source_id`, and both link arrays. Unlisted fields are ignored.

| Field | Used for |
|---|---|
| `scenario_id` | echoed into the result |
| `demand_zones[].demand_ml_per_day` | the demand to fill |
| `demand_zones[].name` | reported as `zone_name` |
| `sources[].enabled` (default true), `.forced_inactive` (default false) | source exclusion |
| `sources[].fixed_activation_cost` (default 0.0) | activation cost of a drawn source |
| `sources[].maximum_withdrawal_ml_per_day_override`, `.maximum_withdrawal_ml_per_day`, `.max_available_ml_per_day_override` | source-side capacity, in that precedence order |
| `data_source.source_rows[]` | `source_name`, `source_type`, `is_active`, `max_available_ml_per_day`, `minimum_withdrawal_ml_per_day`, `cost_per_ml` |
| `network.plants[]` | `enabled`, `treatment_cost_per_ml`, `fixed_activation_cost`, min and max processing capacity |
| `network.source_to_plant_links[]` | connectivity and link capacity |
| `network.plant_to_zone_links[]` | connectivity into the zone |

Precedence follows `MILP/docs/data_loader.md` section 3.1 and ends at the source row; an explicit `null` counts as absent. The plant minimum also accepts the loader's `minimum_operating_flow_ml_per_day` alias. `source_rows[]` exists only in `inline` scenarios, so on the team's `supabase` files no source has a cost, every source falls back to the `source_id` tie-break, and the warning says so.

## Outputs

A JSON-serialisable dict, using Results JSON field names wherever the same quantity exists there.

| Field | Meaning |
|---|---|
| `baseline` | always `"cheapest_first"` |
| `status`, `feasible` | `FEASIBLE` or `INFEASIBLE`, never `OPTIMAL` |
| `demand_zones[]` | `zone_id`, `zone_name`, `demand_ml_per_day`, `volume_supplied_ml_per_day` |
| `unmet_demand_ml_per_day` | `0.0` when demand is met |
| `sources.selected[]` | `source_id`, `source_name`, `source_type`, `volume_drawn_ml_per_day`, `percent_of_blend`, `capacity_ml_per_day`, `capacity_usage_percent`, `cost_per_ml`, `draw_cost` |
| `sources.unused[]` | identity fields plus `capacity_ml_per_day` and `reason` |
| `objective` | `total_cost`, `total_cost_lower_bound`, `currency`, `unit`, `cost_is_complete`, `sources_missing_cost`, `cost_breakdown.{source_activation_cost, plant_activation_cost, source_draw_cost, plant_treatment_cost}` |
| `warnings[]` | non-blocking notes |

`total_cost` is `null` whenever any component is unknown, since a total may not be rebuilt from partial cost fields, and `total_cost_lower_bound` carries the known part. Unlike equal blend, the toy configuration gives a complete total here, because the source with no confirmed cost is never drawn. Treatment and plant activation cost are attributed only when exactly one enabled plant serves the zone.

## Capacity

`Baseline_HandCalculations.md` section 3 leaves open whether a source's capacity is the link's `maximum_flow_ml_per_day` (300 for `yarra_kew`) or its own database limit (290). The formulation caps a source on both, `a_s <= W_upper_s` and `b_st <= L_upper_st`, so the module takes the tighter:

```text
capacity = min(maximum withdrawal, sum of enabled outgoing link limits)
```

**This baseline is where the discrepancy bites.** At 300 it returns 182,500 AUD, below the confirmed MILP optimum of 184,150, and a heuristic cannot beat the true optimum. At 290 it returns 184,150 exactly. Both are covered by tests. Where a source-side limit is absent the link limit governs and a warning records it, so a run whose total undercuts the optimiser should be read alongside that warning.

`Baseline_CheapestFirst.md` section 2.3 asks for a `max_daily_withdrawal_ML` field distinct from storage capacity. The contract already provides it as `maximum_withdrawal_ml_per_day`, which is a daily withdrawal limit, not a storage figure, so that open item is answered.

A source is connected when it has an enabled link to an enabled plant that has an enabled link into the zone.

## Rounding

Per `Baseline_CheapestFirst.md` section 2, the allocation runs at full precision and rounds once on output: volumes and percentages to one decimal place, money to two.

## Warnings

Reported, never corrected, since correcting them would change the approved rule:

- sources with no `cost_per_ml`, which cannot be ranked and are drawn last
- a draw below a source's `minimum_withdrawal_ml_per_day`
- flow outside a serving plant's processing band
- a source with no `maximum_withdrawal_ml_per_day`, or a link with no `maximum_flow_ml_per_day`
- a zone served by more than one plant, leaving treatment cost unattributable

## Open items

- Water quality is not computed, since per-source raw values are not available to this team.
- `FEASIBLE` needs confirming with the Optimisation team; the Results JSON only shows `OPTIMAL`.
- The scenario-reading layer is duplicated from the equal-blend baseline, since each baseline is self-contained. Worth extracting into one shared module once all three are merged.
