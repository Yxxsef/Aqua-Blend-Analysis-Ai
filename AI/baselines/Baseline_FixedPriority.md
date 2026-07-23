\# Fixed-Priority Baseline Heuristic



\## 1. Overview



This document defines an \*\*assumed fixed-priority heuristic\*\* for allocating water sources to satisfy water demand. This baseline method is created for comparison purposes and is \*\*not claimed to represent current operational practice\*\* unless supported by evidence from a water operator or published source.



The heuristic uses a predefined preference order for selecting water sources and allocates supply sequentially until demand is met or available supply is exhausted.



\*\*Units:\*\*

\- Volume: ML

\- Cost: AUD (where applicable)



\---



\## 2. Fixed Source Preference Order



The assumed source preference order is:



| Priority | Source Type | Justification |

|---|---|---|

| 1 | Surface Water Reservoirs | Used as the first preference due to high storage capacity and suitability as a primary supply source. |

| 2 | Recycled Water Sources | Used after surface water to utilise alternative supply and reduce dependence on limited sources. |

| 3 | Groundwater Sources | Used as a secondary backup source when higher-priority sources cannot satisfy demand. |

| 4 | Emergency Supply Sources | Used only when other available sources are insufficient. |



This ordering is an \*\*assumed heuristic preference order\*\* and does not represent actual water management decisions unless validated by operational evidence.



\---



\## 3. Fixed-Priority Allocation Rule



The heuristic follows these steps:



1\. Select the highest-priority active and connected water source.

2\. Allocate water from the selected source until:

&#x20;  - the remaining demand is satisfied, or

&#x20;  - the source capacity limit is reached.

3\. If demand remains, move to the next available source in the preference order.

4\. Continue allocating from available sources until:

&#x20;  - total demand is satisfied, or

&#x20;  - no additional supply remains.

5\. If the total available supply cannot satisfy demand, mark the result as \*\*infeasible\*\*.



\---



\## 4. Constraints and Assumptions



The heuristic respects the following constraints:



| Constraint | Description |

|---|---|

| Source Activation | Only sources marked as active can provide water. |

| Connectivity | A source must have a valid connection to the demand location before allocation. |

| Capacity | Allocated volume cannot exceed the available capacity of a source. |

| Demand Satisfaction | Allocation continues until demand is met or supply is exhausted. |



\---



\## 5. Numerical Example



\### Demand Requirement



Total water demand:



```

Demand = 100 ML

```



\### Available Water Sources



| Source | Source Type | Capacity (ML) | Activated | Connected |

|---|---|---:|---|---|

| Lake Reservoir | Surface Water Reservoir | 60 | Yes | Yes |

| Recycled Water Plant | Recycled Water Source | 30 | Yes | Yes |

| Bore Water Supply | Groundwater Source | 40 | Yes | Yes |



\### Allocation Process



\*\*Step 1: Surface Water Reservoir\*\*



\- Available capacity = 60 ML

\- Demand remaining = 100 ML

\- Allocate 60 ML



Remaining demand:



```

100 - 60 = 40 ML

```



\*\*Step 2: Recycled Water Source\*\*



\- Available capacity = 30 ML

\- Allocate 30 ML



Remaining demand:



```

40 - 30 = 10 ML

```



\*\*Step 3: Groundwater Source\*\*



\- Available capacity = 40 ML

\- Allocate 10 ML



Remaining demand:



```

10 - 10 = 0 ML

```



\### Final Allocation



| Source | Allocated Volume (ML) |

|---|---:|

| Lake Reservoir | 60 |

| Recycled Water Plant | 30 |

| Bore Water Supply | 10 |

| Total | 100 |



The total demand is satisfied, therefore the heuristic result is:



```

Status: Feasible

```



\---



\## 6. Infeasibility Handling



If all active and connected water sources are exhausted before meeting demand, the heuristic returns:



```

Status: Infeasible

Reason: Available water supply is insufficient to satisfy total demand.

```



Example:



If demand is 200 ML but total available supply is only 150 ML:



```

Demand = 200 ML

Available Supply = 150 ML



Result:

Infeasible

```



\---



\## 7. Output Schema Fields



The baseline heuristic uses the following schema fields:



| Field | Description |

|---|---|

| source\_name | Name of the selected water source |

| source\_type | Category/type of water source |

| priority | Priority ranking assigned to the source |

| activated | Indicates whether the source is available for allocation |

| connected | Indicates whether the source can supply the demand location |

| capacity\_ML | Maximum available capacity of the source in ML |

| allocated\_volume\_ML | Amount of water allocated from the source in ML |

| cost\_AUD | Cost associated with using the source in AUD (where applicable) |

| status | Final allocation result: Feasible or Infeasible |



These fields describe the selected source, allocation amount, availability conditions, cost information, and final feasibility status.

