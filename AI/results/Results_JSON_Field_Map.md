# Results JSON Field Map

## Overview

This document maps the confirmed external MILP Results JSON contract to the internal AquaBlend representation.

The external field names must remain unchanged for inter-team integration. Internal naming changes are handled only inside `results_adapter.py`.

The MILP Results JSON remains the factual source of truth. The validator, adapter, and confidence flagger must not modify optimisation decisions, recalculate MILP results, or introduce unsupported values.

---

## Required Top-Level Fields

| External Results JSON Field | Internal Adapter Field | Required | Description |
|---|---|---:|---|
| `scenario_id` | `scenarioId` | Yes | Unique scenario identifier |
| `status` | `status` | Yes | MILP optimisation result status |
| `objective` | `objective` | Yes | Optimisation objective and cost |
| `demand_zones` | `demandZones` | Yes | Demand and supplied volume for each zone |
| `sources` | `sources` | Yes | Selected and unused water sources |
| `transfer_paths` | `transferPaths` | Yes | Source-to-plant and plant-to-zone transfer flows |
| `plants` | `plants` | Yes | Active and inactive treatment plants |
| `water_quality` | `waterQuality` | Yes | Water quality measurements and constraints |
| `constraints` | `constraints` | Yes | MILP constraint evaluation results |
| `diagnostics` | `diagnostics` | Yes | Solver and optimisation diagnostics |
| `data_flags` | `dataFlags` | Yes | Source data provenance and estimation flags |

---

## Optional Top-Level Fields

| External Results JSON Field | Internal Adapter Field | Required | Description |
|---|---|---:|---|
| `solved_at` | `solvedAt` | No | Timestamp when the optimisation was solved |
| `binding_constraints_summary` | `bindingConstraintsSummary` | No | Summary of binding constraints |
| `alternative_feasible_solutions` | `alternativeFeasibleSolutions` | No | Alternative feasible solutions |
| `sensitivity_to_key_assumptions` | `sensitivityToKeyAssumptions` | No | Sensitivity information |
| `explanation` | `explanation` | No | Explanation of the optimisation result |

Missing optional fields must not cause validation failure.

When optional fields are present, the adapter passes them safely into the internal representation without modifying their values.

The adapter must not invent values for missing optional fields.

---

## Valid Status Values

The validator must accept the status values defined by the confirmed `model_output_contract.json`.

In particular:

- `OPTIMAL` is a valid successful optimisation status.
- `OPTIMAL` must be included in `VALID_STATUS`.

The validator must not introduce status values that are not defined by the confirmed external contract.

For example, `FEASIBLE` must not be used if it is not present in the confirmed contract.

---

## Objective

The `objective` field contains the optimisation cost information.

Example:

```json
{
  "total_cost": 184150.00,
  "currency": "AUD",
  "unit": "cost for one representative day",
  "cost_breakdown": {
    "source_activation_cost": 0.00,
    "plant_activation_cost": 0.00,
    "source_draw_cost": 152150.00,
    "plant_treatment_cost": 32000.00
  }
}
```json
The adapter preserves these values and does not recalculate or modify the MILP objective.

Demand Zones

The external demand_zones field is a list.

Each demand-zone entry can contain:

zone_id
zone_name
demand_ml_per_day
volume_supplied_ml_per_day

The validator must ensure that:

demand_zones is a list.
Every demand-zone entry is an object.

The adapter preserves the complete demand-zone structure.

Sources

The external sources field is an object containing two arrays:

{
  "selected": [],
  "unused": []
}

The validator must not treat sources as a flat list.

Both:

sources.selected
sources.unused

must be lists.

Selected Sources

selected contains sources used in the optimisation solution.

Typical fields include:

source_id
source_name
source_type
volume_drawn_ml_per_day
percent_of_blend
cost_per_ml
draw_cost

Every selected source must contain a valid non-empty source_id.

Unused Sources

unused contains available sources that were not selected.

Typical fields include:

source_id
source_name
source_type
reason

Every unused source must contain a valid non-empty source_id.

The confidence flagger does not use sources.selected or sources.unused as its provenance source.

Transfer Paths

The external transfer_paths field is an object containing:

source_to_plant
plant_to_zone

Example:

{
  "source_to_plant": [],
  "plant_to_zone": []
}

These represent the movement of water through the optimisation network.

The validator must ensure that transfer_paths is an object.

The adapter preserves the complete transfer-path structure and does not modify flow values.

Plants

The external plants field is an object containing:

active
inactive

Example:

{
  "active": [],
  "inactive": []
}

Active plants contain treatment and processing information.

Inactive plants identify facilities that are not used by the solution.

The adapter preserves the complete plant structure.

Water Quality

The external water_quality field contains water quality information by plant.

The confirmed contract includes:

pH
alkalinity
turbidity

Each quality measure can contain:

value
unit
constraint_min
constraint_max
status
safety_margin_percent

Example:

{
  "pH": {
    "value": 7.11,
    "unit": "pH",
    "constraint_min": 6.5,
    "constraint_max": 8.5,
    "status": "PASS",
    "safety_margin_percent": 30.5
  }
}

