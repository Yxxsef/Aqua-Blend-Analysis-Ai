# Results

## Task 28: Sensitivity and Value-of-Data Ranking

### Overview

The sensitivity ranking module processes verified
`sensitivity_to_key_assumptions` information from the Results JSON and
cross-references relevant source provenance from `data_flags.sources`.

The module does not modify MILP results or create new impact values.

### Ranking Behaviour

Sensitivity entries are ranked only when the available information supports a
fair comparison.

The current Results JSON provides sensitivity impacts mainly as free-text
descriptions. There is currently no agreed fixed priority rule such as
feasibility > quality > cost.

The module therefore does not invent scores or priorities that are not
supported by the Results JSON.

### Insufficient-Data Behaviour

When sensitivity information is missing, incomplete, or does not support a fair
comparison, the module returns `INSUFFICIENT_DATA` instead of creating an
unsupported ranking.
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
  "status": "INSUFFICIENT_DATA",
  "rankings": [],
  "reason": "Sensitivity information does not support a fair ranking."
}
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

collected 28 items

AI/results/tests/test_confidence_flagger.py .........      [ 32%]
AI/results/tests/test_results_adapter.py .......           [ 57%]
AI/results/tests/test_results_validator.py ............    [100%]

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
---

# Task 73 — AI Run Metadata and Traceability

Task 73 adds a small, machine-readable metadata structure for tracing an AI execution through the AquaBlend integration pipeline.

The metadata layer records execution information that is already supplied by upstream components. It does not generate solver results, scenario identifiers, run identifiers, confidence values, or LLM outcomes.

## Metadata fields

The current metadata structure supports:

- `scenario_id` — scenario identifier supplied by the backend/orchestration layer.
- `run_id` — optimisation run identifier supplied by the backend/orchestration layer.
- `model_id` — identifier of the LLM/model used for the AI execution.
- `prompt_version` — version of the prompt used by the LLM runner.
- `runtime_ms` — AI/LLM execution runtime in milliseconds when available.
- `validator_result` — result supplied by the LLM validation stage.
- `fallback_used` — indicates whether deterministic fallback was used.
- `fallback_reason` — reason for fallback when one occurred.
- `confidence` — confidence information supplied by the existing confidence pipeline when available.
- `module_version` — version identifier for the metadata structure.

## Ownership and integration boundaries

Task 73 follows the AquaBlend integration architecture:

- The backend/orchestration layer owns `scenario_id` and `run_id`.
- Task 73 records these identifiers only when they are supplied.
- Missing optional metadata remains `None`; the module does not invent missing execution facts.
- Existing MILP Results remain the numerical source of truth.
- Secrets, credentials, API keys, and full prompts are not stored in metadata.
- The existing App response contract is not modified by this module.

The metadata component is intentionally independent of the final AI orchestration entry point. It can therefore be connected to the Sprint 3 integration pipeline once the relevant `main.py`/AI response interface is available without changing the existing Results, LLM runner, validator, or App response contracts.

## Files

- `ai_run_metadata.py` — metadata dataclass and builder.
- `sample_ai_run_metadata.json` — example machine-readable metadata output.
- `tests/test_ai_run_metadata.py` — tests for complete metadata, missing optional values, supplied identifiers, fallback information, and dictionary output.
