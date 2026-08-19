# Baseline: Equal-Blend Strategy

Task: 1: Define the equal-blend baseline
Owner: Ali Alabdouli
Status: Updated with confirmed toy-model configuration
First draft due: Thursday 23 July 2026
Final draft due: Sunday 26 July 2026
Temporary submission: Analysis & AI Teams chat
Units: Volume (ML); Cost (AUD, pending confirmed cost_per_ML)

## 1. Description

This baseline attempts to divide the required demand equally across all active and connected sources. It exists to provide a simple comparison baseline for evaluating the MILP optimiser, giving the team a non-optimised reference point rather than an "always split evenly" claim of superiority.

## 2. Rule

1. Identify all active and connected sources (`sources[].source_id`, `sources[].capacity_ML`, `sources[].cost_per_ML`) for the demand zone.
2. Divide the zone's `demand_zones[].required_volume_ML` equally across the number of active sources.
3. For each source, compare its equal share against its `sources[].capacity_ML`.
4. If a source's equal share exceeds its `sources[].capacity_ML`, cap that source at its full `sources[].capacity_ML` and remove it from further redistribution.
5. Redistribute the remaining unmet demand equally across the remaining (uncapped) sources.
6. Repeat steps 3–5 until either all remaining demand is allocated, or no active sources with spare capacity remain.
7. If total available capacity across all active sources is less than `demand_zones[].required_volume_ML`, mark the baseline result as infeasible and report the unmet volume.

### Rounding rule

Rounding is not applied during intermediate steps. Equal-share division, capacity comparisons, and redistribution are all carried out at full (unrounded) precision, so that rounding error cannot compound across multiple redistribution iterations. Volumes are rounded to one decimal place (ML) only once, at the final output stage. Percentages (`sources[].percent_of_blend`) are likewise rounded to one decimal place (%) only in the final output.

## 3. Worked Numerical Example

Toy-model configuration used (sources and capacities now confirmed by the Optimisation team; cost still pending):

| `sources[].source_id` | `sources[].source_name` | `sources[].source_type` | `sources[].capacity_ML` (daily) | `sources[].cost_per_ML` |
|---|---|---|---|---|
| silvan_reservoir | Silvan Reservoir | reservoir | 350 | pending |
| yarra_kew | Yarra River, Kew | river | 300 | pending |
| groundwater_bore_1 | Groundwater Bore 1 | groundwater | 60 | pending |

Demand zone: `zone_id = zone_1`, `demand_zones[].required_volume_ML = 500`

Assumption: all three sources in this example are assumed to be active, available, and connected to the demand zone.

Step 1: Equal share across 3 active sources
500 ÷ 3 = 166.666... ML each (full precision carried forward, not rounded).

Step 2: Capacity check
- Silvan: 350 ≥ 166.666... → OK
- Yarra Kew: 300 ≥ 166.666... → OK
- Groundwater Bore 1: 60 < 166.666... → exceeds capacity

Step 3: Cap Groundwater Bore 1 at its full capacity and redistribute
Groundwater Bore 1 is capped at 60 ML and removed from further redistribution.
Remaining demand = 500 − 60 = 440 ML, split equally across the 2 remaining sources: 440 ÷ 2 = 220 ML each (exact, no rounding needed at this step).

Step 4: Re-check capacity
- Silvan: 350 ≥ 220 → OK
- Yarra Kew: 300 ≥ 220 → OK

No further exceedance. Allocation is complete. Final volumes are rounded to one decimal place only now, at output.

Final result:

| `sources[].source_id` | Volume Drawn (ML) | `sources[].percent_of_blend` | Cost Contribution |
|---|---|---|---|
| silvan_reservoir | 220.0 | 44.0% | pending |
| yarra_kew | 220.0 | 44.0% | pending |
| groundwater_bore_1 | 60.0 | 12.0% | pending |
| Total | 500.0 | 100.0% | pending |

Demand supplied: 500.0 / 500 ML required → feasible, 0 ML unmet.

> Note on example values: `sources[].source_id`, `sources[].source_name`, `sources[].source_type`, and `sources[].capacity_ML` above are now the confirmed official toy-model configuration values, as confirmed by the Optimisation team. `sources[].cost_per_ML` remains pending from Data Engineering; cost contribution figures cannot be computed until it is provided, so they are shown as "pending" rather than an illustrative placeholder, to avoid implying a confirmed cost that does not yet exist.

## 4. Checklist

- [x] Rule is clear enough to code directly
- [x] Only active and connected sources are included, with this assumption stated for the worked example
- [x] Source capacity is never exceeded
- [x] Remaining demand is redistributed correctly
- [x] Infeasibility case is explained (Step 7)
- [x] Full configuration field paths are used (`sources[].source_id`, `sources[].capacity_ML`, `sources[].cost_per_ML`, `demand_zones[].required_volume_ML`, `sources[].percent_of_blend`); `volume_drawn_ML` and `cost_contribution` are shown as plain table labels pending confirmation as Results JSON fields
- [x] A small numerical example is included, using confirmed sources and capacities; cost is shown as pending rather than invented
- [x] Rounding rules are explained, with rounding deferred to the final output only to avoid compounding precision error

## 5. Deliverable

- `Baseline_EqualBlend.md` (this document) — updated with confirmed toy-model sources and capacities
