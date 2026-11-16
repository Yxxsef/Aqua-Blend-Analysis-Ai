# MILP output agreement for the Analysis & AI stream

**Backlog task:** 45, MILP outputs agreement
**Author:** Ali Alabdouli
**Status:** draft for review by the AI lead, the MILP lead and the AI/Optimisation bridge lead
**Checked against:** `Chameleon-company/Aqua-Blend` master at `1bd6ff6`, and the T2 AI code in `Yxxsef/Aqua-Blend-Analysis-Ai` at `d8cdd64`

## 1. Purpose

Tasks 38 (template fallback), 46 to 47 (local LLM) and 48 (LLM number verification) all turn the MILP result into text for users. Before any of them is built, the stream needs one agreed answer to two questions:

1. Which MILP output fields can be shown to users, and which must not be?
2. What should be shown when there is no valid solution?

This document is that answer. `presentation_rules.json` holds the same rules in a form code can read, and `presentation_gate.py` applies them, so tasks 38 and 48 do not each have to decide again.

This was not checked against the contract document alone. I ran the MILP pipeline on `master` and produced two real outputs, one feasible and one infeasible (`fixtures/`). Several differences between the contract and the actual output only show up that way (section 6).

## 2. Where the AI reads the output from

The AI reads `public.milp_model_output.raw_output_json`. The Backend entity (`Backend/Entities/MilpModelOutput.cs`) states that this column is the authoritative serialised `SolvedScenario`. The other columns on that table are flattened copies for querying and must not be used to rebuild the result.

## 3. The gate: decide the mode first

Every explanation starts by putting the output into one of three modes. The mode decides what may be shown.

| Order | Mode | When | What may be shown |
|---|---|---|---|
| 1 | `NO_SOLUTION` | `solver.is_feasible` is not `true` | Only the fields marked `when: always`: scenario ID, solver status, total demand, IDs, excluded sources, validation status (technical view). No flows, costs, shortfall or quality. |
| 2 | `INVALID_OUTPUT` | feasible, but `validation.output_consistency.status` is not `PASSED` | Same as `NO_SOLUTION`, plus the names of the failed checks in the technical view. |
| 3 | `VALID` | otherwise | Everything marked `present`. |

The gate matters because of what postprocessing does today on an infeasible run. It fills every withdrawal and flow with `0.0`, sets `summary.costs.total_cost` to `0.0`, sets `unmet_demand_ml_per_day` to the full demand (1200 ML/day in the fixture) and `demand_satisfied` to `false`. Read without the gate, an LLM would report "total cost 0, 1200 ML/day of demand unmet", which describes zero-filled placeholders, not a real result. The real fact is simply that no blend satisfies the constraints.

## 4. What will be presented (VALID mode)

"Present" means the value can be shown and quoted as a figure. Every field's full rule is in `presentation_rules.json`.

| Area | Fields | Notes |
|---|---|---|
| Result | `solver.status`, `summary.costs.total_cost` | Show a friendly label for the status. Quote `total_cost` or `solver.objective_value`, not both (they are equal when valid). |
| Totals | `summary.total_demand_ml_per_day`, `total_withdrawal_ml_per_day`, `total_treated_ml_per_day`, `total_delivered_ml_per_day`, `selected_source_count`, `active_plant_count` | Total demand may also be shown in the other two modes, because it is an input. |
| Cost breakdown | `total_source_fixed_cost`, `total_source_variable_cost`, `total_plant_fixed_cost`, `total_plant_variable_cost` | No currency (section 6, G11). |
| Sources | `source_id`, `activated`, `selection_status`, `withdrawal_ml_per_day`, `utilisation_percent`, `blend_ratio` (as a %), `variable_withdrawal_cost`, `total_source_cost` | IDs only. Display names come from `ScenarioData`. |
| Plants | `plant_id`, `activated`, `throughput_ml_per_day`, `utilisation_percent`, `variable_treatment_cost`, `total_plant_cost` | |
| Demand zones | `zone_id`, `delivered_ml_per_day`, `surplus_ml_per_day`, `demand_satisfied`, `unmet_demand_ml_per_day` | |
| Flows | source-to-plant and plant-to-zone `flow_ml_per_day`, `utilisation_percent`, `activated` | Utilisation is relative to link capacity. |
| Quality | `parameter_id`, `reported_value`, `reported_unit`, `within_limits`; `model_min` / `model_max` only where `transform` is `identity` | This is the blend entering the plant, before treatment. |
| Binding facts | `binding_constraints_summary[]` | Deterministic sentences such as "Source '225103' is at its maximum withdrawal bound." Quote them, but do not add a cause. |

