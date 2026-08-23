# AquaBlend Deterministic Report Structure

## 1. Purpose

This document defines what the deterministic report will look like.

The report is created from the working Results JSON before any LLM is used.

## 2. Report order

1. Scenario and solver status
2. Result availability warning
3. Demand-zone results
4. Selected sources and blend ratios
5. Unused sources
6. Active plants and transfer results
7. Cost summary
8. Plant-inflow water-quality results
9. Binding constraints
10. Data flags and estimated values
11. Optional alternatives and sensitivity
12. Prototype disclaimer

## 3. Section rules

### Scenario and solver status

JSON paths used:

- `scenario_id`
- `solved_at`
- `status`

When the section appears:

- Always.

Allowed wording:

- State the scenario identifier.
- State the solver status.
- Include the solve completion timestamp only when present.

Forbidden wording:

- Do not imply the result is valid unless the status allows it.
- Do not invent a solve time.

Missing field behavior:

- If `status` or `scenario_id` is missing, stop normal report generation.
- Return a validation-error report.
- Do not continue with solution or recommendation sections.
- If `solved_at` is missing, omit it.

### Result availability warning

JSON paths used:

- `status`

When the section appears:

- Always.

Allowed wording:

- For `OPTIMAL`, state that the solver produced a confirmed optimal solution under the current model and input assumptions.
- For non-optimal statuses, state that the result is not confirmed as usable for a final recommendation.
- Until feasible `TIME_LIMIT` handling is confirmed, only `OPTIMAL` permits full result reporting.

Forbidden wording:

- Do not present a non-optimal run as a final recommendation.
- Do not hide solver limitations.

Missing field behavior:

- If `status` is missing, use a neutral warning that the result state is unknown.

### Demand-zone results

JSON paths used:

- `demand_zones[].zone_id`
- `demand_zones[].zone_name`
- `demand_zones[].demand_ml_per_day`
- `demand_zones[].volume_supplied_ml_per_day`

When the section appears:

- When at least one demand zone exists.

Allowed wording:

- Report each demand zone separately.
- State the required demand and supplied volume exactly.
- Use the zone name when present.

Forbidden wording:

- Do not call demand an exact target.
- Do not invent a demand-zone name.

Missing field behavior:

- If `zone_name` is missing, use the zone identifier.
- If the array is empty, state that no demand-zone result was provided.

### Selected sources and blend ratios

JSON paths used:

- `sources.selected[].source_id`
- `sources.selected[].source_name`
- `sources.selected[].source_type`
- `sources.selected[].volume_drawn_ml_per_day`
- `sources.selected[].percent_of_blend`
- `sources.selected[].cost_per_ml`
- `sources.selected[].draw_cost`

When the section appears:

- When selected sources exist.

Allowed wording:

- Every selected source must appear.
- Values must be copied exactly.
- Blend ratio wording may state the percent of blend.
- Cost fields may be shown when present.

Forbidden wording:

- The report must not invent why a source was selected.
- The report must not change the source name, volume, or percentage.
- The report must not recalculate costs.

Missing field behavior:

- If `source_name` is missing, use the source identifier.
- If the array is empty, state that no selected-source result was provided.

### Unused sources

JSON paths used:

- `sources.unused[].source_id`
- `sources.unused[].source_name`
- `sources.unused[].source_type`
- `sources.unused[].reason`

When the section appears:

- When unused sources exist.

Allowed wording:

- Report each unused source.
- Report that the source was not selected.
- Do not include `sources.unused[].reason` until its producer and verification method are confirmed.

Forbidden wording:

- Do not invent a reason.
- Do not imply the ownership of `reason` is settled.

Missing field behavior:

- If `reason` is missing, no extra wording is required.
- If the array is empty, state that no unused-source result was provided.

### Active plants and transfer results

JSON paths used:

- `plants.active[].plant_id`
- `plants.active[].plant_name`
- `plants.active[].volume_processed_ml_per_day`
- `plants.active[].treatment_cost_per_ml`
- `plants.active[].treatment_cost`
- `plants.inactive[]`
- `transfer_paths.source_to_plant[]`
- `transfer_paths.plant_to_zone[]`

When the section appears:

- When active plants or transfer paths exist.

Allowed wording:

- Report active plants.
- Report transfer results when included.
- Use exact identifiers and values.

Forbidden wording:

- Do not invent a transfer result.
- Do not imply inactive plants contributed flow.

Missing field behavior:

- If active plants are missing, state that no active-plant result was provided.
- If transfer paths are missing, omit the transfer detail subpart.

