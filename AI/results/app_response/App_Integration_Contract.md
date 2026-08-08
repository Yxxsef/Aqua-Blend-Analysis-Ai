# App & Delivery Integration Contract — Task 27

**Version:** `0.1-draft`  
**Owner:** Amantha Kulathunga  
**Purpose:** Define one predictable response shape that App & Delivery can render while Tasks 19, 21, 23, 25 and 26 are still being completed.

> This document contains the first draft of the Task 27 App & Delivery integration contract. It is based on the current MILP input and output contracts. The outer response shape and Task 27 `report_mode` values are defined here, while payloads owned by unfinished upstream tasks are intentionally marked **Draft / pending upstream contract** until those interfaces are finalised.

---

## 1. Scope and responsibility

Task 27 acts as an **adapter layer**. It does not replace the solver, KPI calculator, result validator, confidence flagger, LLM reporting pipeline, or comparison logic owned by other tasks.

The intended flow is:

```text
MILP input / scenario
        |
        v
MILP solve -> raw MILP output
        |
        +--> Task 19: KPIs + pass/fail gate
        +--> Task 21: result validation + confidence flag
        +--> Tasks 23/25: fallback / validated LLM explanation
        +--> Task 26: scenario/baseline comparison
        |
        v
Task 27: app_response_adapter.py
        |
        v
One display-oriented JSON response
        |
        v
App & Delivery UI
```

The adapter must **not overwrite or reshape the raw MILP result in place**. It creates a new response object so the raw result remains independently available for audit/debugging and for other analysis components.

---

## 2. Reference MILP input/output used for this draft

The current reference toy scenario and its matching MILP output are used as realistic data for the mock responses and tests in this draft.

The reference input scenario contains:

- `scenario_id`: `scenario_2026_07_17_001`
- three enabled sources: `silvan_reservoir`, `yarra_kew`, `groundwater_bore_1`
- one plant: `facility_1`
- one demand zone: `zone_1`
- required demand: `500 ML/day`
- plant maximum processing capacity: `600 ML/day`
- source-to-plant link capacities of `350`, `300`, and `60 ML/day`
- water-quality limits applied to `blend_at_plant_inflow`

The matching MILP output is `OPTIMAL` and reports:

- total cost: `AUD 184150.00` for one representative day
- Silvan Reservoir: `210 ML/day` (`42%` of blend)
- Yarra Kew: `290 ML/day` (`58%` of blend)
- Groundwater Bore 1: unused
- demand supplied: `500 ML/day`
- plant processed volume: `500 ML/day`
- pH `7.11`, alkalinity `38.04 mg/L CaCO3`, turbidity `5.28 NTU`, all reported as `PASS`

These values are used only as **mock/reference data** for the draft examples. They do not define the final Task 19 KPI contract, Task 21 confidence enum, or Task 26 comparison structure.

---

## 3. Draft App response shape

The draft defines the following top-level response shape for App & Delivery:

```json
{
  "contract_version": "0.1-draft",
  "scenario_id": "scenario_2026_07_17_001",
  "solver_status": "OPTIMAL",
  "kpis": {},
  "gate_result": "PASS",
  "confidence_flag": "UNKNOWN",
  "comparison": null,
  "report_mode": "LLM_VALIDATED",
  "display_explanation": "Operator-readable explanation.",
  "warnings": []
}
```

### Field definitions

| Field | Type | Status | Source / rule |
|---|---|---|---|
| `contract_version` | string | **Stable for this draft** | Task 27 contract version. |
| `scenario_id` | string or null | **Stable field** | Normally copied from the MILP output, which must match the input scenario ID. `null` is allowed only if invalid input prevents an ID being recovered. |
| `solver_status` | string or null | **Stable enum from MILP output** | `OPTIMAL`, `INFEASIBLE`, `UNBOUNDED`, `TIME_LIMIT`, `ERROR`. `null` is used for `INVALID_INPUT` where the solver was not run/trusted. |
| `kpis` | object or null | **Draft / Task 19** | Passed through from Task 19. Task 27 does not calculate KPI values. `null` for invalid or non-optimal results. |
| `gate_result` | string or null | **Draft / Task 19** | Pass/fail gate value supplied by Task 19. Exact enum is pending Task 19's final contract. |
| `confidence_flag` | string or null | **Draft / Task 21** | Confidence value supplied by Task 21. Exact enum is pending Task 21's final contract. |
| `comparison` | object or null | **Draft / Task 26** | Scenario/baseline comparison supplied by Task 26 when available. `null` otherwise. |
| `report_mode` | string | **Stable Task 27 enum** | One of the four modes documented in Section 5. |
| `display_explanation` | string | **Stable field; content source is draft** | Text the App can display. Content comes from Tasks 23/25 or a status-only message. |
| `warnings` | array of strings | **Stable container; wording may evolve** | Upstream warnings plus safe contract-derived display warnings. |

### Why `kpis`, `gate_result`, `confidence_flag`, and `comparison` are not finalised here

These values belong to dependent tasks that are still being completed. Their positions and broad types are retained in the App response while their internal fields and enums remain open for the relevant upstream tasks to finalise. This avoids duplicating KPI formulas, gate rules, confidence logic, or comparison semantics inside Task 27.

---

## 4. Solver status values

The solver status values are taken directly from the current MILP output contract:

