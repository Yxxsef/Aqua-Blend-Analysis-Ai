# MILP Output Validation Notes — Task 56

Date: 2026-09-03

Scope: validate `results_validator.py` and `results_adapter.py` against the
real MILP output contract v1 fixture
(`AI/results/tests/fixtures/output_contract_v1.json`, copied byte-exact from
the delivered `output_contract_v1.json`).

## Changes applied (each directly justified by the v1 fixture)

- Required top-level fields replaced with the v1 set: `schema_version`,
  `run_id`, `scenario`, `validation`, `solver`, `summary`, `sources`,
  `plants`, `demand_zones`, `flows`, `quality`, `warnings`.
- `scenario_id` relocated to `scenario.scenario_id` (validated there).
- `sources` changed from a `{selected, unused}` object to a flat list of
  source objects; per-entry non-empty `source_id` still enforced.
- `plants` changed from an `{active, inactive}` object to a flat list of
  plant objects.
- `transfer_paths` renamed to `flows` (object with
  `source_to_plant` / `plant_to_zone` lists).
- `water_quality` renamed to `quality` (object).
- Top-level `status` and the `VALID_STATUS` enum check removed: v1
  expresses run state via `scenario.status`, `solver.status`,
  `validation.*.status` and `solver.is_feasible` / `solver.is_optimal`.
  Only string typing is validated — no new enum was invented.
- `constraints`, `diagnostics`, `data_flags` (and all provenance checks)
  removed from validation: none of them exist in the v1 output.
- Adapter pass-through updated to the v1 fields (`schemaVersion`, `runId`,
  `scenario`, `validation`, `solver`, `summary`, `sources`, `plants`,
  `demandZones`, `flows`, `quality`, `warnings`).
- Task 21 optional fields (`solved_at`, `binding_constraints_summary`,
  `alternative_feasible_solutions`, `sensitivity_to_key_assumptions`,
  `explanation`) are still mapped when present — `binding_constraints_summary`
  is present in the v1 fixture; the others remain per the Task 21 field map.

## Unresolved contract questions (not guessed — awaiting MILP team)

1. **Provenance / data flags.** v1 has no `data_flags` block and no
   per-source `provenance` / `has_estimated_values`. The only related
   v1 fields are `scenario.data_source` (incl. `allow_estimated_values`)
   and the loader check `estimated_values_allowed_by_policy`. Where does
   per-field provenance live in v1? Note: `confidence_flagger.py` reads
   `results["data_flags"]["sources"]` and will break against v1 output —
   out of Task 56 scope, flagged for follow-up.
2. **Diagnostics.** v1 has no `diagnostics` object. `solver` carries only
   `status`, `is_feasible`, `is_optimal`, `objective_value`, `version` —
   no solver name, solve time, optimality gap, or variable/constraint
   counts. Intentionally dropped or pending?
3. **Status enums.** Only single samples observed (`scenario.status`:
   "draft", `solver.status`: "NOT_SOLVED", `validation.*.status`:
   "NOT_RUN", `sources[].selection_status`: "PENDING"). Solved/failed
   value sets are undefined, so the validator checks types only.
4. **Constraints.** The old top-level `constraints[]` array is gone. The
   `validation.*.checks[]` entries use different ids/granularity
   (e.g. `demand_satisfaction` vs `demand_satisfaction_zone_1`), and it
   is unclear what `binding_constraints_summary` entries reference in v1.
5. **Objective / costs.** No confirmed v1 equivalent of the old
   `objective{total_cost, currency, cost_breakdown}`. Candidates are
   `solver.objective_value` and `summary.costs.*` (renamed and extended),
   but no mapping is confirmed. There is no currency field anywhere in v1.
6. **run_id.** Present but `null` in the fixture; type and semantics
   undefined, so no type check is applied.
7. **Nullability / run lifecycle.** The fixture is an unsolved run
   (`solver.status` = "NOT_SOLVED", decision values `null`). The
   solved-run shape (which fields become non-null, whether structure
   changes) is unobserved — a solved v1 fixture is needed before
   value-level validation can be added without guessing.
8. **Quality restructure.** `quality.plant_inflow[].parameters[]` carries
   dual model/reported representations and transforms (e.g. pH ↔
   `hydrogen_ion_concentration_mol_l` in nmol/L); `safety_margin_percent`
   is gone. Mapping for downstream consumers is undefined.
9. **Flow IDs.** `flows` entries have no `path_id`; they are identified
   only by `source_id` / `plant_id` / `zone_id` pairs. Uniqueness rules
   unconfirmed.
10. **Task 21 optional fields.** `solved_at`,
    `alternative_feasible_solutions`, `sensitivity_to_key_assumptions`
    and `explanation` are absent from the v1 fixture. Retained as
    optional pass-through per the Task 21 field map, pending confirmation
    they still exist in v1.
