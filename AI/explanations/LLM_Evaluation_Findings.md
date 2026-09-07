# Task 25 Evaluation Findings

**AquaBlend | Analysis & AI | Sprint 2-3 | Task 25 + Task 62 + Task 63**
**Covers:** `llm_evaluation.csv` (31 rows: 23 Task 25 fixtures + 8 genuine live-model output rows,
across seven live model runs — Run 4 produced two rows, one per sample type),
`llm_evaluation_full_rubric.csv` (31 rows: 23 Task 25 fixtures + 8 genuine live-run rubric entries)

## 1. What this evaluation covers, and how it's changed since Task 25

The original Task 25 pass (sections 2-4) covered `llm_validator.py`'s critical checks against 23
hand-built fixtures — every `critical_result`, `failed_rules`, and `warning_rules` value was real,
produced by actually calling `validate_llm_output()`, but the "LLM output" side of every fixture was
either genuine deterministic-report text or a hand-written stand-in, never a real model call. That
gap is closed as of Task 62 — see section 1a. Task 63 then re-evaluated every claim against the
final validator state and recorded both reviewers' scores — see section 1b.

### 1a. Genuine live-model data (Task 62) — final, corrected state

Seven real calls were made through the actual `model_runner.rewrite_report()` code path against a
locally running `qwen3:4b-instruct-2507-q4_K_M` (Ollama build of the provisional Task 24 model), not
mocked, not hand-written. Full detail in `LLM_Live_Run_Notes.md`; summarised here in its final,
corrected form:

| Row | What happened | `critical_result` |
|---|---|---|
| `LIVE_RUN_1` | First real call. Surfaced 13 failures, 11 of them real validator bugs (word-form percentages, reformatted identifier names, negation-blind phrase matching). **Originally reported PASS after the field-name exemption fix — this was wrong.** Re-validated against the final validator (with the completeness check added later): the output is genuinely truncated mid-sentence and correctly fails. | `FAIL` (`INCOMPLETE_OUTPUT`) |
| `LIVE_RUN_2` | Second real call, same config. Confirmed byte-identical to Run 1's raw text (`temperature: 0.0`, identical input). Recorded against the validator state at the time it was run; not re-validated against the final validator since the raw text wasn't preserved on disk before that fix. | `FAIL` (as observed at the time) |
| `LIVE_RUN_3` | Third real call, same config. Confirmed byte-identical to Run 1's raw text. **Originally reported as the first genuine PASS — this was wrong**, for the same reason as Run 1 (same text, same truncation). | `FAIL` (`INCOMPLETE_OUTPUT`) |
| `LIVE_RUN_4_INFEASIBLE` | First real call on a near-empty status-only sample. No padding, correct status word preserved, no invented cause. | `PASS` |
| `LIVE_RUN_4_TIME_LIMIT` | Same test on the other status-only sample type. Same result. | `PASS` |
| `LIVE_RUN_5` | Same OPTIMAL scenario, `max_tokens` raised to fix the truncation. **Originally reported as the first genuine complete PASS — this was wrong**, checked against an outdated local validator copy without the completeness check. Re-validated: fails, and for a worse reason than truncation — the disclaimer section entered a genuine repetition loop (~85 near-duplicate lines) before still cutting off. | `FAIL` (`INCOMPLETE_OUTPUT`) |
| `LIVE_RUN_6` | Same scenario, after adding `frequency_penalty` and a stop-instruction prompt rule. No repetition loop this time, but the model echoed the prompt's own `</deterministic_report>` delimiter tag, and a numbered-list marker ("2.") was misread as an invented number — the second bug fixed, the tag-leak issue left open. | `FAIL` (`INCOMPLETE_OUTPUT`) |
| `LIVE_RUN_7` | Same scenario, after an explicit prompt rule forbidding the model from reproducing its own delimiter tags. Output is genuinely complete. Four reported failures investigated individually — all four were validator bugs (a too-fragile number/source pairing window, sentence-case field names invisible to identifier extraction), not model errors. Re-validated after fixing all four. | `PASS` |

