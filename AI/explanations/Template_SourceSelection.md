# Template: Source-Selection Explanation

**Task 6: Analysis & AI, Sprint 1**
---
**Owner:** Archit

## 1. Scope

This template converts the `sources.selected` and `sources.unused` arrays in the
reference Results JSON (AquaBlend MILP Configuration, Section 8) into
deterministic, operator-readable sentences explaining why each source was or
wasn't used.

Only fields that exist in the current JSON contract are used. Nothing is
invented.

## 2. A schema note before the templates (read this first)

The current output contract gives `unused` sources an explicit `reason`
string, but gives `selected` sources no equivalent field only structural
data (`volume_drawn_ML`, `percent_of_blend`, `cost_per_ML`, `cost_contribution`).

So for **unused** sources, "reason" means: use the JSON's `reason` field
verbatim.

For **selected** sources, there is no field literally called "reason." To
avoid inventing free text, this template derives the explanation from two
fields that *are* in the JSON: `cost_per_ML` (ranked across all sources) and
`binding_constraints_summary` (checked for `{source_id}_capacity`). The rule
is fully deterministic — see Section 4. **This is a design decision, not a
guess, and it's worth confirming with the wider team since it affects what
Task 9's generator needs to implement.**

## 3. Field reference used by this template

| Field | From | Used for |
| --- | --- | --- |
| `source_id` | selected / unused | matching against `binding_constraints_summary` |
| `source_name` | selected / unused | sentence subject |
| `percent_of_blend` | selected | headline share |
| `volume_drawn_ML` | selected | volume clause |
| `cost_per_ML` | selected / unused (if present) | cost clause, cost ranking |
| `reason` | unused only | unused-source sentence |
| `binding_constraints_summary` | top-level array | capacity-binding check |
| `status` | top-level | feasibility gate (see Section 6) |
| `data_flags.estimated_fields` | top-level | estimated-value flagging |

## 4. Selected-source reason logic (deterministic)

Compute once per solve, before generating sentences:

1. **Cost ranking.** Rank every source that appears in either `sources.selected`
   or `sources.unused` and has a numeric `cost_per_ML`, ascending. Rank 1 =
   cheapest. Sources with no `cost_per_ML` are excluded from ranking (see
   Section 7, missing values).
2. **Capacity-binding check.** For each selected source, check whether
   `"{source_id}_capacity"` appears in `binding_constraints_summary`.

Then apply, in this priority order:

| Condition | Reason clause |
| --- | --- |
| cheapest (rank 1) **and** capacity-binding | "it is the cheapest available source and was used at its full available capacity" |
| capacity-binding, not cheapest | "it was used at its full available capacity for this scenario" |
| cheapest, not capacity-binding | "it is the cheapest available source for this scenario, with capacity remaining" |
| neither | "it supplemented the blend, at the {ordinal} lowest cost, to meet remaining demand after lower-cost sources reached capacity" |
| no `cost_per_ML` available for this source or for ranking | fall back to the capacity-only check; if that's also unavailable, use the generic fallback in Section 7 |

## 5. Sentence templates

**Selected source:**
```
{source_name} supplied {percent_of_blend}% of the blend ({volume_drawn_ML} ML)
at ${cost_per_ML}/ML{estimated_tag}, because {reason_clause}.
```

**Unused source:**
```
{source_name} was not selected because {reason}.
```

`{estimated_tag}` is `" (estimated)"` if this source's `cost_per_ML` appears
in `data_flags.estimated_fields`, otherwise empty. See Section 8.

## 6. Feasibility gate (checked before any source sentence)

If `status` is not `"OPTIMAL"` (e.g. `"INFEASIBLE"`), source-selection
sentences are not generated. Emit instead:
```
No blend could be recommended for this scenario ({status}).
```
This takes precedence over everything below.

## 7. Handling zero, one, and multiple selected sources

- **Zero selected** (`sources.selected` is an empty array, status still
  `OPTIMAL` e.g. zero demand): emit `"No sources were required for this
  scenario."` Do not run the reason logic.
- **One selected:** single sentence, no ordering needed.
- **Multiple selected:** sentences ordered by `percent_of_blend` descending
  (largest contributor first: matches how an operator would want to read
  it), one sentence per source, no connecting prose needed between them.
