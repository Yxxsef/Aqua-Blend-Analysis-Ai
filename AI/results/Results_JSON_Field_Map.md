# AquaBlend - Task 21 Results JSON Field Map

## Overview

This document defines the confirmed external MILP Results JSON contract and maps it to the internal AquaBlend representation.

The external field names must remain unchanged for inter-team integration. Internal naming changes are handled only inside `results_adapter.py`.

The **MILP Results JSON remains the factual source of truth**.

The validator, adapter, and confidence flagger must not:

- Modify optimisation decisions.
- Recalculate MILP results.
- Introduce unsupported values.
- Invent missing values.
- Change the original Results JSON.

---

## 1. Required Top-Level Fields

| External Results JSON Field | Internal Adapter Field | Required | Description |
|---|---|:---:|---|
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

## 2. Optional Top-Level Fields

| External Results JSON Field | Internal Adapter Field | Required | Description |
|---|---|:---:|---|
| `solved_at` | `solvedAt` | No | Timestamp when the optimisation was solved |
| `binding_constraints_summary` | `bindingConstraintsSummary` | No | Summary of binding constraints |
| `alternative_feasible_solutions` | `alternativeFeasibleSolutions` | No | Alternative feasible solutions |
| `sensitivity_to_key_assumptions` | `sensitivityToKeyAssumptions` | No | Sensitivity information |
| `explanation` | `explanation` | No | Explanation of the optimisation result |

Missing optional fields must **not** cause validation failure.

When optional fields are present, the adapter must safely pass them into the internal representation without modifying their values.

The adapter must not invent values for missing optional fields.

---

## 3. Valid Status Values

The validator must accept only status values defined by the confirmed `model_output_contract.json`.

In particular:

- `OPTIMAL` is a valid successful optimisation status.
- `OPTIMAL` must be included in `VALID_STATUS`.
- The validator must not introduce status values that are not defined by the confirmed external contract.
- `FEASIBLE` must not be used unless it exists in the confirmed contract.

---

## 4. Objective

The `objective` field contains the optimisation cost information.

