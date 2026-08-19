# AquaBlend High-Demand and Plant-Outage Toy Scenarios

**Task:** Task 11 — Define the high-demand and plant-outage scenarios
**Owner:** Abdulla
**Team:** Analysis & AI, Sprint 1
**Status:** High-demand section complete. Plant-outage section complete, pending confirmation of the outage field.
**Units:** Volume in ML. Changes in %.

---

## 1. Purpose

This document defines two operational-stress scenarios for testing the AquaBlend MILP model, built on the official reference configuration confirmed by the Optimisation team (`model_input_contract.json`):

1. **High-demand scenario** — the reference configuration with `zone_1`'s required demand increased by a justified percentage.
2. **Plant-outage scenario** — the reference configuration with `facility_1` disabled, simulating a treatment-facility outage.

Both scenarios use the confirmed toy-model sources (`silvan_reservoir`, `yarra_kew`, `groundwater_bore_1`), so no placeholder values remain.

---

## 2. Files

| File | Purpose |
|---|---|
| `scenario_high_demand.json` | Reference configuration with `zone_1` demand increased 20% |
| `scenario_plant_outage.json` | Reference configuration with `facility_1` disabled |
| `Scenario_HighDemand_Outage.md` | Documents the scenario assumptions, changes, and feasibility checks |

---

## 3. High-Demand Scenario

### 3.1 Change

`network.demand_zones[].demand_ml_per_day` is increased from **500 ML/day** to **600 ML/day**, a 20% increase.

| Field | Original value | New value | Change |
|---|---|---|---|
| `demand_ml_per_day` (zone_1) | 500 | 600 | +20% |

Calculation: 500 x 1.20 = 600 ML/day.

No other field is changed. Sources, capacities, plant settings, and quality limits remain identical to the reference configuration.

### 3.2 Justification

20% is used as the stress-test increase to keep the two operational-stress scenarios in this sprint on a consistent basis: the dry-year scenario (Task 10) applies the same 20% figure as a supply-side reduction. Using the same percentage on the demand side gives a comparable stress magnitude without introducing a second unresearched assumption this sprint. This is a toy-model planning assumption, not a published peak-demand figure, and should be revisited against real peak-demand data in a later scope.

### 3.3 Feasibility check

Total source capacity: 350 (Silvan) + 300 (Yarra Kew) + 60 (Groundwater Bore 1) = **710 ML/day**, which exceeds the new demand of 600 ML/day, so the scenario is feasible at the source-capacity level.

Plant capacity: `facility_1`'s `maximum_processing_capacity_ml_per_day` is exactly **600 ML/day**, equal to the new demand. This means the plant-to-zone link and the plant itself have zero spare capacity at this demand level: the plant capacity constraint is expected to bind exactly at the new demand value. This is flagged as a tight constraint worth watching once the model is run, since any additional loss or estimation error at the plant would make the scenario infeasible.

---

## 4. Plant-Outage Scenario

### 4.1 Change

`network.plants[].enabled` for `facility_1` is set from `true` to `false`.

| Field | Original value | New value |
|---|---|---|
| `plants[].enabled` (facility_1) | true | false |

This is the exact field confirmed by the Optimisation team's input specification (`model_input_specification.md`, Section 3.4): `network.plants[].enabled`, defaulting to `true`, used to deactivate a plant.

No other field is changed. The `source_to_plant_links` and `plant_to_zone_links` entries for `facility_1` are left as `enabled: true` in the file, since the specification treats plant deactivation and link deactivation as separate mechanisms; disabling the plant itself is sufficient and is the method this scenario uses, consistent with the task's instruction to "set its activation field to inactive."

### 4.2 Why this scenario is expected to be infeasible

`facility_1` is the only treatment facility in the toy model, and all three source-to-plant links route through it. With `facility_1` disabled, there is no active path from any source to `zone_1`, regardless of source availability.

This is documented as an **expected infeasible result**, not an error:

- `demand_zones[].demand_must_be_met` is `true`, so the solver must reject any solution that leaves `zone_1`'s demand unmet.
- With no active plant, `volume_supplied_ml_per_day` for `zone_1` is structurally `0`, which cannot satisfy the 500 ML/day demand.
- Expected solver status: `INFEASIBLE`.

This satisfies the checklist requirement to document possible infeasibility, and demonstrates that the model correctly reports infeasibility when the only treatment path is lost, rather than silently returning a partial or fabricated result.

