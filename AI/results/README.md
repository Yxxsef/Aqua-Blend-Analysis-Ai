# Results JSON Validator, Adapter and Confidence Flags

## Overview

This module provides validation, adaptation, and confidence checking for AquaBlend Results JSON output.

The purpose is to ensure that optimisation results received from the MILP layer are complete, consistent, and safe for downstream systems while preserving the external Results JSON contract.

The implementation provides:

- Results JSON validation
- Stable internal result adaptation
- Confidence disclosure based on source provenance
- Automated testing for valid, incomplete, malformed, and provenance scenarios

---

# Components

## results_validator.py

The Results JSON validator verifies that the external Results JSON conforms to the confirmed contract.

It validates:

- Required top-level fields
- Required data types
- Valid optimisation status values
- Sources structure
- Constraints structure
- Data flag structure
- Source provenance structure

The validator checks:

- Scenario information
- Solver status
- Objective
- Demand zones
- Sources
- Transfer paths
- Plants
- Water quality
- Constraints
- Diagnostics
- Data flags

The validator:

- validates structure only;
- does not modify optimisation results;
- does not recalculate values;
- does not introduce missing values.

---

## results_adapter.py

The adapter converts the validated external Results JSON into the stable internal representation.

Responsibilities include:

- Converting approved external field names to internal names
- Preserving optimisation results
- Preserving source structures
- Preserving plant structures
- Preserving transfer-path structures
- Preserving water-quality structures
- Preserving constraint structures
- Preserving diagnostics
- Preserving data flags
- Safely passing optional fields

The adapter does not:

- modify optimisation decisions;
- recalculate costs;
- invent missing values;
- modify the external Results JSON.

---

## confidence_flagger.py

The confidence flagger evaluates source-data provenance using:

```
data_flags.sources
```

It does **not** read provenance from:

```
sources.selected
sources.unused
```

The confidence flagger returns one of:

| Confidence | Meaning |
|------------|---------|
| PROVISIONAL | One or more contributing sources contain estimated values |
| MEASURED | All sources are confirmed measured |
| UNKNOWN | Provenance is missing, incomplete, or invalid |

---

# Confidence Behaviour

## PROVISIONAL

Returned when at least one source contains:

```json
{
    "has_estimated_values": true
}
```

Example output:

```json
{
    "confidence": "PROVISIONAL",
    "estimated_sources": [
        "groundwater_bore_1"
    ]
}
```

Only actual source IDs are returned.

---

## MEASURED

Returned only when every source:

- has a valid source_id;
- has has_estimated_values = false;
- contains a valid provenance object;
- contains all five required provenance fields.

Example:

```json
{
    "confidence": "MEASURED",
    "estimated_sources": []
}
```

---

## UNKNOWN

Returned when provenance cannot confirm measured data.

Examples include:

- missing provenance;
- incomplete provenance;
- empty source list;
- invalid source_id;
- non-boolean has_estimated_values;
- invalid provenance structure.

Example:

```json
{
    "confidence": "UNKNOWN",
    "estimated_sources": []
}
```

---

# Testing

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
============================= test session starts =============================

collected 28 items

AI/results/tests/test_confidence_flagger.py .........      [ 32%]
AI/results/tests/test_results_adapter.py .......           [ 57%]
AI/results/tests/test_results_validator.py ............    [100%]

============================== 28 passed ==============================
```

### Validator Tests

- Valid Results JSON
- Missing required fields
- Invalid status values
- Invalid data types
- Invalid sources structure
- Invalid constraints structure
- Invalid data_flags structure
- Invalid source IDs

### Adapter Tests

- Field mapping
- Source preservation
- Constraint preservation
- Optional field handling
- Missing required fields
- Invalid input type
- Data flag preservation

### Confidence Tests

- PROVISIONAL with estimated sources
- MEASURED with complete provenance
- UNKNOWN with missing provenance
- UNKNOWN with incomplete provenance
- UNKNOWN with invalid booleans
- UNKNOWN with missing source IDs
- Empty source list
- Mixed provenance scenarios

---

# Task 21 Deliverables

Implemented:

- Results JSON validator
- Stable Results JSON adapter
- Confidence flagger
- Validator test suite
- Adapter test suite
- Confidence test suite
- Sample flagged output
- Results JSON Field Map documentation

---

# Design Notes

- The external MILP Results JSON remains the source of truth.
- External field names remain unchanged.
- Internal naming differences are handled only in `results_adapter.py`.
- The validator performs structural validation only.
- The adapter never changes optimisation results.
- The confidence flagger evaluates provenance only.
- Optional fields are safely preserved when present.
- Missing optional fields never cause validation failure.

---

# File Structure

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

# Task 21 Status

Implementation completed successfully.

- Results Validator implemented
- Results Adapter implemented
- Confidence Flagger implemented
- Results JSON Field Map completed
- Sample flagged output included
- Automated test suite completed

**All tests passing (28/28).**