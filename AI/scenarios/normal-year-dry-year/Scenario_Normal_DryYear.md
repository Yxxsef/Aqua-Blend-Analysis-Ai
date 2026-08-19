# AquaBlend Normal-Year and Dry-Year Scenarios

**Task:** Task 10 — Define the normal-year and dry-year scenarios  
**Owner:** Amantha Kulathunga  
**Team:** Analysis & AI, Sprint 1  
**Status:** Updated to align with the official toy-model input configuration  
**Units:** Flow and demand in ML/day; changes in %

---

## 1. Purpose

This document defines two reproducible input scenarios for testing the AquaBlend MILP model:

1. **Normal-year scenario** — an unchanged copy of the official toy-model input configuration.
2. **Dry-year scenario** — a copy of the normal-year configuration with clearly documented reductions to the maximum source-to-plant flow limits.

The scenarios are intended for model development and comparison. They must not be treated as operational water-supply recommendations.

---

## 2. Files

| File | Purpose |
|---|---|
| `scenario_normal.json` | Unchanged copy of the official toy-model input configuration |
| `scenario_dry_year.json` | Dry-year copy with reduced `network.source_to_plant_links[].maximum_flow_ml_per_day` values |
| `Scenario_Normal_DryYear.md` | Documents the assumptions, changes, calculations, feasibility checks and KPI availability |

---

## 3. Normal-Year Scenario

The normal-year scenario is an unchanged copy of the official toy-model input configuration confirmed by the Optimisation team.

It contains:

- Three enabled water sources:
  - `silvan_reservoir` — reservoir
  - `yarra_kew` — river
  - `groundwater_bore_1` — groundwater
- One treatment plant: `facility_1`
- One demand zone: `zone_1`
- Required demand of **500 ML/day**
- Treatment-plant processing limit of **600 ML/day**
- Plant-to-zone maximum flow of **600 ML/day**
- Total maximum source-to-plant flow of **710 ML/day**

The source-selection records identify which database sources are included. Source attributes such as cost, daily availability and representative quality values are loaded separately from the Supabase view defined in the input contract.

### Normal-year maximum source-to-plant flows

| Source ID | Source type | Field | Normal-year value |
|---|---|---|---:|
| `silvan_reservoir` | Reservoir | `network.source_to_plant_links[].maximum_flow_ml_per_day` | 350 ML/day |
| `yarra_kew` | River | `network.source_to_plant_links[].maximum_flow_ml_per_day` | 300 ML/day |
| `groundwater_bore_1` | Groundwater | `network.source_to_plant_links[].maximum_flow_ml_per_day` | 60 ML/day |
| **Total** |  |  | **710 ML/day** |

No network setting, quality limit, treatment setting, demand value, data-source setting or validation rule is changed in `scenario_normal.json`.

---

## 4. Dry-Year Scenario Definition

### Dry-year changes

The dry-year scenario applies differentiated supply reductions because the official toy model contains different water-source types:

- **20% reduction** to `silvan_reservoir`
- **20% reduction** to `yarra_kew`
- **25% reduction** to `groundwater_bore_1`

The reductions are applied to:

```text
network.source_to_plant_links[].maximum_flow_ml_per_day
```

They represent controlled dry-year stress-test assumptions for the maximum amount that each source can transfer to the treatment plant during the representative day.

The following remain unchanged:

- Source selection and activation settings
- `data_source` settings
- Validation settings
- Treatment-plant processing capacity and costs
- Demand of 500 ML/day
- Plant-to-zone flow limit
- Quality limits
- `treatment` configuration

### Surface-water justification

A 20% reduction is applied to the Silvan reservoir and Yarra Kew river links as a conservative surface-water stress assumption. Victorian Government and Bureau of Meteorology climate research reports that, during the Millennium Drought, more than half of the Victorian catchments analysed experienced an additional **20–40% decline in annual streamflow**. The lower end of that observed range is used to keep the toy dry-year scenario simple and reproducible.

