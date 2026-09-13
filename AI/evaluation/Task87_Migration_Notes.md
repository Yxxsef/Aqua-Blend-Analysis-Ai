# Task 87 — KPI Calculator/Gate vs. the Confirmed MILP Output Contract

## Summary

`kpi_calculator.py` and `kpi_gate.py` were checked directly against the real `milp_model_output`
table schema, and later against an actual captured row provided by the team, not assumed
correct because other modules were already updated. Three real bugs were found and fixed. One
larger, cross-module inconsistency was found and is flagged to the team rather than fixed here,
since it isn't this module's file to change.

## What was checked

- The real `milp_model_output.sql` schema (all 3 tables).
- `AI/integration/supabase_repository.py::normalize_output_columns()` — the real function that
  bridges the flat table columns into the canonical Results JSON shape this module expects.
  Confirmed via `AI/main.py` that this normalization runs before `kpi_gate.evaluate()` is called.
- **A real captured `milp_model_output` row**, provided directly by the team (`tests/fixtures/
  milp_model_output_example.json`). This was the missing piece from the first pass of this task —
  everything below Finding 1 was only discoverable once real data was available; synthetic
  fixtures built from the schema's column names alone could not have caught it.
- `AI/results/Results_JSON_Field_Map.md` — the confirmed contract document.

## Finding 1 (fixed): `FEASIBLE` was incorrectly treated as a valid feasible status

`KPI_Set.md` always hedged this conditionally: *"FEASIBLE: feasible, if this status is officially
supported by the MILP contract."* `Results_JSON_Field_Map.md` states explicitly: *"FEASIBLE must
not be used unless it exists in the confirmed contract"* — it does not. `FEASIBLE_STATUSES` is
now `{"OPTIMAL"}` only. `SUCCESS` is equally rejected. Both confirmed with regression tests.

## Finding 2 (fixed, using the real captured row): `demand_zones` uses different field names than assumed

The real row's `demand_zones` entries use `delivered_ml_per_day` and `unmet_demand_ml_per_day` —
not `demand_ml_per_day`/`volume_supplied_ml_per_day`, which this module previously required.
There is no direct "required demand" field; it is derived as `delivered + unmet`. Before this fix,
`calculate_demand_satisfaction()` returned `N/A` against the real row every time. Fixed to detect
and support both field-name sets, so the older toy-model reference data (Sprint 1–3) still works
unchanged. Confirmed against the real row: now correctly returns `100.0`.

## Finding 3 (fixed, using the real captured row): the `quality` column's real shape has no `safety_margin_percent` or `by_plant` at all

The real `quality` column is `{"applies_to": ..., "plant_inflow": [{"plant_id", "parameters": [{
"parameter_id", "model_value", "model_min", "model_max", "within_limits", "binding_lower",
"binding_upper", "reported_value", "reported_unit", "transform", ...}]}]}` — nothing like the
`by_plant.<plant_id>.<parameter>.safety_margin_percent`/`.status` shape this module previously
required. Before this fix, both `minimum_safety_margin` and `quality_violations` returned `N/A`
against the real row every time.

Fixed: `_collect_quality_entries()` now detects and handles both shapes. For the real shape,
`within_limits` (`True`/`False`) is used directly as the PASS/FAIL status (it's the solver's own
ground truth, more reliable than deriving one), and `safety_margin_percent` is derived using
KPI_Set.md's own margin formula: `min(value-min, max-value)/(max-min)*100`.

**Design decision flagged for team confirmation:** the margin is computed using `model_value`/
`model_min`/`model_max` (the "model" units), not `reported_value` (the human-readable unit). This
was checked against the real row's pH entry specifically: `reported_value` is `7.5` (pH), but
`model_value` is `31.62...` (hydrogen-ion concentration in nmol/L, via the `ph_to_hydrogen_ion`
transform) — and `within_limits` is only consistent with the model bounds, not the reported ones.
The constraint is actually enforced in model space, so the margin is computed there too. For an
identity-transform parameter (turbidity, alkalinity in the real row), model and reported values
coincide, so this makes no practical difference for those two. It only matters for a
non-identity-transform parameter like pH. Confirmed with a dedicated regression test
(`test_ph_margin_is_computed_in_model_units_not_reported_units`).

## Finding 4 (flagged, not fixed here — bug in shared code): `normalize_output_columns()` double-wraps the real `quality` shape

