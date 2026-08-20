# Task 19 — KPI Calculator and Pass/Fail Gate

Implements the six KPIs defined in `AI/evaluation/KPI_Set.md` (PR #18, Yousef) against the
MILP Results JSON contract (`model_output_contract.json` / `model_output_specification.md`).

## Files

- `kpi_calculator.py` — calculates each of the six KPIs individually. Never estimates a
  missing value; every result carries an explicit `status` of `OK`, `N/A`, `INCOMPLETE`,
  or `UNKNOWN` (feasibility only), per KPI_Set.md §2 rule 4.
- `kpi_gate.py` — applies the pass/fail rules on top of the calculator's output and returns
  exactly one of `PASS`, `FAIL`, `UNABLE_TO_EVALUATE`.
- `test_kpi_calculator.py`, `test_kpi_gate.py` — see Testing below.
- `reference_output.json` — the real `model_output_contract.json` reference scenario, used
  as the test fixture that the "Sprint 1 sample calculations" checklist item requires.
- `sample_kpi_and_gate_results.json` — actual output of running this code against the
  reference scenario (not hand-typed).

## Inputs and outputs

**Input:** a single Results JSON object matching `model_output_contract.json`'s shape (either
the optimiser's real output, or a coded baseline's output, as long as it uses the same field
names per `model_output_specification.md`, "Naming follows the `data_loader.py`").

**Output:**
- `kpi_calculator.calculate_kpis(results)` → a `KPIReport` (six `KPIResult` objects, one per
  KPI, each with `status`, `value`, `unit`, `detail`).
- `kpi_gate.evaluate(results)` → `(KPIReport, GateResult)`, where `GateResult.overall_status`
  is `PASS`, `FAIL`, or `UNABLE_TO_EVALUATE`, with a `reasons` list explaining why.

## Gate logic

Per KPI_Set.md §2 ("General evaluation rules"):

1. **Feasibility is the first gate.** `INFEASIBLE`/`UNBOUNDED`/`ERROR` → `FAIL`. Anything
   where feasibility itself can't be confirmed (missing `status`, or `TIME_LIMIT` without a
   verified incumbent) → `UNABLE_TO_EVALUATE`, not `FAIL` — we don't know it's bad, we just
   don't know it's good either.
2. **Demand and quality are mandatory.** Demand satisfaction below 100%, or any confirmed
   quality violation → `FAIL`. If either can't be calculated at all (`N/A`) or only partially
   (`INCOMPLETE`) → `UNABLE_TO_EVALUATE`, since claiming `PASS` or `FAIL` on incomplete
   quality data would be asserting something we can't actually confirm.
3. **Cost and the chemical KPI never gate the result.** Both are comparative-only per
   KPI_Set.md ("lowest among otherwise valid results"), not a fixed threshold. Two otherwise-
   identical feasible/complete results with wildly different costs both `PASS` — this is
   explicitly tested (`test_cost_never_gates_the_result`).

## Design decisions worth flagging to the team

- **"Incomplete" detection for water quality (KPI 4 & 5).** The output contract alone
  doesn't say which parameters *should* be present for a given plant. I used the three
  parameters named in the current `model_input_contract.json`'s `quality_limits.parameters`
  (pH, alkalinity, turbidity) as the expected set — hardcoded as `EXPECTED_QUALITY_PARAMETERS`
  in `kpi_calculator.py`. If the input contract's parameter set changes, this constant needs
  updating in one place. Worth confirming this is the right approach with whoever owns Task 21
  (the Results JSON validator), since they may already have a cleaner source of truth for
  "expected parameters per plant."
- **`TIME_LIMIT` handling.** KPI_Set.md explicitly says the current reference JSON has no
  incumbent-feasibility field, so every `TIME_LIMIT` result today resolves to
  `UNABLE_TO_EVALUATE`. The code checks for an optional `incumbent_feasible` field defensively,
  in case one gets added later, but this path is currently untested against real solver output
  since no such example exists yet.
