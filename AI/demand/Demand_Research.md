# Demand Research: Toy-Model Demand Value

- **Task:** 4. Research and select the toy-model demand value

- **Owner:** Mansoor Shaik

- **Sprint:** Analysis and AI, Sprint 1

- **Deliverables:** `Demand_Research.md`, `toy_demand_value.json`

- **Units:** Volume in ML. Time period stated for every figure.


---

## 1. Purpose

Task 4 requires a published water-demand figure to be found, recorded, converted, and then related to the demand value used in the toy model. This document keeps the original published figure and the smaller toy-model value clearly separated, and states the final value for `demand_zones[].required_volume_ML`.

The toy model is the proof-of-concept described in the AquaBlend MILP Configuration (Scope 1). It uses a single demand zone supplied by three sources of different types: a reservoir, a river extraction point, and a groundwater bore. It is sized so that no single source can meet demand alone, but the connected sources together can.

The toy-model demand of 500 ML/day and the three source capacities used below are the values confirmed by the Optimisation team in the official toy-model configuration. This document does not select those values independently. Its purpose is to record the published demand data behind them, show the unit conversions, reconcile 500 ML/day against that published data, and confirm that the value is reasonable against the confirmed source capacities.

---

## 2. Published demand figures (original, unscaled)

### 2.1 Primary source: Melbourne Water Open Data Hub daily usage

The provided dataset `melbourne_water_5_year_complete.csv` is Melbourne Water Open Data Hub system data, the same source the configuration already uses for reservoir identity and volume. It contains a real, dated system-wide demand series in the `daily_usage_ML` column.

| Statistic | Value | Time basis |
|---|---|---|
| Coverage | 24 July 2021 to 24 July 2026 (1,826 daily values) | daily |
| 5-year mean daily usage | 1,284 ML | ML/day |
| 2025 full-year mean | 1,344 ML | ML/day |
| Minimum recorded | 775 ML | ML/day |
| Maximum recorded (peak) | 2,190 ML | ML/day |

Original published system-demand figure adopted for this document: **1,284 ML/day** (5-year mean, whole-of-Melbourne system).

Publication basis: rolling daily data, most recent value 24 July 2026.

### 2.2 Corroborating source: Melbourne's Annual Water Outlook 2026

Melbourne's Annual Water Outlook 2026 (Melbourne Water, published December 2025, quarterly update 1 March 2026) reports residential water use of about 166 litres per person per day over the most recent 12 months, and 169 litres per person per day in 2024/25.

URL: https://www.melbournewater.com.au/about/publications/water-outlook

### 2.3 Basis of the figure and cross-check between sources

The `daily_usage_ML` series is total system demand: it covers residential plus business (commercial and industrial) use plus system losses, not residential consumption alone. The two published sources reconcile on that basis:

Greater Melbourne population is approximately 5.3 million (Melbourne Water reports growth of about 140,000 in the last year).

- Residential demand implied by the published per-capita figure: 166 L/person/day x 5,300,000 people = about 880 ML/day residential.
- System mean from the dataset: 1,284 ML/day (all uses).
- Residential share implied: 880 / 1,284 = about 69 percent, leaving about 31 percent for business use and system losses.
- Total per-capita implied by the dataset: 1,284 ML/day / 5,300,000 people = about 242 L/person/day (all uses).

A residential share near two-thirds of total system demand is consistent for a large metropolitan system, so the two independent public sources agree. The dataset figure of 1,284 ML/day (total per-capita about 242 L/person/day) is the authoritative original value and the basis for the reconciliation in Section 4, because a demand zone must be supplied for all its uses, not residential only.

---

## 3. Unit conversions

All conversions use 1 GL = 1,000 ML and 1 ML = 1,000,000 L.

| From | Calculation | To |
|---|---|---|
| 1,284 ML/day (system mean) | 1,284 x 365 | 468,660 ML/year (about 469 GL/year) |
| 1,284 ML/day over 5.3 million people | 1,284,000,000 L / 5,300,000 | about 242 L/person/day (total, all uses) |
| 500 ML/day (confirmed toy value) | 500,000,000 L / 242 L/person/day | about 2,066,000 people implied (see Section 4) |
| 500 ML/day (confirmed toy value) | 500 x 365 | 182,500 ML/year |

---

## 4. The toy-model demand value and how it relates to published demand

### 4.1 Why the toy value sits below Melbourne's real demand

The toy model is not a model of Melbourne. It is a reduced-scale model, sized so the MILP mathematics can be checked by hand before the model is grown. Both the supply side and the demand side are reduced together, so the absolute numbers are smaller than the real system but the relationship between them stays realistic.

