# AquaBlend Evaluation KPI Set

> The KPI set has been validated using the current reference MILP output. Final validation across the normal-year, dry-year, high-demand, and plant-outage scenarios will be completed once the corresponding MILP result files are available.

## 1. Purpose

This document defines the six KPIs used to compare:

- baseline results against optimiser results;
- the normal scenario against dry-year, high-demand, and plant-outage scenarios; and
- feasible results against infeasible or incomplete results.

All calculations must use values from the approved MILP Results JSON. Feasibility, demand satisfaction, and quality compliance must be checked before cost or chemical comparisons are treated as successful.

## 2. General evaluation rules

1. **Feasibility is the first gate.** A cheaper result is not better if it is infeasible, unsafe, or incomplete.
2. **Demand and quality are mandatory.** A successful result must supply 100% of required demand and have zero quality violations.
3. **Cost and chemical KPIs are compared only between valid results.** Results must first be feasible, fully satisfy demand, and pass quality requirements.
4. **Missing values are never estimated.** Report `N/A` or `Unavailable` when an approved value is not present.
5. **Exact current field names are used.** In the current reference JSON, required demand is stored as `demand_ml_per_day` and supplied demand is stored as `volume_supplied_ml_per_day`.

## 3. KPI summary

| KPI | JSON path or formula | Unit | Better direction | Required target |
|---|---|---:|---|---|
| Feasibility | `$.status` | Status | Feasible is required | `OPTIMAL` or another explicitly verified feasible status |
| Demand satisfaction | `SUM($.demand_zones[*].volume_supplied_ml_per_day) / SUM($.demand_zones[*].demand_ml_per_day) * 100` | % | Higher | 100% |
| Total cost | `$.objective.total_cost` | `$.objective.currency`, currently AUD | Lower | Lowest among otherwise valid results |
| Minimum safety margin | Minimum of `$.water_quality.by_plant.*.*.safety_margin_percent` | % | Higher | At least 0%; positive margin preferred |
| Quality violations | Count failed parameters under `$.water_quality.by_plant.*.*` | Count | Lower | 0 |
| Chemical cost/use | Approved chemical cost or use field when present | AUD or exact chemical unit | Lower | Lowest among otherwise valid results |

## 4. KPI definitions

### KPI 1: Feasibility status

**Purpose**  
Confirms that the MILP produced a usable solution before any other KPI is treated as successful.

**Exact JSON path**  
`$.status`

**Formula**  
No numerical formula. Read the solver result status directly.

**Interpretation rule**

- `OPTIMAL`: feasible and optimal.
- `FEASIBLE`: feasible, if this status is officially supported by the MILP contract.
- `INFEASIBLE`: no feasible solution was found.
- `UNBOUNDED` or `ERROR`: not a valid result for KPI comparison.
- `TIME_LIMIT`: feasibility is not confirmed unless the MILP output explicitly verifies a feasible incumbent solution. The current reference JSON has no separate incumbent-feasibility field.

**Unit**  
Status category.

**Better direction**  
A verified feasible result is required. `OPTIMAL` is preferred when comparing solver completion.

**Required target**  
`OPTIMAL` or another explicitly verified feasible status.

**If data is missing**  
Report `UNKNOWN`. Treat the result as incomplete and do not mark the evaluation as successful.

**If the result is infeasible**  
Record the status as `INFEASIBLE`. Other KPIs may be shown only as diagnostics when their source data is complete, but they must not be treated as a successful result or compared as if feasible.

---

### KPI 2: Demand satisfaction

**Purpose**  
Measures whether the result supplies the complete required water demand across all demand zones.

**Exact JSON paths**

- Required demand: `$.demand_zones[*].demand_ml_per_day`
- Supplied demand: `$.demand_zones[*].volume_supplied_ml_per_day`

**Formula**

```text
Demand satisfaction (%) =
SUM(volume_supplied_ml_per_day) / SUM(demand_ml_per_day) * 100
```

**Unit**  
Percent (%).

**Better direction**  
Higher.

**Required target**  
100%.

**If data is missing**  
Report `N/A` if any required or supplied value needed for the total is missing. Do not assume a missing value is zero. If total required demand is zero, report `N/A` because the percentage would be undefined.

**If the result is infeasible**  
Calculate the percentage only when complete demand values are present, label it as diagnostic, and do not treat it as a pass. Otherwise report `N/A`.

---

### KPI 3: Total cost

**Purpose**  
Measures the total cost of the result so valid baselines, optimiser runs, and scenarios can be compared.

**Exact JSON paths**

- Value: `$.objective.total_cost`
- Currency: `$.objective.currency`
- Time basis or description: `$.objective.unit`

**Formula**  
No derived formula. Read `objective.total_cost` directly from the MILP output.

**Unit**  
AUD for one representative day in the current reference JSON.

