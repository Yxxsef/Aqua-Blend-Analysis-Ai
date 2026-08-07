# Results JSON Field Map

## Overview

This document describes the mapping between the external MILP Results JSON contract and the internal AquaBlend representation.

The external field names must remain unchanged for inter-team integration.

Internal naming changes are handled only inside `results_adapter.py`.

---

## Results JSON Field Mapping

| External Results JSON Field | Internal Adapter Field | Description |
|---|---|---|
| `scenario` | `scenario` | Scenario configuration and identifier |
| `status` | `status` | Optimisation result status |
| `sources` | `sources` | Water source allocation information |
| `demand` | `demand` | Required demand volume information |
| `cost` | `cost` | Cost calculation information |
| `constraints` | `constraints` | Constraint evaluation results |
| `quality_stage` | `qualityStage` | Water quality stage information |
| `diagnostics` | `diagnostics` | Solver and result diagnostics |

---

## Source Field Mapping

| External Source Field | Internal Field | Description |
|---|---|---|
| `source_id` | `source_id` | Unique source identifier |
| `source_name` | `source_name` | Source display name |
| `allocated_volume_ML` | `allocated_volume_ML` | Allocated water volume |
| `has_estimated_values` | `has_estimated_values` | Indicates whether estimated data was used |

---

## Confidence Flag Mapping

The confidence flag is generated from source provenance information.

| Condition | Confidence Flag |
|---|---|
| Any contributing source has `has_estimated_values = true` | `PROVISIONAL` |
| All contributing sources have `has_estimated_values = false` | `MEASURED` |
| Provenance information is missing | `UNKNOWN` |

---

## Adapter Behaviour

The adapter:

- Preserves external MILP field names.
- Creates a stable internal representation.
- Handles internal naming differences.
- Does not modify optimisation results.
- Does not calculate new values.
- Does not replace MILP decision outputs.

---

## Optional Fields

The following fields may appear in Results JSON but are not required for the core validation flow:

| Field | Handling |
|---|---|
| `alternatives` | Passed safely when available |
| `sensitivity` | Passed safely when available |
| `explanations` | Passed safely when available |

Missing optional fields should not cause validation failure.

---

## Validation Rules

Required fields:

- `scenario`
- `status`
- `sources`
- `demand`
- `cost`
- `constraints`
- `quality_stage`
- `diagnostics`

Missing required fields result in validation errors.

---

## Task 21 Integration Notes

- Results JSON remains the source of truth.
- The adapter provides internal stability.
- Confidence flags disclose data reliability.
- Estimated values are never hidden.
- Optimisation decisions remain controlled by the MILP layer.