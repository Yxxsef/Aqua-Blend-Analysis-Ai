# Task 9 — Fallback Explanation Generator

**AquaBlend | Analysis & AI | Sprint 1**
**Owner:** Abdulla
**Dependencies:** Tasks 6, 7, 8, plus the reference Results JSON (AquaBlend MILP
Configuration document, Section 8)

---

## 1. What this task is, in plain words

The water-blending optimiser produces a big technical report — a JSON file full of
numbers: which water sources to use, how much of each, what it costs, whether the
water is safe to drink. A plant operator can't read raw JSON. Something needs to turn
those numbers into plain sentences, like:

> "We used mostly river water because it was cheapest. Groundwater wasn't used
> because it costs more. The water is safe to drink."

Normally an AI (an LLM) would write that explanation. But if the AI is unavailable,
too slow, or too expensive to call every time, there needs to be a backup that still
produces a correct explanation without any AI involved.

**`json_explainer.py` is that backup.** It's a plain Python script with hand-written
rules. You give it the JSON file, it gives you back readable sentences — the same job
an AI would do, done instead by deterministic code that never guesses and never
invents a fact that isn't in the data.

Everything else in this folder — the tests, the sample outputs, this README — exists
to prove that script actually works correctly and matches what the team already
agreed the explanation should say.

---

## 2. The files, and what each one is for

| File | What it is | Do you need to run it? |
| --- | --- | --- |
| `json_explainer.py` | The actual program. This is the deliverable. | Yes — this is what gets used |
| `sample_explanations.txt` | Real output from the script, already run, saved to a file so you can read it without running anything | No — just open and read |
| `test_json_explainer.py` | 60 automated checks confirming the script behaves correctly, and also contains a full copy of the example data (`REFERENCE_JSON`) that the script can be run against | Optional — run it to double-check everything still works |
| `README.md` | This file | No — just documentation |

These four are Task 9's actual deliverables. There's no separate example-data file
shipped alongside them — Section 2 below shows how to generate one on the spot from
data that's already inside `test_json_explainer.py`, so nothing extra needs to exist
in the deliverable set.

### `json_explainer.py` — the program itself

Reads a Results JSON and produces six sections of plain-English explanation:

1. **Selected & Unused Sources** — which water sources were used, how much of each,
   and why; which were skipped, and why
2. **Binding Constraints** — what limited the result (e.g. "demand had to be fully
   met, leaving no slack"), grouped in a fixed order (demand, then source-capacity,
   then plant-capacity, then link-capacity, then water-quality) regardless of what
   order the JSON lists them in, and flagged with ", estimated" when the underlying
   source-capacity figure is estimated rather than measured (source_capacity is the
   only category with a provenance mechanism in the confirmed contract; demand,
   plant-capacity, link-capacity, and water-quality never disclose "(estimated)",
   since none of them are tracked for provenance)
3. **Water Quality & Safety Margins** — whether the treated water is safe, and which
   measurement is closest to its safety limit
4. **Sensitivity to Key Assumptions** — which guessed/estimated inputs could change
   the answer if they turn out to be wrong
5. **Estimated Fields / Data Limitations** — a plain list of every number in the
   report that's an estimate rather than a real measurement
6. **Summary** — one line: total cost, how many sources used, overall pass/fail

**How to run it**, from a terminal, inside this folder — first create a test input
file from the example data already stored in `test_json_explainer.py`, then run the
script against it:

```bash
python3 -c "
import json
from test_json_explainer import REFERENCE_JSON
with open('try_it.json', 'w') as f:
    json.dump(REFERENCE_JSON, f, indent=2)
"
python3 json_explainer.py try_it.json
```

That first command writes a temporary `try_it.json` file (the same reference scenario
used throughout this README and the tests), and the second prints the full
explanation. Delete `try_it.json` afterwards if you don't want it lying around — it's
not part of the deliverable, just a scratch file for trying the script.

If you just click "Run" in an editor instead of using the terminal, it won't do
anything useful — it needs a file path handed to it, so it just prints a usage message
and stops. That's expected, not a bug.

**The rule the whole script follows: never invent a fact.** If a number, a reason, or
a measurement isn't in the JSON, the script says so plainly ("not reported," "no
reason provided") instead of guessing. This matters because a wrong guess dressed up
as a fact could mislead a real water operator — see Section 5 below for a worked
example of exactly this.

### The example data itself

The `try_it.json` generated in the command above (and the `REFERENCE_JSON` it comes
from inside `test_json_explainer.py`) is the exact reference example from the official
MILP Configuration document (Section 8) — a fictional-but-realistic scenario: two
water sources blended together, one source considered but not used, water quality
checked and passed. It's what the solver's real output looks like.

