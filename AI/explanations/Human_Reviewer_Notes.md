# Human Reviewer Notes — Task 63

**AquaBlend | Analysis & AI | Sprint 3 | Task 63**
**Reviewers:** Abdulla Almannaee (Reviewer 1), Yousef (Reviewer 2)
**Scope:** All eight genuine live-model output rows (across seven live model runs — Run 4 produced
two rows) in `llm_evaluation.csv` and `llm_evaluation_full_rubric.csv`

## 1. Purpose

Task 25 required at least two independent human reviewers to score genuine LLM output on
non-critical style dimensions (clarity, completeness, usefulness, uncertainty handling,
readability) before the pipeline could be called reviewed. Task 62 left this pending — both
reviewer columns in `llm_evaluation.csv` were marked `pending`, not scored. This document records
that both reviewers have now scored all eight live-model output rows independently, and reconciles what the two
scores do and don't agree on.

## 2. Scoring method

Reviewer 1 used the full C1-C9/S1-S6 rubric in `llm_evaluation_full_rubric.csv` — nine critical
content checks (PASS/FAIL/N/A) plus six style scores (1-5), summed to a `TotalScore` and a verdict
band (PASS / REVISE / FAIL). Reviewer 2 scored independently using the single `reviewer_2_style_score`
column in `llm_evaluation.csv` (1-5, one overall style number) plus an explicit PASS/FAIL verdict
where relevant.

These are two different granularities, not two attempts at the same measurement — Reviewer 1's
method is documented per-criterion, Reviewer 2's is a single holistic judgement. That difference in
method is the main driver of the gaps in section 3, not reviewer disagreement about the model's
actual output.

## 3. Per-run scores and reconciliation

| Run | Reviewer 1 | Reviewer 2 | Automated validator | Agreement |
|---|---|---|---|---|
| `LIVE_RUN_1` | 3.83 (TotalScore 23, rubric-band PASS) | 2.0 | FAIL (`INCOMPLETE_OUTPUT`) | Reviewer 2's low score and the validator agree; Reviewer 1's per-criterion average lands on the rubric's own PASS threshold for a text the validator correctly fails — see section 4. |
| `LIVE_RUN_2` | 3.83 (copied from Run 1 — confirmed identical text) | 2.0 | FAIL (as observed at the time) | Same as Run 1, same text. |
| `LIVE_RUN_3` | 3.83 (copied from Run 1 — confirmed identical text) | 2.0 | FAIL (`INCOMPLETE_OUTPUT`) | Same as Run 1, same text. |
| `LIVE_RUN_4_INFEASIBLE` | 4.5 (TotalScore 27, PASS) | 4.0 | PASS | Full agreement — no rubric gap on a genuinely complete, correct output. |
| `LIVE_RUN_4_TIME_LIMIT` | 4.5 (TotalScore 27, PASS) | 4.5 | PASS | Full agreement. |
| `LIVE_RUN_5` | 3.33 (TotalScore 20, rubric-band REVISE) | 1.5, explicit FAIL | FAIL (`INCOMPLETE_OUTPUT`) | Reviewer 2 and the validator agree; Reviewer 1's REVISE band is closer to FAIL than Runs 1-3 landed, since Run 5's repetition loop is a worse failure than simple truncation — see section 4. |
| `LIVE_RUN_6` | 3.67 (TotalScore 22, rubric-band REVISE) | 3.5 | FAIL (`INCOMPLETE_OUTPUT`) | Closest agreement of any FAIL case — both reviewers landed in the same range independently. |
| `LIVE_RUN_7` | 5.0 (TotalScore 30, PASS) | 4.0 | PASS | Full agreement — the one genuinely complete, correct rewrite. |

## 4. The Runs 1/3/5 rubric gap — explained, not dismissed

On every run where the automated validator correctly returns FAIL for `INCOMPLETE_OUTPUT`,
Reviewer 1's per-criterion rubric still lands close to or inside its own PASS/REVISE bands, while
Reviewer 2's single holistic score is consistently low enough to agree with the validator's verdict
(and on `LIVE_RUN_5`, an explicit stated FAIL — see `llm_evaluation_full_rubric.csv`'s
`LiveRun5_RepetitionLoop` entry).

This is not a disagreement about the model's output — both reviewers, reading the same text,
identified the same problem (the response is genuinely truncated or looping). The gap is a rubric
design property: C1-C9 checks nine independent content facts, and a truncated response can still
score PASS on every one of them individually (nothing stated is factually wrong — the response just
stops). The rubric has no C-criterion for "the response is incomplete" — that's caught only by S2
(Completeness), one score out of six, which cannot by itself pull a TotalScore below the PASS band
when every C-criterion passes. Reviewer 1's notes on `LiveRun1_GenuineModelOutput` and
`LiveRun5_RepetitionLoop` in `llm_evaluation_full_rubric.csv` flag this explicitly as "the same
rubric gap already flagged" rather than treating each occurrence as a fresh surprise.

**Recommendation:** the automated validator's critical-check result should always be treated as the
overriding verdict for whether an output is accepted, exactly as `PipelineOutcome` in
`llm_evaluation.csv` already does ("automated validator FAIL overrides any style/rubric score"). The
C1-C9/S1-S6 rubric is useful for *why* a passing output is good or a failing output has other
quality problems beyond the critical failure, but it should not be read as a second, independent
accept/reject gate — Reviewer 2's simpler, holistic scoring already reflects this in practice, and
the rubric could be strengthened with an explicit completeness gate rather than relying on S2 alone.
This is separate from and does not block Task 65 (sensitivity ranking) or any other Sprint 3/4 task.

## 5. What both reviewers agree on, unprompted

Independently, without coordinating:

- Both scored the two status-only samples (`LIVE_RUN_4_*`) as the strongest results (4.0-4.5 range).
- Both scored `LIVE_RUN_7` as the clear best of the OPTIMAL-scenario attempts.
- Both scored `LIVE_RUN_5` as the worst of the eight — the repetition loop was judged more severely
  by both reviewers than plain truncation (Runs 1-3), consistent with `LLM_Live_Run_Notes.md`
  section 8's framing of Run 5 as "worse than a simple repeat of the Run 1/3 mistake."

This convergence, on a rubric with genuinely different scoring granularity, is itself evidence that
the underlying judgement is sound even where the exact numbers differ.

## 6. Outstanding

- The rubric gap in section 4 is documented and explained but not structurally fixed. Recommend a
  dedicated completeness gate in a future rubric revision, tracked alongside the prompt-tag-leak
  validator gap in `LLM_Evaluation_Findings.md`.
- No third reviewer was used on any row. Two independent reviewers satisfies the Task 25 checklist
  requirement ("at least two human reviewers"); a third would only be warranted if a future
  disagreement couldn't be explained by rubric design the way section 4's gap could be.