**Better direction**  
Lower.

**Required target**  
No fixed AUD threshold. Select the lowest total cost only among results that are feasible, satisfy 100% of demand, and have zero quality violations.

**If data is missing**  
Report `N/A`. Do not reconstruct total cost from partial cost fields unless a separate calculation has been approved.

**If the result is infeasible**  
Report `N/A` for comparison purposes, even if the solver output contains a temporary objective value. An infeasible result cannot win a cost comparison.

---

### KPI 4: Minimum safety margin

**Purpose**  
Identifies the quality parameter closest to its allowed limit. This shows the smallest operating buffer in the result.

**Exact JSON path**  
`$.water_quality.by_plant.*.*.safety_margin_percent`

**Formula**

```text
Minimum safety margin (%) =
MIN(all available safety_margin_percent values across all plants and quality parameters)
```

**Unit**  
Percent (%).

**Better direction**  
Higher.

**Required target**  
At least 0%. A positive value is preferred. A value of 0% means the result is exactly at a limit and has no safety buffer. A negative value indicates a quality violation.

**If data is missing**  
Report `N/A` if no verified safety-margin values are available. If only some expected quality parameters are missing, report the calculated value as `Incomplete` rather than claiming it is the true overall minimum.

**If the result is infeasible**  
Use the value only as a diagnostic when the quality output is complete. It cannot make an infeasible result acceptable. Otherwise report `N/A`.

---

### KPI 5: Quality violations

**Purpose**  
Counts how many tested water-quality parameters failed their allowed limits.

**Exact JSON paths**

- Parameter status: `$.water_quality.by_plant.*.*.status`
- Safety-margin fallback check: `$.water_quality.by_plant.*.*.safety_margin_percent`

**Formula**

```text
Quality violations =
COUNT(parameters where status = "FAIL")
```

If a parameter has no status but has a verified negative `safety_margin_percent`, count it as one violation. Each plant-parameter pair is counted once.

**Unit**  
Number of failed quality parameters.

**Better direction**  
Lower.

**Required target**  
0.

**If data is missing**  
Report `N/A` or `Incomplete` when quality statuses are absent or when expected parameters are missing. Missing quality data must not be counted as zero violations.

**If the result is infeasible**  
Count violations only when complete quality results are available and label the value as diagnostic. The overall result remains unsuccessful because feasibility failed.

---

### KPI 6: Chemical cost or chemical use

**Purpose**  
Measures chemical spending or dosing so valid results can be compared for reduced chemical dependency.

**Exact JSON path**  
`N/A in the current reference Results JSON.`

A future calculation must use the exact MILP field approved for either:

- total chemical cost, in AUD; or
- total chemical use, using the exact reported dosing unit.

Chemical cost and chemical use must not be mixed in the same comparison column unless the unit and meaning are clearly identified.

**Formula**  
Read the approved total chemical value directly, or sum approved per-chemical values only when the MILP contract explicitly defines that calculation.

**Unit**  
AUD for chemical cost, or the exact chemical-use unit supplied by the MILP output.

**Better direction**  
Lower.

**Required target**  
No fixed threshold. Select the lowest value only among results that are feasible, satisfy 100% of demand, and have zero quality violations.

**If data is missing**  
Report `N/A` or `Unavailable`. Never create a chemical value from treatment cost or another unrelated field.

**If the result is infeasible**  
Report `N/A` for comparison purposes. Any available chemical value may be retained only as a clearly labelled diagnostic.

## 5. Manual calculation using the current reference JSON

**Scenario:** `scenario_2026_07_17_001`

| KPI | Manual calculation | Result |
|---|---|---:|
| Feasibility | `status = OPTIMAL` | Feasible and optimal |
| Demand satisfaction | `500 / 500 * 100` | 100% |
| Total cost | `objective.total_cost` | AUD 184,150 |
| Minimum safety margin | `MIN(30.5, 22.6, 34.0)` | 22.6% |
| Quality violations | pH = PASS, alkalinity = PASS, turbidity = PASS | 0 |
| Chemical cost/use | No separate verified chemical field exists | N/A |

## 6. Reporting format

- Demand satisfaction: percentage, normally rounded to one decimal place, but show `100%` when exact.
- Total cost: currency plus thousands separator, normally rounded to the nearest AUD unless the output requires decimals.
- Minimum safety margin: percentage rounded to one decimal place.
- Quality violations: whole number.
- Chemical KPI: preserve the exact unit from the approved MILP field; otherwise use `N/A`.

## 7. Future scenario testing

Add one row to `sample_kpi_calculations.csv` for each completed output from:

- normal-year scenario;
- dry-year scenario;
- high-demand scenario; and
- plant-outage scenario.

The same calculation and missing-data rules must be used for every scenario and baseline.
