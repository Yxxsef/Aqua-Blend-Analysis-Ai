# Task 62 — First Live LLM Run

**AquaBlend | Analysis & AI | Sprint 3 | Task 62**
**Owner:** Abdulla
**Model:** `qwen3:4b-instruct-2507-q4_K_M` (Ollama build of the provisional Task 24 model,
`Qwen/Qwen3-4B-Instruct-2507`)
**Endpoint:** local Ollama server, `http://localhost:11434/v1`
**Prompt version:** `aquablend-report-rewrite-v1.0`

## 1. What this covers

This covers four genuine calls through `model_runner.py` against a real, running model - not a
hand-built stand-in text, not a mock `request_fn`. Everything in `llm_evaluation.csv` and
`llm_evaluation_full_rubric.csv` before Task 62 was explicitly documented as covering the
validator's critical-check layer only, using fixtures built by hand to exercise each rule. This is
the first time actual model output has gone through the pipeline.

- **Runs 1-3**: the same OPTIMAL scenario (Sample 1), called three separate times as the validator
  itself was fixed - see sections 3, 5, and 6.
- **Run 4**: the two remaining genuine Task 23 sample types - INFEASIBLE and TIME_LIMIT status-only
  reports - tested for the first time, to see whether a model given a near-empty input pads it out
  with invented content. See section 7.

Every real call also independently exercised the fallback path (a deliberately wrong port) - see
section 8.

## 2. Setup

- Ollama installed locally, model pulled: `ollama pull qwen3:4b-instruct-2507-q4_K_M` (~2.5GB,
  quantised, matching the reasoning already recorded in `Model_Shortlist.md`).
- `model_config.json` created from `model_config.example.json`, with `model_id` changed to the
  Ollama tag. Not committed - added to `.gitignore`, since it's a local/machine-specific file, not a
  secret in the traditional sense (the `api_key` value is just the placeholder string `"ollama"`).
- `timeout_seconds` raised from the example's default `30.0` to `120.0` after the first attempt hit
  the original timeout - see section 9.

## 3. Run 1 (Sample 1, OPTIMAL) — the run that found the bugs

| Field | Value |
|---|---|
| `report_mode` | `LLM_UNVALIDATED` |
| `model_id` | `qwen3:4b-instruct-2507-q4_K_M` |
| `prompt_version` | `aquablend-report-rewrite-v1.0` |
| `runtime_ms` | 43,694 |
| `fallback_used` | `False` |
| `failure_type` | `None` |

The model produced a complete, well-structured rewrite of the reference scenario's deterministic
report, in Markdown with clearer bullet-point formatting than the original. On a first read it looks
like a genuinely good rewrite - which made validating it properly matter more, not less, since a
rewrite that merely *looks* right is exactly the failure mode Task 22's rules exist to catch.

Running it through `llm_validator.py` for real returned `critical_result: FAIL`, with 13 failures.
**Investigating each one individually found that 11 of the 13 were false positives in the validator
itself, not problems with the model's output** - genuinely useful, since this is exactly the kind of
finding a hand-built fixture pack can't produce; every fixture up to this point was written to
exercise a known failure pattern, and none of them happened to hit these particular formatting
choices.

### 3.1 Confirmed validator bugs, fixed as a direct result of this run

| Original failure | Root cause | Fix |
|---|---|---|
| `NUMBER_MISSING_OR_CHANGED` / `NUMBER_INVENTED` on `13.0`, `20.0`, `45.0` (×2 each) | Source writes "45 percent" (word form); model wrote "45%" (symbol form) - same fact, `%` was tracked as part of a number's identity but the word "percent" was never recognised as equivalent | `_normalise_percent_words()` converts `"N percent"`/`"N pct"` to `"N%"` on both texts before number extraction |
| `IDENTIFIER_MISSING` on `zone_1`, `facility_1`, `Yarra Kew` | Source uses `zone_1` and `Zone 1` in different sections; `facility_1` alongside `Treatment Facility 1`; the shorthand `Yarra Kew` once inside the sensitivity notes vs. the full `Yarra River, Kew` everywhere else. Model consistently used the fuller/Title-Case forms throughout - correct, not a fact change | Word-set subset matching: a source identifier counts as present if some rewrite identifier's word set is a superset of it (`{zone,1} ⊆ {zone,1}`; `{facility,1} ⊆ {treatment,facility,1}`; `{yarra,kew} ⊆ {yarra,river,kew}`) |
| `UNSAFE_SAFETY_CLAIM` on "final drinking", `INVENTED_CONTENT` on "regulatory compliance" | Model wrote "The results are **not** final drinking-water quality outcomes" and "**No** claims are made about water safety, regulatory compliance..." - both accurate, faithful negations. The always-banned and differential-content checks matched on bare substring presence, unable to distinguish an assertion from a denial | `_has_unnegated_occurrence()`: a phrase only counts as genuinely present if at least one occurrence isn't governed by a negation word (`not`, `no`, `never`, etc.) within a bounded 12-word window, without crossing a sentence/clause boundary |
| `IDENTIFIER_MISSING` on `cost_per_ml`, `max_available_ml_per_day` | Model paraphrased both into plain English ("the actual cost of groundwater from Bore 1", "the maximum available flow") - clearer prose, raw field name not preserved | `EXEMPT_FIELD_NAME_TOKENS` - a team-lead decision (section 4), not a bug fix; these are attribute labels, not entity references, and their numeric values are still independently checked |

