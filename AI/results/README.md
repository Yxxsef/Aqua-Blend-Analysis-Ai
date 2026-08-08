# Results JSON Validator, Adapter and Confidence Flags

## Overview

This module provides validation, adaptation and confidence checking for AquaBlend Results JSON output.

The purpose is to ensure that optimisation results received from the MILP layer are complete, consistent and safe to use by downstream systems.

The implementation supports:
- Results JSON validation
- Stable internal result adaptation
- Confidence disclosure based on source provenance
- Automated testing for valid, incomplete, malformed and provenance scenarios

---

## Components

### results_validator.py

The Results JSON validator checks that required fields exist and contain valid data.

Validated areas include:

- Scenario information
- Solver status
- Source allocations
- Demand information
- Cost information
- Constraints
- Quality stage
- Diagnostics

The validator returns clear errors when:
- Required fields are missing
- Data types are incorrect
- Results structure is malformed

The validator does not modify the original Results JSON contract.

---

### results_adapter.py

The adapter provides a stable internal representation of Results JSON.

The external MILP Results JSON field names remain unchanged.

Any internal naming differences are handled only inside the adapter layer.

This allows:
- Safe integration between teams
- Future MILP contract updates
- Consistent internal processing

---

### confidence_flagger.py

The confidence flagger determines whether optimisation results rely on estimated or confirmed data.

Confidence levels:

| Flag | Meaning |
|---|---|
| PROVISIONAL | Estimated source values were used |
| MEASURED | All contributing sources have confirmed measured data |
| UNKNOWN | Provenance information is missing |

If estimated values are detected, the affected source IDs are returned.

---

## Confidence Behaviour

### PROVISIONAL

Returned when any contributing source contains:

```json
"has_estimated_values": true
```

Example:

```json
{
    "confidence": "PROVISIONAL",
    "estimated_sources": [
        "groundwater_bore_1"
    ]
}
```

The output identifies which sources relied on estimated values.

---

### MEASURED

Returned only when all contributing sources confirm that no estimated values were used.

Example:

```json
"has_estimated_values": false
```

Example output:

```json
{
    "confidence": "MEASURED",
    "estimated_sources": []
}
```

---

### UNKNOWN

Returned when provenance information is missing and the system cannot confirm whether values are measured or estimated.

Example:

```json
{
    "source_id": "silvan_reservoir"
}
```

Output:

```json
{
    "confidence": "UNKNOWN"
}
```

---

## Testing

Tests are located in:

```
AI/results/tests/
```

Run all Task 21 tests using:

```bash
python -m pytest AI/results/tests/
```

Current test result:

```
9 passed
```

Test coverage includes:

### Validator Tests

- Valid Results JSON
- Missing required fields
- Invalid data types
- Malformed input handling

### Adapter Tests

- Successful field adaptation
- Missing field handling
- Invalid input handling

### Confidence Tests

- PROVISIONAL results with estimated sources
- MEASURED results with confirmed provenance
- UNKNOWN results with missing provenance

---

## Task 21 Deliverables Completed

Implemented:

- Results JSON validator
- Stable internal adapter
- Confidence flagging system
- Validator tests
- Adapter tests
- Confidence flag tests
- Sample flagged output
- Results JSON field mapping documentation

---

## Design Notes

- External MILP Results JSON field names remain unchanged.
- Internal naming changes are handled only inside the adapter.
- Optional fields such as alternatives, sensitivity and explanations are handled safely.
- Estimated data usage is disclosed through confidence flags.
- Optimisation results remain the source of truth.
- Confidence flags only describe data reliability and do not modify optimisation decisions.

---

## File Structure

```
AI/results/

├── results_validator.py
├── results_adapter.py
├── confidence_flagger.py
├── sample_flagged_output.json
├── Results_JSON_Field_Map.md
├── README.md
│
└── tests/
    ├── test_results_validator.py
    ├── test_results_adapter.py
    └── test_confidence_flagger.py
```

---

## Task 21 Status

Implementation completed.

All tests passing:

```
9 passed
```