Use it as a starting point to edit and see how the explanation changes — e.g. delete
a field and see what the script says about the missing data.

### `sample_explanations.txt` — pre-generated example outputs

Ten examples, each showing the script's real output on a slightly different input.
**Every one of these was produced by genuinely running `python3 json_explainer.py`
as a real command** — not typed by hand, not simulated. Each is labelled with what's
different about that scenario and why it's there:

| Sample | What's different | What it proves |
| --- | --- | --- |
| 1 | Nothing — the real reference scenario | What normal, everything-works output looks like |
| 2 | Solve marked as failed (`INFEASIBLE`) | The script doesn't try to explain a result that doesn't exist |
| 3 | No water sources needed (zero demand) | Handles an "empty" result without crashing |
| 4 | One water-quality reading pushed into failure | The script correctly flags unsafe water instead of saying everything's fine |
| 5 | One source's cost missing, plus a plant-capacity binding constraint | Handles missing data, and shows a constraint type Sample 1 doesn't |
| 6 | One water-quality measurement missing entirely | Says "not reported," never assumes it passed |
| 7 | The "what could change the answer" info missing | Shows the fallback message for that section |
| 8 | The whole cost/pricing section missing | Cost shows as "not reported" instead of a guessed number |
| 9 | Binding constraints listed out of order (water-quality first, demand last) | Output still renders in fixed category order, not JSON order |
| 10 | Link-capacity constraints binding (source-to-plant and plant-to-zone) | A category that was missing entirely before this fix now renders correctly |

**Why some of these look like real solver output but aren't:** Samples 2–8 are all the
same reference scenario with one thing deliberately deleted or changed, purely to
check the code handles that situation correctly. None of them are real solver runs.
Sample 1 is the only one that reflects an actual scenario.

**A note on Sample 8, since it came up:** an earlier draft of this file tested the
same idea (does the script handle missing data correctly) by swapping the currency
from AUD to NZD (New Zealand dollars). That proved the code reads currency from the
data instead of it being hard-typed into the program — but it also looked confusing
sitting in a sample file for an Australian project, since AquaBlend will never
actually use anything but AUD. It's been replaced with a version that proves the same
thing (no guessing, no hardcoding) without ever showing a currency other than AUD.

### `test_json_explainer.py` — the automated checks

60 tests. Running them checks that every rule described above actually holds — not
just on the one example scenario, but on every unusual situation: missing data,
failed solves, safety violations, and so on.

**How to run it:**

```bash
pip install pytest --break-system-packages
python3 -m pytest test_json_explainer.py -v
```

All 60 currently pass. You don't need to run this yourself to use the script — it's
there so anyone reviewing or changing the code later can quickly confirm nothing
broke.

---

## 3. How this connects to the rest of the project

This script doesn't invent its own explanation style. It combines work three other
team members already did and agreed on:

- **Task 6** (Ali) defined exactly how to describe selected/unused sources
- **Task 7** (Trminh) defined exactly how to describe what limited the result
- **Task 8** (Faith) defined exactly how to describe water quality and safety

Task 9 wires those three together into one script, and adds two more sections
(sensitivity, and the final summary) that none of the three covered. The sensitivity
section was added later, after Task 13's evaluation rubric (the document used to
judge whether an explanation is good) pointed out that nothing was covering it yet.

**Currency handling was tightened for the same reason.** Task 13's rubric says cost
figures must show their currency (AUD). The script now reads the currency from the
data file itself — never hardcoded — so every dollar amount in the explanation stays
consistent, and would automatically update if the currency ever changed.

**Field paths and binding-constraint matching were rebuilt against the confirmed
output contract** (`model_output_contract.json` / `model_output_specification.md`),
after review flagged that this script was still built against an earlier draft
schema. Every field this script reads was renamed to match the confirmed contract:

- `cost_per_ML` → `cost_per_ml`, `required_volume_ML` → `demand_ml_per_day`,
  `volume_drawn_ML` → `volume_drawn_ml_per_day`
- `treatment_facilities` → `plants`, `facility_id`/`facility_name` →
  `plant_id`/`plant_name`
- `water_quality.after_treatment` → `water_quality.by_plant.<plant_id>`, since the
  confirmed contract reports quality per plant, not once for the whole scenario
- `data_flags.estimated_fields[]` (a flat string list) → `data_flags.sources[]`
  (per-source `has_estimated_values` boolean plus a `provenance` breakdown) and
  `data_flags.notes[]`

Binding-constraint names also changed from suffix-based to prefix-based
(`yarra_kew_capacity` → `source_capacity_yarra_kew`, `facility_1_batch_capacity` →
`plant_capacity_facility_1`, `pH_range` → `quality_range_pH_facility_1`, now
carrying the plant id since quality is per-plant). Two categories were retired
outright rather than renamed:

- **Source-activation** no longer appears, because it's a logical constraint
  (`γ_st ≤ α_s`), and the confirmed contract explicitly excludes logical
  constraints from `binding_constraints_summary` — they can never actually show up
  here, so keeping a rendering branch for them was dead code.
- **Batch counting** ("500 ML across 5 batches") is gone, because the confirmed
  formulation has zero integer variables (`diagnostics.num_integer_variables` is
  always `0`) — there's nothing to count in batches anymore.

**One category was missing entirely, not just misnamed: `link_capacity`.**
Cross-checking against the confirmed output spec (Section 3.8) after the field-path
fix turned up a real gap — `link_capacity_<from>_to_<to>` is a genuine `inequality`
constraint that can legitimately appear in `binding_constraints_summary`, but had no
rendering branch at all, so it would have silently fallen into the generic "no
plain-language mapping available" wording. It's now handled: the id portion after
`link_capacity_` is the exact `path_id` used in `transfer_paths` (both
`source_to_plant` and `plant_to_zone` arrays), so it's a direct lookup, not string
parsing. Since the output contract doesn't echo a link's own maximum flow (that's
input-only), this reports the flow that was reached rather than claiming to know a
specific cap. Sample 10 in `sample_explanations.txt` demonstrates both link types.

**Estimated-value disclosure was also simplified, not just renamed.** The old
"(estimated)" tagging matched free text against a flat `estimated_fields[]` list,
which was flagged as an over-broad hack (a mention of "all sources" anywhere would
mark a source's capacity as estimated, even when the flagged entry was actually
about a different field). That's replaced with a direct read of each source's own
`data_flags.sources[].has_estimated_values` boolean — cleaner, and the ambiguity is
gone rather than just hidden. Per the confirmed contract's own "known gaps"
(Section 6), only source fields carry this provenance mechanism at all; demand,
plant capacity, and quality limits don't, so those categories never attempt to
guess at "(estimated)" anymore.

**Wording was updated per review too:** "treated-water quality" / "water quality
after treatment" / "safe to drink" all became "plant-inflow blend quality"
throughout, since `water_quality.by_plant` reports the blend arriving at a plant,
not final treated water — the confirmed formulation has no post-treatment removal
term, so there's nothing else to report.

---

## 4. Required vs. optional data

**Required** — the script refuses to run without these, with a clear error message:
`status`, `sources`, `water_quality.by_plant`, `binding_constraints_summary[]`.
Without these there's nothing coherent to explain.

**Optional** — missing values are handled gracefully, never crash the script:
`cost_per_ml` on any source, `data_flags.sources[].has_estimated_values`,
`demand_zones[]`, `plants`, `objective`, individual constraint details.

---

## 5. A worked example of why "never invent a fact" matters

Task 13's rubric includes a worked example of a fake explanation that reads
confidently and clearly, but gets the facts wrong — swapping which source was
selected, inventing a made-up reason ("better water quality"), and claiming data was
"fully verified" when parts of it were actually estimates. It reads convincingly. It's
also wrong in five different ways.

That's the exact failure mode this script is built to avoid. Every sentence it
produces traces back to an actual field in the JSON. If the data isn't there, it says
so instead of filling the gap with something that sounds plausible.

---

## 6. Known open items — things worth double-checking with the team

- **The selected-source "reason" text is derived, not a literal field in the data.**
  The JSON doesn't say *why* a source was picked — only the numbers (cost, capacity).
  The script infers the reason from those numbers using a fixed rule (cheapest source
  first, then capacity limits, etc.). This was flagged in Task 6's own review as worth
  confirming with the team, and it's now also directly tested by Task 13's rubric
  (criterion "no invented reasons") — it should pass, since it's built from real data,
  not made up, but it's worth a second look before merging.
- **A genuine zero-demand solver result has never been tested against real solver
  output** — only against a made-up version of the reference JSON with the sources
  deleted. Worth confirming with the Optimisation team whether that's even a real
  situation the solver can produce.
- **Every PR in this repo has needed a second reviewer before merge, without
  exception** — including ones with only minor feedback. Don't expect one approval to
  be enough.

**Resolved since the last review round:**

- Tasks 6, 7, and 8 are now merged, so this script's dependency on their wording is
  no longer a moving target.
- The old "all sources" estimated-disclosure ambiguity (any mention of "all sources"
  in a flat string list marking unrelated fields as estimated) is gone, not just
  narrowed — disclosure now reads a clean per-source `has_estimated_values` boolean
  from the confirmed output contract, so there's no longer a literal-reading judgment
  call to make.
