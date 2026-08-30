# Task 25 Test Pack

**AquaBlend | Analysis & AI | Sprint 2 | Task 25**
**Covers:** `test_llm_validator.py`, 38 tests, all currently passing

## 1. What this is

`test_llm_validator.py` is the automated test suite for `llm_validator.py`. There is no separate
fixture-file directory - every fixture lives inline in the test file itself, as a string constant or
built with one `.replace()` call on `CORRECT_REWRITE`, the same approach `test_model_runner.py`
(Task 24) uses for its own `TEMPLATE_REPORT` fixture. Each incorrect fixture is built from
`CORRECT_REWRITE` with exactly one change, so each test isolates exactly one failure category - if a
test for `NUMBER_INVENTED` fails, the fixture that produced it changed a number and nothing else.

**How to run it:**

```bash
pip install pytest --break-system-packages
python -m pytest test_llm_validator.py -v
```

All 38 currently pass.

## 2. The reference text

`REFERENCE_REPORT` is not invented. It is copied verbatim from
`AI/explanations/sample_explanations_sprint2.txt`, Sample 1 - Task 23's own genuine output for the
shared `OPTIMAL` reference scenario, produced by actually running `generate_explanation()`, not
typed by hand. Using Task 23's real output rather than a fresh example keeps this test pack directly
traceable to what the pipeline actually produces, and means any future change to `json_explainer.py`
that alters Sample 1's wording will surface here too.

`REFERENCE_REPORT_INFEASIBLE` is the same file's Sample 2, also verbatim, used only for the general
status-handling robustness tests (see section 4).

## 3. `CORRECT_REWRITE`, and why it took several tries

`CORRECT_REWRITE` is a hand-written, faithfully-reworded version of `REFERENCE_REPORT` - different
sentence structure, different section order, different phrasing, but every number, unit code,
Title-Case identifier, snake_case identifier, and status word from the source is still present
somewhere. It is meant to represent what a good LLM rewrite looks like.

It did not pass on the first attempt. Building it against the real validator - not assuming it would
pass by construction - surfaced four genuine bugs in the validator itself, not fixture mistakes:

1. **A false-positive identifier.** The reference report's own text, "Reduce Yarra Kew share to 45
   percent...", was captured as a phantom identifier ("Reduce Yarra Kew") because "Reduce" is
   capitalised only as a sentence-starter. No rewrite could ever reasonably reproduce that exact
   three-word run. Fixed with a small stopword list - see Validation_Rules.md section 3.
2. **A false-positive safety claim.** An early draft of the rewrite said "...not final treated
   water" - a *negated*, correct, safe statement - but `ALWAYS_BANNED_PHRASES` matches the phrase
   "treated water" regardless of negation. The fix was to the fixture, not the rule: reworded to
   match the source's own phrasing ("not final post-treatment drinking-water results"), the same
   phrasing `json_explainer.py` itself deliberately uses to avoid ever writing "treated water" at
   all, negated or not.
3. **An exact-repetition-count false positive.** The first draft compressed three separate
   transfer-result lines (each repeating "Treatment Facility 1") into one combined sentence - a
   legitimate readability improvement. An exact-count number check flagged this as a missing fact.
   The check was changed from counting repetitions to checking presence - see Validation_Rules.md
   section 3 for the full reasoning.
4. **An asymmetric-heading-stripping false positive**, found after `CORRECT_REWRITE` was already
   passing, while generating `llm_evaluation.csv`: validating the deterministic report against
   *itself* (an unchanged rewrite) produced a spurious `NEW_IDENTIFIER` warning. Headings were being
   stripped from the deterministic side only, and several of Report_Structure.md's own section
   headings ("Selected Sources", "Active Plants") are themselves Title-Case two-word phrases that
   match the identifier pattern - so an unstripped rewrite's headings looked like brand-new
   identifiers purely from the asymmetry, even with nothing actually changed. Fixed by stripping
   headings from both sides; `test_identical_text_passes_with_no_warnings` is the regression test.

None of this is hidden in the final test suite - `test_leading_word_stopword_does_not_false_positive`,
`test_legitimate_compression_does_not_fail`, and `test_identical_text_passes_with_no_warnings` all
exist specifically to keep these fixes from silently regressing later. Bug 2 (the negated safety
claim) doesn't have its own dedicated regression test the same way, since it was a fixture wording
problem rather than a validator bug - `test_treated_water_always_fails` instead confirms the rule
that caused it behaves correctly on purpose.

