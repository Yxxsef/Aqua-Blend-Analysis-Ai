# Task 23 — Deterministic Fallback Explanation Generator (upgraded)

**AquaBlend | Analysis & AI | Sprint 2**
**Depends on:** the Results JSON produced upstream and adapted by Task 21's
`results_adapter.py` (`AI/results/`), and the Task 22 reporting specification
(`explanations/llm_reporting/docs/LLM_Report_Scope.md`, `Report_Structure.md`,
`Results_JSON_Field_Map.md`)
**Consumed by:** Task 24's LLM runner, which takes this script's plain-text output
and rewrites it in natural language without changing any of its facts

---

## 1. What this task is, in plain words

The water-blending optimiser produces a big technical JSON report: which water
sources to use, how much of each, what it costs, whether the plant-inflow blend
meets quality limits. A plant operator can't read raw JSON. Something needs to turn
those numbers into plain sentences.

Normally an LLM does that rewriting (Task 24). But an LLM call can fail, time out, or
be unavailable — and this project is a proof-of-concept, so its output should never
be trusted blindly anyway. **`json_explainer.py` is the required deterministic
fallback**: plain Python, no AI, no network call, that reads the Results JSON and
produces a complete, correctly-ordered, fact-only report on its own. It's also the
plain-text input Task 24's LLM rewriter starts from — so its output has to be
complete and correct even before an LLM ever sees it.

**Sprint 2 changed what "correct" means for this script.** The Task 22 specification
(`Report_Structure.md`, `LLM_Report_Scope.md`) settled several questions Sprint 1
left open, and this upgrade brings the generator in line with it:

- Reports are structured as the 12 sections `Report_Structure.md` defines, in that
  fixed order, not the old 6-section structure.
- The generator **no longer invents a reason a source was selected or unused**.
  `LLM_Report_Scope.md` §4 forbids the template from creating source-selection
  reasons, and §10 flags that ownership of `sources.unused[].reason` is still
  unconfirmed — so that field is never rendered, even when present in the input.
- Numeric values and units are reported **exactly as given**, never rounded or
  reworded into an approximation.
- Only an `OPTIMAL` result gets the full 12-section report. Every other status
  (`INFEASIBLE`, `UNBOUNDED`, `ERROR`, `TIME_LIMIT`, or anything unrecognised) gets a
  short **status-only** report: scenario/status, a result-availability warning, and
  the prototype disclaimer — nothing else, since there's no solution to describe.
- A prototype disclaimer is now a mandatory, always-present final section.
- Water-quality output states explicitly which stage of the process it applies to
  (`waterQuality.applies_to`) and always ends with a fixed note that these are
  plant-inflow results, not final post-treatment drinking-water results.

## 2. Note on Task 21 (`results_adapter.py`)

Task 21 (`AI/results/results_adapter.py`, now merged) converts the raw external
Results JSON into a stable internal shape by renaming a fixed set of TOP-LEVEL
keys to camelCase (e.g. `scenario_id` -> `scenarioId`, `demand_zones` ->
`demandZones`, `transfer_paths` -> `transferPaths`, `water_quality` ->
`waterQuality`, `data_flags` -> `dataFlags`). `status`, `objective`, `sources`,
`plants`, `constraints` and `diagnostics` pass through unchanged, and the
adapter never renames anything nested inside those top-level values, so
nested field names still match `Results_JSON_Field_Map.md` exactly.