All four are documented in full, including the safety checks and the decision's reasoning, in
`Validation_Rules.md` sections 3 and 6. Regression tests for all four live in
`test_llm_validator.py`, and the actual captured model output (this run's real text) is now a
permanent fixture (`REAL_LIVE_MODEL_OUTPUT_SAMPLE_1`) rather than a description of what happened.

**After all four, re-running the real output returns `critical_result: PASS`** - see section 3.2 for
the one remaining warning (not a failure), and section 4 for the full reasoning behind the fourth
fix.

### 3.2 The one remaining item - a warning, not a failure

| Item | What the model actually wrote | Why it's correctly a warning, not a failure |
|---|---|---|
| `NEW_IDENTIFIER` warning on "Bore 1" | Used as informal shorthand for Groundwater Bore 1 in the sensitivity notes | Correctly a warning, not a failure - this is exactly the "may be legitimate rewording" case the warning tier exists for. |

**The negation-detection fix is deliberately bounded, not a claim that negation is fully solved** -
see `Validation_Rules.md` section 8 for the honest limits, and
`test_distant_negation_in_a_long_sentence_does_not_carry_over` for the adversarial case it was
specifically tested against (an unrelated negation far earlier in a long sentence must never hide a
genuinely unsafe claim later in that same sentence).

## 4. Decision: cost_per_ml and max_available_ml_per_day are exempt from the identifier check

Both real runs against the live model paraphrased these exact two fields the same way -
`cost_per_ml for groundwater_bore_1` became "the actual cost of groundwater from Bore 1", and
`max_available_ml_per_day` became "the maximum available flow." Consistent model behaviour, not a
one-off, and it was the only thing keeping either run from a genuine `critical_result: PASS`.

**Decided by Abdulla, as Analysis & AI stream lead, in this pass** rather than left open: these two
tokens are attribute *labels*, not entity references. `silvan_reservoir`, `zone_1`, and `facility_1`
identify a specific real-world source, zone, or plant, and must still survive under this or a
covering name. `cost_per_ml` and `max_available_ml_per_day` are just the *names of properties* -
the actual numeric values attached to them are already independently checked by the number-presence
check regardless of how the surrounding label is worded, so exempting the label's literal spelling
does not weaken fact coverage. It stops penalising a rewrite for doing exactly what `prompts.py`
already permits ("simplify wording... organise the same facts more clearly") to a token an operator
was never going to need to see verbatim in the first place.

**Scoped narrowly, not a blanket exemption:** only these two specific tokens, added to
`EXEMPT_FIELD_NAME_TOKENS` in `llm_validator.py`. Every other snake_case field name in the same
report - `storage_capacity`, `reference_flow`, `alkalinity`, `cost`, `max_available` in the Data
Flags section - remains required, and correctly survived verbatim in both real runs anyway (that
section is a literal bullet list, which naturally resists paraphrasing the way free-flowing prose
does not). Widening the exemption to the whole field-name category was considered and rejected, since
it would weaken a check that already works correctly for those other fields.
`test_exemption_is_narrow_other_field_names_still_required` in `test_llm_validator.py` is the
regression test confirming `storage_capacity` is still enforced.

**Result: `REAL_LIVE_MODEL_OUTPUT_SAMPLE_1` now returns `critical_result: PASS`** -
`test_real_output_now_genuinely_passes` is the regression test. This is the first genuine accepted
rewrite from the live model, satisfying the task checklist's "demonstrate at least one accepted valid
rewrite" for real, not by re-running until one happened to pass.

## 5. Run 2 (Sample 1, OPTIMAL) — confirming the fix generalises

A second, completely independent call, same scenario, same config, run partway through fixing the
validator (percent-form and identifier-matching fixes applied; negation-detection and the field-name
exemption not yet).

| Field | Value |
|---|---|
| `runtime_ms` | 48,278 |
| `fallback_used` | `False` |
| `critical_result` (against the validator state at the time) | `FAIL` - `IDENTIFIER_MISSING` ×2, `INVENTED_CONTENT`, `UNSAFE_SAFETY_CLAIM` |

The same four failures Run 1 showed at that point in the fix process - not new problems, confirmation
that the fixes made so far generalise to a freshly-generated output, not just the one text they were
written against. The raw output was not preserved on disk before the timestamped-output-folder fix
was added (see `Validation_Rules.md` section 2 for that fix), so this run could not be re-validated
against the final validator once the remaining fixes landed - recorded in `llm_evaluation.csv` as
`LIVE_RUN_2`, explicitly labelled as observed at the time rather than re-confirmed.

## 6. Run 3 (Sample 1, OPTIMAL) — the first genuine PASS on fresh output

A third independent call, after all four fixes (the three validator bugs plus the field-name
exemption decision in section 4).

| Field | Value |
|---|---|
| `runtime_ms` | 53,457 |
| `fallback_used` | `False` |
| `critical_result` | `PASS` |
| Remaining items | One `NEW_IDENTIFIER` warning on "Bore 1" - not a failure |

This is the more meaningful confirmation of the two PASS results: `REAL_LIVE_MODEL_OUTPUT_SAMPLE_1`
(Run 1, section 3) is baked into the test suite as a fixture, so it will always pass once the code
that makes it pass exists - that's expected, not surprising. Run 3 is a fresh generation the fixes
were never written against, and it passed on its own. Saved in
`AI/explanations/live_run_output_run3_pass/`, recorded as `LIVE_RUN_3` in `llm_evaluation.csv`.

## 7. Run 4 (Samples 2 and 3, INFEASIBLE and TIME_LIMIT) — the remaining sample types

The task checklist says "run existing deterministic explanation *samples*" - plural. Runs 1-3 all
used the same OPTIMAL scenario; Task 23's other two genuine samples (the INFEASIBLE and TIME_LIMIT
status-only reports from `sample_explanations_sprint2.txt`) had never been sent to the real model.