Confirmed by feeding the real captured row through the real function: the output was
`water_quality: {"applies_to": null, "by_plant": {"applies_to": ..., "plant_inflow": [...]}}` —
the entire real `quality` blob (including its own `plant_inflow` key) got nested one level too
deep under a synthetic `"by_plant"` wrapper, rather than being recognised and passed through
correctly. This module now defensively recovers the real structure from underneath that
incorrect wrapping rather than silently returning nothing, but the underlying bug is in
`supabase_repository.py`, not this module's file. Flagged to the team.

## Finding 5 (flagged, not fixed here — bug in shared code): every plant lands in `plants.active`, regardless of its real `activated` value

Confirmed with the real row: `PLANT_002` has `"activated": false`, but after
`normalize_output_columns()`, it still appears in `plants.active` (with `plants.inactive` always
empty). This module now re-checks each plant's own `activated` field defensively, rather than
trusting the pre-split list, so an inactive plant is correctly excluded from the "must have
complete quality data" check regardless. The underlying bug is in `supabase_repository.py`,
not fixed here. Flagged to the team. Confirmed with a regression test using the real row
(`test_inactive_plant_is_correctly_excluded_despite_the_shared_bug`).

## Finding 6 (flagged, not fixed here): a three-way inconsistency on the status vocabulary

While confirming Finding 1, found that three modules currently disagree on what counts as a valid
solver status:

| Module | Statuses treated as valid |
|---|---|
| `Results_JSON_Field_Map.md` (confirmed contract) | `OPTIMAL`, `INFEASIBLE`, `UNBOUNDED`, `TIME_LIMIT`, `ERROR` |
| `llm_validator.py` | Matches the confirmed doc exactly, with its own comment citing the same reasoning independently |
| `results_validator.py` (as it stood at the time this was first checked) | `VALID_STATUS` included both `SUCCESS` and `FEASIBLE`, contradicting the confirmed doc |
| `kpi_calculator.py` (this task, now fixed) | Matches the confirmed doc |

`results_validator.py` is not explicitly owned by any Sprint 4 task, so nobody is currently
assigned to fix it. Raising this with the team rather than editing that file directly.

## Deliverables

- `kpi_calculator.py` — `FEASIBLE_STATUSES` corrected; `calculate_demand_satisfaction()` and
  `_collect_quality_entries()` rewritten to support both the old canonical shape and the real
  v1/flat-column field names, confirmed against an actual captured row, not just synthetic data.
- `tests/test_kpi_calculator.py` — one existing test corrected, one new regression test added.
- `tests/test_kpi_supabase_integration.py` — 11 tests total. Covers synthetic rows built from the
  real schema's column names, plus (critically) **the actual real captured row itself**
  (`tests/fixtures/milp_model_output_example.json`), checked into the repo as a permanent
  regression fixture. Confirms a full correct `PASS`, the pH model-vs-reported-units margin
  decision, and that the inactive-plant bug in the shared normalization function doesn't leak
  into an incorrect result here.
- `KPI_Set.md` — the `FEASIBLE` interpretation rule updated to match the resolved contract.
- This document.

## What was not changed

- `results_validator.py` and `supabase_repository.py` — both flagged, not edited. This module
  works defensively around the two real bugs found in the latter, but the bugs themselves
  belong to whoever owns that file.
- `kpi_calculator.py`/`kpi_gate.py`'s core logic and structure — unchanged. All fixes are
  additive (supporting a second real field-name shape alongside the old one), so the existing
  Sprint 1–3 toy-model tests still pass unmodified.

## What's still open

- No known remaining gaps for the fields this module actually reads. Everything KPI_Set.md's six
  KPIs depend on has now been confirmed against a real row: `solver_status`, `total_cost`,
  `demand_zones[]`, and `quality.plant_inflow[]`.
- The `results_validator.py` status-vocabulary inconsistency (Finding 6) is still unresolved by
  the team.
- The two `supabase_repository.py` bugs (Findings 4 and 5) are still unresolved by the team; this
  module is defensively correct regardless, but the shared function itself should still be fixed
  so other consumers of it aren't affected the same way.
- **`supabase_repository.py` itself is not on `master` yet.** It lives on the still-unmerged
  `ai-final-integration-polish` / `task-61-ai-main-pipeline` / `task-86-main-output-contract`
  branches. `test_kpi_supabase_integration.py` uses `pytest.importorskip` to skip gracefully
  (not fail) when that module isn't importable in the current checkout, the same pattern Task 72
  used for its dependency on Task 71 before that merged. `kpi_calculator.py`'s actual fixes are
  fully covered by `test_kpi_calculator.py` independently of this, so this PR isn't blocked on
  waiting for that other branch, but the Supabase-integration tests will only really execute
  (rather than skip) once one of those branches lands.