## 5. What will not be presented, and why

**Evidence only (can shape wording, never shown as a raw value):** `sources[].decision_evidence.unit_cost_rank`, `binding_lower`, `binding_upper`, `quality...binding_lower/upper`, `solver.is_feasible`, `solver.is_optimal`, `model_included`, `demand_must_be_met`, `quality.applies_to`.

**Technical view only:** all `validation.*` statuses and checks, `warnings[]`, `exclusion_reason_code`, `cost_reconciles`, `scenario.status`.

**Not presented anywhere:** `schema_version`, `run_id`, `solver.version`, `scenario.data_source.*` (currently placeholders), `validation.input_policy.*`, `reconstructed_total_cost`, and the model-space quality fields `model_value`, `model_unit`, `model_parameter_id`, `transform`.

**Statements the explanation must never make:**

- That a source was chosen *because* it is the cheapest. `unit_cost_rank` is context, not cause (contract section 8.5.3). In the feasible fixture the second-cheapest source supplies the most water (700 of 1200 ML/day), so cost rank alone would give a wrong story.
- Any treatment, chemical-dosing or removal cost. The formulation (`docs/formulation.tex`) includes them, but the objective in `model.py` on `master` has four terms only.
- That inflow quality is the quality of treated or delivered water.
- A currency for any cost.
- A pH limit taken from `model_min` / `model_max`. For pH those are hydrogen-ion limits in nmol/L (3.16 to 316.23), not pH 6.5 to 8.5.
- Any figure from a `NO_SOLUTION` or `INVALID_OUTPUT` result other than the `when: always` fields.

## 6. Gaps between the contract and the current output

Each gap was observed in the real outputs in `fixtures/`, not inferred from the documents.

| ID | Contract says | `master` actually produces | Effect on AI | Who decides |
|---|---|---|---|---|
| G1 | `schema_version` "1.0" | "0.1" (`postprocessing.py` line 111) | Version checks will reject real output | MILP |
| G2 | `solver.status` uppercase: `OPTIMAL`, `INFEASIBLE`, ... | raw Pyomo lowercase: `optimal`, `infeasible` | Compare case-insensitively until fixed | MILP |
| G3 | `selection_status` `UNUSED` | `NOT_SELECTED` | Accept both until fixed | MILP |
| G4 | `exclusion_reason_code` null for included sources | `"N/A"` | Ignore unless `EXCLUDED` | MILP |
| G5 | Infeasible: decision values null, `objective_value` null | decisions `0.0`, `total_cost` `0.0`, `unmet_demand` = full demand, `output_consistency` FAILED, 16 "unset by the solver" warnings | Handled by the gate (section 3); MILP may want to emit nulls as section 22 of `output_json.md` says | MILP |
| G6 | `demand_zones[].demand_ml_per_day` kept as context (doc 8.7) | Field absent from the template, the dataclass and the output | Per-zone demand cannot be stated; only `summary.total_demand_ml_per_day` | MILP |
| G7 | `scenario.data_source` describes the input source | `type`/`view` are "placeholder", `allow_estimated_values` null | Cannot say whether data was estimated | MILP / Data Engineering |
| G8 | `parameter_id` "pH" | Key comes from the scenario: "ph" in `base_scenarios_v1.json` | Match case-insensitively, never hard-code | MILP |
| G9 | `blend_ratio` = share of the plant's inflow | withdrawal / total delivered across the network | Same while there is one plant; differs with several | MILP |
| G10 | Cost breakdown matches the objective | Objective has 4 terms; formulation adds removal and dosing costs | Explanations must not mention treatment-chemical costs | Optimisation |
| G11 | (silent) | No currency or cost unit anywhere | No "$" or "AUD" in text | Product Owner |
| G12 | Raw pH limits removed from output (v1.0) | Only hydrogen-ion `model_min`/`model_max` | pH limits cannot be quoted from the output; suggest adding `reported_min`/`reported_max` | MILP |
| G13 | n/a | `MILP/tests/mock_pipeline.py` fails on `master`: it builds source quality with key "pH" while the scenario uses "ph" | `make_fixtures.py` uses "ph" | MILP |