A fifth bug was found separately, in PR review rather than while building this fixture pack:
`_normalise_number` stripped the `%` sign before comparing values, so `58.0%` and `58.0` were the
same fact as far as the validator was concerned - a rewrite that dropped the percent sign while
keeping the same digits passed validation, even though that is a real, meaningful fact change. Fixed
by tracking each number as a `(value, is_percent)` pair instead of a bare value; see
Validation_Rules.md section 3. `test_dropped_percent_sign_fails` and `test_added_percent_sign_also_fails`
are the regression tests, covering both directions.

## 4. Fixture families and what each proves

| Family | Test class(es) | What it proves |
| --- | --- | --- |
| Correct | `TestCorrectFixture` | A faithful rewrite passes with zero warnings; identical text (the runner's own template fallback) always passes trivially |
| Incorrect - numbers | `TestNumberFailures` | Changed, invented, and missing numbers are each caught; legitimate compression is not |
| Incorrect - units | `TestUnitCodeFailures` | A dropped currency code (AUD) is caught |
| Incorrect - identifiers | `TestIdentifierFailures` | A dropped Title-Case name and a dropped snake_case ID are both caught; a genuinely new name is a warning, not a failure; the sentence-initial false positive from section 3 stays fixed |
| Incorrect - status | `TestStatusFailures` | A status flip (OPTIMAL → INFEASIBLE) is caught from both directions; a silently dropped status word is caught |
| Incorrect - invented content | `TestInventedContentFailures` | An invented reason and an invented recommendation both fail; a weak signal phrase is a warning only; a phrase already present in the source is never flagged |
| Incorrect - safety | `TestSafetyClaimFailures` | "safe to drink", "compliant", and "treated water" are all always-banned, regardless of source content |
| Incorrect - disclaimer / water-quality note | `TestDisclaimerAndWaterQualityNoteFailures` | Both markers are enforced when the source has the relevant content, and correctly skipped when it doesn't |
| Malformed | `TestMalformedFixtures` | Empty and whitespace-only output both fail cleanly with a single, clear `EMPTY_OUTPUT` failure rather than a wall of noise; non-string input raises `ValidatorInputError` |
| Missing-optional-field | `TestMissingOptionalFieldFixture` | A short deterministic report that legitimately omits Data Flags and Alternatives & Sensitivity (both optional per Report_Structure.md), paired with a faithful rewrite of it, passes - the validator never demands content the source never had |
| Warnings | `TestWarningsDoNotAffectCriticalResult` | A short-rewrite length anomaly and multiple simultaneous warnings never change `critical_result` |
| Aggregation | `TestMultipleFailuresAggregate` | Several independent failures in one rewrite are all reported together, not just the first one found |
| Result shape | `TestResultShape` | `to_dict()` round-trips correctly for both PASS and FAIL |
| Status robustness | `TestNonOptimalReportRobustness` | See section 5 below |

## 5. On "non-optimal fixtures"

The task card's checklist says: *"Add non-optimal fixtures only when official examples are provided."*
No official non-optimal *LLM rewrite* examples exist yet - Task 25's evaluation has not yet run
against a real INFEASIBLE, UNBOUNDED, TIME_LIMIT, or ERROR scenario through a live model. That
dedicated fixture category is deliberately not included here, per the card's own instruction.

`TestNonOptimalReportRobustness` is a different, narrower thing: it checks that the validator's
*generic logic* - number, identifier, and status-word checking - still works correctly against a
short, three-section status-only report, using Task 23's own genuine Sample 2 (`INFEASIBLE`) text as
the source. This is general code-path coverage (a short report is structurally different from a
12-section one and is worth testing on its own terms), not a claim that these are official
evaluation fixtures. When real non-optimal LLM output becomes available, it should be added as its
own fixture family here, following the same "verbatim from a real run, not hand-typed" standard the
rest of this pack follows.

## 6. What this pack does not cover

- **Style scoring (1-5).** Per the task card, "critical checks before style scores" - `llm_validator.py`
  only produces the critical PASS/FAIL and warnings. Style scoring is a human-reviewer step, covered
  in `LLM_Evaluation_Findings.md`, not this module or its tests.
- **A live model.** Every test here runs against hand-written or genuinely-captured text. No test in
  this file makes a network call or requires a running LLM endpoint, matching Task 24's own
  `test_model_runner.py` convention.
- **Semantic correctness of the deterministic report itself.** This validator trusts
  `deterministic_report` as ground truth. If `json_explainer.py` has a bug, `test_json_explainer.py`
  is where that gets caught, not here.