| | Real Melbourne system | Toy model |
|---|---|---|
| People served | about 5.3 million | one demand zone (about 2,066,000 implied) |
| Sources | 10 reservoirs plus desalination | 3 mixed sources (`silvan_reservoir`, `yarra_kew`, `groundwater_bore_1`) |
| Daily supply available | the whole system | 710 ML/day (sum of the three confirmed capacities) |
| Daily demand | about 1,284 ML/day | 500 ML/day |

The real system demand of 1,284 ML/day cannot be placed on the toy, because the three toy sources supply only 710 ML/day between them. A demand of 1,284 against 710 would be trivially infeasible and would prove nothing about the model's logic. The confirmed toy demand of 500 ML/day is about 39 percent of real system demand, matched to a toy supply that is a similar fraction of the real system.

This matches the configuration, which calls for a single demand zone sized so no single source can meet demand alone, on a toy simple enough to validate by hand. The full-scale demand near 1,300 ML/day belongs to the later fuller representative configuration (eleven reservoirs, eighteen sources), not to this toy.

### 4.2 Method: reconciling the confirmed value against published per-capita demand

The demand value of 500 ML/day is a confirmed configuration input from the Optimisation team, so it is not derived from the ground up here. The method below works in the opposite direction: it takes the published total per-capita rate from Section 2 and asks what served population 500 ML/day corresponds to, so that the confirmed value carries a traceable basis in published data rather than standing as a bare number.

- Total per-capita rate: 1,284 ML/day / 5,300,000 people = about 242 L/person/day. This is the whole-of-system rate and, unlike the residential-only figure of 166 L/person/day, it already includes non-residential (business and industrial) demand and system losses, which is what a demand zone must actually be supplied.
- Confirmed toy demand: 500 ML/day.

Implied served population:

```
500 ML/day / 242 L/person/day
= 500,000,000 L/day / 242 L/person/day
= about 2,066,000 people
```

Checked in the forward direction, the same two figures reproduce the confirmed value:

```
242 L/person/day x 2,066,000 people
= 499,972,000 L/day
= about 500 ML/day
```

**Final toy-model demand = 500 ML/day (confirmed configuration value).**

The implied served population of about 2,066,000 is an assumed toy-model characterisation, not a measured service area. Section 4.3 sets out why a zone of this size is a reasonable reading of the confirmed demand.

### 4.3 Plausibility of the implied served population of about 2,066,000

Because the implied population is what gives the confirmed 500 ML/day a real-world meaning, it is checked on two independent grounds: it must correspond to a recognisable part of Melbourne's water system, and it must sit inside the window that makes the toy a genuine blending problem.

**Ground 1: it corresponds to a major metropolitan supply region rather than a single council area.**

Greater Melbourne's roughly 5.3 million residents are spread across 31 metropolitan local government areas, an average of about 171,000 residents each, with mid-sized councils such as the City of Monash at 209,268 and the City of Whitehorse at 183,462 at 30 June 2024. An implied population of about 2,066,000 is therefore not one council area but a grouping equivalent to roughly twelve mid-sized LGAs, or about 39 percent of Greater Melbourne.

A zone of that scale is consistent with the confirmed source set. Silvan is a principal distribution point in Melbourne's supply system rather than a local storage, and it feeds a large share of the eastern and south-eastern metropolitan area; a Yarra extraction at Kew and a production bore are likewise system-scale inputs rather than local ones. Three sources of that type, with capacities in the hundreds of ML/day, would not be assigned to a zone of a couple of hundred thousand people. The earlier version of this document used a single mid-sized council area of about 207,000, which suited a reservoir-only toy with caps in the tens of ML/day. With the confirmed capacities the matching demand zone is regional, and the implied population moves with it. No claim is made that 2,066,000 is the measured population of any specific Melbourne Water service area.

**Ground 2: it lands the demand inside the window that makes the toy non-trivial.**

The toy is only useful if demand is above the largest single source capacity (so no source can meet it alone) and no greater than the sum of the capacities (so a blend is feasible). Against the confirmed capacities in Section 6, that window is above 350 and up to 710 ML/day, which at 242 L/person/day corresponds to a served population above about 1,446,000 and up to about 2,934,000. The confirmed 500 ML/day, and its implied 2,066,000, sits inside that band with room on both sides.

Sensitivity of the toy's validity across the window:

