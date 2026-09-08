# Task 25 Evaluation Findings

**AquaBlend | Analysis & AI | Sprint 2-3 | Task 25 + Task 62**
**Covers:** `llm_evaluation.csv` (26 rows: 23 Task 25 fixtures + 3 genuine Task 62 live runs),
`llm_evaluation_full_rubric.csv` (24 rows: 23 Task 25 fixtures + 1 genuine Task 62 live run)

## 1. What this evaluation covers, and how it's changed since Task 25

The original Task 25 pass below (sections 2-5) covered `llm_validator.py`'s critical checks against
23 hand-built fixtures - every `critical_result`, `failed_rules`, and `warning_rules` value was real,
produced by actually calling `validate_llm_output()`, but the "LLM output" side of every fixture was
either genuine deterministic-report text or a hand-written stand-in, never a real model call. That
gap is closed as of Task 62 - see section 1a.

### 1a. Genuine live-model data (Task 62)

Three real calls were made through the actual `model_runner.rewrite_report()` code path against a
locally running `qwen3:4b-instruct-2507-q4_K_M` (Ollama build of the provisional Task 24 model), not
mocked, not hand-written. Full detail in `LLM_Live_Run_Notes.md`; summarised here:

| Row | What happened | `critical_result` |
|---|---|---|
| `LIVE_RUN_1` | First real call. Surfaced 13 failures, 11 of them real validator bugs (word-form percentages, reformatted identifier names, negation-blind phrase matching) - fixed, with regression tests using this exact captured text. Re-validated here against the final validator. | `PASS` |
| `LIVE_RUN_2` | Second real call, same config. Recorded as observed against an intermediate validator state (percent/identifier fixes applied, negation and field-name-exemption fixes not yet) - the raw text was not preserved on disk before the timestamped-output fix, so it could not be re-validated against the final validator. Given an identical failure pattern to Runs 1 and 3, both of which resolved to PASS, this would very likely also now pass - noted as an inference in the CSV, not asserted as a re-run result. | `FAIL` (as observed at the time) |
| `LIVE_RUN_3` | Third real call, run after all four fixes. First genuine PASS on a freshly-generated output not already used as a test fixture. | `PASS` |

`LIVE_RUN_1` also has a full C1-C9/S1-S6 rubric entry in `llm_evaluation_full_rubric.csv`
(`LiveRun1_GenuineModelOutput`) - genuinely checked against the actual JSON facts, not assumed. It's
marked as a draft needing a second independent human reviewer, the same standing note as every other
rubric row in that file.

**Still not done:** `LIVE_RUN_2` and `LIVE_RUN_3` don't have full rubric entries yet (would need their
complete text, not just the validator's summary), and no genuine second human reviewer has scored any
of the three real runs. `reviewer_1_style_score`/`reviewer_2_style_score` remain `pending` for all
three rows, honestly, not filled with invented numbers.

### 1b. The original Task 25 fixtures (unchanged)

Every other row in `llm_evaluation.csv` is either Task 23's own genuine deterministic-report text
(used as a stand-in correct case, or as the base for a deliberately-introduced single fault) or a
hand-written faithful rewrite (`CORRECT_REWRITE` and its variants). For these rows specifically:

- **`runtime_ms` is not available.** No model call was timed for these - only the three `LIVE_RUN_*`
  rows have a genuine value here, taken from `RewriteResult.runtime_ms`.
- **`reviewer_1_style_score` and `reviewer_2_style_score` are marked "pending" for every row, not
  scored.** The task card requires at least two human reviewers scoring selected examples on
  non-critical style (1-5); that has not happened in this pass. These columns are left as explicit
  placeholders rather than filled with invented numbers.

What *is* real and load-bearing here: the automated critical-check layer has been run against every
failure category `LLM_Report_Scope.md` section 6 describes, plus the malformed and missing-optional-
field cases the task card asks for, and it behaves correctly on all of them - see section 2.

## 2. Critical-check results

23/23 fixtures behave as designed:

- **4 correct fixtures (F01-F04) all PASS**, with zero critical failures and zero warnings. F02 (the
  trivial identical-text case) surfaced a real validator bug during development - see
  Test_Pack_README.md section 3 and Validation_Rules.md section 3 - now fixed and covered by a
  regression test. F03 (a short report legitimately missing optional sections) passed on its first
  run and confirms the validator does not demand content that was never in the source.