The validator must ensure that water_quality is an object.

The adapter does not calculate or modify quality values.

Constraints

The external constraints field is a list of constraint objects.

Example:

{
  "name": "demand_satisfaction_zone_1",
  "type": "inequality",
  "status": "PASS",
  "slack": 0.0,
  "binding": true
}

constraints must be a list, not a dictionary.

Each constraint entry must be an object.

The validator must reject invalid constraint structures.

The adapter preserves the complete constraint list without changing constraint results.

Diagnostics

The external diagnostics field contains solver and optimisation information.

Typical fields include:

solver
solve_time_seconds
optimality_gap
num_continuous_variables
num_binary_variables
num_integer_variables
num_constraints

Example:

{
  "solver": "HiGHS",
  "solve_time_seconds": 0.084,
  "optimality_gap": 0.0
}

The validator must ensure that diagnostics is an object.

Diagnostics are informational and must not change the optimisation result.

Data Flags and Provenance
Data Flags

The external data_flags field contains source-data provenance and estimation information.

The confidence flagger reads provenance from:

data_flags.sources[]

It must not read provenance from:

sources.selected[]

or:

sources.unused[]

This distinction is required by the confirmed MILP contract.

Each data-flag source contains:

source_id
has_estimated_values
availability_origin
provenance

Example:

{
  "source_id": "silvan_reservoir",
  "has_estimated_values": true,
  "availability_origin": "database",
  "provenance": {
    "storage_capacity": "estimate",
    "reference_flow": "estimate",
    "max_available": "estimate",
    "cost": "estimate",
    "alkalinity": "estimate"
  }
}

The validator must ensure that:

data_flags is an object.
data_flags.sources is a list.
Each entry in data_flags.sources is an object.
Each entry contains a valid source_id.
has_estimated_values, when present, is a boolean.
provenance, when present, is an object.
Provenance Fields

The confirmed contract contains five provenance fields:

Provenance Field	Description
storage_capacity	Provenance of the source storage capacity
reference_flow	Provenance of the source reference flow
max_available	Provenance of the maximum available source volume
cost	Provenance of the source cost
alkalinity	Provenance of the alkalinity value

All five provenance fields must be present before a source can be considered fully confirmed for MEASURED confidence.

Missing or incomplete provenance must not be interpreted as estimated data.

Confidence Flags

The confidence flagger returns exactly one of:

PROVISIONAL
MEASURED
UNKNOWN

Confidence is determined from:

data_flags.sources[]

It must not use source allocation objects under:

sources.selected[]
sources.unused[]
PROVISIONAL

Return PROVISIONAL when at least one source has:

"has_estimated_values": true

The value must be the actual boolean true.

The affected source ID must be included in estimated_sources.

Example:

{
  "confidence": "PROVISIONAL",
  "estimated_sources": [
    "groundwater_bore_1"
  ]
}

Sources with missing or invalid provenance must not automatically be added to estimated_sources.

MEASURED

Return MEASURED only when all source records can be confirmed as measured.

Each source must:

have a valid non-empty source_id;
have has_estimated_values set to boolean false;
contain a valid provenance object;
contain all five provenance fields:
storage_capacity
reference_flow
max_available
cost
alkalinity

A missing provenance field prevents the source from being confirmed as MEASURED.

UNKNOWN

Return UNKNOWN when provenance cannot confirm that the data is measured and no valid estimated source has triggered PROVISIONAL.

UNKNOWN includes:

missing provenance;
incomplete provenance;
empty source list;
missing source_id;
has_estimated_values is null;
has_estimated_values is not a boolean;
invalid provenance structure.

Missing data must not automatically be treated as estimated data.

The confidence flagger must not generate artificial source IDs such as:

source_0
source_1

A missing source_id must instead result in an UNKNOWN confidence condition or invalid-input handling, according to the implementation.

Boolean Validation

The has_estimated_values field must be validated as a real boolean.

Valid values are:

true

or:

false

Invalid examples include:

null
"true"
"false"
1
0

A non-boolean value must not be treated as confirmed measured provenance.

Empty Provenance Handling

An empty or missing provenance object must not result in MEASURED.

If there is no provenance available to confirm the source data, the confidence result must be UNKNOWN, unless another valid estimated source has already triggered PROVISIONAL.

An empty data_flags.sources list must not fall through to MEASURED.

Mixed Provenance

If one source contains valid estimated data and another source has missing or incomplete provenance, the overall result is:

PROVISIONAL

The estimated source ID is included in estimated_sources.

The source with missing or incomplete provenance is not incorrectly labelled as estimated.

Example:

Source A:
has_estimated_values = true
→ Estimated

Source B:
provenance missing
→ Unknown provenance

Overall result:
PROVISIONAL

estimated_sources:
[Source A]

The presence of an unknown-provenance source does not cause that source to be added to estimated_sources.

Confidence Output

The confidence flagger returns:

{
  "confidence": "PROVISIONAL",
  "estimated_sources": [
    "source_id"
  ]
}

estimated_sources contains only actual source IDs for sources where estimated values were detected.

Generated IDs such as source_0 or source_1 are not permitted.

