# AquaBlend Results JSON Field Map

**Status:** Working draft  
**Purpose:** Map the current Results JSON fields to deterministic report use and LLM evaluation.

The current JSON is treated as a working draft contract. Exact field names are preserved from the current specification.

## Core rules

- The MILP is the only decision-maker.
- The deterministic template copies facts and numbers first.
- The LLM may only rewrite wording.
- Missing optional fields must not break report generation.
- `water_quality` applies to the blend at plant inflow.
- It is not final post-treatment drinking-water quality.
- `explanation` is an output field, not a factual input source.

## Field map

| Exact JSON path | Meaning | Required? | Report use | Main risk |
|---|---|---:|---|---|
| `scenario_id` | Scenario identifier | Yes | Report heading and traceability | Low |
| `solved_at` | Time the solve finished | Optional | Technical summary | Low |
| `status` | Solver result status | Yes | Controls which report sections are allowed | Critical |
| `objective.total_cost` | Total modelled cost | Only for valid solution | Main cost summary | Critical |
| `objective.currency` | Currency code | With cost | Cost wording | High |
| `objective.unit` | Cost time basis | With cost | Prevents misleading cost wording | High |
| `objective.cost_breakdown.source_activation_cost` | Source activation cost term | With objective | Detailed cost section | Medium |
| `objective.cost_breakdown.plant_activation_cost` | Plant activation cost term | With objective | Detailed cost section | Medium |
| `objective.cost_breakdown.source_draw_cost` | Total source draw cost | With objective | Detailed cost section | High |
| `objective.cost_breakdown.plant_treatment_cost` | Total plant treatment cost | With objective | Detailed cost section | High |
| `demand_zones[].zone_id` | Demand-zone identifier | Yes per zone | Zone reporting and validation | Medium |
| `demand_zones[].zone_name` | Demand-zone name | Optional | Human-readable report wording | Low |
| `demand_zones[].demand_ml_per_day` | Minimum required demand | Yes per zone | Demand summary | High |
| `demand_zones[].volume_supplied_ml_per_day` | Supplied volume | Yes per zone | Demand summary and validation | Critical |
| `sources.selected[]` | Sources activated by MILP | Yes for valid solution | Selected-source section | Critical |
| `sources.selected[].source_id` | Selected-source identifier | Yes | Validation | High |
| `sources.selected[].source_name` | Selected-source name | Optional | Report wording | Critical |
| `sources.selected[].source_type` | Source category | Optional | Additional context | Low |
| `sources.selected[].volume_drawn_ml_per_day` | Volume drawn | Yes | Source summary | Critical |
| `sources.selected[].percent_of_blend` | Blend share | Yes | Blend summary | Critical |
| `sources.selected[].cost_per_ml` | Source cost per ML | Optional | Cost detail | Critical |
| `sources.selected[].draw_cost` | Total draw cost | Optional | Cost detail and validation | Critical |
| `sources.unused[]` | Sources not activated | Optional | Unused-source section | Critical |
| `sources.unused[].source_id` | Unused-source identifier | Yes when item exists | Validation | High |
| `sources.unused[].source_name` | Unused-source name | Yes when item exists | Report wording | Critical |
| `sources.unused[].source_type` | Source category | Optional | Additional context | Low |
| `sources.unused[].reason` | Written non-selection reason | Optional | Copy only when present, verified, and ownership is confirmed | Critical |
| `transfer_paths.source_to_plant[]` | Source-to-plant path results | Optional for main report | Technical validation | High |
| `transfer_paths.plant_to_zone[]` | Plant-to-zone path results | Optional for main report | Technical validation | High |
| `plants.active[]` | Active treatment plants | Yes when present | Plant summary | High |
| `plants.active[].plant_id` | Plant identifier | Yes | Validation | High |
| `plants.active[].plant_name` | Plant name | Yes | Report wording | Medium |
| `plants.active[].volume_processed_ml_per_day` | Plant inflow volume | Yes | Plant summary and validation | Critical |
| `plants.active[].treatment_cost_per_ml` | Treatment cost per ML | Optional | Cost detail | Critical |
| `plants.active[].treatment_cost` | Total treatment cost | Optional | Cost detail and validation | Critical |
| `plants.inactive[]` | Inactive treatment plants | Optional | Technical detail | Low |
| `water_quality.applies_to` | Quality stage | Yes with quality block | Mandatory plant-inflow warning | Critical |
| `water_quality.by_plant.<plant_id>.<parameter>.value` | Quality value | Yes when parameter exists | Quality section | Critical |
| `water_quality.by_plant.<plant_id>.<parameter>.unit` | Quality unit | Yes when parameter exists | Quality wording | Critical |
| `water_quality.by_plant.<plant_id>.<parameter>.constraint_min` | Lower model limit | Optional | Quality range | High |
| `water_quality.by_plant.<plant_id>.<parameter>.constraint_max` | Upper model limit | Optional | Quality range | High |
| `water_quality.by_plant.<plant_id>.<parameter>.status` | PASS or FAIL | Yes when parameter exists | Quality status | Critical |
| `water_quality.by_plant.<plant_id>.<parameter>.safety_margin_percent` | Margin from nearest limit | Optional | Quality-margin section | Critical |
| `constraints[]` | Detailed model constraints | Optional for main report | Validation and technical reporting | High |
| `constraints[].name` | Technical constraint name | Yes when item exists | Exact constraint reference | High |
| `constraints[].type` | Constraint category | Yes when item exists | Interprets slack and binding | High |
| `constraints[].status` | Constraint status | Yes when item exists | Technical reporting | High |
| `constraints[].slack` | Distance from binding point | Yes when item exists | Constraint analysis | High |
| `constraints[].binding` | Whether the constraint limits the solution | Yes when item exists | Binding validation | High |
| `binding_constraints_summary[]` | Main limiting constraints | Optional | Binding-constraint section | Critical |
| `alternative_feasible_solutions[]` | Verified alternative solutions | Optional | Analysis section | High |
| `sensitivity_to_key_assumptions[]` | Verified sensitivity findings | Optional | Analysis section | High |
| `explanation` | Final readable explanation | Optional output | Written back after validation | Critical |
| `diagnostics.solver` | Solver name | Optional | Technical appendix | Low |
| `diagnostics.solve_time_seconds` | Solve time | Optional | Technical appendix | Medium |
| `diagnostics.optimality_gap` | Final optimality gap | Optional | Solver-quality check | High |
| `diagnostics.num_continuous_variables` | Continuous-variable count | Optional | Technical appendix | Low |
| `diagnostics.num_binary_variables` | Binary-variable count | Optional | Technical appendix | Low |
| `diagnostics.num_integer_variables` | Integer-variable count | Optional | Technical appendix | Low |
| `diagnostics.num_constraints` | Constraint count | Optional | Consistency check | Medium |
| `data_flags.sources[].source_id` | Source linked to data flags | Yes when item exists | Warning mapping | High |
| `data_flags.sources[].has_estimated_values` | Whether source inputs are estimated | Yes when item exists | Mandatory estimate disclosure | Critical |
| `data_flags.sources[].availability_origin` | Database or scenario override | Yes when item exists | Provenance warning | High |
| `data_flags.sources[].provenance` | Per-field provenance | Optional | Detailed limitations | High |
| `data_flags.notes[]` | General limitations and warnings | Optional | Limitations section | High |

## Special handling rules

### Non-optimal runs

- `OPTIMAL`: full report may be generated.
- `INFEASIBLE`: do not report a recommended blend.
- `UNBOUNDED`: do not report a recommended blend.
- `TIME_LIMIT`: do not assume the result is usable until feasible-solution handling is confirmed.
- `ERROR`: do not report solution values.

### Optional Analysis & AI fields

The report must still work when these are missing or empty:

- `alternative_feasible_solutions`
- `sensitivity_to_key_assumptions`
- `explanation`

### Unused-source reasons

`sources.unused[].reason` may only be copied when it exists. The reporting layer must not invent it.

### Water-quality wording

Every report using `water_quality` must state that the values apply to `blend_at_plant_inflow` and are not final post-treatment drinking-water results.