`json_explainer.py`'s input contract is that ADAPTED shape — i.e. this module
assumes `results_adapter.adapt_results()` has already run upstream, not that
it's reading the raw Results JSON directly. It does not call
`adapt_results()` (or `results_validator.py`'s `validate_results()`) itself:
both of those hard-require every top-level field and raise on the first gap,
which conflicts with this module's own deliberately tolerant contract — only
`status`/`scenarioId` are required here, and everything else degrades
gracefully instead of raising. If the adapter's output shape changes, only
the field-name constants at the top of `json_explainer.py` should need to
change.

---

## 3. The files, and what each one is for

| File | What it is | Do you need to run it? |
| --- | --- | --- |
| `json_explainer.py` | The actual program. This is the deliverable. | Yes — this is what gets used |
| `test_json_explainer.py` | Automated checks confirming the script's behaviour against `Report_Structure.md` and `LLM_Report_Scope.md`, plus the reference input data (`REFERENCE_JSON`) | Optional — run it to double-check everything still works |
| `sample_explanations_sprint2.txt` | Real Sprint 2 output, already run, for an OPTIMAL scenario and two non-optimal (status-only) scenarios | No — just open and read |
| `sample_explanations.txt` | Sprint 1 output, kept for history; describes the old 6-section structure and is no longer representative of the script's current behaviour | No — superseded by the file above |
| `README.md` | This file | No — just documentation |

### `json_explainer.py` — the program itself

Produces the 12 sections `Report_Structure.md` defines, in this fixed order:

1. **Scenario & Solver Status** — scenario id, solver status, solved-at time
2. **Result Availability** — a plain statement of whether this result is usable
3. **Demand-Zone Results** — required vs. supplied volume per zone
4. **Selected Sources & Blend Ratios** — which sources were used, exact volumes,
   percentages, and costs — facts only, never a reason for the selection
5. **Unused Sources** — which sources were not selected — never echoes
   `sources.unused[].reason`
6. **Active Plants & Transfer Results** — plant throughput and treatment cost, plus
   transfer-path flows when reported
7. **Cost Summary** — total cost and its breakdown, copied from `objective`, never
   recalculated
8. **Plant-Inflow Water Quality** — states what stage the results apply to, reports
   pass/fail and safety margins per plant, and always ends with the fixed
   plant-inflow-not-final-drinking-water note
9. **Binding Constraints** — what limited the result, grouped in a fixed category
   order (demand, then source-capacity, then plant-capacity, then link-capacity,
   then water-quality) regardless of the order the JSON lists them in
10. **Data Flags & Estimated Values** *(only shown when there's something to
    disclose)* — which sources have estimated rather than measured values, plus any
    data-provenance notes
11. **Alternatives & Sensitivity** *(only shown when there's something to report)* —
    alternative feasible solutions and which assumptions the result is sensitive to
12. **Prototype Disclaimer** — always present, states this is a decision-support
    proof-of-concept, not a substitute for qualified operators or regulators

Sections 3–11 only appear for an `OPTIMAL` result. Any other status produces sections
1, 2, and 12 only.

**How to run it**, from a terminal, inside this folder:

```bash
python json_explainer.py path\to\results.json
```

That prints the full report to standard output. There's no bundled example JSON file
in this folder — the reference scenario used throughout the tests and
`sample_explanations_sprint2.txt` lives inside `test_json_explainer.py` as
`REFERENCE_JSON`. To try the script against it directly:

```bash
python -c "import json; from test_json_explainer import REFERENCE_JSON; json.dump(REFERENCE_JSON, open('try_it.json', 'w'), indent=2)"
python json_explainer.py try_it.json
```

**The rule the whole script follows: never invent a fact.** If a value isn't in the
JSON, the script says so plainly (e.g. "No demand-zone result was provided.") instead
of guessing — this is the same rule Sprint 1 followed, now enforced more strictly:
Sprint 1's source-selection reason clauses ("because it is the cheapest available
source...") are gone, since `LLM_Report_Scope.md` §4 settled that the template must
not create those reasons at all.

### `test_json_explainer.py` — the automated checks

93 tests, covering every section, every non-optimal status, missing-vs-empty field
handling per section, the `waterQuality.applies_to` rule, estimated-data disclosure,
and determinism (identical input always produces identical output).

**How to run it:**

```bash
python -m pytest test_json_explainer.py -v
```

All 93 currently pass.

### `sample_explanations_sprint2.txt` — pre-generated example outputs

Three genuine outputs, produced by actually running `generate_explanation()` against
`REFERENCE_JSON` (not typed by hand):

| Sample | Status | What it shows |
| --- | --- | --- |
| 1 | `OPTIMAL` | The full 12-section report |
| 2 | `INFEASIBLE` | The 3-section status-only report |
| 3 | `TIME_LIMIT` | The 3-section status-only report (treated as non-reportable, since `TIME_LIMIT` feasible-solution handling is an open question in `LLM_Report_Scope.md`) |

---

## 4. Required vs. optional data

**Required** — the script refuses to run without these, raising `ExplainerInputError`:
`status`, `scenarioId`. Without these the report cannot even state what it's
describing.

**Everything else is optional.** Missing or empty data never crashes the generator —
each section states plainly when a result wasn't provided. A few gaps are not hard
stops but do surface as an inline validation warning within the affected section,
per `Report_Structure.md`'s per-section missing-field rules:

- `bindingConstraintsSummary` missing on an `OPTIMAL` run
- `dataFlags` missing entirely (as opposed to present-but-empty, which just omits
  the section)
- `waterQuality.applies_to` missing while `waterQuality.by_plant` is present

---

## 5. What changed from Sprint 1, and why

- **Report structure**: rebuilt from the old ad hoc 6-section layout to the fixed
  12-section order `Report_Structure.md` defines, with status-gated sections 3–11
  and a mandatory closing disclaimer.
- **Source-selection reasoning removed**: the old cost-ranking / capacity-binding
  heuristic that produced sentences like "because it is the cheapest available
  source" is gone. `LLM_Report_Scope.md` §4 forbids the template from inventing
  these reasons at all — selected and unused sources are now reported as plain
  copied facts only.
- **`sources.unused[].reason` is never rendered**, even when present in the input,
  since `LLM_Report_Scope.md` §10 flags its ownership as unconfirmed.
- **Exact values, not rounded ones**: ML volumes are shown exactly as given; the old
  rounding helper was removed.
- **Non-optimal statuses get a short status-only report** instead of a single
  short-circuit sentence — they still get a proper scenario/status section and a
  result-availability explanation, just not sections 3–11.
- **Water-quality wording tightened**: results now explicitly say what stage they
  apply to (`applies_to`), and never claim water is "safe," "compliant," or a
  "final" drinking-water result — only that plant-inflow values passed or failed
  against the modelled constraint range.
- **The old free-standing "Summary" section is gone.** It isn't one of
  `Report_Structure.md`'s 12 sections; the Cost Summary and Scenario & Solver Status
  sections now cover the same ground with exact figures instead of a rounded
  one-line recap.

---

## 6. Known open items — worth confirming with the team

- **`results_adapter.py` is now merged (Task 21, `AI/results/`).** This script
  consumes its adapted (camelCase-top-level) output shape rather than the raw
  external Results JSON — see Section 2 above. It deliberately does not call
  `adapt_results()`/`validate_results()` itself, since both are stricter
  (all-fields-required) than this module's own graceful-degradation contract.
- **`TIME_LIMIT` handling is provisional.** `Results_JSON_Field_Map.md` flags that
  whether a `TIME_LIMIT` result may carry a usable feasible solution is still an
  open approval question. This script currently treats `TIME_LIMIT` the same as
  `INFEASIBLE`/`UNBOUNDED`/`ERROR` (status-only, no solution values reported) until
  that's confirmed either way.
- **`sources.unused[].reason` ownership is unconfirmed.** The field is never
  rendered by this script regardless, so no behaviour change is needed if this gets
  resolved — but the field itself still exists unused in the input schema.