### 4.3 No invented plant-inflow blend quality values

Per the task's checklist, no invented water-quality values are created for this scenario. `water_quality.by_plant` reports the blend arriving at a plant's inflow, not final treated water (per the output specification, Section 3.7). Since no source-to-plant flow occurs when `facility_1` is disabled, `water_quality.by_plant` should have no entry for `facility_1` in the resulting output ("a plant with zero inflow has no defined blend and is omitted").

---

## 5. JSON Structure and Validation

Both scenario files follow the same structure as the confirmed reference configuration (`model_input_contract.json`). The only intended differences from the reference file are:

- `scenario_id` and `scenario_name`, which differ per scenario for traceability
- `description`, updated to state what each scenario changes
- **High-demand file:** `network.demand_zones[].demand_ml_per_day` only
- **Plant-outage file:** `network.plants[].enabled` only

No unofficial fields are added. No output-only fields (`volume_drawn_ml_per_day`, `percent_of_blend`, `total_cost`, `status`, etc.) are present in either input file.

### Validation checklist

- [x] `scenario_high_demand.json` opens as valid JSON
- [x] `scenario_plant_outage.json` opens as valid JSON
- [x] Both files contain the same top-level structure as the reference configuration
- [x] Both files contain the same three source records, unchanged
- [x] Original demand value is recorded (500 ML/day)
- [x] High-demand multiplier is stated (20%)
- [x] New demand value is calculated correctly (600 ML/day)
- [x] Demand increase is justified (Section 3.2)
- [x] Outage facility is clearly named (`facility_1`, Treatment Facility 1)
- [x] Exact outage field is identified (`network.plants[].enabled`)
- [x] Only supported fields are changed
- [x] Connectivity after the outage is checked (Section 4.2)
- [x] Remaining treatment capacity is checked (0 ML/day, facility fully disabled)
- [x] Possible infeasibility is documented (Section 4.2)
- [x] No invented plant-inflow blend quality values are created when no treatment occurs (Section 4.3)

---

## 6. KPI Availability

| KPI | High-demand scenario | Plant-outage scenario |
|---|---|---|
| Total available source capacity | Available before solving (710 ML/day) | Available before solving (710 ML/day, but unreachable) |
| Required demand | Available before solving (600 ML/day) | Available before solving (500 ML/day) |
| Basic capacity margin | Available before solving (110 ML/day) | Not meaningful — no active treatment path |
| Solver feasibility status | Pending MILP run | Expected `INFEASIBLE`, pending MILP run to confirm |
| Demand satisfaction percentage (KPI 2) | Pending MILP run, expect near 100% given capacity margin | Not applicable — pending MILP run. Since the expected solver status is `INFEASIBLE`, there is no valid solved `volume_supplied_ml_per_day` to report, so KPI 2 should be marked unavailable rather than 0%. The pre-solve check (Section 4.2) separately confirms no active treatment capacity exists, which is why infeasibility is expected. |
| Selected source volumes | Pending MILP run | Not applicable — expected infeasible |
| Blend percentages | Pending MILP run | Not applicable — expected infeasible |
| Total cost | Pending MILP run | Not applicable — expected infeasible |
| Binding constraints | Pending MILP run — plant capacity expected to bind (Section 3.3) | Not applicable — expected infeasible |
| Water-quality safety margins | Pending MILP run | Not applicable — no plant-inflow blend at facility_1 (Section 4.3) |

---

## 7. Limitations

1. The 20% high-demand increase is a toy-model planning assumption matched to the dry-year scenario's reduction percentage, not a published peak-demand figure. Real peak-demand analysis (e.g. the dataset's recorded 2,190 ML/day system peak vs 1,284 ML/day mean, roughly a 70% peak-to-mean ratio at system scale) would justify a different toy-model figure in a later scope.
2. The plant-outage scenario is expected to be infeasible by construction, since the toy model has only one treatment facility. This scenario validates that the model correctly reports infeasibility rather than testing a realistic partial-capacity outage. A partial-capacity outage (e.g. reduced `maximum_processing_capacity_ml_per_day` rather than full deactivation) may be a more operationally realistic scenario for a later scope, once more than one treatment facility exists in the model.
3. Both scenarios apply to the Scope 1 public-data proof-of-concept only and are not operational recommendations.
