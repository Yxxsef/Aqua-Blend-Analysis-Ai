# Template — Binding Constraints Explanation

Briefly, binding constraints mean the contraints are used completely. For example, `{source}_capacity >= 1000L`, then it only shown when the solution exhausts the source water at exactly 1000L. In other words, the binding constraints can be smaller than the actual constraints, as this template only describes why the binding constraints exist, not how all the constraints are kept in the feasible region.

Therefore, these outputs are only generated if these constraints are included in `binding_constraints_summary` field in the json contract. In this template, the constraints are separated for readability, and can then be concatenated in the final output.

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

## Empty list — `binding_constraints_summary` is `[]`

It is possible to have a solution without any binding contraints. Said differently, all variables stay within the bounds given by the contraints.

```
No constraint was binding; the solution stayed within every limit.
```

## Unknown — name matches none of the above

This is used for binding constraints that are not defined in the json contract. In other words, this raise errors when the json contract does not align with the pre-defined contraints and variables.

```
The solution was limited by {binding_constraint} (no plain-language mapping available).
```