These are a genuinely different kind of test: a near-empty, 3-section report gives a model very
little to work with, which is exactly the situation where a model might "helpfully" pad the output
with invented detail rather than just faithfully restating what little is there.

| Sample | `runtime_ms` | `critical_result` |
|---|---|---|
| Sample 2 (INFEASIBLE) | 8,641 | `PASS` |
| Sample 3 (TIME_LIMIT) | 4,262 | `PASS` |

Neither padded the output. Both faithfully restated the status and its meaning ("The solver found no
valid solution", "The solver reached a time limit and did not complete the calculation") without
inventing a cause for the infeasibility or the time limit, and both correctly preserved the exact
status word. Saved in `AI/explanations/live_run_output_run4_non_optimal_samples/`, recorded as
`LIVE_RUN_4_INFEASIBLE` and `LIVE_RUN_4_TIME_LIMIT` in `llm_evaluation.csv`.

## 8. Fallback demonstration (model unavailable)

Every one of Runs 1-3 independently exercised the fallback path (`run_live_llm.py` always makes a
second call to a deliberately wrong port after the real one) - consistent results all three times:

| Field | Value |
|---|---|
| `report_mode` | `TEMPLATE_FALLBACK` |
| `fallback_used` | `True` |
| `failure_type` | `MODEL_UNAVAILABLE` |
| `failure_message` | `[Errno 61] Connection refused` |

Confirmed each time that the fallback text is character-for-character identical to the deterministic
report - the fallback path returns the trusted source unchanged, not a degraded or partial version.

## 9. A real bug found along the way, not yet fixed (belongs to Task 24, not this task)

The first attempt at Run 1 used the example config's default `timeout_seconds: 30.0` and hit that
limit before the model finished generating (`runtime_ms: 30008`, essentially exactly the timeout).
It was reported as `failure_type: MODEL_ERROR`, not `TIMEOUT`.

Root cause: `model_runner.py` catches `except TimeoutError`, but on Python 3.9 (the version used for
this run), `urllib`'s real network timeout raises `socket.timeout`, a **separate sibling class** to
the builtin `TimeoutError` - both are `OSError` subclasses, but not the same class before Python
3.10, when they were unified. So a genuine timeout on 3.9 falls through the specific handler and
lands in the generic `except Exception` catch-all, mis-labelled as `MODEL_ERROR`. Every existing
test for this path injects a `TimeoutError` directly via a mocked `request_fn`, so none of them
exercise the actual exception class a real network call raises on this Python version - only a
genuine run against a real endpoint could have found this. Worth raising with Yousef as a fix needed
in `model_runner.py`, not something this task's files should patch directly.

## 10. Recommendation

**Continue.** The model's raw output quality was good across all four runs - clear, complete,
factually faithful in every case that mattered once the validator's own bugs were accounted for, and
it did not pad the two near-empty status-only samples with invented content, which was the specific
risk Run 4 was designed to check for.

Four real validator bugs found across Runs 1-3 are now fixed and covered by regression tests using
the actual captured output, not a redescription of it: word-form percentages, reformatted/fuller
identifier names, negation-blind phrase matching, and the field-name exemption decided in section 4.

**Every checklist item for this task is now satisfied, including "run existing deterministic
explanation samples" (plural - all three genuine Task 23 sample types, not just the OPTIMAL one) and
"demonstrate at least one accepted valid rewrite"** - both Run 1 (re-validated) and Run 3 (fresh
output, never used to write the fixes) return `critical_result: PASS`, and Run 4 confirms the same
holds on the two sample types nothing had tested against a real model before. Not achieved by
re-running until one happened to pass - achieved by finding and fixing four real, specific problems,
three of them validator bugs and one a deliberate, narrowly-scoped, documented team-lead decision
about what this validator should and shouldn't require verbatim.
