# Template — Binding Constraints Explanation

Briefly, binding constraints mean the contraints are used completely. For example, `{source}_capacity >= 1000L`, then it only shown when the solution exhausts the source water at exactly 1000L. In other words, the binding constraints can be smaller than the actual constraints, as this template only describes why the binding constraints exist, not how all the constraints are kept in the feasible region.

Therefore, these outputs are only generated if these constraints are included in `binding_constraints_summary` field in the json contract. In this template, the constraints are separated for readability, and can then be concatenated in the final output — see Output composition below for the sentence shape, order and separator.

## Output composition — shape, order, separator

Each entry in `binding_constraints_summary` renders as one sentence:
```
The solution was limited by {binding_constraint}: {plain_language_explanation}.
```
This is the shape the Unknown fallback at the end of this file already uses, so every branch of the template produces the same sentence form.

**Order.** Group by category in the fixed order below, and within a category keep the order the names appear in `binding_constraints_summary`:

1. Demand
2. Source-capacity
3. Source-activation
4. Treatment-capacity
5. Water-quality


## Demand — name `demand_satisfaction_{zone}` (matches `demand_zones[].zone_id`)
```
{binding_constraint}         = the water demand for {demand_zones[].zone_id}
{plain_language_explanation} = the full {demand_zones[].required_volume_ML} ML needed by {demand_zones[].zone_id} had to be delivered, leaving no room to supply any less
```

## Source-capacity — name `{source}_capacity` (matches `sources.selected[].source_id`)
```
{binding_constraint}         = the available capacity of {sources.selected[].source_name}
{plain_language_explanation} = {sources.selected[].source_name} was drawn up to the most its capacity allows ({sources.selected[].volume_drawn_ML} ML), so any additional water had to come from other sources
```

## Source-activation — name `{source}_activation` (matches `sources.selected[]`/`sources.unused[]` `source_id`)
### Selected — `source_id` found in `sources.selected[]`
```
{binding_constraint}         = whether {sources.selected[].source_name} is switched on
{plain_language_explanation} = {sources.selected[].source_name} had to be switched fully on rather than partly used, and that is what allowed it into the blend
```

### Unused — `source_id` found in `sources.unused[]`
```
{binding_constraint}         = whether {sources.unused[].source_name} is switched on
{plain_language_explanation} = {sources.unused[].source_name} was left switched off entirely rather than partly used, so none of it could enter the blend
```

## Treatment-capacity — name `{facility}_batch_capacity` (matches `treatment_facilities.active[].facility_id`)
```
{binding_constraint}         = the processing capacity of {treatment_facilities.active[].facility_name}
{plain_language_explanation} = {treatment_facilities.active[].facility_name} was already treating as much as it can handle ({treatment_facilities.active[].volume_processed_ML} ML across {treatment_facilities.active[].treatment_batches} batches), leaving no spare capacity
```

## Water-quality — name `{parameter}_range` (matches `water_quality.after_treatment.{parameter}`)
```
{binding_constraint}         = the {parameter} limit
{plain_language_explanation} = {parameter} sat right at the edge of its safe range ({water_quality.after_treatment.{parameter}.constraint_min}–{water_quality.after_treatment.{parameter}.constraint_max} {water_quality.after_treatment.{parameter}.unit}), so the blend could not be pushed any further
```

## Rounding and units

- `required_volume_ML`, `volume_drawn_ML`, `volume_processed_ML`: whole ML
- `treatment_batches`: whole number, and match the noun to it — "1 batch", not "1 batches"
- `constraint_min` / `constraint_max`: exactly as given in the JSON, decimals preserved (`0` stays `0`, `5.0` stays `5.0`) — never normalise or add precision the solver did not report
- `unit`: printed verbatim from `water_quality.after_treatment.{parameter}.unit`, never translated or abbreviated
- Range separator: en dash, no spaces (`6.5–8.5`)

## Estimated-value disclosure


Before rendering, scan `data_flags.estimated_fields` and treat a section's figures as estimated when an entry mentions:

| Section | Entry in `data_flags.estimated_fields` mentions |
| --- | --- |
| Demand | `required_volume_ML`, or demand for that zone |
| Source-capacity | capacity, together with the source's name or id, or "all sources" |
| Treatment-capacity | treatment facility capacity, batches, or dosing rates |
| Water-quality | quality readings, or the parameter's name |

Source-activation quotes no figure, so it has nothing to disclose.

When flagged, append `, estimated` inside the existing parenthetical clause rather than opening a second set of brackets:
```
{plain_language_explanation} = {sources.selected[].source_name} was drawn up to the most its capacity allows ({sources.selected[].volume_drawn_ML} ML, estimated), so any additional water had to come from other sources
```

If the clause carrying the figure was dropped under the Missing-field rule, the tag goes with it — there is no figure left to qualify.

## Empty list — `binding_constraints_summary` is `[]`

It is possible to have a solution without any binding contraints. Said differently, all variables stay within the bounds given by the contraints.

```
No constraint was binding; the solution stayed within every limit.
```

## No matching entry — the name matches a section, but no entry has that id

For example, `facility_1_batch_capacity` is binding but `treatment_facilities.active[]` has no `facility_1`. Emit the Unknown wording and raise:
```
The solution was limited by {binding_constraint} (no plain-language mapping available).
```

Finding the id in the sibling array (`sources.unused[]`, `treatment_facilities.inactive[]`) still counts as no match: an unused source or inactive facility cannot be binding, so that is a contradiction in the solver output. Do not read the figures from it. Source-activation is the exception — it reads both `selected[]` and `unused[]`, so only absence from both counts.

If the entry is found and only a field such as `volume_processed_ML` is absent, that is the Missing-field case below.

## Missing field — name matches, but a field it needs is absent

Every field interpolated above is required by the json contract, so an entry whose source, facility or parameter is missing one of them is the same kind of misalignment as the Unknown case below — it is just detectable at the field level rather than the name level. Raise it the same way, but still produce the best sentence the available data supports rather than dropping the constraint from the output.

Whether a field can be dropped depends on what it carries.

**Identity fields** (`source_name`, `facility_name`, `zone_id`, `parameter`) name the thing being explained, so the sentence does not survive without them. Fall back to the matching `source_id` / `facility_id`. If that is missing too, nothing is left to identify and the Unknown wording applies.

**Detail fields** (all volumes, batch counts, limits and units) only qualify the sentence. Drop the clause carrying them and keep the rest. If one clause holds several and only some are missing, drop the whole clause rather than rendering a half-filled one.

For example, source-capacity with `volume_drawn_ML` absent:
```
{binding_constraint}         = the available capacity of {sources.selected[].source_name}
{plain_language_explanation} = {sources.selected[].source_name} was drawn up to the most its capacity allows, so any additional water had to come from other sources
```

The same rule elsewhere: demand becomes `the full volume needed by {demand_zones[].zone_id} had to be delivered, leaving no room to supply any less`; treatment-capacity becomes `{treatment_facilities.active[].facility_name} was already treating as much as it can handle, leaving no spare capacity`; water-quality becomes `{parameter} sat right at the edge of its safe range, so the blend could not be pushed any further`.

## Unknown — name matches none of the above

This is used for binding constraints that are not defined in the json contract. In other words, this raise errors when the json contract does not align with the pre-defined contraints and variables.

This covers the constraint *name* only. A name that does match a section above but is missing a field that section needs is the Missing-field case, and a name that matches a section but resolves to no entry is the No-matching-entry case — neither is this one.

```
The solution was limited by {binding_constraint} (no plain-language mapping available).
```
