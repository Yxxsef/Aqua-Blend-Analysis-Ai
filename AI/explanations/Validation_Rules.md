# AquaBlend Validation Rules

**AquaBlend | Analysis & AI | Sprint 2 | Task 25**
**Depends on:** LLM_Report_Scope.md section 6 ("Critical Failure Conditions"), Report_Structure.md
(Task 22), the merged json_explainer.py (Task 23), and the merged model_runner.py / prompts.py (Task 24)

## 1. Purpose

This document defines what `llm_validator.py` checks, and exactly how each check is implemented.
LLM_Report_Scope.md section 6 lists eleven critical failure conditions in plain language ("an
invented number", "a wrong quality status", and so on). This document is the bridge between that
plain-language list and the actual code: for each condition, it states the detection method used,
what it will and will not catch, and why that method was chosen over a more precise but much more
complex alternative.

The validator does not understand the report. It does not parse the original Results JSON, and it
does not call `json_explainer.py` or `model_runner.py`. It compares two plain strings - the
deterministic report and the candidate rewrite - using pattern matching. Every rule below is
written so a human reviewer can look at a `CriticalFailure` or `Warning_` in the validator's output
and immediately see which specific words or numbers triggered it, and check that call themselves.

## 2. Two input strings, one comparison

`validate_llm_output(deterministic_report, llm_output)` takes:

- `deterministic_report` - the trusted text from `json_explainer.generate_explanation()` (Task 23).
  Treated as ground truth throughout, the same way Task 24's own prompt treats it: "The
  deterministic report is the complete factual source for this task."
- `llm_output` - the candidate rewrite, typically a successful `model_runner.RewriteResult.report_text`
  where `report_mode` is `"LLM_UNVALIDATED"` (Task 24).

The validator does not call `model_runner.py` or read a `RewriteResult` object directly - it takes
two strings. Whatever calls this module supplies the two correct strings and decides what happens
next (e.g. converting `report_mode` from `"LLM_UNVALIDATED"` to `"LLM_VALIDATED"` on a PASS, or
keeping `"TEMPLATE_FALLBACK"` on a FAIL). That conversion is out of scope for this module, the same
way `json_explainer.py` does not call `results_adapter.adapt_results()` itself even though it
depends on that function's output shape.

## 3. Fact extraction

Before any rule runs, both texts are lower-cased for the phrase-based checks, and `## Heading` lines
are stripped from **both** texts - the deterministic report and the rewrite - before number,
identifier, unit-code, and status-word extraction. Headings are stripped because prompts.py rule 5
explicitly permits the LLM to reword headings ("you may improve headings and sentence flow"), so a
legitimately reworded heading must never be mistaken for a missing identifier or a missing fact.

Both sides are stripped, not just the source, because Report_Structure.md's own section headings
are frequently Title-Case two-word phrases - "Selected Sources", "Active Plants", "Data Flags" - that
match the identifier pattern just as well as a real source name does. Stripping only the
deterministic side was tried first and found to be wrong by testing the trivial case of a rewrite
that exactly equals the source: with only one side stripped, the rewrite's own (unstripped) headings
were compared against the source's (stripped) body and reported as brand-new identifiers, even
though nothing had actually changed. `test_identical_text_passes_with_no_warnings` in
`test_llm_validator.py` exists specifically to keep this fixed.

**Numbers.** A number is any token matching `-?\$?\d[\d,]*(?:\.\d+)?%?` - an optional sign or `$`,
digits with optional thousands separators, an optional decimal part, an optional `%`. `$68,150.0`
and `68150.0` normalise to the same value; `235` and `235.00` are treated as the same fact (same
underlying value, different precision - the rule is about the fact, not the exact string).

**The percent sign is part of a number's identity, not stripped away.** `58.0%` and `58.0` are
tracked as different facts, even though they share the same digits - each number is recorded as a
`(value, is_percent)` pair, not a bare value. An earlier version of this function stripped `%`
before comparing, which meant a rewrite that dropped the percent sign while keeping the same digits
(`58.0%` becoming `58.0`) passed validation - a real fact change (a proportion becoming an
ambiguous bare number) went completely undetected. Found in code review, not by the original test
pack; `test_dropped_percent_sign_fails` and `test_added_percent_sign_also_fails` in
`test_llm_validator.py` now guard both directions.

The `$` prefix is not tracked the same way, deliberately: a dropped `$` sign on its own is a weaker
signal than a dropped `%`, since the currency itself is still independently checked by the unit-code
rule (`AUD`, `NZD`, and so on) whenever a currency code appears nearby in the source. Percent has no
equivalent second check anywhere else in this module, which is exactly why losing it silently was a
real gap rather than a redundant one.

A candidate number is discarded if it is actually embedded inside a longer identifier token - e.g.
the `01` inside `scenario_2026_07_17_001`, or the `1` inside `facility_1`. A single-character
lookaround on the regex catches the simple case (a digit directly touching a letter or underscore)
but not a multi-digit run where a match could start partway through - the `01` in `..._17_001`
starts right after another digit (`0`), which a plain "not preceded by a letter or underscore"
check would happily accept. The actual check extends outward through the full contiguous run of
letters/digits/underscores on both sides of the candidate match and discards it if that whole run
contains a letter. This was found and fixed by testing against `scenario_2026_07_17_001` directly,
not designed abstractly in advance.

**Presence, not repetition count.** A number is checked for presence (does it appear at least once
in the rewrite if it appeared at least once in the source), not exact repetition count. This was
tried the other way first - an exact count match - and rejected: the deterministic report often
restates the same fact across more than one section (a source's flow volume appears in both its
selection line and its transfer-results line, for example), and a faithful, naturally-compressed
rewrite can legitimately state a fact fewer times than the source without dropping it. For example,
this sentence from the deterministic report:

> Silvan Reservoir to Treatment Facility 1: 210 ML/day (active).
>
> Yarra River, Kew to Treatment Facility 1: 290 ML/day (active).
>
> Groundwater Bore 1 to Treatment Facility 1: 0 ML/day (inactive).

can be faithfully compressed into one sentence -

> Flows into the facility were 210 ML/day from Silvan Reservoir and 290 ML/day from Yarra River,
> Kew; the link from Groundwater Bore 1 carried 0 ML/day and was inactive.

- which mentions "Treatment Facility 1" once instead of three times, without losing the fact that
all three sources flow into it. An exact-count check flagged this as `NUMBER_MISSING_OR_CHANGED`;
a presence check correctly does not.

**Identifiers.** Two kinds are checked, since the deterministic report uses both to refer to the
same entities:

- Title-Case phrases: two or more consecutive capitalised words, e.g. `Silvan Reservoir`,
  `Yarra River, Kew`, `Treatment Facility 1`, `Zone 1`. Matches the actual naming pattern of every
  source, plant, and zone name in the confirmed contract's example data.
- snake_case tokens: `\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b`, e.g. `silvan_reservoir`,
  `groundwater_bore_1`, `storage_capacity`, `cost_per_ml`, `zone_1`. These are the internal IDs and
  field names the Data Flags and Sensitivity sections quote directly, and are just as easy for a
  rewrite to drop as the display names are.

A missing identifier (present in the source, absent from the rewrite) is a critical failure. A new
identifier (present in the rewrite, absent from the source) is a warning only, not a failure -
paraphrasing can introduce a plausible-looking name in ways that are hard to distinguish from a
genuine invention with a text-only check, so this is surfaced for a human to check rather than
auto-failed.

**Sentence-initial false positives.** The Title-Case pattern was found, by testing against the
actual reference report, to false-positive on ordinary sentence-initial words directly followed by
a real proper noun. The reference report's own Alternatives section contains:

> Reduce Yarra Kew share to 45 percent and introduce Groundwater Bore 1 at 13 percent.

"Reduce" is capitalised only because it starts the sentence, and "Yarra Kew" immediately follows it
with no lowercase word in between to break the match - so the regex captured "Reduce Yarra Kew" as
one phantom identifier that no faithful rewrite could ever reasonably reproduce verbatim. The fix is
a short, explicit stopword list (`Reduce`, `Increase`, `Introduce`, `Remove`, `Add`, `Consider`,
`See`, `Note`, `Include`, `Exclude`, `Downstream`, `For`, `Overall`, `Given`, `Based`, `According`):
a Title-Case match is discarded if its first word is one of these. None of AquaBlend's actual
source, plant, or zone names begin with any of them, so this removes the false positive without
weakening genuine identifier coverage. This list was built by testing, not guessed in advance - the
first version of this validator failed its own "correct rewrite" fixture on exactly this false
positive.

**Unit and currency codes.** `\bpH\b|\b[A-Z]{2,5}\b` - catches `AUD`, `NZD`, `ML`, `NTU`, and `pH`.
Checked for presence only, same rationale as numbers.

**Status words.** The confirmed contract's solver-status set - `OPTIMAL`, `INFEASIBLE`, `UNBOUNDED`,
`TIME_LIMIT`, `ERROR` - plus `PASS`/`FAIL` for water-quality parameter status. `SUCCESS` and
`FEASIBLE` are deliberately excluded: those were placeholder values from an earlier draft schema,
not the confirmed `model_output_contract.json` set. Unlike numbers and identifiers, status words are
checked in both directions as critical failures: a status word present in the source but missing
from the rewrite (`STATUS_MISSING`), and a status word present in the rewrite but not the source
(`STATUS_INVENTED`) - together these catch a status flip (`OPTIMAL` silently becoming
`INFEASIBLE`, say) from either side.

## 4. Invented content

LLM_Report_Scope.md rule 3 forbids the template - and by extension the LLM rewrite - from creating
"reasons, causal claims, recommendations, decisions, alternatives, sensitivity findings, regulatory
claims, compliance claims, [or] operational advice." This is checked with two phrase lists, both
**differential**: a phrase only counts if it appears in the rewrite but is genuinely absent from the
deterministic report, never a blanket ban on the phrase existing anywhere.

This distinction matters in practice. The deterministic report's own Data Flags notes genuinely
contain the word "because" (explaining why `source_activation_cost` is structurally `0.00`), so
"because" appearing in a rewrite is not automatically suspicious - only a *new* occurrence, in a
place the source never used it, is.

- **Strong phrases** (`because`, `we recommend`, `cheapest available`, `in compliance with`,
  `ensures safety`, and others - see `STRONG_INVENTED_CONTENT_PHRASES` in the code) are a critical
  failure (`INVENTED_CONTENT`) when new.
- **Weak phrases** (`this shows`, `probably`, `may indicate`, and others - see
  `WEAK_INVENTED_CONTENT_PHRASES`) are common enough in ordinary explanatory prose that a hard fail
  risks real false positives, so these are recorded as a warning (`WEAK_INVENTED_CONTENT_PHRASE`)
  for a human to check rather than auto-failed.

## 5. Safety claims - never negotiable

LLM_Report_Scope.md rule 4 and section 6 both call out "an unsafe result described as safe" as its
own category, separate from ordinary invented content, and for good reason: this is the one failure
mode with a real-world safety consequence if missed. `ALWAYS_BANNED_PHRASES` -
`"final drinking"`, `"safe to drink"`, `"compliant"`, `"treated water"` - are banned in the rewrite
regardless of whether they happen to already exist in the source. These four phrases are not chosen
independently; they are lifted directly from `json_explainer.py`'s own permanent test guarantee
(`test_water_quality_never_claims_final_or_safe` in `test_json_explainer.py`), which already proves
the deterministic report never contains them. Their appearance in a rewrite is therefore always a
rule 4 violation, never a legitimate carry-over from the source - there is nothing to carry over.

## 6. Disclaimer and water-quality stage note

Both are checked by marker phrase, not exact text, because the LLM is explicitly allowed to reword
them:

- **Disclaimer** (`DISCLAIMER_MISSING`): if the source contains `"proof-of-concept"` (or
  `"proof of concept"`), the rewrite must contain one of those two forms somewhere.
- **Water-quality stage note** (`WATER_QUALITY_NOTE_MISSING`): if the source contains water-quality
  content (`"plant inflow"`, `"plant-inflow"`, `"blend_at_plant_inflow"`, or `"water quality"`), the
  rewrite must contain `"plant inflow"`, `"plant-inflow"`, or the non-breaking-hyphen variant
  somewhere.

Both checks look for the marker phrase *anywhere* in the rewrite, not specifically attached to the
right section. This is a known, deliberate simplification - see section 7.

## 7. Known limits

This validator is a fast, explainable, deterministic first pass, not a substitute for a human
reading the rewrite. The following gaps are deliberate, not oversights:

- **Marker checks are not section-scoped.** The disclaimer and water-quality checks look for their
  marker phrase anywhere in the whole rewrite. A rewrite that mentions "plant inflow" once, in an
  unrelated paragraph, while genuinely dropping the note from the quality discussion itself, would
  pass this check. Properly scoping this to "within the quality section" would require actual
  section parsing, which this module deliberately does not do (see section 2). Caught in testing:
  the deterministic report mentions "plant inflow" twice - once in the quality section, once again
  in the Data Flags notes - so a test that removed only the first occurrence did not fail until the
  test itself was corrected to remove every occurrence.
- **A number written with no space before its unit could be missed.** The number/identifier
  boundary check (`_is_embedded_in_identifier`) extends outward through any contiguous run of
  letters, digits, and underscores. If a rewrite wrote `290ML` instead of the source's `290 ML`,
  the digits and letters would be touching with no space between them, and the whole run would be
  treated as one identifier-like token and excluded from the number check - producing a
  `NUMBER_MISSING_OR_CHANGED` failure for an otherwise faithful rewrite. This has not been observed
  in practice: every deterministic report fixture always writes a space before the unit, and
  prompts.py's rewrite rules give the LLM every reason to copy that spacing rather than invent a
  new style. Documented here rather than guarded against in code, since adding a special case for an
  unobserved formatting choice would add real complexity for a hypothetical problem.
- **`UNIT_OR_CODE_MISSING` and `STATUS_MISSING` can overlap harmlessly.** `_UNIT_CODE_PATTERN`
  (`\bpH\b|\b[A-Z]{2,5}\b`) also matches some solver-status words that happen to be 2-5 letters -
  `ERROR`, `PASS`, `FAIL` (`OPTIMAL`, `INFEASIBLE`, `TIME_LIMIT`, and `UNBOUNDED` are all too long to
  match). Dropping one of these words from a rewrite would correctly trigger both
  `UNIT_OR_CODE_MISSING` and `STATUS_MISSING` for the same underlying problem. This is treated as
  acceptable redundancy, not a bug worth suppressing - two independent rules agreeing that the same
  word went missing is a stronger signal, not a misleading one.
- **Identifier and number checks cannot distinguish a genuinely wrong value from a coincidentally
  identical new one.** If a rewrite invents a new number that happens to equal a value already
  present in the source, this validator cannot detect it - it only tracks *which values exist*, not
  which sentence they came from.
- **The invented-content phrase lists are not exhaustive.** They cover the patterns this project's
  own generated reports have actually produced or are likely to produce, not every possible way to
  phrase a recommendation or a safety claim in English.
- **PASS/FAIL status words are checked but rarely fire in practice.** `json_explainer.py` converts
  quality PASS/FAIL into prose ("passed", "breached its allowed range") rather than rendering the
  literal words, so `QUALITY_STATUS_WORDS` mostly guards against a future renderer or a different
  report style that does render them literally.
- **This is a text check, not a solver.** It cannot verify a number is *correct* against the
  original Results JSON - only that it matches what the deterministic report (already produced from
  that JSON) already said. If Task 23's own generator has a bug, this validator will not catch it;
  that is `test_json_explainer.py`'s job, not this module's.

## 8. Rule-to-code map

| LLM_Report_Scope.md section 6 condition | Rule name(s) | Function |
|---|---|---|
| An invented number | `NUMBER_INVENTED` | `_check_numbers` |
| A changed number | `NUMBER_MISSING_OR_CHANGED` + `NUMBER_INVENTED` | `_check_numbers` |
| An incorrect unit | `UNIT_OR_CODE_MISSING` | `_check_unit_codes` |
| A wrong selected source | `IDENTIFIER_MISSING` / `STATUS_*` | `_check_identifiers`, `_check_status_words` |
| A wrong unused source | `IDENTIFIER_MISSING` | `_check_identifiers` |
| An invented reason | `INVENTED_CONTENT` | `_check_invented_content` |
| A wrong binding constraint | `IDENTIFIER_MISSING` / `NUMBER_*` | `_check_identifiers`, `_check_numbers` |
| A wrong quality status | `STATUS_MISSING` / `STATUS_INVENTED` | `_check_status_words` |
| An unsafe result described as safe | `UNSAFE_SAFETY_CLAIM` | `_check_always_banned_safety_claims` |
| An omitted required fact | `NUMBER_MISSING_OR_CHANGED` / `IDENTIFIER_MISSING` / `UNIT_OR_CODE_MISSING` | various |
| An omitted critical warning | `DISCLAIMER_MISSING` / `WATER_QUALITY_NOTE_MISSING` | `_check_disclaimer`, `_check_water_quality_note` |
| *(not in section 6 - defensive addition)* | `EMPTY_OUTPUT` | `_check_empty_output` |
| *(not in section 6 - defensive addition)* | `LENGTH_ANOMALY` (warning) | `_check_length_anomaly` |
| *(not in section 6 - defensive addition)* | `NEW_IDENTIFIER` (warning) | `_check_identifiers` |
| *(not in section 6 - defensive addition)* | `WEAK_INVENTED_CONTENT_PHRASE` (warning) | `_check_invented_content` |

"A wrong selected source" and "a wrong binding constraint" do not have a single dedicated rule -
they are covered by the combination of the identifier check (the source or constraint's name), the
number check (the volumes and figures attached to it), and the status check (feasibility outcomes),
since a "wrong" source or constraint in practice means at least one of these three fact categories
no longer matches.
