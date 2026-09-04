# AI Integration Test Pack — Task 72

A shared fixture pack so AI-stream components (KPI/gate, sensitivity ranking, LLM validator)
are tested against the same representative cases, instead of each task inventing its own
one-off examples.

## Running it

One command, from the repo root:

```
pytest AI/integration_tests/test_ai_pipeline.py -v
```

25 tests, all passing as of this PR. No live model call, no database connection, and no
network access required — every fixture is either real captured output or a self-contained
synthetic JSON file.

**Dependency note:** the `fixtures/diagnostics/` tests import `diagnostics_adapter.py` from
`AI/explanations/`. That module is currently on the still-open `task-71-infeasibility-diagnostics`
branch, not yet merged into `master`. If this PR merges before Task 71 does, those two tests
will fail on `ModuleNotFoundError` until Task 71 lands — this is a real, expected dependency,
not a bug in this pack. Confirm Task 71 is merged (or rebase onto it) before merging this PR.

## What "real" and "synthetic" mean here

Every fixture is labelled in the table below. **Real** means it is either genuine solver/model
output that already exists elsewhere in this repo (copied here unmodified, not paraphrased),
or output *produced by actually running* the real function against another real fixture in
this pack (e.g. `sensitivity/unsupported_real.json`, confirmed byte-for-byte reproducible by
feeding `results_json/optimal_provisional_real.json` through the real `rank_sensitivities()`).
**Synthetic** means hand-constructed for this task, because no real example of that case exists
anywhere in the codebase yet.

## Fixture inventory

### `fixtures/results_json/` (7 files) — for the KPI calculator and gate (Tasks 19, 21)

| File | Real or synthetic | Source |
|---|---|---|
| `optimal_provisional_real.json` | **Real** | `AI/evaluation/reference_output.json` (Task 19), unmodified. Every source is flagged `has_estimated_values: true`. |
| `optimal_measured_synthetic.json` | Synthetic | No real output with `has_estimated_values: false` exists anywhere in the repo — checked directly. Hand-built so the confidence-flag path (Task 57) has a "fully measured" case to test against once it's wired up. Replace with a genuine sample the moment one exists. |
| `infeasible_status_only_synthetic.json` | Synthetic | Minimal `{scenario_id, solved_at, status: "INFEASIBLE"}`, matching `model_output_specification.md`'s own rule that a non-OPTIMAL result should omit the solution blocks rather than fill them with zeros. |
| `failed_solver_error_synthetic.json` | Synthetic | `status: "ERROR"`, same minimal shape. |
| `failed_solver_unbounded_synthetic.json` | Synthetic | `status: "UNBOUNDED"`, same minimal shape. |
| `failed_solver_time_limit_no_incumbent_synthetic.json` | Synthetic | `status: "TIME_LIMIT"` with no `incumbent_feasible` field — exercises the "cannot confirm feasibility" path from Task 19's bug fix. |
| `invalid_input_malformed_synthetic.json` | Synthetic | Missing the required `status` field entirely — genuinely invalid input, not just a non-optimal one. |

### `fixtures/llm_reporting/` (4 files) — for the LLM validator (Task 25)

| File | Real or synthetic | Source |
|---|---|---|
| `accepted_rewrite_real.json` | **Real** | `REFERENCE_REPORT` / `CORRECT_REWRITE` from `test_llm_validator.py` (task-25-llm-validator branch), extracted programmatically (not retyped) to guarantee byte-accuracy. |
| `validator_failure_truncated_real.json` | **Real** | `REAL_LIVE_MODEL_OUTPUT_SAMPLE_1` — a genuine captured `Qwen/Qwen3-4B-Instruct-2507` response from Task 62, cut off mid-sentence at "All data and estimates" from hitting `max_tokens`. Originally miscategorised as a PASS; caught in PR #46 review (Yousef). See `LLM_Live_Run_Notes.md` on the Task 25 branch for the full account. |
| `infeasible_status_only_real.json` | **Real** | `REFERENCE_REPORT_INFEASIBLE` / `CORRECT_REWRITE_INFEASIBLE` from `test_llm_validator.py`, same extraction method. |
| `empty_output_synthetic.json` | Synthetic | Trivial empty-string case — not worth capturing a real model failure for something this simple to construct correctly. |

