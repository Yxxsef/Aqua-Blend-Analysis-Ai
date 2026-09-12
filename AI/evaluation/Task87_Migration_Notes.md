# Task 87 — KPI Calculator/Gate vs. the Confirmed MILP Output Contract

## Summary

`kpi_calculator.py` and `kpi_gate.py` were checked directly against the real `milp_model_output`
table schema (`AI/integration/supabase_schema/milp_model_output.sql`), not assumed correct
because other modules were already updated. One real bug was found and fixed. One larger,
cross-module inconsistency was found and is flagged to the team rather than fixed here, since
it isn't this module's file to change.

## What was checked

- The real `milp_model_output.sql` schema (all 3 tables: `milp_model_input`, `milp_model_output`,
  `milp_ai_output`).
- `AI/integration/supabase_repository.py::normalize_output_columns()` / `extract_canonical_output()`
  — the real function that bridges the flat table columns into the canonical Results JSON shape
  this module expects. Confirmed via `AI/main.py` (line ~238) that this normalization runs
  **before** `kpi_gate.evaluate()` is ever called — this module does not need to read raw flat
  columns directly, and was not rewritten to do so.
- `AI/results/Results_JSON_Field_Map.md` — the actual confirmed contract document.
- `AI/results/results_validator.py` and `AI/explanations/llm_validator.py` — cross-checked for
  consistency on the status vocabulary.

## Finding 1 (fixed): `FEASIBLE` was incorrectly treated as a valid feasible status

`KPI_Set.md` always hedged this conditionally: *"FEASIBLE: feasible, if this status is officially
supported by the MILP contract."* That condition is now resolved. `Results_JSON_Field_Map.md`
states explicitly: *"FEASIBLE must not be used unless it exists in the confirmed contract"* — and
it does not appear anywhere in the confirmed status enumeration.

`kpi_calculator.py`'s `FEASIBLE_STATUSES` previously included `"FEASIBLE"` unconditionally. Fixed:
`FEASIBLE_STATUSES` is now `{"OPTIMAL"}` only. A `FEASIBLE` status is now correctly treated as
unrecognised (`UNKNOWN`), the same as any other unconfirmed value. Updated the one existing test
that asserted the old (incorrect) behaviour, and added two new regression tests
(`test_feasible_status_is_rejected_not_confirmed_valid`,
`test_success_status_is_rejected_not_silently_treated_as_optimal`).

## Finding 2 (flagged, not fixed here): a three-way inconsistency on the status vocabulary

While confirming Finding 1, found that three modules currently disagree on what counts as a valid
solver status:

| Module | Statuses treated as valid |
|---|---|
| `Results_JSON_Field_Map.md` (confirmed contract) | `OPTIMAL`, `INFEASIBLE`, `UNBOUNDED`, `TIME_LIMIT`, `ERROR` |
| `llm_validator.py` | Matches the confirmed doc exactly (`SOLVER_STATUS_WORDS`), with its own comment citing the same reasoning independently |
| `results_validator.py` | `VALID_STATUS` includes **both** `SUCCESS` and `FEASIBLE`, contradicting the confirmed doc |
| `kpi_calculator.py` (this task, now fixed) | Matches the confirmed doc |

`results_validator.py` is not explicitly owned by any Sprint 4 task (86–94), so nobody is
currently assigned to fix it. Raising this with the team rather than editing that file directly,
since it's outside this task's scope and outside this stream member's ownership.

## Finding 3 (documented, not fully resolvable yet): the `quality` jsonb column's internal shape is unverified against a real row

No real captured `milp_model_output` row exists anywhere in the repo as of this task (checked
`master` and `ai-final-integration-polish`). `normalize_output_columns()` has a defensive
fallback for when `quality` doesn't have a `by_plant` key (assumes the column is already a bare
per-plant mapping and nests it), and the new regression test suite confirms `kpi_calculator`
handles *that fallback's output* correctly — but this cannot confirm the fallback's *input*
assumption is what a real row actually looks like. Re-run
`tests/test_kpi_supabase_integration.py` against a real captured row the moment one is available.

## Deliverables

- `kpi_calculator.py` — `FEASIBLE_STATUSES` corrected; comments document the reasoning and link
  to `Results_JSON_Field_Map.md`.
- `tests/test_kpi_calculator.py` — one existing test corrected, one new regression test added
  (`SUCCESS`).
- `tests/test_kpi_supabase_integration.py` — new. 8 tests running the real
  `normalize_output_columns()` against synthetic rows built strictly from
  `milp_model_output.sql`'s real column names, feeding the result into the real
  `calculate_kpis()`/`evaluate_gate()`. Covers: a full OPTIMAL pass matching the known Sprint 2/3
  reference numbers exactly, lowercase-to-uppercase status normalization, both deprecated status
  values (`SUCCESS`/`FEASIBLE`) being correctly rejected end-to-end, the `NOT_SOLVED` default
  being handled safely, and the `quality`-without-`by_plant` fallback shape.
- `KPI_Set.md` — the `FEASIBLE` interpretation rule and required-target line updated to match
  the resolved contract; the `results_validator.py` inconsistency documented inline.
- This document.

## What was not changed

- `results_validator.py` — flagged, not edited (see Finding 2).
- `kpi_calculator.py`/`kpi_gate.py`'s core logic and structure — unchanged. The fix was narrowly
  scoped to the one incorrect status value; everything else already worked correctly once fed
  through the real normalization layer, confirmed by the new integration tests.