| Status | App behaviour |
|---|---|
| `OPTIMAL` | Solution data may be displayed. Reporting can be `LLM_VALIDATED`, `TEMPLATE_FALLBACK`, or `STATUS_ONLY`. |
| `INFEASIBLE` | `STATUS_ONLY`; do not display optimal-solution KPIs/comparisons. |
| `UNBOUNDED` | `STATUS_ONLY`; do not display optimal-solution KPIs/comparisons. |
| `TIME_LIMIT` | `STATUS_ONLY`; do not present the result as an optimal answer. |
| `ERROR` | `STATUS_ONLY`; show status/error information only. |

The MILP output specification states that `OPTIMAL` is the only status for which the solution blocks are meaningful. Based on that rule, the adapter clears `kpis` and `comparison` whenever the solver status is not `OPTIMAL`, even if stale values are accidentally supplied by a caller.

---

## 5. `report_mode` values

Task 27 requires the following report modes, which are included directly in the draft contract.

### `LLM_VALIDATED`

Use when:

- input is valid;
- solver status is `OPTIMAL`;
- an LLM explanation is available; and
- the upstream reporting/validation step confirms that explanation is valid.

App behaviour: display the validated explanation and any warnings.

### `TEMPLATE_FALLBACK`

Use when:

- input is valid;
- solver status is `OPTIMAL`;
- a validated LLM explanation is unavailable; and
- the deterministic fallback explanation from the reporting pipeline is available.

App behaviour: display the deterministic explanation and a warning that fallback mode is being used.

### `STATUS_ONLY`

Use when:

- solver status is non-optimal; or
- an optimal result exists but no validated LLM explanation or deterministic fallback is available.

App behaviour: display status and warning information without presenting a full report. For non-optimal results, solution KPIs/comparisons are not displayed.

### `INVALID_INPUT`

Use when scenario/input validation fails before a trustworthy solve is available.

App behaviour: display an input-validation error. `solver_status`, `kpis`, `gate_result`, `confidence_flag`, and `comparison` may be `null` because downstream solve/analysis steps were not reached.

> **Draft integration rule:** The exact upstream signal names that trigger LLM success/failure are still pending Tasks 23 and 25. The draft exposes `llm_validated`, `llm_explanation`, and `fallback_explanation` as adapter inputs so they can later be connected to the final upstream contract without changing the outer App response shape.

---

## 6. Warning behaviour

The adapter combines warnings supplied by upstream components with a small number of warnings that are directly supported by the current MILP contract.

Using the current reference result, the adapter can safely warn that:

1. one or more source inputs contain estimated values;
2. source activation cost is currently structurally zero because the source input path does not supply the corresponding fixed activation cost; and
3. the reported water-quality values apply to the blend at plant inflow, not post-treatment regulatory quality.

Mode-specific warnings are also added for:

- `TEMPLATE_FALLBACK` — validated LLM explanation unavailable;
- non-optimal `STATUS_ONLY` — no optimal-solution metrics/comparisons should be displayed; and
- `INVALID_INPUT` — scenario validation failed and a solver result is not available for display.

The exact warning text or severity can be refined with App & Delivery once their display requirements are final. For this draft, the consistent part of the contract is that every response contains a `warnings` array.

---

## 7. Raw MILP result preservation

One of the Task 27 requirements is that the raw MILP result must not be overwritten. The following pattern should therefore be avoided:

```python
milp_result["kpis"] = ...
milp_result["report_mode"] = ...
milp_result["confidence_flag"] = ...
```

Instead, the adapter returns a new object:

```python
response = build_app_response(
    milp_result,
    kpis=task19_kpis,
    gate_result=task19_gate,
    confidence_flag=task21_confidence,
    comparison=task26_comparison,
    llm_explanation=task25_text,
    llm_validated=True,
)
```

`app_response_adapter.py` deep-copies the values it needs. The test suite also verifies that the original MILP dictionary remains unchanged after the adapter runs.

---

## 8. Mock package

The `examples/` responses provide App & Delivery with stable sample payloads while end-to-end integration is still incomplete.

### `examples/success_response.json`

Represents an `OPTIMAL` solve with a validated LLM explanation (`LLM_VALIDATED`). The mock KPI values are based on the current reference input/output example, but their final naming and structure remain owned by Task 19.

### `examples/fallback_response.json`

Represents an `OPTIMAL` solve where the validated LLM path is unavailable and a deterministic explanation is displayed (`TEMPLATE_FALLBACK`).

### `examples/error_response.json`

Represents a non-optimal `INFEASIBLE` solver result (`STATUS_ONLY`). It deliberately contains no solution KPIs or comparison payload.

### `examples/invalid_input_response.json`

Provides additional coverage for `INVALID_INPUT`. It shows what App & Delivery receives when validation fails before a trustworthy solver result exists.

---

## 9. Structural validation

`validate_app_response()` provides dependency-free structural validation for the draft response. It verifies that:

- every required top-level field exists;
- solver status is documented;
- report mode is one of the four required values;
- `kpis` and `comparison` are objects or `null`;
- `gate_result` and `confidence_flag` are strings or `null`;
- `display_explanation` is a non-empty string;
- `warnings` is a list of non-empty strings;
- invalid/non-optimal responses do not expose optimal-solution KPI/comparison data; and
- LLM/fallback report modes are used only with an `OPTIMAL` result.

`test_app_response_adapter.py` tests the success, fallback, non-optimal, and invalid-input branches, confirms that the mock JSON examples pass structural validation, and verifies that the raw MILP result is not mutated.

The tests can be run from the Task 27 folder with:

```bash
python -m unittest -v test_app_response_adapter.py
```