## 7. Effect on the T2 AI code

The T2 AI pipeline (`AI/main.py` in `Yxxsef/Aqua-Blend-Analysis-Ai`) still treats the older pre-v1 shape (`status`, `objective`, `transfer_paths`, `water_quality`, `data_flags`) as canonical. I ran it on the real feasible output:

- `run_pipeline(output)` raises `KeyError: 'status'`, because v1 has no top-level `status`.
- `extract_canonical_output()` always falls back to the flattened columns, because `raw_output_json` never contains the old required fields.
- `main.py` only calls the LLM when `status == "OPTIMAL"`. v1 output never has that exact string at top level, so the LLM path would not run on real data.

Task 56 last trimester already listed ten open contract questions in `AI/results/MILP_Output_Validation_Notes.md`. The real outputs now answer four of them: status values (Q3, see G2/G3), costs (Q5: `summary.costs.*`, `total_cost` equals the objective, no currency), `run_id` (Q6: a string, the shared run ID) and the solved and infeasible shapes (Q7, see `fixtures/`).

Whatever replaces the T2 explanation code should read v1 directly and apply this agreement, rather than adapting v1 back into the old shape.

## 8. Open questions to agree on

1. MILP lead: will G1 to G5 be fixed in postprocessing, or should the AI side keep the tolerant handling described above?
2. MILP lead: can `demand_ml_per_day` (G6) and pH `reported_min`/`reported_max` (G12) be added to the output?
3. Optimisation stream: when removal and dosing costs reach `model.py`, which new cost fields will appear in `summary.costs`? The drift test will flag them.
4. Product Owner: what is the cost unit and currency?
5. AI lead / App: is a technical view planned in the frontend for validation checks and warnings, or should those stay in logs only?
6. AI lead: where does T3 AI code live? The company repo's `AI/` folder is empty, and `CONTRIBUTING.md` there describes the MILP team's fork.

## 9. Files and how to rerun

| File | What it is |
|---|---|
| `MILP_Output_Agreement.md` | This document |
| `presentation_rules.json` | Every output field with its category (`present`, `evidence`, `technical`, `internal`) and mode (`always`, `valid`) |
| `presentation_gate.py` | `gate_mode(output)` and `presentable_values(output)`. Standard library only |
| `test_presentation_rules.py` | 9 tests. Two of them are drift checks that fail if the MILP output gains or loses a field the rules do not cover |
| `fixtures/feasible.json`, `fixtures/infeasible.json` | Real outputs from `master` at `1bd6ff6` |
| `fixtures/output_contract_v1.json` | Copy of the contract template, so the drift check also covers it |
| `make_fixtures.py` | Regenerates the two fixtures from `MILP/` |

```bash
# regenerate fixtures (from the MILP folder of Aqua-Blend)
PYTHONPATH=. python3 path/to/make_fixtures.py path/to/fixtures

# run the checks
python3 -m pytest test_presentation_rules.py

# see what may be presented for one output
python3 presentation_gate.py fixtures/feasible.json
```
