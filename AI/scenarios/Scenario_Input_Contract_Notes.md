# Scenario Input Contract Notes

**AquaBlend Analysis & AI — Sprint 2, Task 20**  
**Owner:** Sravya Tudi  
**Status:** Review update aligned with the current MILP input contract.

## 1. Scope

Task 20 loads and validates the existing Sprint 1 AquaBlend toy scenarios:

- `normal-year-dry-year/scenario_normal.json`
- `normal-year-dry-year/scenario_dry_year.json`
- `high-demand-outage/scenario_high_demand.json`
- `high-demand-outage/scenario_plant_outage.json`

These scenario JSON files are upstream inputs to the MILP workflow. Task 20 validates the inputs before downstream use. It does not make MILP optimisation decisions and does not fabricate solver outputs.

## 2. Task 20 Files

The Task 20 implementation is organised under `AI/scenarios/`:

```text
AI/scenarios/
├── normal-year-dry-year/
├── high-demand-outage/
├── tests/
│   └── test_scenario_validator.py
├── scenario_loader.py
├── scenario_validator.py
└── Scenario_Input_Contract_Notes.md
```

The main responsibilities are:

- `scenario_loader.py` — loads scenario JSON files using strict UTF-8 and performs basic JSON loading checks.
- `scenario_validator.py` — validates scenario structure, contract fields, scenario-specific changes, capacity, and connectivity.
- `tests/test_scenario_validator.py` — contains the `pytest` test suite for the loader and validator.
- `Scenario_Input_Contract_Notes.md` — documents the contract assumptions and validation behaviour used by Task 20.

`scenario_plant_outage.json` already existed from the Sprint 1 scenario work. Task 20 consumes and validates this existing file rather than adding a duplicate copy.

## 3. Loader Behaviour

The loader implementation is provided in `scenario_loader.py`.

It:

- reads JSON using strict UTF-8;
- rejects malformed JSON;
- requires the top-level JSON value to be an object;
- discovers `scenario_*.json` files recursively in deterministic path order; and
- leaves contract and scenario-rule validation to `scenario_validator.py`.

This keeps file loading separate from the validation logic.

## 4. Current MILP Input-Contract Alignment

Task 20 uses the current MILP input contract/specification as the input authority.

Important fields used by the validator include:

- `network.demand_zones[].demand_ml_per_day`
- `network.plants[].enabled`
- `network.plants[].minimum_processing_capacity_ml_per_day`
- `network.plants[].maximum_processing_capacity_ml_per_day`
- `network.source_to_plant_links[].maximum_flow_ml_per_day`
- `network.plant_to_zone_links[].maximum_flow_ml_per_day`
- `sources[].minimum_withdrawal_ml_per_day`

The current MILP specification documents `minimum_operating_flow_ml_per_day` as a legacy fallback for the plant minimum-capacity field. The existing Sprint 1 scenario files still use that legacy name.

For compatibility, `scenario_validator.py` accepts the legacy field and reports a warning, while treating `minimum_processing_capacity_ml_per_day` as the preferred current field.

Task 20 does not silently rewrite the existing upstream Sprint 1 scenario JSON files.

## 5. ID-Based Scenario Comparison

Scenario comparison is implemented in `scenario_validator.py`.

The current MILP specification uses IDs as join keys. Therefore, the validator compares known arrays using stable IDs instead of relying on array positions.

Examples of the validator's internal path notation are:

```text
network.demand_zones[zone_id=zone_1].demand_ml_per_day
network.plants[plant_id=facility_1].enabled
network.source_to_plant_links[source_id=silvan_reservoir,plant_id=facility_1].maximum_flow_ml_per_day
```

This means that reordering entries in arrays such as `sources` or `source_to_plant_links` does not incorrectly appear as an operational scenario change.

This behaviour is covered by regression tests in `tests/test_scenario_validator.py`.

## 6. Stable Scenario IDs and Types

The validator uses the following internal scenario types and existing stable scenario IDs:

| Internal type | Stable scenario ID |
|---|---|
| `NORMAL` | `toy_model_normal_year` |
| `DRY_YEAR` | `toy_model_dry_year` |
| `HIGH_DEMAND` | `scenario_2026_07_17_high_demand` |
| `PLANT_OUTAGE` | `scenario_2026_07_17_plant_outage` |

The validator infers an internal scenario type from the existing scenario information. It does not add a new `scenario_type` field to the input JSON.

## 7. Approved Scenario Changes

Scenario-specific change validation is handled by `scenario_validator.py`.

The normal scenario is used as the reference. Metadata differences are limited to:

- `scenario_id`
- `scenario_name`
- `description`

Operational changes are restricted according to the scenario type.

### 7.1 Normal Scenario

No operational field may differ from the approved normal reference input.

### 7.2 Dry-Year Scenario

The approved dry-year changes are the three source-to-plant maximum-flow changes below:

| Source | Plant | Normal | Dry year |
|---|---|---:|---:|
| `silvan_reservoir` | `facility_1` | 350 ML/day | 280 ML/day |
| `yarra_kew` | `facility_1` | 300 ML/day | 240 ML/day |
| `groundwater_bore_1` | `facility_1` | 60 ML/day | 45 ML/day |