This percentage is a scenario proxy applied to the model's maximum flow limits. It is not a claim that the actual daily availability of Silvan Reservoir or Yarra Kew always falls by exactly 20% in a dry year.

**Source:** [Victoria's Water in a Changing Climate](https://www.water.vic.gov.au/__data/assets/pdf_file/0026/664145/victorias-water-in-a-changing-climate.pdf)

### Groundwater justification

A separate 25% reduction is applied to `groundwater_bore_1`. Goulburn–Murray Water reported a Victorian groundwater-management example in which groundwater allocations were set at **75% of licensed entitlement**, equivalent to a 25% reduction, using groundwater recovery levels and management triggers.

The example relates to the Lower Campaspe Valley rather than Melbourne. It is used as a provisional Victorian groundwater-management proxy because the generic toy-model bore is not linked to a confirmed aquifer or management area. It should not be interpreted as evidence that groundwater automatically falls by 25% during every dry season.

**Source:** [Goulburn–Murray Water — Lower Campaspe Valley 2023 Annual Newsletter](https://www.g-mwater.com.au/downloads/gmw/Groundwater/Lower_Campaspe_Valley_WSPA/2023%20ANNUAL%20NEWSLETTER%20-%20LOWER%20CAMPASPE%20VALLEY%20WATER%20SUPPLY%20PROTECTION%20AREA%20.pdf)

---

## 5. Maximum Flow Changes

### Surface-water calculation

```text
Dry-year maximum flow = Normal-year maximum flow × (1 - 20/100)
                      = Normal-year maximum flow × 0.80
```

### Groundwater calculation

```text
Dry-year maximum flow = Normal-year maximum flow × (1 - 25/100)
                      = Normal-year maximum flow × 0.75
```

| Source ID | Source type | Changed field | Normal-year value | Dry-year value | Reduction |
|---|---|---|---:|---:|---:|
| `silvan_reservoir` | Reservoir | `maximum_flow_ml_per_day` | 350 ML/day | 280 ML/day | 20% |
| `yarra_kew` | River | `maximum_flow_ml_per_day` | 300 ML/day | 240 ML/day | 20% |
| `groundwater_bore_1` | Groundwater | `maximum_flow_ml_per_day` | 60 ML/day | 45 ML/day | 25% |
| **Total** |  |  | **710 ML/day** | **565 ML/day** | **20.42% overall** |

### Individual calculations

```text
Silvan Reservoir:
350 ML/day × 0.80 = 280 ML/day

Yarra Kew:
300 ML/day × 0.80 = 240 ML/day

Groundwater Bore 1:
60 ML/day × 0.75 = 45 ML/day
```

### Overall reduction

```text
Total reduction = 710 - 565
                = 145 ML/day

Overall reduction percentage = (145 / 710) × 100
                             = 20.42%
```

---

## 6. Remaining Supply Check

The official toy-model demand is:

```text
network.demand_zones[].demand_ml_per_day = 500 ML/day
```

### Normal year

```text
Total normal-year maximum source-to-plant flow
= 350 + 300 + 60
= 710 ML/day
```

```text
Normal-year supply margin
= 710 - 500
= 210 ML/day
```

### Dry year

```text
Total dry-year maximum source-to-plant flow
= 280 + 240 + 45
= 565 ML/day
```

```text
Dry-year supply margin
= 565 - 500
= 65 ML/day
```

The dry-year scenario retains **565 ML/day** of total maximum source-to-plant flow against demand of **500 ML/day**. It therefore passes the basic supply-volume feasibility check, with a remaining margin of **65 ML/day**.

The treatment plant and plant-to-zone link are both limited to 600 ML/day, which remains above the 500 ML/day demand.

---

## 7. Possible Infeasibility

Passing the basic flow check does not guarantee that the MILP will find a feasible solution.

The dry-year scenario could still become infeasible if:

- Database availability for a selected source is lower than the scenario link limit
- A required source is missing from the database or lacks a required quality value
- The available source blend cannot satisfy the pH constraint
- The available source blend cannot satisfy alkalinity or turbidity limits
- Source activation or link constraints prevent enough flow from reaching the treatment plant
- The treatment plant or plant-to-zone link cannot pass the required volume

The scenario is definitely infeasible from the simplified source-to-plant flow check when:

```text
Total enabled maximum source-to-plant flow < Required demand
```

This condition does not occur in the current dry-year scenario because:

```text
565 ML/day > 500 ML/day
```

However, the margin is only **65 ML/day**, so a lower database availability value or a quality restriction could make the dry-year solve infeasible.

---

## 8. JSON Structure and Validation

The normal-year and dry-year files use the same official input-contract structure.

### Intended differences

The intended differences in `scenario_dry_year.json` are:

1. Dry-year metadata:
   - `scenario_name`
   - `description`
2. Three documented `network.source_to_plant_links[].maximum_flow_ml_per_day` values

No unofficial fields are added to describe the dry-year assumptions. The reasoning and evidence are recorded in this Markdown document.

### Validation checklist

- [x] `scenario_normal.json` is an unchanged copy of the official model input contract
- [x] `scenario_dry_year.json` opens as valid JSON
- [x] Both files contain the same official top-level sections
- [x] Both files select the same three source IDs
- [x] Both files define the same plant, demand zone and network links
- [x] Only the documented metadata and maximum source-to-plant flow values differ
- [x] Demand remains 500 ML/day
- [x] Treatment-plant capacity remains 600 ML/day
- [x] Plant-to-zone maximum flow remains 600 ML/day
- [x] Quality limits remain unchanged
- [x] Data-source and validation settings remain unchanged
- [x] All scenario flow values use ML/day
- [x] No output-only fields such as selected volumes, blend percentages, total cost or solver status have been added

---

## 9. KPI Availability

| KPI | Availability | Explanation | Status |
|---|---|---|---|
| Total maximum source-to-plant flow | Available before solving | Sum of `network.source_to_plant_links[].maximum_flow_ml_per_day` | [x] Completed |
| Total supply reduction | Available before solving | Normal total minus dry-year total: 145 ML/day | [x] Completed |
| Overall reduction percentage | Available before solving | `(145 / 710) × 100 = 20.42%` | [x] Completed |
| Required demand | Available before solving | Read from `network.demand_zones[].demand_ml_per_day` | [x] Completed |
| Basic supply margin | Available before solving | Total maximum source-to-plant flow minus demand | [x] Completed |
| Solver feasibility status | Available after solving | Returned by the MILP solver | [ ] Pending MILP run |
| Selected source volumes | Available after solving | Decided by the MILP | [ ] Pending MILP run |
| Blend percentages | Available after solving | Calculated from selected source volumes | [ ] Pending MILP run |
| Total cost | Available after solving | Uses database source costs and treatment decisions | [ ] Pending MILP run |
| Binding constraints | Available after solving | Identified from solver constraint slack | [ ] Pending MILP run |
| Water-quality safety margins | Available after solving | Calculated from the solved blend against the quality limits | [ ] Pending MILP run |
| Separate energy-use KPI | Unavailable in the current formulation | Energy and chemical costs are folded into `treatment_cost_per_ml`; no separate energy term is defined | [ ] Unavailable |

---

## 10. Scope and Assumptions

The source set, network structure, demand and normal-year flow limits now align with the official toy-model input contract confirmed by the Optimisation team.

The dry-year reductions remain scenario assumptions:

- The 20% surface-water reduction uses the lower end of a documented Victorian drought-related streamflow decline range.
- The 25% groundwater reduction uses a Victorian allocation-management example as a proxy.
- The groundwater example is not Melbourne-specific, and the generic bore is not linked to a confirmed aquifer.
- Source costs, representative quality values and database daily availability are loaded from Supabase and are not redefined in these scenario files.

These assumptions should be revisited if the Optimisation or Data Engineering teams later connect the scenario to source-specific hydrological evidence or a confirmed groundwater management area.
