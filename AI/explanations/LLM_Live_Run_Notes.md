# Task 62 — First Live LLM Run

**AquaBlend | Analysis & AI | Sprint 3 | Task 62**
**Owner:** Abdulla
**Model:** `qwen3:4b-instruct-2507-q4_K_M` (Ollama build of the provisional Task 24 model,
`Qwen/Qwen3-4B-Instruct-2507`)
**Endpoint:** local Ollama server, `http://localhost:11434/v1`
**Prompt version:** `aquablend-report-rewrite-v1.0`

## 1. What this covers

This covers five genuine calls through `model_runner.py` against a real, running model - not a
hand-built stand-in text, not a mock `request_fn`. Everything in `llm_evaluation.csv` and
`llm_evaluation_full_rubric.csv` before Task 62 was explicitly documented as covering the
validator's critical-check layer only, using fixtures built by hand to exercise each rule. This is
the first time actual model output has gone through the pipeline.

- **Runs 1-3**: the same OPTIMAL scenario (Sample 1), called three separate times as the validator
  itself was fixed - see sections 3, 5, and 6.
- **Run 4**: the two remaining genuine Task 23 sample types - INFEASIBLE and TIME_LIMIT status-only
  reports - tested for the first time, to see whether a model given a near-empty input pads it out
  with invented content. See section 7.
- **Run 5**: the same OPTIMAL scenario again, with `max_tokens` raised after Runs 1-3 turned out to
  be truncated - also failed, for a different and more concerning reason (a repetition loop, not
  just running out of room). See section 8.

Every real call also independently exercised the fallback path (a deliberately wrong port) - see
section 9.

### 1a. Corrections made - read this before the rest of the doc

Three real problems in `llm_validator.py` were found through review, not by more live-model
testing, and they change the headline claims made earlier in this document materially enough that
they need stating plainly up front rather than buried in each section:

1. **The accepted-rewrite claim for Runs 1 and 3 was wrong at the time.** The captured output is
   genuinely truncated - it cuts off mid-sentence at "All data and estimates" with nothing after,
   almost certainly from hitting the model's `max_tokens` limit. The validator had no check for
   output completeness at all until this review. `_check_output_completeness` now catches this
   (`INCOMPLETE_OUTPUT`), and the real captured output correctly fails. **Not yet resolved** - Run 5
   (section 8) was a second attempt at this, also originally reported as a PASS, and that report was
   also wrong, for a related but distinct reason (an outdated local validator, not a new bug) and a
   genuinely new failure mode (a repetition loop, not just truncation). There is still no confirmed
   genuine complete PASS of the flagship OPTIMAL scenario. See section 3, section 6, and section 8.
2. **Runs 2 and 3's raw text is identical**, not independent fresh generations as originally
   claimed. `model_config.json` sets `temperature: 0.0` (greedy decoding), and every call was fed
   the exact same `deterministic_report.txt` - under those conditions it's expected, not a data
   error, that the model produced the same output each time. The "Run 3 confirms the fix
   generalises to fresh output" claim was incorrect and is corrected in section 6.
3. **Two more real validator gaps were found and fixed**: a swapped pair of source figures (e.g.
   Yarra River, Kew's 58.0% swapped with Silvan Reservoir's 42.0%) passed silently, since the plain
   presence-based number check has no concept of which value belongs to which source -
   `_check_number_association` now catches this. Separately, a negation could incorrectly suppress
   an unrelated, genuinely unsafe claim later in the same sentence across a contrastive conjunction
   (e.g. "not safe to drink, **but** it is compliant") - fixed by treating "but"/"however"/"although"
   etc. as hard negation-scope boundaries. Both are documented in `Validation_Rules.md` sections 4
   and 6, with regression tests using the exact examples that surfaced them.

## 2. Setup

- Ollama installed locally, model pulled: `ollama pull qwen3:4b-instruct-2507-q4_K_M` (~2.5GB,
  quantised, matching the reasoning already recorded in `Model_Shortlist.md`).
- `model_config.json` created from `model_config.example.json`, with `model_id` changed to the
  Ollama tag. Not committed - added to `.gitignore`, since it's a local/machine-specific file, not a
  secret in the traditional sense (the `api_key` value is just the placeholder string `"ollama"`).
- `timeout_seconds` raised from the example's default `30.0` to `120.0` after the first attempt hit
  the original timeout - see section 10.

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

