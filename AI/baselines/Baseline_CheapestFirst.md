# Baseline: Cheapest-First Strategy

Task: 2: Define the cheapest-first baseline
Owner: Ali Alabdouli
Status: Updated with confirmed toy-model configuration
First draft due: Thursday 23 July 2026
Final draft due: Sunday 26 July 2026
Temporary submission: Analysis & AI Teams chat
Units: Volume (ML); cost_per_ML (AUD/ML, pending); total cost values (AUD, pending)

## 1. Description

This baseline uses the cheapest active source first, moving on to the next-cheapest source only when more water is required. It is a cost-only heuristic with no regard for water quality, so it exists to provide a simple cost-based comparison point for evaluating the MILP optimiser, rather than to represent good operational practice. This replaces the earlier, unclear name "single source."

## 2. Rule

1. Identify all active and connected sources (`sources[].source_id`, `sources[].capacity_ML`, `sources[].cost_per_ML`) for the demand zone.
2. Sort sources from lowest to highest `sources[].cost_per_ML`. Real `cost_per_ML` values are still pending from Data Engineering; until they arrive, this baseline uses a documented placeholder order based on the project's stated cost tiering (reservoir cheapest, river mid-range, groundwater most expensive), applied at the source-type level. This placeholder order is flagged explicitly wherever it is used below, and must be re-run once real `cost_per_ML` values are confirmed.
3. Before drawing from any source, validate its maximum daily withdrawal limit. `sources[].capacity_ML` is not assumed to be fully drawable in a single day: this baseline uses the separate `sources[].max_daily_withdrawal_ML` field (distinct from `capacity_ML`) as each source's usable draw limit, consistent with the project's own documented distinction between storage capacity and maximum daily withdrawal (AquaBlend MILP Configuration, Section 3, "Source capacity clarification"). Confirmed `max_daily_withdrawal_ML` values are not yet available either; the worked example below uses `capacity_ML` as a stand-in until they are, flagged explicitly where used.
4. Starting with the cheapest source (real, or placeholder-ordered pending real costs), draw either its usable draw limit or the remaining unmet demand, whichever is smaller.
5. If demand remains, move to the next-cheapest source and repeat step 4.
6. Continue until `demand_zones[].required_volume_ML` is fully met, or all active sources have reached their usable draw limit.
7. If the total usable draw limit across all active sources is less than `demand_zones[].required_volume_ML`, mark the result as infeasible and report the unmet volume.
8. Tie-break rule: if two or more sources share the same `sources[].cost_per_ML`, they are ordered by ascending `sources[].source_id` (alphabetical) for reproducibility. This applies once real cost values are confirmed; it is not exercised by the current placeholder tiering, since the three source types are distinct.

### Rounding rule

Rounding is not applied during intermediate steps. Source sorting and draw amounts are all calculated at full (unrounded) precision, so rounding error cannot compound as the algorithm moves through multiple sources. Volumes are rounded to one decimal place (ML) only once, at the final output stage. Percentages (`sources[].percent_of_blend`) are likewise rounded to one decimal place (%) only in the final output. This is consistent with the equal-blend baseline.

### Scope note

This rule ranks sources on `sources[].cost_per_ML` only. It does not evaluate or claim to optimise water quality (pH, alkalinity, turbidity): a cheapest-first blend may or may not pass quality constraints, and this is treated purely as a cost-comparison baseline for the optimiser.

## 3. Worked Numerical Example

Toy-model configuration used (sources and capacities now confirmed by the Optimisation team; cost still pending):

| `sources[].source_id` | `sources[].source_name` | `sources[].source_type` | `sources[].capacity_ML` (daily) | `sources[].cost_per_ML` |
|---|---|---|---|---|
| silvan_reservoir | Silvan Reservoir | reservoir | 350 | pending |
| yarra_kew | Yarra River, Kew | river | 300 | pending |
| groundwater_bore_1 | Groundwater Bore 1 | groundwater | 60 | pending |

Demand zone: `zone_id = zone_1`, `demand_zones[].required_volume_ML = 500`