### `fixtures/sensitivity/` (1 file) — for the sensitivity ranking module (Task 28)

| File | Real or synthetic | Source |
|---|---|---|
| `unsupported_real.json` | **Real** | `AI/results/sample_sensitivity_ranking.json` (Task 28), unmodified. Confirmed reproducible: `test_unsupported_real_fixture_matches_live_function_output` feeds `results_json/optimal_provisional_real.json` through the real `rank_sensitivities()` and asserts the output equals this file exactly. |

### `fixtures/diagnostics/` (2 files) — for the infeasibility diagnostics adapter (Task 71)

Task 71 landed after this pack was first drafted (still an open PR, not yet merged into
`master` as of this writing) — these two fixtures were added once it did, closing what was
originally documented here as a gap.

**Important caveat, carried over directly from `Infeasibility_AI_Interface.md`:** the payload
*shape* (`likely_causes[].type` / `.severity` / `.details`) is explicitly **provisional, not
confirmed** — Task 71's own doc sources it from `integration_v1_3.md` section 20's "conceptual"
example, not a locked contract. The *module and its outcome logic* (`build_infeasibility_context`,
the three-outcome classification) are real and genuinely tested (38 passing tests on the Task 71
branch); the field names the fixtures use could still change once the diagnostics/feasibility
workstream confirms a real contract.

| File | Real or synthetic | Source |
|---|---|---|
| `infeasible_diagnostics_driven_provisional.json` | **Real** (module) / **provisional** (payload shape) | Built directly from `Infeasibility_AI_Interface.md` section 3's own documented example payload, run through the real `build_infeasibility_context()` / `render_diagnostics_section()` and confirmed to produce `INFEASIBLE_WITH_DIAGNOSTICS` with the exact rendered text captured in the fixture. |
| `infeasible_status_only_no_payload_real.json` | **Real** | `INFEASIBLE` with no diagnostics supplied — confirms the core safety guarantee: `render_diagnostics_section()` returns `None`, never a guessed explanation. |

## Known gaps (deliberately not filled with invented data)

- **No "sensitivity ranking — supported" fixture exists in this pack.** I initially built one
  (a hand-constructed `RANKED` case with a fabricated `impact_score` field), then checked it
  against the actual `sensitivity_ranking.py` source before including it. `STATUS_RANKED` is
  defined as a constant in that module but is **never returned by any code path in the current
  implementation** — the function's own docstring states it deliberately does not convert
  free-text impact descriptions into a numerical ranking, "because that would invent a ranking
  rule." Including a fixture that claims to show "supported" behaviour the real code cannot
  currently produce would misrepresent the module, so it was removed rather than shipped. A
  genuine `RANKED` fixture can only be added once `rank_sensitivities()` itself gains a code
  path that produces one — that's a change to Task 65's scope, not this test pack's.
- **No genuine LLM timeout fixture.** A timeout is a runtime/network event, not something
  representable as a static input/output pair the way the other LLM cases are. Worth checking
  with whoever owns Task 24/62's `model_runner.py` whether it has a way to simulate or record a
  timeout deterministically — flagging this rather than fabricating a fake one.

~~No infeasible + diagnostics-driven case~~ — **closed.** Task 71 landed (as an open PR) after
this pack was first drafted; see the `fixtures/diagnostics/` table above. The payload shape it
uses is still provisional, not the gap itself.

## Adding a fixture later

Keep the real/synthetic distinction explicit for anything added to this pack. If it's synthetic,
say so in this README and explain why no real example exists yet. Do not add a
`_fixture_provenance`-style field inside the JSON fixture itself — that breaks the fixture's
conformance to the real contract shape it's supposed to represent. Provenance belongs here, in
this file, not inside the data.