**Result at the time: the field-name exemption alone got `REAL_LIVE_MODEL_OUTPUT_SAMPLE_1` to
`critical_result: PASS`.** This was reported as the first genuine accepted rewrite. **That was
incorrect** - see section 1a and section 6. The output is genuinely truncated, and the validator had
no check for that at all at the time. With `_check_output_completeness` now in place
(`test_real_output_correctly_fails_on_truncation`), this same output correctly fails with
`INCOMPLETE_OUTPUT`. The field-name exemption itself is still a correct, narrowly-scoped fix - it
just wasn't sufficient on its own to call this specific output accepted.

## 5. Run 2 (Sample 1, OPTIMAL) — same text as Run 1, different validator state

A second call, same scenario, same config. **Originally described as an independent fresh
generation - it is not.** `model_config.json` sets `temperature: 0.0` (greedy decoding), and every
call is fed the exact same `deterministic_report.txt`; under those conditions the model producing
the same output each time is expected, not a data-integrity problem. Confirmed directly: Run 2's
raw text is byte-identical to Run 1's.

This run was made partway through fixing the validator (percent-form and identifier-matching fixes
applied; negation-detection, the field-name exemption, and the completeness check not yet).

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

## 6. Run 3 (Sample 1, OPTIMAL) — same text as Runs 1 and 2, corrected

A third call, same scenario, same config, made after the exemption fix landed.

| Field | Value |
|---|---|
| `runtime_ms` | 53,457 |
| `fallback_used` | `False` |
| `critical_result` at the time | `PASS` |
| `critical_result` now, with the completeness check | `FAIL` - `INCOMPLETE_OUTPUT` |

**Originally described as "a fresh generation the fixes were never written against" - not accurate.**
Confirmed directly: Run 3's raw text is byte-identical to Run 1's (see section 1a for why - greedy
decoding on an identical prompt). The only genuine difference between Run 1's and Run 3's recorded
results was which validator version checked the same text, not the text itself. With the
completeness check now in place, the same truncation Run 1 has applies here too, and this run
correctly fails for the same reason. Saved in `AI/explanations/live_run_output_run3_pass/` -
the folder name is now inaccurate and kept only because renaming it would break the git history
being described here; the CSV description has been corrected instead.

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