- **18 incorrect/malformed fixtures (F05-F13, F15-F23) all correctly FAIL**, each with the expected
  rule(s) firing and no others - a changed number fails only on number rules, a status flip fails
  only on status rules, and so on. `F21` (three fault categories introduced together: a status flip,
  a dropped identifier, and an unsafe claim) correctly reports all four resulting rule violations -
  the status flip alone fires both `STATUS_MISSING` and `STATUS_INVENTED` by design (see
  Validation_Rules.md section 3) - confirming the validator aggregates every issue in one pass rather
  than stopping at the first failure it finds. `F23` (a percent sign dropped while the digits stay
  the same) was added after a PR review finding - see section 5.
- **1 borderline fixture (F14) correctly PASSes with a warning**, not a failure - a weak causal
  phrase ("this shows...") is surfaced for human attention without blocking the result, matching the
  intended severity split between critical failures and warnings.

Fallback rate: not meaningful in this pass, since no fixture here represents `model_runner.py`
actually choosing `TEMPLATE_FALLBACK` over a live model response - that rate can only be measured
once real model calls are happening.

## 3. What this pass confirms about the pipeline so far

- The critical-check layer correctly separates "the fact changed" from "the fact was stated fewer
  times but is still present" (see `test_legitimate_compression_does_not_fail` /
  Validation_Rules.md section 3) - an earlier, stricter design would have produced false failures on
  entirely faithful, well-written rewrites.
- The always-banned safety phrases (`safe to drink`, `compliant`, `treated water`, `final drinking`)
  fire regardless of context, including a case where the phrase appeared only inside a *correct*
  negated sentence during fixture development - confirming the rule is strict enough to catch the
  real failure mode it targets (LLM_Report_Scope.md section 6, "an unsafe result described as safe"),
  at the cost of also requiring careful phrasing on the deterministic-report side to avoid the phrase
  even when negated (which `json_explainer.py` already does).
- The malformed-input path (empty/whitespace rewrite) produces one clear, specific failure rather
  than a wall of misleading secondary failures.

## 4. PR review finding: dropped percent sign (F23)

A PR reviewer (Yousef) found that changing `58.0%` to `58.0` passed validation - the percent sign
was being stripped before values were compared, so a proportion silently becoming a bare number went
undetected. This was a real gap, not a false alarm: `_normalise_number` now tracks each number as a
`(value, is_percent)` pair, and `58.0%`/`58.0` are correctly treated as different facts. F23 is the
new fixture covering this case; `test_dropped_percent_sign_fails` and `test_added_percent_sign_also_fails`
are the code-level regression tests. See Validation_Rules.md section 3 for the full reasoning,
including why the `$` prefix is not tracked the same way.

## 5. Recommendation

**Continue** the pipeline as built. Item 1 from the original recommendation is now done - see
section 1a. What's left before this can be called a complete evaluation:

1. **~~Run a genuine model call~~ Done (Task 62)** - three real calls made, `LLM_Live_Run_Notes.md`
   has the full writeup, and `LIVE_RUN_1`/`LIVE_RUN_3` show `critical_result: PASS` in
   `llm_evaluation.csv`.
2. **Get two team members to style-score** the three genuine `LIVE_RUN_*` rows (and ideally a couple
   more real runs beyond these three) on the 1-5 scale, and fill in `reviewer_1_style_score` /
   `reviewer_2_style_score`. Yousef has already volunteered as one of the two reviewers during PR
   review; this now has real model output to actually score, not a hand-built stand-in.
3. **Record the real fallback rate** once enough genuine model calls have been made to compute one
   meaningfully - three calls (two fallback-triggered on purpose, one genuine model call each run)
   isn't yet a large enough sample for a meaningful rate.
4. **Add a full C1-C9/S1-S6 rubric entry for `LIVE_RUN_2` and `LIVE_RUN_3`** to
   `llm_evaluation_full_rubric.csv`, matching what's already done for `LIVE_RUN_1` - needs their
   complete text on hand, not just the validator's summary.
5. **Add the deferred non-optimal LLM-rewrite fixture family** (see Test_Pack_README.md section 5)
   once real non-optimal output exists to build it from.

Nothing found across either pass suggests `template-only` mode is necessary - the critical-check
layer works correctly against every synthetic failure pattern tested, and the genuine live-model
data now backs that up: real output either passes cleanly or fails for real, specific, fixed
reasons, not for reasons that turned out to be validator noise once investigated.
