# ScenarioData AI Field Map

This document defines the subset of canonical `ScenarioData` fields that the AI context adapter is allowed to use.

The goal is to give AI enough scenario context to explain a run clearly, while avoiding duplication of database metadata and keeping solved flows / optimisation decisions out of `ScenarioData` handling.

## Purpose

The AI adapter should:
- read scenario-side context from canonical `ScenarioData`;
- preserve stable IDs;
- tolerate missing optional fields safely;
- avoid duplicating unnecessary database metadata;
- exclude solver-produced values and optimisation decisions.

## Included fields

### 1. Scenario metadata

| ScenarioData field | AI context field | Why it is included |
|---|---|---|
| `scenario_id` | `scenario_id` | Stable identifier for traceability. |
| `run_id` | `run_id` | Links the context to one optimisation execution. |
| `scenario_name` | `scenario_name` | Human-readable scenario label. |
| `description` | `description` | Short narrative context for the AI. |
| `status` | `status` | Helps explain the scenario or run lifecycle state. |
| `is_ready` | `is_ready` | Indicates whether the scenario passed readiness checks. |
| `validation_issues` | `validation_issues` | Explains why a scenario may not be ready or valid. |

### 2. Sources

| ScenarioData field | AI context field | Why it is included |
|---|---|---|
| `source_id` | `source_id` | Stable entity reference. |
| `name` | `name` | Human-readable label. |
| `enabled` | `enabled` | Indicates whether the source is active in the scenario. |
| `forced_inactive` | `forced_inactive` | Shows deliberate disablement. |
| `minimum_withdrawal_ml_per_day` | `minimum_withdrawal_ml_per_day` | Relevant input constraint. |
| `maximum_withdrawal_ml_per_day` | `maximum_withdrawal_ml_per_day` | Relevant input constraint. |
| `withdrawal_bounds_origin` | `withdrawal_bounds_origin` | Shows whether bounds came from data or override. |
| `availability_status` | `availability_status` | Helps explain availability or outage conditions. |

### 3. Treatment plants

| ScenarioData field | AI context field | Why it is included |
|---|---|---|
| `plant_id` | `plant_id` | Stable entity reference. |
| `name` | `name` | Human-readable label. |
| `enabled` | `enabled` | Indicates whether the plant is active in the scenario. |
| `minimum_processing_capacity_ml_per_day` | `minimum_processing_capacity_ml_per_day` | Relevant input constraint. |
| `maximum_processing_capacity_ml_per_day` | `maximum_processing_capacity_ml_per_day` | Relevant input constraint. |
| `availability_status` | `availability_status` | Helps explain plant availability or outage conditions. |

### 4. Demand zones

| ScenarioData field | AI context field | Why it is included |
|---|---|---|
| `zone_id` | `zone_id` | Stable entity reference. |
| `name` | `name` | Human-readable label. |
| `demand_ml_per_day` | `demand_ml_per_day` | Core demand input for explanations and anomalies. |

### 5. Source → Plant links

| ScenarioData field | AI context field | Why it is included |
|---|---|---|
| `source_id` | `source_id` | Stable route reference. |
| `plant_id` | `plant_id` | Stable route reference. |
| `enabled` | `enabled` | Indicates whether the route is available. |
| `maximum_flow_ml_per_day` | `maximum_flow_ml_per_day` | Relevant network constraint. |
| `override` | `override` | Captures scenario-level network changes. |

### 6. Plant → Demand Zone links

| ScenarioData field | AI context field | Why it is included |
|---|---|---|
| `plant_id` | `plant_id` | Stable route reference. |
| `zone_id` | `zone_id` | Stable route reference. |
| `enabled` | `enabled` | Indicates whether the route is available. |
| `maximum_flow_ml_per_day` | `maximum_flow_ml_per_day` | Relevant network constraint. |
| `override` | `override` | Captures scenario-level network changes. |

### 7. Water-quality limits

| ScenarioData field | AI context field | Why it is included |
|---|---|---|
| `quality_profile_id` | `profile_id` | Identifies the selected quality profile. |
| `parameter_id` | `parameter_id` | Stable identifier for a quality constraint. |
| `name` | `name` | Human-readable label. |
| `minimum` | `minimum` | Lower bound if applicable. |
| `maximum` | `maximum` | Upper bound if applicable. |
| `unit` | `unit` | Required for correct interpretation. |
| `override` | `override` | Captures custom quality changes. |

## Fields intentionally excluded

The adapter must not include:
- solved flows;
- objective value;
- total cost;
- allocations produced by the solver;
- optimiser decisions;
- model diagnostics unless passed through a separate diagnostics contract;
- duplicate database metadata that can be resolved from canonical storage.

These values belong to solver results, diagnostics, or other downstream contracts, not scenario context.

## Stability rules

- Prefer stable IDs over repeated names wherever possible.
- Treat missing optional fields as valid unless the contract says otherwise.
- Do not assume a field is present just because another layer may have populated it.
- Keep the adapter output small, readable, and deterministic.

## Output shape expectation

The AI context object should be a clean, minimal structure containing:
- scenario/run metadata;
- selected sources, plants, zones, and links;
- demand values;
- quality constraints;
- validation status.

It should not contain solver output or duplicated canonical database records.