- **Missing `cost_per_ML` on a selected source:** drop the cost clause
  entirely and use the generic fallback reason: `"it was included in the
  optimal blend to help meet demand at minimum total cost."` Do not guess a
  cost ranking without the number.
- **Missing `reason` on an unused source:** this should not happen per the
  current contract, but if it does, emit `"{source_name} was not selected
  (no reason provided in the solver output)."` rather than inventing one.

## 8. Estimated-value disclosure

Before generating sentences, check `data_flags.estimated_fields` for any
entry mentioning `cost_per_ML`. If a source's cost is estimated, append
`" (estimated)"` immediately after the dollar figure in that source's
sentence. This is required otherwise Task 13's rubric fails any explanation that
doesn't disclose estimated fields.

## 9. Rounding rules

- `percent_of_blend`: 1 decimal place (matches JSON, e.g. `42.0`)
- `volume_drawn_ML`: whole ML
- `cost_per_ML`: as given in the JSON (2 decimals where present)
- Ordinal words ("2nd lowest cost") spelled out, not "2nd" — use "second,"
  "third," etc.

## 10. Worked example (using the reference JSON's toy-model solve)

Input (relevant fields):
- Selected: Silvan Reservoir (42.0%, 210 ML, $400/ML), Yarra River Kew
  (58.0%, 290 ML, $235/ML)
- Unused: Groundwater Bore 1 reason: "Higher cost per ML than the selected
  sources with no quality benefit large enough to justify inclusion for this
  demand level"
- `binding_constraints_summary`: `["demand_satisfaction_zone_1",
  "yarra_kew_capacity"]`
- Cost ranking (all three sources): Yarra Kew ($235, rank 1), Silvan ($400,
  rank 2), Groundwater Bore 1 (estimated cost, higher than both, rank 3)
- `data_flags.estimated_fields` includes `cost_per_ML (all sources)`

Applying the rules:

- **Yarra Kew** - rank 1 (cheapest) **and** `yarra_kew_capacity` is in
  `binding_constraints_summary` → first rule applies.
- **Silvan** - rank 2, not capacity-binding → falls to the "neither" case →
  "second lowest cost."
- **Groundwater Bore 1** - unused, use `reason` verbatim.

Generated output (ordered by `percent_of_blend` descending):

```
Yarra River, Kew supplied 58.0% of the blend (290 ML) at $235.00/ML
(estimated), because it is the cheapest available source and was used at
its full available capacity.

Silvan Reservoir supplied 42.0% of the blend (210 ML) at $400.00/ML
(estimated), because it supplemented the blend, at the second lowest cost,
to meet remaining demand after lower-cost sources reached capacity.

Groundwater Bore 1 was not selected because higher cost per ML than the
selected sources with no quality benefit large enough to justify inclusion
for this demand level.
```

This is a close paraphrase of the JSON's own free-text `explanation` field
for this scenario, generated entirely from structured fields — confirming
the reason logic in Section 4 is sound.

## 11. Checklist (against Task 6 requirements)

- [x] Template exists for selected sources
- [x] Template exists for unused sources
- [x] Exact JSON field names used
- [x] `source_name` included
- [x] `percent_of_blend` included where available
- [x] Cost included only when supported by the JSON (dropped if missing)
- [x] Reasons taken from the JSON - verbatim for unused; deterministically
      derived from `cost_per_ML` and `binding_constraints_summary` for
      selected, since no per-source reason field exists for selected sources
- [x] Zero, one, and multiple selected sources handled
- [x] Missing optional values handled (cost, reason)
- [x] Estimated values identified via `data_flags.estimated_fields`
- [x] Tested against the reference JSON's real sample values (Section 10)
- [x] Sentences are plain-language, no jargon, readable by a non-technical
      operator

## 12. Open item for the team

Flag for Bao Minh Tran (Task 7) and Faith (Task 8): confirm whether your
templates also need a "derive from structural fields" fallback, or whether
your constraint/quality sections have explicit reason-equivalent fields
already. If binding-constraints and quality templates hit the same gap,
it's worth raising once with the group rather than three separate people
solving it slightly differently.