# Scenario Input Contract Notes

**AquaBlend Analysis & AI — Sprint 2, Task 20**  
**Owner:** Sravya Tudi  
**Purpose:** Document the scenario loader, validator, approved scenario changes, and conservative pre-solve checks implemented for the current MILP input contract.

## 1. Scope

Task 20 loads and validates the approved AquaBlend toy-model input scenarios:

- `normal-year-dry-year/scenario_normal.json`
- `normal-year-dry-year/scenario_dry_year.json`
- `high-demand-outage/scenario_high_demand.json`
- `high-demand-outage/scenario_plant_outage.json`

The structured scenario JSON is an **input** to the MILP. The loader and validator do not make optimisation decisions and do not create solver outputs.

## 2. File placement

The Sprint 2 files are stored in `AI/scenarios/` beside the Sprint 1 scenario folders:

```text
AI/scenarios/
├── normal-year-dry-year/
├── high-demand-outage/
├── scenario_loader.py
├── scenario_validator.py
├── test_scenario_validator.py
└── Scenario_Input_Contract_Notes.md
```

## 3. Loader behaviour

`scenario_loader.py`:

1. Reads JSON using strict UTF-8 decoding.
2. Rejects malformed JSON.
3. Requires the top-level JSON value to be an object.
4. Can discover `scenario_*.json` files recursively in deterministic path order.
5. Does not perform contract validation.

Example:

```bash
python AI/scenarios/scenario_loader.py AI/scenarios
```

## 4. Required top-level input fields

The current contract contains:

- `scenario_id`
- `scenario_name`
- `status`
- `description`
- `data_source`
- `validation`
- `sources`
- `network`
- `quality_limits`
- `treatment`

Unknown fields are rejected at the top level and within supported nested objects.

The contract's top-level `status` is input metadata, currently `draft`. It is not treated as a MILP solve result.

## 5. Nested structure

### 5.1 Data source

Required fields:

- `type`
- `view`
- `allow_estimated_values`

### 5.2 Validation settings

Required Boolean fields:

- `fail_if_source_missing_from_database`
- `fail_if_daily_availability_missing`
- `fail_if_required_quality_value_missing`
- `fail_if_demand_missing`

### 5.3 Sources

Each source requires:

- `source_id`
- `enabled`
- `forced_inactive`
- `max_available_ml_per_day_override`

Source IDs must be non-empty and unique. An availability override must be `null` or a non-negative number.

### 5.4 Network

The network requires:

- `plants`
- `demand_zones`
- `source_to_plant_links`
- `plant_to_zone_links`

Plant, zone, and link fields must follow the current contract. Duplicate IDs and duplicate links are rejected. Links must reference known source, plant, and demand-zone IDs.

### 5.5 Quality limits

`quality_limits.applies_to` must be:

```text
blend_at_plant_inflow
```

The required parameters are:

- `pH`
- `alkalinity`
- `turbidity`

Each parameter requires `unit`, `min`, `max`, and `transform`.

These values describe **plant-inflow blend limits**. They are not after-treatment results, final drinking-water results, or proof of regulatory compliance.

## 6. Stable internal scenario types and IDs

The current input contract does not define a `scenario_type` field. The validator therefore assigns an internal type from existing metadata without modifying the input JSON.

| Internal type | Stable scenario ID |
|---|---|
| `NORMAL` | `toy_model_normal_year` |
| `DRY_YEAR` | `toy_model_dry_year` |
| `HIGH_DEMAND` | `scenario_2026_07_17_high_demand` |
| `PLANT_OUTAGE` | `scenario_2026_07_17_plant_outage` |

An unsupported type or unstable ID is rejected.

## 7. Approved scenario changes

Scenario comparisons use the normal scenario as the reference. Metadata changes are limited to:

- `scenario_id`
- `scenario_name`
- `description`

### 7.1 Normal

No operational field may differ from the approved reference input.

### 7.2 Dry year

Only the three source-to-plant maximum-flow values may change:

| Source | Normal | Dry year |
|---|---:|---:|
| `silvan_reservoir` | 350 ML/day | 280 ML/day |
| `yarra_kew` | 300 ML/day | 240 ML/day |
| `groundwater_bore_1` | 60 ML/day | 45 ML/day |

