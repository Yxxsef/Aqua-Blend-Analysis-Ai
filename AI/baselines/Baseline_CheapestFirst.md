# Baseline: Cheapest-First Strategy

Task: 2: Define the cheapest-first baseline
Owner: Ali Alabdouli
Status: Safe to start
First draft due: Thursday 23 July 2026
Final draft due: Sunday 26 July 2026
Temporary submission: Analysis & AI Teams chat
Units: Volume (ML); Cost (AUD)

## 1. Description

This baseline uses the cheapest active source first, moving on to the next-cheapest source only when more water is required. It is a cost-only heuristic with no regard for water quality, so it exists to show whether the MILP optimiser genuinely produces something better than "always pick the cheapest option," rather than to represent good operational practice. This replaces the earlier, unclear name "single source."

## 2. Rule

1. Identify all active and connected sources (`source_id`, `capacity_ML`, `cost_per_ML`) for the demand zone.
2. Sort sources from lowest to highest `cost_per_ML`.
3. Starting with the cheapest source, draw either its full `capacity_ML` or the remaining unmet demand, whichever is smaller.
4. If demand remains, move to the next-cheapest source and repeat step 3.
5. Continue until `required_volume_ML` is fully met, or all active sources have been exhausted.
6. If total available capacity across all active sources is less than `required_volume_ML`, mark the result as infeasible and report the unmet volume.
7. Tie-break rule: if two or more sources share the same `cost_per_ML`, they are ordered by ascending `source_id` (alphabetical) for reproducibility.

### Rounding rule

All volumes are rounded to one decimal place (ML); percentages (`percent_of_blend`) are rounded to one decimal place (%), consistent with the equal-blend baseline (Task 1).

### Scope note

This rule ranks sources on `cost_per_ML` only. It does not evaluate or claim to optimise water quality (pH, alkalinity, turbidity): a cheapest-first blend may or may not pass quality constraints, and this is treated purely as a cost-comparison baseline for the optimiser.

## 3. Worked Numerical Example

Toy-model configuration used (same illustrative values as Task 1, for direct comparison):

| `source_id` | `source_name` | `source_type` | `capacity_ML` (daily) | `cost_per_ML` (AUD) |
|---|---|---|---|---|
| silvan_reservoir | Silvan Reservoir | reservoir | 220 | 400 |
| thomson_reservoir | Thomson Reservoir | reservoir | 260 | 380 |
| sugarloaf_reservoir | Sugarloaf Reservoir | reservoir | 150 | 420 |

Demand zone: `zone_id = zone_1`, `required_volume_ML = 500`

Step 1: Sort by `cost_per_ML` ascending
1. Thomson (380)
2. Silvan (400)
3. Sugarloaf (420)

Step 2: Draw from Thomson (cheapest) first
min(capacity 260, remaining demand 500) = 260 ML drawn.
Remaining demand = 500 − 260 = 240 ML.

Step 3: Move to Silvan (next-cheapest)
min(capacity 220, remaining demand 240) = 220 ML drawn.
Remaining demand = 240 − 220 = 20 ML.

Step 4: Move to Sugarloaf (most expensive)
min(capacity 150, remaining demand 20) = 20 ML drawn.
Remaining demand = 20 − 20 = 0 ML. Demand fully met.

Final result:

| `source_id` | `volume_drawn_ML` | `percent_of_blend` | `cost_contribution` (AUD) |
|---|---|---|---|
| thomson_reservoir | 260.0 | 52.0% | 98,800 |
| silvan_reservoir | 220.0 | 44.0% | 88,000 |
| sugarloaf_reservoir | 20.0 | 4.0% | 8,400 |
| Total | 500.0 | 100.0% | 195,200 |

Demand supplied: 500.0 / 500 ML required → feasible, 0 ML unmet.

Comparison with equal-blend baseline (Task 1): cheapest-first totals $195,200 AUD vs. $199,500 AUD for equal-blend on the same configuration, a $4,300 saving, since cheapest-first fully exhausts the two lowest-cost sources before touching the most expensive one.

> Note on example values: as in Task 1, `capacity_ML` and `cost_per_ML` are illustrative placeholders, not the confirmed official toy-model configuration. Task 5 will re-run this rule against the official config once available.

## 4. Checklist

- [x] Sorting rule is clear (ascending `cost_per_ML`)
- [x] Capacity exhaustion is handled (move to next-cheapest source)
- [x] Cost ties are handled (alphabetical `source_id` tie-break)
- [x] Infeasibility is handled
- [x] Exact schema fields are used (`source_id`, `capacity_ML`, `cost_per_ML`, `required_volume_ML`, `percent_of_blend`)
- [x] A numerical example is included
- [x] The rule does not claim to optimise water quality (see Scope note)

## 5. Deliverable

- `Baseline_CheapestFirst.md` (this document)
