# Baseline Validation Notes — Task 18

Compares Sprint 2's coded baselines (`baseline_runner.py`, running Tasks 15, 16, 17) against the Sprint 1 hand calculations (`Baseline_HandCalculations.md`), and records the differences that showed up between the two.

## How to run

```bash
cd AI/tests
python -m pytest test_baseline_runner.py -v
```

```bash
cd AI/baselines
python3 baseline_runner.py <scenario.json> [zone_id]
```

```python
from baseline_runner import run_all_baselines
result = run_all_baselines(scenario_dict)
```

`zone_id` is only needed when the scenario has more than one demand zone. `baseline_equal_blend.py`, `baseline_cheapest_first.py`, and `baseline_fixed_priority.py` must be importable from the same folder as `baseline_runner.py` — it imports all three directly.

## 1. Result: coded output matches the hand calculations

Toy configuration (demand 500 ML/day, Silvan 350 / Yarra Kew 300 / Groundwater 60 link capacities, confirmed costs 400 / 235 / unconfirmed):

| Baseline | Volumes (Silvan / Yarra Kew / GW) | Total cost | Matches hand calc? |
|---|---|---:|---|
| Equal-blend | 220 / 220 / 60 | incomplete (GW cost unconfirmed) | Yes — Section 5 |
| Cheapest-first (documented 300 cap) | 200 / 300 / 0 | 182,500.00 | Yes — Section 6 |
| Fixed-priority | 350 / 150 / 0 | 207,250.00 | Yes — Section 7 |

No numeric discrepancies. All three coded baselines reproduce their hand-calculated counterparts exactly, within the tolerance each baseline's own test suite uses (volumes/percentages to 0.05, cost to 0.01).

## 2. Differences found, and why they exist

### 2.1 `objective.cost_breakdown` key count differs by baseline

Equal-blend's raw result carries two keys (`source_draw_cost`, `plant_treatment_cost`). Cheapest-first and fixed-priority carry four (adding `source_activation_cost`, `plant_activation_cost`).

**Cause:** Equal-blend (Task 15) was built before the MILP output contract added activation-cost fields. Cheapest-first and fixed-priority (Tasks 16, 17) were built after. Each is correct against the contract version it targeted.

**Resolution:** not a code fix. `baseline_runner.py` normalizes every result to the full four-key set, filling equal-blend's two missing keys with `0.00` — a real zero (no activation-cost concept existed for that baseline), not a stand-in for an unknown value. See `baseline_runner.py`'s module docstring for the same reasoning in code.

### 2.2 `priority_order` and `metadata` only appear on fixed-priority's result

**Cause:** fixed-priority's own approved rule (Task 17 checklist) specifically requires storing the heuristic's label and a short justification in `metadata`. Equal-blend and cheapest-first have no equivalent requirement.

**Resolution:** not a gap to close. The runner normalizes both fields to `None` on the two baselines that don't produce them, so every baseline's result carries the same key set, and a consumer can tell "this baseline doesn't have this concept" (`None`) apart from "this baseline has this concept and it's blank" (which does not occur here).

### 2.3 No rounding discrepancies found

All three baselines round volumes and percentages to one decimal place and money to two, applied once on output, never mid-calculation. No case was found where this produced a mismatch against the hand-calculated figures.

## 3. Water quality

No baseline computes water quality. `baseline_runner.py` treats a `water_quality` key appearing on any baseline's result as an error rather than passing it through, since no baseline is currently approved to make that claim. This matches all three baselines' own stated position (per their implementation docs) and the Task 18 checklist's "include water-quality values only when approved code calculates them."

## 4. Cost-breakdown consistency check

`baseline_runner.py` also checks each normalized result against `model_output_specification.md` section 5, rule 1: `cost_breakdown` must sum to `total_cost`. This is checked only when `total_cost` is present — a baseline with an incomplete cost (e.g. equal-blend on the toy config, where groundwater's price is unknown) has no total to check against, and that incompleteness is already visible via `cost_is_complete`.

No inconsistency was found in any of the three real baselines during testing; the check itself is exercised directly against a deliberately broken objective in `test_baseline_runner.py`, since none of the three actual baselines currently produce one to trigger it against naturally.

## 5. Feasibility and the demand-800 case

All three baselines are feasible on the toy configuration (500 ML/day demand against 710 ML/day total capacity). Each baseline's own test suite additionally confirms `INFEASIBLE` is correctly reported once demand exceeds total capacity (tested at 800 ML/day in each baseline's individual test file). The runner's own test suite confirms this holds when all three run together via the committed plant-outage scenario, where every baseline reports infeasible for the same reason (the only plant is disabled, so no source has a route to the zone).

## 6. Open items carried forward from Tasks 15–17

These weren't introduced by Task 18 and aren't fixed by it — flagged here so they aren't lost:

- `FEASIBLE`/`INFEASIBLE` as status strings haven't been confirmed acceptable downstream by anyone outside this stream; all three baselines' Results JSON only formally defines `OPTIMAL` and its solver-status siblings.
- The scenario-parsing logic (source resolution, connectivity, capacity precedence) is duplicated identically across all three baseline files. `baseline_runner.py` does not deduplicate this — it only normalizes each baseline's *output*, not its internals. Worth extracting into one shared module in a later sprint if all three baselines are settled.
- `MILP/json_contracts/output_contract_v1.json` uses a different, richer schema than the one all three baselines (and this runner) currently target. Not resolved here; the runner's normalization is built against the current target contract and would need revisiting if that changes.

## 7. What was tested

`test_baseline_runner.py` (35 tests): shape consistency across all three baselines, scenario-mutation isolation, end-to-end agreement with the Sprint 1 hand calculations for all three baselines, comparison logic (cheapest by total cost, correctly excluding baselines with incomplete totals), the cost-breakdown consistency check (both a passing and a deliberately-failing case), JSON serializability, zone selection (single-zone default, multi-zone requiring an explicit `zone_id`, multi-zone with the wrong zone omitted correctly), determinism (running twice gives identical results), input validation (non-dict scenario), zero-demand handling, and the team's committed scenario files (normal-year and plant-outage).
