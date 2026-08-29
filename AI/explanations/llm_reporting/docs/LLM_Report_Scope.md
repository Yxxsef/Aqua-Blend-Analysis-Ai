# AquaBlend LLM Report Generation Scope

## 1. Purpose

This document defines the boundaries for generating reports from AquaBlend MILP Results JSON.

The MILP is the only decision-maker.

The reporting flow has two stages:

1. A deterministic template copies supported facts and numbers from the Results JSON.
2. An optional LLM rewrites the template into clearer wording.

The template-only report is the fallback and must remain usable on its own.

## 2. Working Contract Status

The current Results JSON is a working draft contract for parallel development.

Analysis & AI does not own the final inter-team contract.

Current field names remain in use until the MILP team or Project Lead confirms changes.

## 3. Source of Truth

The structured Results JSON is the factual source of truth.

The LLM normally receives the completed deterministic report, not the raw Results JSON.

The existing `explanation` field must not be used as factual input when generating a new report.

The reporting layer must not:

- invent missing values;
- calculate new results;
- create source-selection reasons;
- change numbers or units;
- change solver decisions;
- add recommendations;
- make independent safety claims;
- describe plant-inflow quality as final drinking-water quality.

## 4. Deterministic Template Role

The deterministic template must:

- read exact JSON paths;
- copy facts and numbers exactly;
- support missing optional fields;
- handle empty arrays safely;
- handle non-optimal runs safely;
- include warnings and estimated-value notices when present;
- clearly state that water quality applies to the blend at plant inflow.

If a required field is missing or invalid, the system must stop normal report generation and return a validation-error report.

It must not produce a partial recommendation from incomplete required data.

## 5. LLM Role

The LLM may:

- improve grammar;
- simplify wording;
- improve sentence flow;
- organise the same facts more clearly.

The LLM must not:

- add or remove numbers;
- change units;
- invent reasons;
- change selected or unused sources;
- change solver outputs;
- change constraints;
- change quality status;
- change safety language;
- add calculations;
- add recommendations.

## 6. Critical Failure Conditions

An LLM output fails if it contains:

- an invented number;
- a changed number;
- an incorrect unit;
- a wrong selected source;
- a wrong unused source;
- an invented reason;
- a wrong binding constraint;
- a wrong quality status;
- an unsafe result described as safe;
- an omitted required fact;
- an omitted critical warning.

Critical failures override readability scores.

## 7. Fallback Behaviour

Use the deterministic template when:

- the LLM is unavailable;
- generation fails;
- validation fails;
- facts are changed;
- required content is omitted;
- unsafe wording is detected;
- solver status is non-optimal and safe handling is not confirmed.

## 8. Current Quality Limitation

`water_quality` currently applies to `blend_at_plant_inflow`.

It does not represent final post-treatment drinking water.

## 9. Optional Analysis Fields

The following fields may be empty or missing:

- `alternative_feasible_solutions`
- `sensitivity_to_key_assumptions`
- `explanation`

The reporting system must continue working without them.

## 10. Unresolved Ownership

Ownership of `sources.unused[].reason` is not confirmed.

Until the producer and verification method are confirmed, the deterministic report must not include `sources.unused[].reason`.

It may only state that the source was not selected.

It must never generate the reason itself.

## 11. In Scope

- Results JSON field mapping
- deterministic report design
- template generator
- controlled LLM rewriting
- factual validation
- safety-first evaluation
- fallback behaviour

## 12. Out of Scope

- changing the MILP model
- changing optimisation decisions
- independently calculating solver results
- producing operational drinking-water advice
- replacing engineers, operators or regulators
- finalising the inter-team contract

## 13. Approval Questions

- Can the LLM reorder report sections?
- Must every template sentence remain?
- Who approves safety wording?
- What report should appear for `TIME_LIMIT`?
- Can a feasible time-limit solution be reported?
- Who owns unused-source reasons?