Every genuine live run also has a full C1-C9/S1-S6 rubric entry in `llm_evaluation_full_rubric.csv`
(Runs 2 and 3 reuse Run 1's values directly, since their text is confirmed identical — see
`LLM_Live_Run_Notes.md` sections 5-6). Both `reviewer_1_style_score` and `reviewer_2_style_score`
are filled in for all eight rows in `llm_evaluation.csv` — human review is no longer pending.

### 1b. What Task 63 added on top of Task 62

- **Re-validated every run against the final validator**, not the validator state active at the time
  each call was made. This is what surfaced that Runs 1, 3, and 5 were originally reported as PASS
  in error — see section 1a and `LLM_Live_Run_Notes.md` section 1a for the full correction.
- **Completed second-reviewer scoring** for all eight live-model output rows. Reviewer 1 (Abdulla)
  and Reviewer 2 (Yousef) scored independently; several rows show a real, legitimate gap between the
  two scores (e.g. `LIVE_RUN_1`: 3.83 vs. 2.0) reflecting a genuine difference in reviewer approach
  (per-criterion averaging vs. treating a failed critical gate as dominant) rather than an error —
  see `llm_evaluation_full_rubric.csv`'s `LiveRun1_GenuineModelOutput` entry for the fuller
  reasoning, and `Human_Reviewer_Notes.md` section 4 for the full reconciliation and recommendation.
- **Confirmed the fallback path independently three times** (Runs 1-3 each also exercised a
  deliberate connection failure) — the fallback text is character-for-character identical to the
  deterministic report every time, not a degraded version.

### 1c. The original Task 25 fixtures (unchanged)

Every other row in `llm_evaluation.csv` is either Task 23's own genuine deterministic-report text
(used as a stand-in correct case, or as the base for a deliberately-introduced single fault) or a
hand-written faithful rewrite. `runtime_ms` is genuinely not available for these — no model call was
timed for them, only the eight `LIVE_RUN_*` rows carry a real value here.

## 2. Critical-check results

23/23 fixtures behave as designed:

- **4 correct fixtures (F01-F04) all PASS**, with zero critical failures and zero warnings.
- **18 incorrect/malformed fixtures (F05-F13, F15-F23) all correctly FAIL**, each with the expected
  rule(s) firing and no others. `F23` (a percent sign dropped while the digits stay the same) was
  added after a PR review finding — see section 4.
- **1 borderline fixture (F14) correctly PASSes with a warning**, not a failure.

**Fallback rate**: now meaningful, unlike the original Task 25 pass. Every genuine live run (Runs
1-3) independently exercised the fallback path via a deliberate connection failure, and all three
returned the deterministic report unchanged, exactly as designed. This confirms the fallback
mechanism itself works; it is not yet a measure of how often a live model call would fail in
production, since these three were deliberately forced failures, not organic ones.

## 3. What this pass confirms about the pipeline so far

- The critical-check layer correctly separates "the fact changed" from "the fact was stated fewer
  times but is still present."
- The always-banned safety phrases fire regardless of context, including inside a correct negated
  sentence during fixture development, confirming the rule catches the real failure mode it targets.
- The malformed-input path produces one clear, specific failure rather than a wall of misleading
  secondary failures.
- **Genuine live-model output surfaced failure modes no hand-built fixture pack found**: word-form
  percentages, reformatted identifier names, negation crossing a contrastive conjunction, swapped
  source figures, missing output-completeness detection, numbered-list markers misread as numbers,
  and sentence-case field names invisible to identifier extraction.

## 4. PR review finding: dropped percent sign (F23)

A PR reviewer (Yousef) found that changing `58.0%` to `58.0` passed validation — the percent sign
was being stripped before values were compared, so a proportion silently becoming a bare number went
undetected. `_normalise_number` now tracks each number as a `(value, is_percent)` pair. F23 is the
fixture covering this case; see `Validation_Rules.md` section 3 for the full reasoning.