### Cost summary

JSON paths used:

- `objective.total_cost`
- `objective.currency`
- `objective.unit`
- `objective.cost_breakdown.source_activation_cost`
- `objective.cost_breakdown.plant_activation_cost`
- `objective.cost_breakdown.source_draw_cost`
- `objective.cost_breakdown.plant_treatment_cost`

When the section appears:

- Only when a usable solution status allows cost reporting.

Allowed wording:

- Preserve currency.
- Preserve the time basis.
- Show the cost breakdown if present.

Forbidden wording:

- Do not show cost values for invalid or missing solution blocks.
- Do not change units or currency.

Missing field behavior:

- If objective fields are missing, state that the cost summary is unavailable.

### Plant-inflow water-quality results

JSON paths used:

- `water_quality.applies_to`
- `water_quality.by_plant.<plant_id>.<parameter>.value`
- `water_quality.by_plant.<plant_id>.<parameter>.unit`
- `water_quality.by_plant.<plant_id>.<parameter>.constraint_min`
- `water_quality.by_plant.<plant_id>.<parameter>.constraint_max`
- `water_quality.by_plant.<plant_id>.<parameter>.status`
- `water_quality.by_plant.<plant_id>.<parameter>.safety_margin_percent`

When the section appears:

- When water-quality results exist.

Allowed wording:

- State that the values apply to plant inflow.
- Report each parameter value, unit, model constraint range, status, and model constraint margin when present.

The reported quality values describe the blended water entering the treatment plant. They were checked against the modelled plant-inflow constraints and are not final post-treatment drinking-water results.

Forbidden wording:

- Do not call the quality values final treated-water quality.
- Do not remove the stage warning.
- Do not change PASS or FAIL.
- Do not describe the values as safe, compliant, treated, or final.

Missing field behavior:

- If `water_quality` exists but `water_quality.applies_to` is missing, treat the quality section as invalid.
- Include a validation warning instead of a normal quality interpretation.
- If the block is empty, state that no water-quality result was provided.

### Binding constraints

JSON paths used:

- `binding_constraints_summary[]`
- `constraints[]`

When the section appears:

- When binding constraints or constraints are present.

Allowed wording:

- Report the binding constraints using exact names.
- Use technical constraint details only as provided.

Forbidden wording:

- Do not invent the practical meaning of an unknown name.
- Do not promote a non-binding constraint into a binding one.

Missing field behavior:

- If the array exists and is empty, state that no binding inequality or ranged constraints were reported.
- If the field is missing from an `OPTIMAL` result, add a validation warning.

### Data flags and estimated values

JSON paths used:

- `data_flags.sources[].source_id`
- `data_flags.sources[].has_estimated_values`
- `data_flags.sources[].availability_origin`
- `data_flags.sources[].provenance`
- `data_flags.notes[]`

When the section appears:

- When data flags or notes exist.

Allowed wording:

- Disclose estimated values.
- Disclose scenario overrides.
- Include important notes.

Forbidden wording:

- Do not hide limitations to improve readability.

Missing field behavior:

- If `data_flags` exists but contains no flags or notes, omit this section.
- If `data_flags` is missing, add a validation warning because estimate and provenance disclosures cannot be checked.

### Optional alternatives and sensitivity

JSON paths used:

- `alternative_feasible_solutions[]`
- `sensitivity_to_key_assumptions[]`

When the section appears:

- Only when these arrays exist and are non-empty.

Allowed wording:

- Summarise verified alternatives and sensitivity findings.

Forbidden wording:

- Do not generate alternatives or sensitivity findings during basic report creation.

Missing field behavior:

- If either array is missing or empty, omit that subsection.

### Prototype disclaimer

JSON paths used:

- None required.

When the section appears:

- Always.

Allowed wording:

- State that AquaBlend is a public-data decision-support proof-of-concept.
- State that the report does not replace qualified operators, engineers, regulators, or health authorities.

Forbidden wording:

- Do not imply operational certification.

Missing field behavior:

- No JSON fields are required.

## 4. LLM rewrite boundary

The LLM receives the completed deterministic report.

The LLM may only rewrite wording.

The LLM must not add numbers, reasons, calculations, decisions, safety claims, or new recommendations.

## 5. Relationship to existing templates

The following existing files support sections of this report:

- `Template_SourceSelection.md`
- `Template_BindingConstraints.md`
- `Template_QualityMargins.md`

These remain separate source templates for now.

The quality template must be aligned with the current plant-inflow quality stage before implementation.