### Example

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
```

The adapter must:

- Preserve these values.
- Not recalculate the objective.
- Not modify the MILP objective.
- Not introduce unsupported cost values.

---

## 5. Demand Zones

The external `demand_zones` field is a list.

Each demand-zone entry can contain:

- `zone_id`
- `zone_name`
- `demand_ml_per_day`
- `volume_supplied_ml_per_day`

### Validation Requirements

The validator must ensure that:

- `demand_zones` is a list.
- Every demand-zone entry is an object.

The adapter must preserve the complete demand-zone structure.

---

## 6. Sources

The external `sources` field is an object containing two arrays:

```json
{
  "selected": [],
  "unused": []
}
```

The validator must **not** treat `sources` as a flat list.

### Required Structure

```text
sources.selected -> list
sources.unused   -> list
```

The validator must ensure that:

- `sources` is an object.
- `sources.selected` is a list.
- `sources.unused` is a list.
- Each selected source is an object.
- Each unused source is an object.
- Every source entry contains a valid non-empty `source_id`.

---

## 7. Selected Sources

`selected` contains sources used in the optimisation solution.

Typical fields include:

- `source_id`
- `source_name`
- `source_type`
- `volume_drawn_ml_per_day`
- `percent_of_blend`
- `cost_per_ml`
- `draw_cost`

Every selected source must contain a valid non-empty `source_id`.

> **Important:** The confidence flagger must not use `sources.selected[]` as its provenance source.

---

## 8. Unused Sources

`unused` contains available sources that were not selected.

Typical fields include:

- `source_id`
- `source_name`
- `source_type`
- `reason`

Every unused source must contain a valid non-empty `source_id`.

> **Important:** The confidence flagger must not use `sources.unused[]` as its provenance source.

---

## 9. Transfer Paths

The external `transfer_paths` field is an object containing:

- `source_to_plant`
- `plant_to_zone`

### Example

```json
{
  "source_to_plant": [],
  "plant_to_zone": []
}
```

These represent the movement of water through the optimisation network.

### Validation

The validator must ensure that:

- `transfer_paths` is an object.

The adapter must:

- Preserve the complete transfer-path structure.
- Not modify flow values.
- Not recalculate transfer quantities.

---

## 10. Plants

The external `plants` field is an object containing:

- `active`
- `inactive`

### Example

```json
{
  "active": [],
  "inactive": []
}
```

Active plants contain treatment and processing information.

Inactive plants identify facilities that are not used by the solution.

### Validation

The validator must ensure that:

- `plants` is an object.

The adapter must preserve the complete plant structure.

---

## 11. Water Quality

The external `water_quality` field contains water quality information by plant.

The confirmed contract includes:

- `pH`
- `alkalinity`
- `turbidity`

Each quality measure can contain:

- `value`
- `unit`
- `constraint_min`
- `constraint_max`
- `status`
- `safety_margin_percent`

### Example

```json
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
```

### Validation

The validator must ensure that:

- `water_quality` is an object.

The adapter must:

- Preserve water quality values.
- Not calculate quality values.
- Not modify quality values.
- Not introduce unsupported quality values.

---

## 12. Constraints

The external `constraints` field is a list of constraint objects.

### Example

```json
{
  "name": "demand_satisfaction_zone_1",
  "type": "inequality",
  "status": "PASS",
  "slack": 0.0,
  "binding": true
}
```

### Validation Requirements

The validator must ensure that:

- `constraints` is a list.
- Every constraint entry is an object.

The validator must reject invalid constraint structures.

The adapter must preserve the complete constraint list without changing constraint results.

---

## 13. Diagnostics

The `diagnostics` field contains solver and optimisation information.

Typical fields include:

- `solver`
- `solve_time_seconds`
- `optimality_gap`
- `num_continuous_variables`
- `num_binary_variables`
- `num_integer_variables`
- `num_constraints`

### Example

```json
{
  "solver": "HiGHS",
  "solve_time_seconds": 0.084,
  "optimality_gap": 0.0
}
```

### Validation

The validator must ensure that:

- `diagnostics` is an object.

Diagnostics are informational and must not change the optimisation result.

---

# 14. Data Flags and Provenance

## 14.1 Data Flags

The external `data_flags` field contains source-data provenance and estimation information.

The confidence flagger reads provenance **only** from:

```text
data_flags.sources[]
```

It must **not** read provenance from:

```text
sources.selected[]
sources.unused[]
```

### Validation Requirements

The validator must ensure that:

- `data_flags` is an object.
- `data_flags.sources` is a list.
- Each entry in `data_flags.sources` is an object.
- Each entry contains a valid non-empty `source_id`.
- `has_estimated_values`, when present, is a boolean.
- `provenance`, when present, is an object.

---

## 14.2 Data Flag Source Structure

Each `data_flags.sources` entry contains:

- `source_id`
- `has_estimated_values`
- `availability_origin`
- `provenance`

### Example

```json
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
```

---

# 15. Provenance Fields

The confirmed contract contains five provenance fields.

| Provenance Field | Description |
|---|---|
| `storage_capacity` | Provenance of the source storage capacity |
| `reference_flow` | Provenance of the source reference flow |
| `max_available` | Provenance of the maximum available source volume |
| `cost` | Provenance of the source cost |
| `alkalinity` | Provenance of the alkalinity value |

All five provenance fields must be present before a source can be considered fully confirmed for `MEASURED` confidence.

Missing or incomplete provenance must **not** be interpreted as estimated data.

---

# 16. Boolean Validation

The `has_estimated_values` field must be a real boolean.

### Valid Values

```json
true
false
```

### Invalid Values

```json
null
"true"
"false"
1
0
```

A non-boolean value must not be treated as confirmed measured provenance.

If `has_estimated_values` is missing or invalid, the source cannot be confirmed as `MEASURED`.

---

# 17. Confidence Flags

The confidence flagger returns exactly one of:

```text
PROVISIONAL
MEASURED
UNKNOWN
```

Confidence is determined from:

```text
data_flags.sources[]
```

It must not use:

```text
sources.selected[]
sources.unused[]
```

---

## 17.1 PROVISIONAL

Return `PROVISIONAL` when at least one source has:

```json
"has_estimated_values": true
```

The value must be the actual boolean `true`.

The affected source ID must be included in `estimated_sources`.

### Example

```json
{
  "confidence": "PROVISIONAL",
  "estimated_sources": [
    "groundwater_bore_1"
  ]
}
```

Sources with missing or invalid provenance must not automatically be added to `estimated_sources`.

---

## 17.2 MEASURED

Return `MEASURED` only when **all source records** can be confirmed as measured.

Each source must:

1. Have a valid non-empty `source_id`.
2. Have `has_estimated_values` set to boolean `false`.
3. Contain a valid `provenance` object.
4. Contain all five provenance fields.

Required provenance fields:

- `storage_capacity`
- `reference_flow`
- `max_available`
- `cost`
- `alkalinity`

A missing provenance field prevents the source from being confirmed as `MEASURED`.

---

## 17.3 UNKNOWN

Return `UNKNOWN` when provenance cannot confirm that the data is measured and no valid estimated source has triggered `PROVISIONAL`.

`UNKNOWN` includes:

- Missing provenance.
- Incomplete provenance.
- Empty source list.
- Missing `source_id`.
- `has_estimated_values` is `null`.
- `has_estimated_values` is not a boolean.
- Invalid provenance structure.

Missing data must **not** automatically be treated as estimated data.

---

# 18. Empty Provenance Handling

An empty or missing provenance object must not result in `MEASURED`.

If there is no provenance available to confirm the source data, the confidence result must be `UNKNOWN`, unless another valid estimated source has already triggered `PROVISIONAL`.

An empty `data_flags.sources` list must return:

```text
UNKNOWN
```

It must not fall through to `MEASURED`.

---

# 19. Mixed Provenance

If one source contains valid estimated data and another source has missing or incomplete provenance, the overall result is:

```text
PROVISIONAL
```

The estimated source ID is included in `estimated_sources`.

The source with missing or incomplete provenance is **not** incorrectly labelled as estimated.

### Example

Source A:

```text
has_estimated_values = true
```

Result:

```text
Estimated
```

Source B:

```text
provenance = missing
```

Result:

```text
Unknown provenance
```

### Overall Result

```json
{
  "confidence": "PROVISIONAL",
  "estimated_sources": [
    "source_a"
  ]
}
```

The presence of an unknown-provenance source does not cause that source to be added to `estimated_sources`.

---

# 20. Source IDs

Every source must have a valid non-empty `source_id`.

The confidence flagger must not generate artificial source IDs.

The following are not permitted:

```text
source_0
source_1
source_2
```

If `source_id` is missing, the result must be `UNKNOWN` or the input must be rejected according to validator behaviour.

`estimated_sources` must contain only actual source IDs from the input.

---

# 21. Confidence Decision Summary

| Condition | Result |
|---|---|
| At least one source has `has_estimated_values = true` | `PROVISIONAL` |
| All sources have `has_estimated_values = false` and all five provenance fields are present | `MEASURED` |
| Provenance is missing/incomplete and no estimated source exists | `UNKNOWN` |
| `has_estimated_values` is not boolean | `UNKNOWN` |
| `source_id` is missing | `UNKNOWN` or invalid input |
| Source list is empty | `UNKNOWN` |
| Estimated source + unknown-provenance source | `PROVISIONAL` |
| Missing provenance | Never automatically treated as estimated |
| Generated source IDs | Not permitted |

---

# 22. Confidence Output

The confidence flagger returns an object such as:

```json
{
  "confidence": "PROVISIONAL",
  "estimated_sources": [
    "groundwater_bore_1"
  ]
}
```

`estimated_sources` must contain only actual source IDs for sources where estimated values were detected.

Generated IDs such as `source_0` or `source_1` are not permitted.

---

# 23. Adapter Behaviour

The adapter must:

- Preserve the external MILP contract.
- Keep inter-team field names unchanged.
- Handle internal naming differences only inside `results_adapter.py`.
- Preserve optimisation results.
- Not recalculate objective values.
- Not make optimisation decisions.
- Safely pass optional alternatives.
- Safely pass sensitivity information.
- Safely pass explanations.
- Preserve source structures.
- Preserve plant structures.
- Preserve transfer-path structures.
- Preserve water-quality structures.
- Preserve constraint structures.
- Preserve diagnostics.
- Preserve data flags.

The MILP Results JSON remains the factual source of truth.

---

# 24. Internal Adapter Mapping

| External Field | Internal Field |
|---|---|
| `scenario_id` | `scenarioId` |
| `demand_zones` | `demandZones` |
| `transfer_paths` | `transferPaths` |
| `water_quality` | `waterQuality` |
| `data_flags` | `dataFlags` |
| `solved_at` | `solvedAt` |
| `binding_constraints_summary` | `bindingConstraintsSummary` |
| `alternative_feasible_solutions` | `alternativeFeasibleSolutions` |
| `sensitivity_to_key_assumptions` | `sensitivityToKeyAssumptions` |

Fields that do not require internal renaming remain unchanged.

The adapter must not rename fields in the external Results JSON itself.

---

# 25. Validation Rules

The validator must check the following required fields:

- `scenario_id`
- `status`
- `objective`
- `demand_zones`
- `sources`
- `transfer_paths`
- `plants`
- `water_quality`
- `constraints`
- `diagnostics`
- `data_flags`

The validator must also check:

- `scenario_id` is a non-empty string.
- `status` is a valid contract status.
- `objective` is an object.
- `demand_zones` is a list.
- Each demand-zone entry is an object.
- `sources` is an object.
- `sources.selected` is a list.
- `sources.unused` is a list.
- Each selected source is an object.
- Each unused source is an object.
- Source entries contain a valid non-empty `source_id`.
- `transfer_paths` is an object.
- `plants` is an object.
- `water_quality` is an object.
- `constraints` is a list.
- Each constraint entry is an object.
- `diagnostics` is an object.
- `data_flags` is an object.
- `data_flags.sources` is a list.
- Each data-flag source is an object.
- Data-flag source entries contain a valid non-empty `source_id`.
- `has_estimated_values`, when present, is a boolean.
- `provenance`, when present, is an object.

Missing required fields must produce clear validation errors.

---

# 26. Optional Results Handling

The following fields are optional:

- `solved_at`
- `binding_constraints_summary`
- `alternative_feasible_solutions`
- `sensitivity_to_key_assumptions`
- `explanation`

Missing optional fields must not cause validation failure.

When present, the adapter must safely pass these fields into the internal representation.

The adapter must not invent values for missing optional fields.

---

# 27. Results JSON Source of Truth

The **MILP Results JSON is the factual source of truth**.

## Validator

The validator:

- Validates the structure.
- Validates required fields.
- Validates basic data types.
- Does not change values.
- Does not recalculate optimisation results.

## Adapter

The adapter:

- Creates the stable internal representation.
- Does not modify MILP results.
- Does not recalculate values.
- Does not make optimisation decisions.

## Confidence Flagger

The confidence flagger:

- Evaluates source-data provenance.
- Validates `has_estimated_values`.
- Evaluates the five provenance fields.
- Identifies estimated sources.
- Reports `PROVISIONAL`, `MEASURED`, or `UNKNOWN`.
- Does not modify optimisation results.

---

# 28. Task 21 Integration Flow

The Results JSON processing flow is:

```text
Receive Results JSON from MILP optimiser
                |
                v
