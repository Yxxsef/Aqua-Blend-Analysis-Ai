# Baseline Hand Calculations

Task: 5: Calculate and validate all three baselines
Owner: Abdulla
Status: Draft, ready for second-member check
First draft due: Saturday 25 July 2026
Final draft due: Sunday 26 July 2026
Temporary submission: Analysis & AI Teams chat
Dependencies: Tasks 1, 2, 3 and 4, plus the official toy-model configuration
Units: Volume (ML); Cost (AUD); Blend share (%)

---

## 1. Purpose

This document applies the three approved baseline rules (`Baseline_EqualBlend.md`, `Baseline_CheapestFirst.md`, `Baseline_FixedPriority.md`) by hand to the official toy-model configuration, to confirm the rules work correctly before they are coded or compared against the optimiser (Sprint 2).

---

## 2. Confirmed inputs used

| Field | Value | Source |
|---|---|---|
| `demand_zones[].zone_id` | `zone_1` | `model_input_contract.json` |
| `demand_zones[].demand_ml_per_day` | 500 | `model_input_contract.json`, matches `toy_demand_value.json` |
| `sources[].source_id` | `silvan_reservoir`, `yarra_kew`, `groundwater_bore_1` | `model_input_contract.json` |
| `source_to_plant_links[].maximum_flow_ml_per_day` (used as `capacity_ML`, per Tasks 1–4) | Silvan 350, Yarra Kew 300, Groundwater Bore 1 60 | `model_input_contract.json` |
| `cost_per_ml`, selected sources | Silvan 400, Yarra Kew 235 | `model_output_contract.json` (confirmed reference solve, `scenario_2026_07_17_001`, same scenario as our toy configuration) |
| `cost_per_ml`, `groundwater_bore_1` | Not disclosed — output contract only echoes cost for **selected** sources. `groundwater_bore_1` is unused in the reference solve, and its exclusion reason states its cost is "higher than the selected sources," so it is known to exceed 400, but no exact figure exists in any file we have. | `model_output_contract.json` |
| `treatment_cost_per_ml` | 64 | `model_input_contract.json`, applies to all inflow at `facility_1` regardless of source |

**Note on cost:** Tasks 1 and 2 (approved) treated `cost_per_ML` as pending. The confirmed reference solve in `model_output_contract.json` now discloses real, database-sourced costs for the two sources it selected. This document uses those confirmed values. This does not require reopening Tasks 1/2, since their rules and worked examples remain correct; it simply means Task 5 has better data available than they did at the time.

---

## 3. Critical open item found during this validation — `yarra_kew` capacity discrepancy

Before presenting the three baselines, this needs to be flagged, because it affects how the results below should be read.

