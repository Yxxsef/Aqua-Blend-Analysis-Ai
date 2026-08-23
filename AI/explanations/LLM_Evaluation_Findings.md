# Task 25 Evaluation Findings

**AquaBlend | Analysis & AI | Sprint 2 | Task 25**
**Covers:** `llm_evaluation.csv` (23 fixtures)

## 1. What this evaluation actually covers, and what it doesn't

This is the first controlled evaluation of `llm_validator.py`'s critical checks, run against the
23 fixtures in `llm_evaluation.csv`. Every `critical_result`, `failed_rules`, and `warning_rules`
value in that CSV is real - produced by actually calling `validate_llm_output()` on each fixture
pair, not written by hand. `test_llm_validator.py` (38 tests, all passing) checks the same logic at
finer grain.

**What this evaluation is not:** a live-model run. No LLM endpoint was available to generate genuine
`Qwen/Qwen3-4B-Instruct-2507` output for this pass, so the "LLM output" side of every fixture in
`llm_evaluation.csv` is either Task 23's own genuine deterministic-report text (used as a stand-in
correct case, or as the base for a deliberately-introduced single fault) or a hand-written faithful
rewrite (`CORRECT_REWRITE` and its variants). This means:

- **`runtime_ms` is not available for any row.** No model call was timed. Once a live model is
  actually connected and run per Task 24's `model_runner.py`, this column should be filled from
  `RewriteResult.runtime_ms`, which the runner already records for exactly this purpose.
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

**Continue** the pipeline as built, with the following before this can be called a complete Task 25
evaluation rather than its first pass:

1. **Run a genuine model call** through `model_runner.py` against at least the `REFERENCE_REPORT`
   fixture, capture the real `RewriteResult`, and validate that actual output - not a hand-written
   stand-in - through `llm_validator.py`. This is the one thing this pass could not do without a
   running local model endpoint.
2. **Get two team members to style-score** a representative sample of real model output (once
   available) on the 1-5 scale, and fill in `reviewer_1_style_score` / `reviewer_2_style_score` for
   those rows. Yousef has already volunteered as one of the two reviewers during PR review.
3. **Record the real fallback rate** once enough genuine model calls have been made to compute one
   meaningfully.
4. **Add the deferred non-optimal LLM-rewrite fixture family** (see Test_Pack_README.md section 5)
   once real non-optimal output exists to build it from.

Nothing found in this pass suggests `template-only` mode is currently necessary - the critical-check
layer itself is working correctly against every failure pattern tested. The open question is
entirely about real model behaviour, which this pass could not observe.