Validate confirmed external Results JSON contract
                |
                v
Validate required fields and basic structures
                |
                v
Validate sources object
                |
                v
Validate sources.selected and sources.unused
                |
                v
Validate constraints list
                |
                v
Read provenance from data_flags.sources
                |
                v
Validate source_id
                |
                v
Validate has_estimated_values as boolean
                |
                v
Validate provenance structure
                |
                v
Check all five provenance fields
                |
                v
Determine confidence flag
                |
                +----> PROVISIONAL
                |
                +----> MEASURED
                |
                +----> UNKNOWN
                |
                v
Identify affected estimated source IDs
                |
                v
Adapt validated Results JSON
                |
                v
Safely pass optional fields
                |
                v
Preserve original MILP Results JSON
```

---

# 29. Task 21 Processing Rules

The implementation must follow these rules:

1. Receive Results JSON from the MILP optimiser.
2. Validate the confirmed external Results JSON contract.
3. Validate required fields and basic data structures.
4. Validate the `sources` object.
5. Validate `sources.selected` and `sources.unused`.
6. Validate the `constraints` list.
7. Read source provenance only from `data_flags.sources`.
8. Validate `source_id`.
9. Validate `has_estimated_values` as a boolean.
10. Validate the provenance structure.
11. Check all five provenance fields.
12. Determine the confidence flag.
13. Identify affected estimated source IDs.
14. Adapt the validated Results JSON for internal application use.
15. Safely pass optional alternatives, sensitivity information, and explanations.
16. Preserve the original MILP Results JSON as the factual source of truth.
17. Never allow the validator, adapter, or confidence flagger to change MILP optimisation decisions.

---

# 30. Contract Alignment

This field map is aligned with the confirmed `model_output_contract.json`.

The implementation must maintain the following contract requirements:

- `OPTIMAL` is a valid status.
- `constraints` is a list.
- `sources` is an object containing `selected` and `unused` arrays.
- Required fields use the confirmed external names.
- `scenario_id` is required.
- `objective` is required.
- `demand_zones` is required.
- `sources` is required.
- `transfer_paths` is required.
- `plants` is required.
- `water_quality` is required.
- `constraints` is required.
- `diagnostics` is required.
- `data_flags` is required.
- Source provenance is read from `data_flags.sources`.
- `has_estimated_values` must be a boolean.
- All five provenance fields are required for `MEASURED`.
- Missing provenance results in `UNKNOWN`.
- Missing provenance is not automatically treated as estimated.
- Actual source IDs are used in `estimated_sources`.
- Generated IDs such as `source_0` are not permitted.
- Mixed estimated and unknown provenance results in `PROVISIONAL`.
- Optional alternatives are handled safely.
- Optional sensitivity information is handled safely.
- Optional explanation fields are handled safely.

---

# 31. Future Contract Changes

This field map must remain synchronised with the confirmed `model_output_contract.json`.

Any future contract changes must be reflected in:

- Results JSON validator.
- `results_adapter.py`.
- Confidence flagger.
- Associated tests.
- This field map.

The **MILP Results JSON remains the factual source of truth at all times**.

---

# Task 21 Summary

The implementation consists of three main components:

| Component | Responsibility |
|---|---|
| **Validator** | Validate the external Results JSON structure and required data types |
| **Confidence Flagger** | Evaluate source provenance and return `PROVISIONAL`, `MEASURED`, or `UNKNOWN` |
| **Adapter** | Convert the validated external structure into the stable internal representation |

The three components must preserve the MILP output and must never change optimisation decisions or introduce unsupported values.