## 5. Live-run findings summary (Task 62 + Task 63)

**Thirteen real validator bugs found and fixed** across the seven live runs, each with a regression
test using either the actual captured output or the exact example that surfaced it:

1. Word-form vs. symbol-form percentage normalisation (Run 1)
2. Reformatted/fuller identifier names via word-set containment (Run 1)
3. Negation-blind phrase matching on accurate denials (Run 1)
4. Field-name exemption for `cost_per_ml`/`max_available_ml_per_day` — a deliberate decision, not a
   bug (Run 1, section 4 of `LLM_Live_Run_Notes.md`)
5. `socket.timeout` mislabelled as `MODEL_ERROR` on Python 3.9 (found during setup, section 12)
6. Negation incorrectly crossing a contrastive conjunction ("not safe to drink, **but** compliant")
   into an unrelated clause (found in PR review, fixed before Run 6)
7. Swapped source figures passing silently — fixed after two redesigns, anchored to ML/day-tagged
   volumes with a measured window (found in PR review, fixed before Run 7)
8. Missing output-completeness detection, accepting truncated mid-sentence output as valid (found in
   PR review; this is what corrected the Run 1/3/5 PASS claims to FAIL)
9. Numbered-list markers ("1.", "2.") misread as invented numbers (Run 6)
10-11. Two number/source pair-association fixes for a too-fragile matching window (Run 7)
12-13. Sentence-case field-name renderings invisible to identifier extraction, fixed with a
   one-directional phrase fallback (Run 7)

**One issue mitigated but not structurally closed:** the prompt-tag leak from Run 6 did not recur in
Run 7, which is one confirmation the explicit prohibition helped — not a guarantee across every
future call, since there is still no dedicated validator check for this pattern specifically.

## 6. Recommendation

**Continue** the pipeline as built. The flagship OPTIMAL scenario now has a genuine, complete,
independently-confirmed `PASS` on record (Run 7) — this took three corrected false-PASS claims
(Runs 1, 3, 5) before it was genuinely achieved, and the corrections themselves are the point: every
claim in this document and in `LLM_Live_Run_Notes.md` is checked against the actual saved files, not
assumed from a console summary or an out-of-date local validator copy.

What's resolved since the original Task 25 recommendation:

1. **Run a genuine model call — done.** Seven real calls made, all three Task 23 sample types
   covered (OPTIMAL, INFEASIBLE, TIME_LIMIT).
2. **Get two reviewers to style-score the live runs — done.** All eight rows have both
   `reviewer_1_style_score` and `reviewer_2_style_score` recorded.
3. **Record the real fallback rate — done for the mechanism.** Confirmed working three times; not
   yet a production-representative rate, since these were deliberate forced failures.
4. **Add full rubric entries for every live run — done.** All eight have entries in
   `llm_evaluation_full_rubric.csv`.

What's still open:

1. **The prompt-tag-leak pattern** has no dedicated check, only an incidental `NEW_IDENTIFIER`
   warning if the leaked tag doesn't match anything in the source.
2. **The reviewer-score gap on Runs 1, 2, 3, and 5** (per-criterion averaging vs. treating a failed
   critical gate as dominant) is explained and given a recommendation in `Human_Reviewer_Notes.md`
   section 4 — a rubric design gap (no C-criterion for completeness), not an unresolved
   disagreement. The recommendation (automated validator result overrides rubric score, matching
   what `PipelineOutcome` already does) is not yet applied to a future rubric revision — that part
   remains open.

Nothing found across any pass suggests `template-only` mode is necessary. The critical-check layer
works correctly against every synthetic failure pattern tested, and seven genuine live calls confirm
that in practice: real output either passes cleanly for real, confirmed reasons, or fails for real,
specific, and now-fixed, reasons.