Demand remains 500 ML/day. The validator records every leaf-level change from the reference.

### 7.3 High demand

Only this field changes:

```text
network.demand_zones[0].demand_ml_per_day
```

The approved value changes from 500 to 600 ML/day. Other operational fields must remain unchanged.

### 7.4 Plant outage

The confirmed outage field is:

```text
network.plants[0].enabled
```

For `facility_1`, it changes from `true` to `false`.

No link, demand, capacity, cost, quality-limit, or source setting is changed. The physical links remain in the input, but the disabled plant removes the active treatment path.

## 8. Pre-solve capacity check

The validator calculates:

- active source-to-plant link capacity reachable through enabled sources and plants;
- active plant processing capacity;
- active plant-to-zone capacity;
- mandatory demand;
- aggregate effective capacity;
- remaining aggregate capacity.

The aggregate effective capacity is the minimum of the three active capacity layers. This is a conservative toy-network screening check and is not a replacement for the MILP.

Expected current results:

| Scenario | Effective capacity | Demand | Remaining | Static warning |
|---|---:|---:|---:|---|
| Normal | 600 ML/day | 500 ML/day | 100 ML/day | No shortfall |
| Dry year | 565 ML/day | 500 ML/day | 65 ML/day | No shortfall |
| High demand | 600 ML/day | 600 ML/day | 0 ML/day | Tight, no shortfall |
| Plant outage | 0 ML/day | 500 ML/day | -500 ML/day | Possible infeasibility |

A passed static check does not prove MILP feasibility. Database availability, quality limits, and optimisation constraints may still prevent a feasible solve.

## 9. Connectivity check

For every positive mandatory-demand zone, the validator checks for an active path:

```text
enabled source
→ enabled source-to-plant link
→ enabled plant
→ enabled plant-to-zone link
→ demand zone
```

The plant-outage scenario has no active path to `zone_1`, so the validator reports possible infeasibility. It does not create or assert the official MILP solve status.

## 10. No fake outputs

The validator rejects output-only fields in scenario inputs, including:

- `objective`
- `total_cost`
- `volume_drawn_ml_per_day`
- `volume_supplied_ml_per_day`
- `percent_of_blend`
- `binding_constraints_summary`
- `water_quality`
- `diagnostics`
- `data_flags`
- `alternatives`
- `sensitivity_to_key_assumptions`

The Task 20 code does not generate selected volumes, blend shares, costs, binding constraints, quality results, or an `OPTIMAL`/`INFEASIBLE` solver result.

## 11. Running validation

Example for the dry-year scenario:

```bash
python AI/scenarios/scenario_validator.py \
  AI/scenarios/normal-year-dry-year/scenario_dry_year.json \
  --reference AI/scenarios/normal-year-dry-year/scenario_normal.json \
  --type DRY_YEAR
```

Example for the outage scenario:

```bash
python AI/scenarios/scenario_validator.py \
  AI/scenarios/high-demand-outage/scenario_plant_outage.json \
  --reference AI/scenarios/normal-year-dry-year/scenario_normal.json \
  --type PLANT_OUTAGE
```

## 12. Tests

Run from the scenario folder:

```bash
cd AI/scenarios
python -m unittest -v test_scenario_validator.py
```

The suite covers:

- valid normal, dry-year, high-demand, and plant-outage inputs;
- UTF-8/JSON loading failures;
- missing and unknown fields;
- nested unknown fields;
- incorrect data types;
- duplicate source IDs;
- unknown link references;
- output-only fields;
- unapproved dry-year changes;
- incorrect high-demand values;
- unapproved outage changes;
- capacity-shortfall warnings;
- outage connectivity.

## 13. Known limitations

- The capacity check is aggregate and does not replace the MILP network solve.
- Source database availability and quality values are not loaded by this validator.
- The scenario-specific change rules intentionally reflect the approved Sprint 1 toy scenarios.
- Future multi-plant or multi-zone scenarios may require a stronger maximum-flow pre-check and revised stable-ID rules.
- The plant-outage scenario validates full deactivation of the only treatment facility; it is not a partial-capacity outage.
