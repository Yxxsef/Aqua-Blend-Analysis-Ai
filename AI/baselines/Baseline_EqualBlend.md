# Baseline: Equal-Blend Strategy

Task: 1: Define the equal-blend baseline
Owner: Ali Alabdouli
Status: Safe to start
First draft due: Thursday 23 July 2026
Final draft due: Sunday 26 July 2026
Temporary submission: Analysis & AI Teams chat
Units: Volume (ML); Cost (AUD)

## 1. Description

This baseline attempts to divide the required demand equally across all active and connected sources. It exists so the team has a simple, non-optimised comparison point to prove that the MILP optimiser is actually doing better than a naive "split it evenly" approach.

## 2. Rule

1. Identify all active and connected sources (`source_id`, `capacity_ML`, `cost_per_ML`) for the demand zone.
2. Divide the zone's `required_volume_ML` equally across the number of active sources.
3. For each source, compare its equal share against its `capacity_ML`.
4. If a source's equal share exceeds its `capacity_ML`, cap that source at its full `capacity_ML` and remove it from further redistribution.
5. Redistribute the remaining unmet demand equally across the remaining (uncapped) sources.
6. Repeat steps 3–5 until either all remaining demand is allocated, or no active sources with spare capacity remain.
7. If total available capacity across all active sources is less than `required_volume_ML`, mark the baseline result as infeasible and report the unmet volume.

### Rounding rule

All volumes are rounded to one decimal place (ML) after each redistribution step, to avoid compounding rounding error across iterations. Percentages (`percent_of_blend`) are rounded to one decimal place (%).

## 3. Worked Numerical Example

Toy-model configuration used (illustrative values, see note below):

| `source_id` | `source_name` | `source_type` | `capacity_ML` (daily) | `cost_per_ML` (AUD) |
|---|---|---|---|---|
| silvan_reservoir | Silvan Reservoir | reservoir | 220 | 400 |
| thomson_reservoir | Thomson Reservoir | reservoir | 260 | 380 |
| sugarloaf_reservoir | Sugarloaf Reservoir | reservoir | 150 | 420 |

Demand zone: `zone_id = zone_1`, `required_volume_ML = 500`

Step 1: Equal share across 3 active sources
500 ÷ 3 = 166.7 ML each.

Step 2: Capacity check
- Silvan: 220 ≥ 166.7 → OK
- Thomson: 260 ≥ 166.7 → OK
- Sugarloaf: 150 < 166.7 → exceeds capacity

Step 3: Cap Sugarloaf at its full capacity and redistribute
Sugarloaf is capped at 150 ML and removed from further redistribution.
Remaining demand = 500 − 150 = 350 ML, split equally across the 2 remaining sources: 350 ÷ 2 = 175 ML each.

Step 4: Re-check capacity
- Silvan: 220 ≥ 175 → OK
- Thomson: 260 ≥ 175 → OK

No further exceedance. Allocation is complete.

Final result:

| `source_id` | `volume_drawn_ML` | `percent_of_blend` | `cost_contribution` (AUD) |
|---|---|---|---|
| silvan_reservoir | 175.0 | 35.0% | 70,000 |
| thomson_reservoir | 175.0 | 35.0% | 66,500 |
| sugarloaf_reservoir | 150.0 | 30.0% | 63,000 |
| Total | 500.0 | 100.0% | 199,500 |

Demand supplied: 500.0 / 500 ML required → feasible, 0 ML unmet.

> Note on example values: `capacity_ML` and `cost_per_ML` above are illustrative placeholders consistent with the toy model's documented scope (3 named Melbourne Water reservoirs, reservoirs treated as lowest-cost tier). They are not the confirmed official toy-model configuration values. Task 5 (hand-validation against the official config) is where these get replaced with the real confirmed figures once available.

## 4. Checklist

- [x] Rule is clear enough to code directly
- [x] Only active and connected sources are included
- [x] Source capacity is never exceeded
- [x] Remaining demand is redistributed correctly
- [x] Infeasibility case is explained (Step 7)
- [x] Exact configuration field names are used (`source_id`, `capacity_ML`, `cost_per_ML`, `required_volume_ML`, `percent_of_blend`)
- [x] A small numerical example is included
- [x] Rounding rules are explained

## 5. Deliverable

- `Baseline_EqualBlend.md` (this document)