Adapter Behaviour

The adapter:

preserves the external MILP contract;
keeps inter-team field names unchanged;
handles internal naming differences only inside results_adapter.py;
does not modify optimisation results;
does not recalculate objective values;
does not make optimisation decisions;
safely passes optional alternatives;
safely passes sensitivity information;
safely passes explanations;
preserves source structures;
preserves plant structures;
preserves transfer-path structures;
preserves water-quality structures;
preserves constraint structures;
preserves diagnostics;
preserves data flags.

The MILP Results JSON remains the factual source of truth.

Internal Adapter Mapping

The adapter may use internal camelCase names while preserving the external contract.

External Field	Internal Field
scenario_id	scenarioId
demand_zones	demandZones
transfer_paths	transferPaths
water_quality	waterQuality
data_flags	dataFlags
solved_at	solvedAt
binding_constraints_summary	bindingConstraintsSummary
alternative_feasible_solutions	alternativeFeasibleSolutions
sensitivity_to_key_assumptions	sensitivityToKeyAssumptions

Fields that do not require internal renaming remain unchanged.

The adapter must not rename fields in the external Results JSON itself.

Validation Rules

The validator must check these required fields:

scenario_id
status
objective
demand_zones
sources
transfer_paths
plants
water_quality
constraints
diagnostics
data_flags

The validator must also check:

scenario_id is a non-empty string;
status is a valid contract status;
objective is an object;
demand_zones is a list;
each demand-zone entry is an object;
sources is an object;
sources.selected is a list;
sources.unused is a list;
each selected source is an object;
each unused source is an object;
source entries contain a valid non-empty source_id;
transfer_paths is an object;
plants is an object;
water_quality is an object;
constraints is a list;
each constraint entry is an object;
diagnostics is an object;
data_flags is an object;
data_flags.sources is a list;
each data-flag source is an object;
data-flag source entries contain a valid non-empty source_id;
has_estimated_values, when present, is a boolean;
provenance, when present, is an object.

Missing required fields must produce clear validation errors.

Optional Results Handling

The following fields are optional:

solved_at
binding_constraints_summary
alternative_feasible_solutions
sensitivity_to_key_assumptions
explanation

Missing optional fields must not cause validation failure.

When present, the adapter must pass these fields safely into the internal representation.

The adapter must not invent values for missing optional fields.

Results JSON Source of Truth

The MILP Results JSON is the factual source of truth.

Validator

The validator:

validates the structure;
validates required fields;
validates basic data types;
does not change values;
does not recalculate optimisation results.
Adapter

The adapter:

creates the stable internal representation;
does not modify MILP results;
does not recalculate values;
does not make optimisation decisions.
Confidence Flagger

The confidence flagger:

evaluates source-data provenance;
validates has_estimated_values;
evaluates the five provenance fields;
identifies estimated sources;
reports PROVISIONAL, MEASURED, or UNKNOWN;
does not modify optimisation results.
Task 21 Integration Flow

The Results JSON processing flow is:

Receive Results JSON from the MILP optimiser.
Validate the confirmed external Results JSON contract.
Validate required fields and basic data structures.
Validate the sources object and its selected and unused arrays.
Validate the constraints list.
Read source provenance from data_flags.sources.
Validate source_id.
Validate has_estimated_values as a boolean.
Validate the provenance structure.
Check all five provenance fields.
Determine the confidence flag.
Identify affected estimated source IDs.
Adapt the validated Results JSON for internal application use.
Safely pass optional alternatives, sensitivity information, and explanations.
Preserve the original MILP Results JSON as the factual source of truth.
Never allow the validator, adapter, or confidence flagger to change MILP optimisation decisions.
Task 21 Confidence Summary
Condition	Result
At least one source has has_estimated_values = true	PROVISIONAL
All sources have has_estimated_values = false and all five provenance fields are present	MEASURED
Provenance is missing or incomplete and no estimated source exists	UNKNOWN
has_estimated_values is not boolean	UNKNOWN
source_id is missing	UNKNOWN or invalid input
Source list is empty	UNKNOWN
Estimated source + unknown-provenance source	PROVISIONAL
Missing provenance	Never automatically treated as estimated
Generated source IDs	Not permitted
Contract Alignment

This field map is aligned with the confirmed model_output_contract.json.

In particular, it reflects the following contract requirements:

OPTIMAL is a valid status.
constraints is a list.
sources is an object containing selected and unused arrays.
Required fields use the confirmed names:
scenario_id
objective
demand_zones
sources
transfer_paths
plants
water_quality
constraints
diagnostics
data_flags
Source provenance is read from data_flags.sources.
has_estimated_values must be a boolean.
All five provenance fields are required for MEASURED.
Missing provenance is UNKNOWN, not automatically estimated.
Actual source IDs are used in estimated_sources.
Generated IDs such as source_0 are not permitted.
Mixed estimated and unknown provenance results in PROVISIONAL.
Optional alternatives, sensitivity, and explanation fields are handled safely.

This field map is intended to remain synchronized with the confirmed model_output_contract.json. Any future contract changes must be reflected here and in the validator, adapter, confidence flagger, and associated tests.
