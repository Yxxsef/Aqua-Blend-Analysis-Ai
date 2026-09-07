# Prompt/Config Regression Evidence — Task 63

**AquaBlend | Analysis & AI | Sprint 3 | Task 63**
**Scope:** Every prompt version change and `model_runner.py` config change made during Task 62,
re-verified here against the same live-run cases rather than assumed safe.

## 1. Purpose

Task 63's checklist requires that prompts/config are only changed when repeated failures justify
it, and that the same cases are re-run after any change — not that a fix is assumed to work once
written. This document lists every prompt and config change made, what specific failure justified
it, and the evidence that re-running the same case afterward confirmed the fix without silently
breaking something else.

## 2. Prompt version history

| Version | Change | Justified by | Re-run evidence |
|---|---|---|---|
| `v1.0` | Original system prompt (rules 1-7 in `prompts.py`, no explicit stop or tag-prohibition rule) | Baseline — used for Runs 1-5 | N/A — this is the starting point the other versions are measured against |
| `v1.1` | Added rule 8: stop immediately after the final section, no trailing restatement | Runs 1, 3, and 5 all cut off mid-sentence before finishing the Prototype Disclaimer — a stop instruction was the direct response | Run 6 used v1.1. Result: no repetition loop (confirming the separate `frequency_penalty` fix, section 3), but the model still didn't finish cleanly — it leaked the `</deterministic_report>` tag instead. v1.1 alone was not sufficient; see v1.2. |
| `v1.2` | Strengthened rule 6: explicitly forbids writing `<deterministic_report>`/`</deterministic_report>` or any XML-like tag, anywhere in the response | Run 6 leaked the closing delimiter tag into its output | Run 7 used v1.2. Result: no tag leak, genuinely complete output, first confirmed `PASS`. Confirms the fix targeted the actual failure — the tag stopped appearing, not just "the run happened to pass this time." |

**Current prompt version on master:** `aquablend-report-rewrite-v1.2` (`PROMPT_VERSION` in
`prompts.py`), confirmed by direct inspection.

**Not yet re-tested going forward:** v1.2 has only been confirmed against one clean run (Run 7).
Section 4 (`LLM_Evaluation_Findings.md`) already flags that Run 7 not recurring the tag-leak issue
"is one confirmation, not a guarantee" — this document doesn't repeat that judgement, just points to
it, since it's the same evidence gap.

## 3. `model_runner.py` config/code changes

| Change | Justified by | Re-run evidence |
|---|---|---|
| `except (TimeoutError, socket.timeout)` — previously `except TimeoutError` only | First attempt at Run 1 hit `timeout_seconds: 30.0` and was mis-labelled `MODEL_ERROR` instead of `TIMEOUT`, because Python 3.9's `urllib` raises `socket.timeout`, a separate class from `TimeoutError` before Python 3.10 | `test_socket_timeout_also_returns_timeout_not_model_error` injects `socket.timeout` directly — the exact class the previous test suite never exercised, since every existing test mocked a `TimeoutError` directly. Confirmed passing on the real Python 3.9.6 environment the original bug was found on (`python3 -m pytest test_model_runner.py -v`, 16/16 passed). |
| `timeout_seconds` raised from the example default (30.0) to 120.0 for live runs | The same Run 1 timeout above — the model genuinely needs more than 30 seconds to rewrite a full 12-section report on local hardware | Confirmed working: every subsequent run (2-7) completed within the raised timeout, with `runtime_ms` values ranging 43,694-78,487ms (see `LLM_Live_Run_Notes.md` sections 3-10) — well under 120,000ms in every case. |
| `frequency_penalty` (optional, opt-in via `model_config.json`) added to the request payload | Run 5's repetition loop — the disclaimer section generated ~85 lines of near-duplicate filler, and nothing in the validator or the prompt addressed repetition directly at the token-generation level | `test_frequency_penalty_is_included_when_set` confirms the field reaches the payload when configured; `test_frequency_penalty_is_omitted_from_payload_by_default` confirms it stays out of the payload otherwise, so the opt-in behaviour doesn't leak into calls that don't set it. Run 6, made with `frequency_penalty` enabled, showed no repetition loop — the specific failure mode it targeted did not recur. (Run 6 still failed for a different reason — tag leakage — which `frequency_penalty` was never meant to address; see section 2.) |

## 4. Validator changes re-run against the full regression suite

Every validator fix made during Task 62 (see `LLM_Evaluation_Findings.md` section 5 for the full
list of thirteen) was re-run against the complete test suite after being added, not just the
specific case that motivated it — confirming no fix silently broke an earlier passing case.

- `test_llm_validator.py`: 76 tests passing on the final validator state (`python3 -m pytest
  test_llm_validator.py -v`), including every one of the 23 original Task 25 fixtures, the real
  captured output from Runs 1, 6, and 7 embedded as permanent fixtures, and an adversarial
  regression test for each of the thirteen fixes confirming it doesn't reintroduce a false positive
  elsewhere (e.g. `test_exemption_is_narrow_other_field_names_still_required` confirms the
  `cost_per_ml`/`max_available_ml_per_day` exemption didn't accidentally widen to other fields).
- `test_model_runner.py`: 16 tests passing, including the `socket.timeout` regression and
  `frequency_penalty` coverage above.

## 5. What this confirms, and what it doesn't

**Confirmed:** every prompt and config change made during Task 62 was made in direct response to a
specific, named failure (never speculatively), and re-running the relevant case afterward showed
that specific failure resolved without reopening an earlier one — the full regression suite staying
green after each change is the evidence for the second half of that claim, not just the single
targeted re-run.

**Not confirmed, and not claimed here:** that the current prompt/config combination is failure-proof
going forward. Run 7 is one clean run on one scenario. The open validator gap
(`LLM_Evaluation_Findings.md` — prompt-tag-leak detection) means that if that failure mode recurred
under different phrasing or a different scenario, nothing in the current pipeline is guaranteed to
catch it structurally — the fixes made so far closed the specific instances observed, not the
general failure category, and are documented as one occurrence of "no tag leak," not a proof.