The documented `capacity_ML` for `yarra_kew` (350/300/60 table above, from the link's `maximum_flow_ml_per_day`) is **300 ML/day**. But the confirmed reference solve's own constraint list shows `source_capacity_yarra_kew` as **binding with zero slack**, at a drawn volume of **290 ML/day** — meaning the source's real database capacity ($\overline{W}_s$) is 290, tighter than the 300 figure the link config states.

**Why this matters:** running cheapest-first using the documented 300 ML/day cap produces a total cost (182,500 AUD, see Section 5) that is *lower* than the confirmed MILP-optimal total (184,150 AUD). A valid heuristic can never beat the true optimum — if it does, the heuristic used a capacity that isn't real, and the resulting "solution" is not actually feasible. Re-running cheapest-first with 290 ML/day instead of 300 for `yarra_kew` reproduces the optimiser's exact source cost (152,150 = 152,150), which strongly confirms 290 is the source's real usable limit, not 300.

**Recommendation:** confirm with the Optimisation team whether `capacity_ML` should be read from the link's `maximum_flow_ml_per_day` (300) or the source's own database capacity (apparently 290) before this baseline is coded in Sprint 2. Silvan's own source-capacity constraint has very large slack (40,371), so this issue is specific to `yarra_kew` and does not affect Silvan or Groundwater Bore 1.

**Decision for this document:** Section 5 below computes the primary results using the documented 300 ML/day figure, for consistency with Tasks 1–4 and reproducibility by a second checker. A sensitivity re-check using 290 ML/day is included alongside cheapest-first specifically, since that is the only baseline where the two values actually produce a different result.

---

## 4. Assumption carried from Tasks 1–3

All three sources are active, available, and connected to `zone_1`, consistent with the worked examples in the approved Task 1–3 documents.

---

## 5. Baseline 1 — Equal-Blend

Rule from `Baseline_EqualBlend.md`, applied to the confirmed configuration.

Step 1: 500 ÷ 3 = 166.667 ML each (full precision).
Step 2: Groundwater Bore 1 (60) < 166.667 → capped, removed.
Step 3: Remaining 440 ÷ 2 = 220 ML each for Silvan and Yarra Kew.
Step 4: Silvan 220 ≤ 350 OK. Yarra Kew 220 ≤ 300 OK (also ≤ 290, so the capacity discrepancy in Section 3 does not affect this baseline).

| Source | Volume (ML) | % of blend | Cost (AUD) | Capacity usage |
|---|---:|---:|---:|---:|
| silvan_reservoir | 220.0 | 44.0% | 88,000.00 | 220/350 = 62.9% |
| yarra_kew | 220.0 | 44.0% | 51,700.00 | 220/300 = 73.3% |
| groundwater_bore_1 | 60.0 | 12.0% | not computable — cost unconfirmed | 60/60 = 100.0% |
| **Total** | **500.0** | **100.0%** | **≥ 139,700.00 (source only), + treatment** | |

- Treatment cost: 500 × 64 = 32,000.00 AUD (all baselines fully meet demand at 500 ML/day, so this figure is the same for all three).
- Treatment capacity usage: 500/600 = **83.3%** of `facility_1`'s processing capacity.
- Total cost: **≥ 171,700.00 AUD** (source cost for Silvan and Yarra Kew, plus treatment; Groundwater Bore 1's contribution is a genuine unknown, not an omitted zero).
- Demand supplied: 500.0 / 500 → **feasible, 0 ML unmet.**
- Water-quality results: **not computable.** Per-source raw pH/alkalinity/turbidity values live in the database and are not disclosed in any file available to this task. The confirmed reference output only reports the *blended* result for the optimiser's own specific 42%/58% ratio, which is a different blend from this baseline's 44%/44%/12%, so it cannot be reused here. This checklist item is marked unavailable, not assumed to pass.
- Constraint violations: none detected against what is computable (capacity, demand).

---

## 6. Baseline 2 — Cheapest-First

Rule from `Baseline_CheapestFirst.md`. That document used a placeholder source-type cost tiering (reservoir cheapest, river mid, groundwater priciest) because real costs were pending at the time. Real confirmed costs are now available for two of the three sources (Section 2), so this document uses them instead of the placeholder tiering.

**Real cost order:** Yarra Kew (235) < Silvan (400) < Groundwater Bore 1 (unconfirmed, but known to exceed 400). This is a different order from Task 2's placeholder (which had Silvan first) — flagged here, not silently substituted into Task 2's approved document.

### Primary result (documented 300 ML/day cap for Yarra Kew)

Step 1: Yarra Kew (cheapest) draws min(300, 500) = 300. Remaining = 200.
Step 2: Silvan draws min(350, 200) = 200. Remaining = 0.
Step 3: Groundwater Bore 1 not needed, draws 0.

| Source | Volume (ML) | % of blend | Cost (AUD) | Capacity usage |
|---|---:|---:|---:|---:|
| yarra_kew | 300.0 | 60.0% | 70,500.00 | 300/300 = 100.0% |
| silvan_reservoir | 200.0 | 40.0% | 80,000.00 | 200/350 = 57.1% |
| groundwater_bore_1 | 0.0 | 0.0% | 0.00 | 0/60 = 0.0% |
| **Total** | **500.0** | **100.0%** | **150,500.00** | |

- Treatment capacity usage: 500/600 = 83.3%.
- Total incl. treatment: 150,500.00 + 32,000.00 = **182,500.00 AUD**
- **Flag: this total (182,500) is lower than the confirmed MILP-optimal total (184,150) — see Section 3. This result should be treated as provisional, not confirmed feasible, until the capacity discrepancy is resolved.**

### Sensitivity re-check (290 ML/day cap for Yarra Kew, per the confirmed reference solve)

Step 1: Yarra Kew draws min(290, 500) = 290. Remaining = 210.
Step 2: Silvan draws min(350, 210) = 210. Remaining = 0.

| Source | Volume (ML) | % of blend | Cost (AUD) | Capacity usage |
|---|---:|---:|---:|---:|
| yarra_kew | 290.0 | 58.0% | 68,150.00 | 290/290 = 100.0% |
| silvan_reservoir | 210.0 | 42.0% | 84,000.00 | 210/350 = 60.0% |
| groundwater_bore_1 | 0.0 | 0.0% | 0.00 | 0/60 = 0.0% |
| **Total** | **500.0** | **100.0%** | **152,150.00** | |

- Treatment capacity usage: 500/600 = 83.3%.
This exactly reproduces the confirmed MILP-optimal source allocation (42% Silvan / 58% Yarra Kew) and source cost (152,150.00 AUD). This is expected: with only one treatment facility and no water-quality trade-off considered by this baseline, cheapest-first and the true optimum coincide once the real capacity is used. This is strong supporting evidence for the Section 3 finding.

- Demand supplied: 500.0 / 500 → feasible under both capacity readings.
- Water-quality results: not computable, same reasoning as Section 5 — though note the 290/210 split happens to match the optimiser's own blend exactly, so if per-source quality values become available later, the optimiser's blended result (Section 2, `model_output_contract.json`) could be reused directly for this specific version of the baseline.

---

## 7. Baseline 3 — Fixed-Priority

Rule from `Baseline_FixedPriority.md` (already updated with confirmed sources; reproduced here for completeness and cost calculation, which the original document left as "where applicable").

Priority order: Silvan Reservoir → Yarra Kew → Groundwater Bore 1 (unaffected by the cost discrepancy in Section 3, since this rule does not sort by cost).

Step 1: Silvan draws min(350, 500) = 350. Remaining = 150.
Step 2: Yarra Kew draws min(300, 150) = 150. Remaining = 0. (150 ≤ 290 too, so the capacity discrepancy does not affect this baseline either.)
Step 3: Groundwater Bore 1 not needed, draws 0.

| Source | Volume (ML) | % of blend | Cost (AUD) | Capacity usage |
|---|---:|---:|---:|---:|
| silvan_reservoir | 350.0 | 70.0% | 140,000.00 | 350/350 = 100.0% |
| yarra_kew | 150.0 | 30.0% | 35,250.00 | 150/300 = 50.0% |
| groundwater_bore_1 | 0.0 | 0.0% | 0.00 | 0/60 = 0.0% |
| **Total** | **500.0** | **100.0%** | **175,250.00** | |

- Treatment capacity usage: 500/600 = 83.3%.
- Total incl. treatment: 175,250.00 + 32,000.00 = **207,250.00 AUD**
- Demand supplied: 500.0 / 500 → feasible, 0 ML unmet.
- Water-quality results: not computable, same reasoning as Section 5.

---

## 8. Comparison and differences explained

| Baseline | Volumes (Silvan / Yarra Kew / GW) | Source cost (AUD) | Total incl. treatment (AUD) |
|---|---|---:|---:|
| Equal-blend | 220 / 220 / 60 | ≥ 139,700 (GW unknown) | ≥ 171,700 |
| Cheapest-first (documented cap) | 200 / 300 / 0 | 150,500 | 182,500 — **flagged as provisional, see Section 3** |
| Cheapest-first (real cap, 290) | 210 / 290 / 0 | 152,150 | 184,150 — **matches confirmed MILP optimum exactly** |
| Fixed-priority | 350 / 150 / 0 | 175,250 | 207,250 |
| **Confirmed MILP optimum** | **210 / 290 / 0** | **152,150** | **184,150** |

- **Why cheapest-first (real cap) matches the optimum:** with a single treatment facility and no quality trade-off modelled by any baseline, minimising cost reduces to "use the cheapest source to its real limit, then the next," which is exactly what the MILP does too in this simple case. This will not generally hold once water-quality constraints become binding or multiple facilities exist.
- **Why fixed-priority costs the most:** it ignores cost entirely and draws from Silvan (the more expensive of the two main sources at 400 AUD/ML) up to its full 350 ML/day before touching the cheaper Yarra Kew, the opposite of a cost-minimising order.
- **Why equal-blend can't be fully cost-ranked:** Groundwater Bore 1's cost is a genuine unknown, not a placeholder. Even so, its lower bound (≥171,700) already sits below fixed-priority's total, and it draws a meaningful 12% share from the least-connected, least-understood source — worth flagging to the team as a reason equal-blend may not be a reliable comparison point until Groundwater Bore 1's cost is confirmed.
- Groundwater Bore 1 is never used by either cost-based baseline, consistent with the confirmed reference solve's own stated exclusion reason.

---

## 9. Checklist

- [x] Equal-blend rule is applied correctly
- [x] Cheapest-first rule is applied correctly (both the documented-capacity version and a sensitivity re-check against the confirmed reference solve)
- [x] Fixed-priority rule is applied correctly
- [x] Official toy-model source names are used
- [x] Task 4 demand value is used (500 ML/day)
- [x] Costs are calculated using configuration values where confirmed; unconfirmed values (Groundwater Bore 1's cost) are marked as such, never invented
- [x] Capacities are not exceeded, under the documented configuration values
- [x] Source capacity usage is reported for every source in every baseline (% of that source's own capacity used)
- [x] Treatment capacity usage is reported for every baseline (500/600 = 83.3% throughout, since every baseline meets demand exactly)
- [x] Demand satisfaction is checked — all three baselines are feasible, 0 ML unmet in every case
- [ ] Water-quality limits are checked — **not possible with data currently available; per-source raw quality values are not disclosed anywhere in the files provided to this task.** Flagged as an open item, not silently skipped. The minimum-safety-margin calculation has the same root cause and is unavailable for the same reason.
- [x] Unsafe or incomplete results are marked infeasible where applicable — no infeasible cases arose, since total capacity (710 ML/day) comfortably exceeds demand (500 ML/day) in all three baselines
- [ ] A second member checks the calculations — pending
- [x] Differences between the baselines are explained (Section 8)

---

## 10. Deliverables

- `Baseline_HandCalculations.md` (this document)
- `baseline_results.csv`

## 11. Units

- Volume: ML
- Cost: AUD
- Blend share: %
- Water-quality units: not applicable this pass — see Section 9