- **Chemical KPI (KPI 6) is permanently `N/A` for now.** `APPROVED_CHEMICAL_FIELDS` is
  deliberately an empty whitelist. Per KPI_Set.md, this must never fall back to
  `plant_treatment_cost` or any other unrelated field — so it stays `N/A` until a real field is
  added to the output contract and explicitly approved.

## Testing

Run with:
```
pytest test_kpi_calculator.py test_kpi_gate.py -v
```

42 tests, all passing. Coverage includes:
- The real reference scenario (`scenario_2026_07_17_001`), cross-checked field-by-field
  against KPI_Set.md §5's own manual calculation table.
- Every feasibility status value (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNBOUNDED`, `ERROR`,
  `TIME_LIMIT` with and without an incumbent, missing, and unrecognised).
- Demand satisfaction: normal, excess-supply, multi-zone, missing-field, and zero-demand cases.
- Total cost: the specific "infeasible but a cost value is still present" case.
- Quality KPIs: all-pass, one-fail, fallback-negative-margin-without-status, fully-missing,
  and partially-missing (`INCOMPLETE`) cases.
- Gate logic: pass, each individual fail reason, each `UNABLE_TO_EVALUATE` trigger, and the
  cost-never-gates guarantee.

## Fixed after review

**TIME_LIMIT-with-verified-incumbent feasibility bug** (flagged by AbdullaAlmannaee, refined by
Amxntha): `calculate_feasibility()` correctly marked a `TIME_LIMIT` result with a verified
incumbent as feasible (`status="OK"`, `value="TIME_LIMIT_FEASIBLE_INCUMBENT"`), but
`calculate_total_cost()` and `evaluate_gate()` each checked `feasibility.value in
FEASIBLE_STATUSES` directly, a set that didn't include that value — so both silently
contradicted the calculator's own answer (cost came back `N/A`, gate came back
`UNABLE_TO_EVALUATE`).

**Why the naive fix (`feasibility.status == "OK"`) would have been worse:** `status="OK"` means
"we have a confirmed, definitive answer," not "feasible" — `INFEASIBLE`, `UNBOUNDED`, and
`ERROR` all also return `status="OK"`. Switching the check to `status == "OK"` would have made
`calculate_total_cost()` report a real cost for infeasible results too, which is the exact
behaviour `KPI_Set.md` explicitly forbids (see `test_na_when_infeasible_even_if_value_present`,
which still passes after this fix).

**Actual fix:** added `is_confirmed_feasible()`, a single shared helper checking against
`CONFIRMED_FEASIBLE_VALUES = {"OPTIMAL", "FEASIBLE", "TIME_LIMIT_FEASIBLE_INCUMBENT"}`, used by
both `calculate_total_cost()` and `evaluate_gate()`, per Amxntha's suggestion. Added a
calculator-level test (`test_ok_for_time_limit_with_verified_incumbent`) and an end-to-end
gate-level test (`test_time_limit_with_verified_incumbent_passes_when_otherwise_complete`), so
this path is now covered at both layers.

## Other review feedback

- **Trminh06-work** suggested moving the test files into a `tests/` subfolder. Flagging that
  `AI/explanations/test_json_explainer.py` (Task 9) lives alongside its source file rather than
  in a nested folder, so moving these would be inconsistent with that existing precedent unless
  the team wants to standardise on `tests/` going forward, happy to move it either way once
  that's settled.
- **Trminh06-work** also noted no official `model_output_contract.json` exists from the MILP
  team yet. Confirmed, already flagged below under Known open items, `reference_output.json`
  is what the AI stream has today, not yet an official MILP-team-published file, will revisit
  if/when one is published.

## Known open items

- Not yet tested against real coded-baseline output (Tasks 15–17), since their confirmed
  output shape wasn't finalised at the time this was written. The calculator should work
  as-is against any object matching the output contract's field names, but this is unverified
  against actual baseline code output.
- `KPI_Set.md` (PR #18) is itself still open and was branched from an old point in `master`'s
  history — if it changes before merging, this implementation should be re-checked against
  the final version.