Assumption: all three sources in this example are assumed to be active and connected to the demand zone.

Step 1: Sort using the placeholder cost tiering (real `cost_per_ML` pending)

Real costs are not yet available, so sources are ordered using the documented placeholder tiering by source type (reservoir cheapest, river mid-range, groundwater most expensive):

1. Silvan Reservoir (reservoir, placeholder cheapest)
2. Yarra Kew (river, placeholder mid-range)
3. Groundwater Bore 1 (groundwater, placeholder most expensive)

This order is a placeholder only and must be re-run once real `cost_per_ML` values are confirmed by Data Engineering.

Step 2: Draw from Silvan Reservoir (placeholder cheapest) first

`max_daily_withdrawal_ML` is not yet confirmed either, so `capacity_ML` is used as the draw limit for now.

min(`capacity_ML` 350, remaining demand 500) = 350 ML drawn.

Remaining demand = 500 − 350 = 150 ML.

Step 3: Move to Yarra Kew (placeholder mid-range)

min(`capacity_ML` 300, remaining demand 150) = 150 ML drawn.

Remaining demand = 150 − 150 = 0 ML. Demand fully met.

Step 4: Groundwater Bore 1 is not required

Since demand was fully met after Yarra Kew, Groundwater Bore 1 (placeholder most expensive) draws 0 ML.

All draw amounts above are exact at full precision; no rounding was needed until the final output table below.

Final result:

| `sources[].source_id` | Volume drawn (ML) | `sources[].percent_of_blend` | Cost contribution |
|---|---|---|---|
| silvan_reservoir | 350.0 | 70.0% | pending |
| yarra_kew | 150.0 | 30.0% | pending |
| groundwater_bore_1 | 0.0 | 0.0% | pending |
| Total | 500.0 | 100.0% | pending |

Demand supplied: 500.0 / 500 ML required → feasible, 0 ML unmet.

> Note on example values: `sources[].source_id`, `sources[].source_name`, `sources[].source_type`, and `sources[].capacity_ML` above are now the confirmed official toy-model configuration values, as confirmed by the Optimisation team. `sources[].cost_per_ML` remains pending from Data Engineering, so the Step 1 sort order is a documented placeholder (source-type tiering), not a real cost ranking, and `max_daily_withdrawal_ML` is not yet confirmed either, so `capacity_ML` is used as the draw limit for now. Once real `cost_per_ML` and `max_daily_withdrawal_ML` values are confirmed, the sort order, draw-down sequence, and final numbers all need a follow-up pass to verify they still hold.

## 4. Checklist

- [x] Sorting rule is clear (ascending `sources[].cost_per_ML`, with a documented placeholder tiering used until real costs are confirmed)
- [x] Capacity exhaustion is handled (move to next-cheapest source)
- [x] Maximum daily withdrawal is validated in principle; `capacity_ML` is used as a stand-in until `max_daily_withdrawal_ML` is confirmed
- [x] Cost ties are handled (alphabetical `sources[].source_id` tie-break), for use once real costs are confirmed
- [x] Infeasibility is handled
- [x] Full configuration field paths are used (`sources[].source_id`, `sources[].capacity_ML`, `sources[].max_daily_withdrawal_ML`, `sources[].cost_per_ML`, `demand_zones[].required_volume_ML`, `sources[].percent_of_blend`); `Volume drawn` and `Cost contribution` are shown as plain table labels pending confirmation as Results JSON fields
- [x] A numerical example is included, using confirmed sources and capacities; cost and sort order are clearly flagged as pending/placeholder
- [x] Rounding rules are explained, with rounding deferred to the final output only to avoid compounding precision error
- [x] The rule does not claim to optimise water quality (see Scope note)
- [ ] Re-run sort order, draw-down sequence, and final numbers once real `cost_per_ML` and `max_daily_withdrawal_ML` are confirmed (open item)

## 5. Deliverable

- `Baseline_CheapestFirst.md` (this document) — updated with confirmed toy-model sources and capacities; cost-based sort order remains a placeholder pending real `cost_per_ML`