**Re-checked against the completeness fix (section 1a): both genuinely still pass.** Unlike Runs
1-3, these used a different input prompt each, so they're not affected by the same
identical-output situation, and both end with proper terminal punctuation ("...regulators, or
health authorities."). At the time this was the only pair of results that held up as complete,
genuinely-passing live-model output - see section 8 for the fix that closed the remaining gap.

## 8. Run 5 (Sample 1, OPTIMAL) — still no genuine complete PASS, and a new failure mode found

Runs 1-3 all hit the same wall: `model_config.json`'s original `max_tokens: 1200` wasn't enough for
the model to finish rewriting the full 12-section OPTIMAL report before being cut off, and with
`temperature: 0.0` on an identical input, every attempt hit the identical cutoff point. `max_tokens`
was raised and the same scenario was called again.

| Field | Value |
|---|---|
| `runtime_ms` | 78,487 |
| `fallback_used` | `False` |
| `critical_result` reported at the time | `PASS` |
| `critical_result` on re-validation against the final validator | `FAIL` - `INCOMPLETE_OUTPUT` |

**This was originally reported as "the first genuine complete accepted rewrite of the flagship
scenario." That was wrong, and worse than a simple repeat of the Run 1/3 mistake.** The reported
`PASS` was checked against an outdated local copy of `llm_validator.py` that did not yet have the
completeness check - the fix existed in this repository, but had not actually been placed on the
machine that ran this call yet. Re-validating the actual saved output against the final validator
returns `FAIL`, confirmed directly.

**And this run is a genuinely different, more concerning failure than Runs 1-3.** It isn't simply
truncated - the Prototype Disclaimer section entered a real repetition loop, generating roughly 85
lines of near-duplicate filler sentences ("It does not...", "All values are...", "No estimation...")
restating the same handful of ideas over and over, none of it present in the deterministic report at
all, before still cutting off mid-sentence at the very end ("This report is a"). No fact was
invented, no number was wrong, no unsafe claim was made - which is exactly why none of the existing
checks (`_check_invented_content`, the number checks, the safety checks) caught this on their own.
It was only caught here because the run also happened to run out of tokens before the loop ended.

**This is a genuine, currently unaddressed gap, not just a fixed bug:** there is no check in
`llm_validator.py` for excessive repetition or redundant, padded generation. A response that looped
like this but happened to end on a clean sentence before hitting the token limit would pass every
current check completely. Recommend the team consider this for a future pass - a repetition-ratio or
near-duplicate-sentence check, distinct from the completeness check, which only catches truncation.

**There is still no confirmed genuine complete PASS of the flagship OPTIMAL scenario on record.**
Saved in `AI/explanations/live_run_output_run5_optimal_pass/`, corrected in `llm_evaluation.csv`.

## 9. Fallback demonstration (model unavailable)

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

## 10. A real bug found along the way - fixed

The first attempt at Run 1 used the example config's default `timeout_seconds: 30.0` and hit that
limit before the model finished generating (`runtime_ms: 30008`, essentially exactly the timeout).
It was reported as `failure_type: MODEL_ERROR`, not `TIMEOUT`.

Root cause: `model_runner.py` caught `except TimeoutError`, but on Python 3.9 (the version used for
this run), `urllib`'s real network timeout raises `socket.timeout`, a **separate sibling class** to
the builtin `TimeoutError` - both are `OSError` subclasses, but not the same class before Python
3.10, when they were unified. So a genuine timeout on 3.9 fell through the specific handler and
landed in the generic `except Exception` catch-all, mis-labelled as `MODEL_ERROR`. Every existing
test for this path injected a `TimeoutError` directly via a mocked `request_fn`, so none of them
exercised the actual exception class a real network call raises on this Python version - only a
genuine run against a real endpoint could have found this.

**Fixed**: `except TimeoutError` is now `except (TimeoutError, socket.timeout)`, correct and safe on
every Python version - on 3.10+ the two are already the same class, so this only ever catches the
same thing twice; on 3.9 it correctly catches both. A new regression test
(`test_socket_timeout_also_returns_timeout_not_model_error`) injects `socket.timeout` directly,
exercising the exact class the existing test never touched. Confirmed on the real Python 3.9.6
environment this bug was originally found on - all 12 tests in `test_model_runner.py` pass.

## 11. Recommendation

**Continue, but with an honest correction, not a clean close.** This section originally claimed
every checklist item was satisfied, including a genuine accepted rewrite. That claim was found to be
wrong, along with two further validator gaps. All three are fixed as of this revision - see section
1a for the full list - but the correction changes what can honestly be claimed here.

**Seven real validator bugs have now been found and fixed**, plus one genuine gap found and
documented but not yet fixed, across this task's live runs and the corrections that followed - the
fixed ones covered by regression tests using actual captured output or the exact examples that
surfaced them, not redescriptions: word-form percentages, reformatted/fuller identifier names,
negation-blind phrase matching, a negation incorrectly crossing a contrastive conjunction into an
unrelated clause, swapped source figures passing silently, and missing output-completeness detection
- plus the field-name exemption, a deliberate decision rather than a bug. **The one gap not yet
fixed**: no check exists for excessive repetition or padded generation (section 8) - a response that
loops without inventing any wrong fact would currently pass every check, as Run 5 nearly did.

**"Run existing deterministic explanation samples" (plural) is genuinely satisfied** - all three
Task 23 sample types have real live-model calls on record (section 3, section 7).

**"Demonstrate at least one accepted valid rewrite" is still not satisfied for the flagship
scenario.** Runs 1, 3, and 5 all fail, for real reasons, not the same bug repeated: Runs 1 and 3
were genuinely truncated; Run 5 was also genuinely truncated, after a repetition loop, and was only
ever reported as passing due to a stale local validator, not a real result. Run 4's two samples pass
genuinely, but they're short status-only reports, not the full 12-section case this checklist item
is really asking about. **Getting a genuine, complete, accepted rewrite of the full OPTIMAL scenario
is still an open item** - raising `max_tokens` alone was not sufficient; the repetition-loop finding
in section 8 suggests the model may need prompt-level guidance against repeating itself as well,
not just more room to finish. Any future attempt should be verified the same way this correction
was made: by pulling the actual saved file and reading it, not trusting the console summary or
assuming the local validator is current.

**Human review is still pending** and this document should not describe any result as fully reviewed
until reviewer names, dates, scores, and notes are actually recorded in `llm_evaluation.csv` and
`llm_evaluation_full_rubric.csv`.