| Implied population | Demand (ML/day) | Toy still valid? |
|---|---|---|
| about 1,446,000 | 350 | No, equals the largest single capacity |
| about 2,066,000 (confirmed value) | 500 | Yes, inside the window |
| about 2,934,000 | 710 | No, exhausts total supply with zero headroom |

The two grounds agree. A regional supply area of roughly two million people is both the natural scale for a reservoir, a river extraction and a bore operating together, and the population that, at Melbourne's total per-capita rate, produces a demand inside the feasible blending window.

### 4.4 Cross-check: fraction of system demand

500 ML/day is 500 / 1,284 = about 39 percent of Melbourne's mean system demand. A single zone drawing roughly two fifths of total system demand from three sources is a reasonable proportion for a proof-of-concept fragment of a system that has ten reservoirs plus desalination, particularly when one of those three sources is Silvan, which in the real system is a major distribution point rather than a minor storage. The per-capita method and the fraction method agree that a value in the hundreds of ML/day is the correct order of magnitude for this source set.

---

## 5. Final value

| Field | Value |
|---|---|
| `demand_zones[].required_volume_ML` | **500** |
| Time basis | per day (ML/day) |
| Annual equivalent | 182,500 ML/year |
| Status | confirmed configuration value (Optimisation team, official toy-model configuration) |
| Reconciliation | about 2,066,000 people implied x 242 L/person/day (total per-capita) |
| Original published system figure (kept separate) | 1,284 ML/day system mean (total, all uses); 242 L/person/day total per-capita |

---

## 6. Reasonableness against the confirmed source capacities

The source set and the per-source daily-extractable capacities used below are the values confirmed by the Optimisation team in the official toy-model configuration. They are configuration inputs rather than published Melbourne Water safe-yield figures, and they supersede the provisional reservoir-only capacities used in the earlier version of this document.

### 6.1 Calibration rule the demand must satisfy

1. No single source daily-extractable capacity is greater than or equal to demand (so no single source meets demand alone).
2. The sum of connected source daily-extractable capacities is greater than or equal to demand (so the blend is feasible).

### 6.2 Calibration check against the confirmed capacities

Confirmed toy source set. The toy is no longer reservoir-only: it now mixes a surface storage, a river extraction point and a groundwater bore.

| Toy source | Type | Daily-extractable capacity (ML/day) | Role |
|---|---|---|---|
| `silvan_reservoir` | Surface storage. Silvan Reservoir, full-supply capacity 40,445 ML per `melbourne_reservoir_daily_history.csv` | 350 | large / primary |
| `yarra_kew` | Surface water extraction from the Yarra River at Kew. No storage volume, so the capacity is a withdrawal rate only | 300 | mid |
| `groundwater_bore_1` | Groundwater bore. No storage volume, so the capacity is an extraction rate only | 60 | small / backup |
| Total | | 710 | |

Against demand of 500 ML/day:

- Largest single daily capacity = 350 ML/day, which is less than demand of 500 ML/day. Rule 1 holds: no single source meets demand alone.
- Sum of daily capacities = 710 ML/day, which is greater than demand of 500 ML/day. Rule 2 holds: the blend is feasible.
- Largest source is 350 of 710 = about 49 percent of the three-source total, below the 60 to 65 percent level at which one source would swamp the blend. The toy is a genuine blending problem, and the split is more even than in the earlier reservoir-only set.
- Every feasible solution must draw on at least two sources, and specifically on both `silvan_reservoir` and `yarra_kew`. Dropping either leaves at most 410 ML/day (350 plus 60) or 360 ML/day (300 plus 60), both short of 500. The model therefore cannot solve on a single source, and the two large sources are structurally required.
- `groundwater_bore_1` is not required in the baseline, because `silvan_reservoir` plus `yarra_kew` supply 650 ML/day against demand of 500. Its binary activation variable stays off in the baseline and only switches on under stress, for example a dry-year or capacity-reduction scenario. This exercises the MILP on/off activation logic, which is one of the behaviours the toy model exists to validate.
- Headroom = 710 minus 500 = 210 ML/day, about 42 percent above demand and about 30 percent of total available capacity. That is enough slack for the optimiser to trade sources off against each other, while still allowing a later capacity-reduction scenario to push the model toward infeasibility, which is what makes that scenario test meaningful.

Both calibration rules hold on the confirmed values, so the demand value of 500 ML/day and the confirmed capacities of 350, 300 and 60 ML/day are mutually consistent and ready for the Task 5 hand validation.

### 6.3 Superseded source analysis