These changes are validated using `source_id` and `plant_id`, rather than array positions.

Demand remains `500 ML/day`.

### 7.3 High-Demand Scenario

For `zone_1`, the approved operational change is:

```text
network.demand_zones[zone_id=zone_1].demand_ml_per_day
```

The value changes from `500 ML/day` to `600 ML/day`.

Other operational fields must remain unchanged.

### 7.4 Plant-Outage Scenario

The existing Sprint 1 plant-outage scenario uses the plant activation field:

```text
network.plants[plant_id=facility_1].enabled
```

For `facility_1`, the value changes from `true` to `false`.

Task 20 validates this existing outage scenario and then uses the capacity and connectivity checks in `scenario_validator.py` to identify the resulting pre-solve risk.

## 8. Pre-Solve Capacity Check

The capacity check is implemented in `scenario_validator.py`.

It calculates:

- active source-to-plant link capacity;
- active plant processing capacity;
- active plant-to-zone capacity;
- mandatory demand;
- aggregate effective capacity; and
- remaining aggregate capacity.

The aggregate effective capacity is the minimum of the three active capacity layers.

Expected screening results for the current scenarios are:

| Scenario | Effective capacity | Demand | Remaining |
|---|---:|---:|---:|
| Normal | 600 ML/day | 500 ML/day | 100 ML/day |
| Dry year | 565 ML/day | 500 ML/day | 65 ML/day |
| High demand | 600 ML/day | 600 ML/day | 0 ML/day |
| Plant outage | 0 ML/day | 500 ML/day | -500 ML/day |

These checks are conservative **pre-solve screening checks only**.

A capacity warning does not prove MILP infeasibility, and passing the static check does not prove MILP feasibility. The validator does not create a solver status such as `OPTIMAL` or `INFEASIBLE`.

## 9. Connectivity Check

The connectivity check in `scenario_validator.py` checks whether each positive mandatory-demand zone has an active path through the network:

```text
enabled source
→ enabled source-to-plant link
→ enabled plant
→ enabled plant-to-zone link
→ demand zone
```

When `facility_1` is disabled in the existing plant-outage scenario, there is no active treatment path to `zone_1`.

The validator therefore reports a possible pre-solve feasibility risk without claiming a MILP solver result.

## 10. Protection Against Output-Only Fields

Scenario inputs must not contain fields that belong to downstream MILP results.

`scenario_validator.py` rejects output-only fields including:

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

Task 20 does not generate selected volumes, blend shares, costs, binding constraints, water-quality results, or an `OPTIMAL`/`INFEASIBLE` solver result.

## 11. Tests

Tests are stored in:

```text
AI/scenarios/tests/test_scenario_validator.py
```

The test suite uses `pytest` for consistency with the repository's other test work.

From `AI/scenarios/`, run:

```bash
python -m pytest -v tests/test_scenario_validator.py
```

The current suite contains **24 tests** covering:

- valid normal, dry-year, high-demand, and plant-outage scenarios;
- strict UTF-8 and malformed JSON handling;
- non-object top-level JSON rejection;
- required and unknown field validation;
- incorrect data types;
- duplicate source IDs;
- unknown link references;
- output-only field rejection;
- scenario-specific approved-change rules;
- capacity screening;
- connectivity screening;
- ID-based comparison and array-order independence;
- current `minimum_processing_capacity_ml_per_day` support;
- legacy `minimum_operating_flow_ml_per_day` compatibility warning; and
- `minimum_withdrawal_ml_per_day` support.

The suite is implemented using `pytest` assertions, fixtures, and `pytest.raises()` rather than `unittest`.

## 12. Review Updates Addressed

The following review points have been addressed:

1. **Test location**  
   `test_scenario_validator.py` has been moved to `AI/scenarios/tests/`.

2. **Test framework**  
   The test suite has been converted from `unittest` to `pytest`.

3. **ID-based validation**  
   Scenario comparisons use stable source, plant, and zone IDs instead of depending on array positions.

4. **Plant-outage field**  
   The existing outage scenario uses `network.plants[].enabled`. For `facility_1`, the scenario changes `enabled` from `true` to `false`.

5. **Existing outage scenario**  
   `scenario_plant_outage.json` already existed from Sprint 1 and is reused by Task 20.

6. **Current plant minimum-capacity field**  
   The validator accepts `minimum_processing_capacity_ml_per_day` while retaining compatibility with the documented legacy field used by the existing Sprint 1 scenarios.

7. **Documentation formatting**  
   File names, JSON fields, IDs, paths, and code references are formatted using Markdown code notation and are linked clearly to the relevant Task 20 implementation files.

## 13. Future Integration Note

The MILP team also has a `data_loader.py` implementation that may be useful for future alignment between the Analysis & AI and MILP streams.

This is currently treated as a **non-blocking follow-up**, as noted in the review. No Task 20 implementation change is being made for `data_loader.py` until the expected integration or alignment is confirmed with the team.