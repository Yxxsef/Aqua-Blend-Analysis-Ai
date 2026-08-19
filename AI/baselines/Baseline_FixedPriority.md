# Fixed-Priority Baseline Heuristic

**Task:** Task 3 — Create Fixed-Priority Baseline Heuristic  
**Member:** Naga Kowshik  
**Project:** AquaBlend — Analysis & AI Team  
**Version:** Sprint 1 Draft (Updated)

---

## 1. Overview

This document defines a **fixed-priority heuristic** for allocating water sources to satisfy water demand. This baseline method is used as the reference allocation strategy for evaluating optimisation approaches. The allocation logic remains fixed and follows a predefined priority order for selecting water sources. The confirmed project water sources and capacities are used in the worked example below.

The heuristic allocates supply sequentially until demand is met or the available supply is exhausted.

**Units:**
- Volume: ML/day
- Cost: AUD (where applicable)

---

## 2. Fixed Source Preference Order

The fixed-priority baseline uses the confirmed project water sources in the following priority order.

| Priority | Water Source | Capacity (ML/day) | Justification |
|---|---|---:|---|
| 1 | Silvan Reservoir | 350 | Primary reservoir with the highest available capacity. |
| 2 | Yarra Kew | 300 | Secondary surface water source used after Silvan Reservoir. |
| 3 | Groundwater Bore 1 | 60 | Backup groundwater source used when higher-priority sources cannot satisfy demand. |

This priority order defines the baseline allocation strategy used for comparison with optimisation methods.

---

## 3. Fixed-Priority Allocation Rule

The heuristic follows these steps:

1. Select the highest-priority active and connected water source.

2. Validate the maximum daily withdrawal limit of the selected source before allocation.

3. Allocate water from the selected source up to the lower value between:
   - available source capacity (`sources[].capacity_ML`), and
   - maximum daily withdrawal limit (`sources[].max_daily_withdrawal_ML`).

4. Allocation continues until:
   - `demand_zones[].required_volume_ML` is satisfied, or
   - the validated daily withdrawal limit is reached.

5. If demand remains, move to the next available source in the preference order.

6. Continue allocating from available sources until:
   - `demand_zones[].required_volume_ML` is satisfied, or
   - no additional supply remains.

7. If the total available supply cannot satisfy `demand_zones[].required_volume_ML`, mark the result as **Infeasible**.

---

## 4. Constraints

The heuristic respects the following constraints:

| Constraint | Description |
|---|---|
| Source Activation | Only sources marked as active can provide water. |
| Connectivity | A source must have a valid connection to the demand location before allocation. |
| Capacity and Withdrawal Limit | Allocated volume cannot exceed `sources[].capacity_ML` or the validated maximum daily withdrawal limit `sources[].max_daily_withdrawal_ML`. |
| Demand Satisfaction | Allocation continues until `demand_zones[].required_volume_ML` is met or supply is exhausted. |

---

## 5. Numerical Example

### Demand Requirement

```text
Demand = 500 ML/day
```

### Available Water Sources

| Source | Capacity (ML/day) | Max Daily Withdrawal (ML/day) | Activated | Connected |
|---|---:|---:|---|---|
| Silvan Reservoir | 350 | 350 | Yes | Yes |
| Yarra Kew | 300 | 300 | Yes | Yes |
| Groundwater Bore 1 | 60 | 60 | Yes | Yes |

> **Note:** Separate maximum daily withdrawal limits have not been provided. For this worked example, the confirmed source capacities are used as the withdrawal limits so that the fixed-priority allocation logic remains unchanged.

### Allocation Process

#### Step 1 – Silvan Reservoir

- Available capacity = **350 ML/day**
- Maximum daily withdrawal = **350 ML/day**
- Allocate **350 ML/day**

Remaining demand:

```text
500 − 350 = 150 ML/day
```

---

#### Step 2 – Yarra Kew

- Available capacity = **300 ML/day**
- Maximum daily withdrawal = **300 ML/day**
- Allocate **150 ML/day**

Remaining demand:

```text
150 − 150 = 0 ML/day
```

Demand has now been fully satisfied.

---

#### Step 3 – Groundwater Bore 1

No allocation is required because the demand has already been satisfied.

---

### Final Allocation

| Source | Allocated Volume (ML/day) |
|---|---:|
| Silvan Reservoir | 350 |
| Yarra Kew | 150 |
| Groundwater Bore 1 | 0 |
| **Total** | **500** |

The required demand is fully satisfied using the first two priority sources.

```text
Status: Feasible
```

---

## 6. Infeasibility Handling

If all active and connected water sources reach their validated maximum daily withdrawal limits before meeting demand, the heuristic returns:

```text
Status: Infeasible

Reason: Available daily withdrawal capacity is insufficient to satisfy total demand.
```

### Example

```text
Demand = 800 ML/day
```

Available Daily Withdrawal:

- Silvan Reservoir = 350 ML/day
- Yarra Kew = 300 ML/day
- Groundwater Bore 1 = 60 ML/day

```text
Total Available Daily Withdrawal = 710 ML/day
```

Since:

```text
710 < 800
```

the result is:

```text
Status: Infeasible
```

---

## 7. Output Schema Fields

The baseline heuristic uses the following schema fields:

| Field | Description |
|---|---|
| source_name | Name of the selected water source |
| source_type | Category/type of water source |
| priority | Priority ranking assigned to the source |
| activated | Indicates whether the source is available for allocation |
| connected | Indicates whether the source can supply the demand location |
| capacity_ML | Maximum available capacity of the source in ML/day |
| max_daily_withdrawal_ML | Maximum volume that can be withdrawn from the source per day in ML/day |
| allocated_volume_ML | Amount of water allocated from the source in ML/day |
| cost_AUD | Cost associated with using the source in AUD (where applicable) |
| status | Final allocation result: **Feasible** or **Infeasible** |

These fields describe the selected source, allocation amount, availability conditions, withdrawal limits, cost information, and the final feasibility status.