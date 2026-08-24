# Equal-Blend Baseline: Implementation

| File | |
|---|---|
| [`baseline_equal_blend.py`](baseline_equal_blend.py) | the implementation |
| [`Baseline_EqualBlend.md`](Baseline_EqualBlend.md) | the approved rule it codes |
| [`../tests/test_baseline_equal_blend.py`](../tests/test_baseline_equal_blend.py) | 36 tests |

## Run

```bash
python3 baseline_equal_blend.py <scenario.json> [zone_id]
python3 -m pytest ../tests/test_baseline_equal_blend.py -v
```

```python
from baseline_equal_blend import run_equal_blend
result = run_equal_blend(scenario_dict)
```

`zone_id` is needed only for multi-zone scenarios. `allocate_equal_blend(capacities, demand)` exposes the rule on its own, without scenario parsing.

## Inputs

A scenario dict in the MILP scenario-input shape (`MILP/docs/data_loader.md`). Required: `demand_zones[].zone_id`, `demand_zones[].demand_ml_per_day`, `sources[].source_id`, and both link arrays. Unlisted fields are ignored.

| Field | Used for |
|---|---|
| `scenario_id` | echoed into the result |
| `demand_zones[].demand_ml_per_day` | the demand to divide |
| `demand_zones[].name` | reported as `zone_name` |
| `sources[].enabled` (default true), `.forced_inactive` (default false) | source exclusion |
| `sources[].maximum_withdrawal_ml_per_day_override`, `.maximum_withdrawal_ml_per_day`, `.max_available_ml_per_day_override` | source-side capacity, in that precedence order |
| `data_source.source_rows[]` | `source_name`, `source_type`, `is_active`, `max_available_ml_per_day`, `minimum_withdrawal_ml_per_day`, `cost_per_ml` |
| `network.plants[]` | `enabled`, `treatment_cost_per_ml`, min and max processing capacity |
| `network.source_to_plant_links[]` | connectivity and link capacity |
| `network.plant_to_zone_links[]` | connectivity into the zone |

Precedence follows `MILP/docs/data_loader.md` section 3.1 and ends at the source row; an explicit `null` counts as absent. `source_rows[]` exists only in `inline` scenarios, so on the team's `supabase` files capacity comes from link limits alone and cost is reported as unavailable rather than invented.

## Outputs

A JSON-serialisable dict, using Results JSON field names wherever the same quantity exists there.

| Field | Meaning |
|---|---|
| `baseline` | always `"equal_blend"` |
| `status`, `feasible` | `FEASIBLE` or `INFEASIBLE`, never `OPTIMAL` |
| `demand_zones[]` | `zone_id`, `zone_name`, `demand_ml_per_day`, `volume_supplied_ml_per_day` |
| `unmet_demand_ml_per_day` | `0.0` when demand is met |
| `sources.selected[]` | `source_id`, `source_name`, `source_type`, `volume_drawn_ml_per_day`, `percent_of_blend`, `capacity_ml_per_day`, `capacity_usage_percent`, `cost_per_ml`, `draw_cost` |
| `sources.unused[]` | identity fields plus `capacity_ml_per_day` and `reason` |
| `objective` | `total_cost`, `total_cost_lower_bound`, `currency`, `unit`, `cost_is_complete`, `sources_missing_cost`, `cost_breakdown.{source_draw_cost, plant_treatment_cost}` |
| `warnings[]` | non-blocking notes |

`total_cost` is `null` whenever any component is unknown, since a total may not be rebuilt from partial cost fields, and `total_cost_lower_bound` carries the known part. On the toy configuration that gives `null` and `171700.00`, matching the ">= 171,700.00 AUD" in `Baseline_HandCalculations.md`. Treatment cost is attributed only when exactly one enabled plant serves the zone.

## Capacity

`Baseline_HandCalculations.md` section 3 leaves open whether a source's capacity is the link's `maximum_flow_ml_per_day` (300 for `yarra_kew`) or its own database limit (290). The formulation caps a source on both, `a_s <= W_upper_s` and `b_st <= L_upper_st`, so the module takes the tighter:

```text
capacity = min(maximum withdrawal, sum of enabled outgoing link limits)
```

No ruling is needed, because 220 ML/day sits below both and the Sprint 1 numbers hold either way. Where one limit is absent the other governs and a warning records it.

A source is connected when it has an enabled link to an enabled plant that has an enabled link into the zone.

## Rounding

Per `Baseline_EqualBlend.md` section 2, the allocation runs at full precision and rounds once on output: volumes and percentages to one decimal place, money to two.

## Warnings

Reported, never corrected, since correcting them would change the approved rule:

- a draw below a source's `minimum_withdrawal_ml_per_day`
- flow outside a serving plant's processing band
- a source with no `maximum_withdrawal_ml_per_day`, or a link with no `maximum_flow_ml_per_day`
- a zone served by more than one plant, leaving treatment cost unattributable

## Open items

- Water quality is not computed, since per-source raw values are not available to this team.
- `FEASIBLE` needs confirming with the Optimisation team; the Results JSON only shows `OPTIMAL`.
- `source_name` falls back to `source_id` when no source rows are available.
- The plant `minimum_operating_flow_ml_per_day` alias the loader accepts is not read yet, and `fixed_activation_cost` is not in the cost total.
- The test file's import still needs fixing after its move to `../tests/`.