The earlier version of this document worked from a reservoir-only assumption. It tested candidate reservoir trios against the two calibration rules, excluded Thomson and Upper Yarra as too large for a demand in the tens of ML/day, selected Sugarloaf, Silvan and O'Shannassy, and resolved the names "Barawon" and "Yashai127" as water quality monitoring station identifiers rather than reservoirs. That analysis is superseded. The confirmed configuration is not reservoir-only, the source set is fixed as `silvan_reservoir`, `yarra_kew` and `groundwater_bore_1`, and the capacities are confirmed, so no source-selection question remains open at this task. The record is kept here only so the change of basis is traceable. Silvan is the one source carried across from the earlier set.

---

## 7. Limitations

1. The per-capita rate (about 242 L/person/day) is a whole-of-system total, covering residential plus business plus system losses, consistent with the total `daily_usage_ML` series. It is derived by dividing total system demand by population, so it also carries any non-revenue water and loss in that total. It is not a billed-consumption figure.
2. The implied served population of about 2,066,000 is a reconciliation of the confirmed demand value against published per-capita demand, not a measured demand zone. Section 4.3 tests the size against Melbourne LGA populations and against the calibration window, but the zone remains representative rather than an actual Melbourne Water service area boundary.
3. Demand is treated as a single steady daily value. Real demand is seasonal, with the dataset showing a summer peak of 2,190 ML/day against a mean of 1,284 ML/day. Peak-demand behaviour is a scenario concern (Task 11 high-demand scenario), not part of the baseline toy value.
4. The confirmed source capacities of 350, 300 and 60 ML/day are official configuration inputs from the Optimisation team, not published Melbourne Water safe-yield or maximum-daily-withdrawal figures. The datasets used here carry storage volumes for reservoirs only, so no independent public capacity figure exists for `yarra_kew` or `groundwater_bore_1` against which the 300 and 60 ML/day values could be checked.
5. The value applies to the Scope 1 public-data proof-of-concept only and is not an operational recommendation.

---

## 8. Task 4 checklist mapping

| Checklist item | Where addressed |
|---|---|
| At least one reliable public source is cited | Sections 2.1, 2.2, 9 |
| Publication date is recorded | Sections 2.1 (data to 24 July 2026), 2.2 (Dec 2025 / Mar 2026) |
| Original demand value is recorded | Section 2.1 (1,284 ML/day) |
| Time basis is clear (ML/day or ML/year) | Sections 2, 3, 5 (per day, with annual equivalents) |
| Unit conversions are shown | Section 3 |
| Any scaling for the toy model is explained | Section 4 |
| Final value for `demand_zones[].required_volume_ML` is stated | Section 5 (500 ML/day) |
| Final value is reasonable compared with source capacities | Section 6 (both rules hold against 350, 300 and 60) |
| Duplicated research is avoided | Section 6 (source set and capacities taken from the Optimisation team's confirmed configuration rather than researched again) |
| Limitations are stated | Section 7 |

---

## 9. Sources

1. Melbourne Water Open Data Hub system data, provided as `melbourne_water_5_year_complete.csv`, coverage 24 July 2021 to 24 July 2026. Column `daily_usage_ML`.
2. Melbourne's Annual Water Outlook 2026, Melbourne Water, published December 2025 with quarterly update 1 March 2026. https://www.melbournewater.com.au/about/publications/water-outlook
3. AquaBlend official toy-model configuration, Optimisation team. Source of the confirmed demand value of 500 ML/day, the source set `silvan_reservoir`, `yarra_kew` and `groundwater_bore_1`, and the daily-extractable capacities of 350, 300 and 60 ML/day.
4. Melbourne Water daily reservoir history, provided as `melbourne_reservoir_daily_history.csv`, coverage 1 January 2000 to 24 July 2026. Per-reservoir full-supply capacity and daily volume for the ten major Melbourne Water reservoirs (Thomson, Cardinia, Upper Yarra, Sugarloaf, Silvan, Tarago, Yan Yean, Greenvale, Maroondah, O'Shannassy). Used here for the Silvan full-supply capacity of 40,445 ML.
5. Melbourne Water water storage reservoirs, including Silvan's role in the supply system. https://www.melbournewater.com.au/water-and-environment/water-management/water-storage-reservoirs
6. Australian Bureau of Statistics, Regional Population, estimated resident population by local government area at 30 June 2024. City of Monash 209,268; City of Whitehorse 183,462. https://profile.id.com.au/monash/about
7. Local government areas of metropolitan Melbourne (31 LGAs across Greater Melbourne). https://en.wikipedia.org/wiki/Category:Local_government_areas_in_Melbourne