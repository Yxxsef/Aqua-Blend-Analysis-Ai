# AquaBlend Analysis & AI

## Sprint 1 Final Integration Review and Sign-Off

**Reviewer:** Yousef Al Ali  
**Role:** Analysis & AI Lead  
**Review date:** 3 August 2026  
**Sprint:** Sprint 1  
**Overall decision:** Approved with future integration work

## 1. Review Purpose

This document records the final integration review of the Analysis & AI Sprint 1 deliverables.

The review checks:

- Configuration and JSON consistency
- Baseline definitions and calculations
- Demand research and scenario definitions
- KPI definitions and calculations
- Explanation templates and fallback generator
- LLM evaluation rubric
- Remaining risks and future work

## 2. Task Review Summary

| Task | Deliverable area | Review evidence | Final outcome |
|---|---|---|---|
| 1 | Equal-blend baseline | [PR #19](https://github.com/Yxxsef/Aqua-Blend-Analysis-Ai/pull/19) | Approved |
| 2 | Cheapest-first baseline | [PR #20](https://github.com/Yxxsef/Aqua-Blend-Analysis-Ai/pull/20) | Approved |
| 3 | Fixed-priority baseline | [PR #17](https://github.com/Yxxsef/Aqua-Blend-Analysis-Ai/pull/17) | Approved |
| 4 | Toy-model demand research | [PR #10](https://github.com/Yxxsef/Aqua-Blend-Analysis-Ai/pull/10) | Approved |
| 5 | Baseline calculations and validation | [PR #21](https://github.com/Yxxsef/Aqua-Blend-Analysis-Ai/pull/21) | Awaiting peer review |
| 6 | Source-selection explanation template | [PR #11](https://github.com/Yxxsef/Aqua-Blend-Analysis-Ai/pull/11) | Approved |
| 7 | Binding-constraints explanation template | [PR #9](https://github.com/Yxxsef/Aqua-Blend-Analysis-Ai/pull/9) | Approved |
| 8 | Water-quality and safety-margin explanation template | [PR #13](https://github.com/Yxxsef/Aqua-Blend-Analysis-Ai/pull/13) | Approved |
| 9 | Fallback explanation generator | [PR #14](https://github.com/Yxxsef/Aqua-Blend-Analysis-Ai/pull/14) | Approved |
| 10 | Normal-year and dry-year scenarios | [PR #12](https://github.com/Yxxsef/Aqua-Blend-Analysis-Ai/pull/12) | Approved |
| 11 | High-demand and plant-outage scenarios | [PR #16](https://github.com/Yxxsef/Aqua-Blend-Analysis-Ai/pull/16) | Scenario specification approved; final plant-outage integration remains |
| 12 | Evaluation KPI set | [PR #18](https://github.com/Yxxsef/Aqua-Blend-Analysis-Ai/pull/18) | Awaiting peer review |
| 13 | LLM evaluation rubric | [PR #8](https://github.com/Yxxsef/Aqua-Blend-Analysis-Ai/pull/8) | Awaiting peer review |

All submitted work was reviewed through the pull request process. Review comments were either resolved before approval or recorded as future integration work.

## 3. Configuration Consistency

- [x] Deliverables use fields from the available MILP configuration and reference JSON.
- [x] JSON files follow a valid and readable structure.
- [x] Scenario files clearly identify changed values.
- [x] Assumptions and estimated values are labelled.
- [x] No unsupported results are presented as confirmed operational data.
- [x] Known contract differences have been recorded for later integration.

The Sprint 1 work was created while the input and output contracts were still developing. The approved work is suitable as a specification and prototype foundation, but some field paths may require updates when connected to the final MILP output.

## 4. Baseline Review

### Equal-Blend Baseline

- [x] Active and available sources are identified.
- [x] Demand is divided equally between available sources.
- [x] Source capacities are respected.
- [x] Remaining demand is redistributed when a source reaches capacity.
- [x] Infeasibility is identified when total capacity cannot meet demand.
- [x] A numerical example and rounding behaviour are documented.

### Cheapest-First Baseline

- [x] Sources are sorted using the available cost field.
- [x] The cheapest available source is used first.
- [x] Capacity exhaustion is handled.
- [x] Cost ties are handled using a documented rule.
- [x] Infeasibility is identified when demand cannot be met.
- [x] The baseline does not claim to optimise water quality.

### Fixed-Priority Baseline

- [x] The source order is clearly documented.
- [x] The order is presented as an assumed heuristic.
- [x] Source activation, availability and capacity are respected.
- [x] Remaining demand moves to the next source in the defined order.
- [x] Infeasibility is handled.
- [x] The work does not incorrectly describe the rule as real operator practice.

### Baseline Calculations

- [x] The three baseline rules were applied to the toy-model configuration.
- [x] Source volumes and blend percentages were calculated.
- [x] Demand satisfaction and unmet demand were checked.
- [x] Costs and capacity usage were reported where available.
- [x] Water-quality and feasibility outcomes were considered.
- [x] Differences between the baseline strategies were explained.

**Status:** Awaiting peer review.

## 5. Demand and Scenario Review

### Demand Research

- [x] A public demand source is documented.
- [x] The publication date and original value are recorded.
- [x] The time basis and units are stated.
- [x] Unit conversions and scaling are explained.
- [x] The final toy-model demand value is clearly identified.
- [x] Limitations of using a scaled public value are recorded.

### Normal-Year Scenario

- [x] The normal scenario represents the reference configuration.
- [x] No unnecessary changes are introduced.
- [x] The scenario can be used as the control case.

### Dry-Year Scenario

- [x] The supply reduction is clearly defined.
- [x] Original and changed values are documented.
- [x] The percentage reduction is stated.
- [x] The assumption is explained.
- [x] Remaining capacity and possible infeasibility are discussed.

### High-Demand Scenario

- [x] The original demand value is recorded.
- [x] The demand multiplier is stated.
- [x] The new demand value is calculated.
- [x] The reason for the demand increase is explained.
- [x] Possible infeasibility is documented.

### Plant-Outage Scenario

- [x] The intended outage behaviour is documented.
- [x] The affected treatment facility is identified.
- [x] A supported configuration method is proposed.
- [x] Remaining treatment capacity and connectivity are considered.
- [ ] Final execution against the working configuration remains to be tested.

The scenario specifications are accepted as the Sprint 1 foundation. Final execution against the working optimisation model will occur during later integration.

## 6. KPI Review

The KPI set includes the required measures for comparing baseline, optimiser and scenario results.

**Status:** Awaiting peer review.

### Approved KPI Areas

- Feasibility status
- Demand satisfaction percentage
- Total cost
- Minimum water-quality safety margin
- Number of quality violations
- Chemical cost or chemical use

### Review Results

- [x] Each KPI has a field path or formula.
- [x] Units are provided.
- [x] Better directions are stated.
- [x] Required targets or thresholds are included.
- [x] Missing data behaviour is explained.
- [x] Infeasible results are handled.
- [x] Feasibility is checked before cost comparisons.
- [x] Sample calculations are included.
- [x] At least one KPI calculation was manually checked against the reference JSON.

### Manual Verification Record

One sample KPI calculation was manually checked using the reference JSON:

- KPI checked: Demand satisfaction percentage
- Formula: `(delivered volume / required volume) × 100`
- Result: Confirmed against the submitted calculation
- Outcome: Passed

An infeasible, incomplete or unsafe solution must not be treated as successful only because it has a lower cost.

## 7. Explanation System Review

### Explanation Templates

- [x] Selected-source explanations are supported.
- [x] Unused-source explanations are supported.
- [x] Binding constraints can be explained in readable wording.
- [x] Water-quality pass and fail results are handled.
- [x] The smallest safety margin is treated as the main safety-margin result.
- [x] Missing optional values are handled.
- [x] Estimated values and data limitations are disclosed.
- [x] Templates do not allow unsupported values to be invented.

### Fallback Explanation Generator

- [x] The generator reads structured JSON input.
- [x] Selected and unused sources are included.
- [x] Binding constraints are included.
- [x] Water-quality results and safety margins are included.
- [x] Missing required information produces a clear failure.
- [x] Optional information does not cause unnecessary crashes.
- [x] Numbers, reasons and decisions are taken from structured input.
- [x] The generator can operate without an external LLM.
- [x] Tests and usage documentation were included in the approved submission.
- [ ] Full testing against current MILP solver outputs remains future integration work.

The deterministic generator remains the required safe fallback. An LLM must not replace the optimisation model or become the source of numerical facts.

## 8. LLM Evaluation Review

The LLM evaluation rubric has been submitted and is awaiting peer review.

### Critical Checks

- [x] Selected sources must match the JSON.
- [x] Unused sources must match the JSON.
- [x] Binding constraints must match the JSON.
- [x] Numbers must not be invented.
- [x] Reasons must not be invented.
- [x] Water-quality status must be correct.
- [x] Units must be correct.
- [x] Estimated information must be disclosed.
- [x] Unsafe results must not be described as safe.
- [x] A critical safety failure causes the explanation to fail.

### Scored Areas

- Factual accuracy
- Completeness
- Clarity
- Usefulness to an operator
- Handling of uncertainty
- Consistency with the JSON

The rubric correctly separates factual and safety failures from writing quality. An explanation should not pass only because it sounds professional.

## 9. Remaining Risks

The following risks do not block approval of the Sprint 1 specification work:

- Some Results JSON fields may change during integration with the optimisation model.
- Some quality values may describe an intermediate treatment stage rather than final drinking water.
- The ownership of some generated explanation reasons may require further confirmation.
- Additional examples are needed for infeasible, time-limit, unbounded and error solver outcomes.
- The plant-outage scenario requires final testing against the working configuration.
- The fallback generator requires broader testing using real solver outputs.
- The LLM layer will require factual validation before its output can be displayed.
- Public and toy-model data must not be presented as real operational recommendations.

## 10. Future Work

The next stage may include:

- Implementing the approved baseline rules as working Python code.
- Running all scenarios through a shared and repeatable pipeline.
- Updating field mappings when the current Results JSON is confirmed.
- Improving the fallback explanation generator using real solver outputs.
- Supporting safe explanations for unsuccessful solver outcomes.
- Building an LLM prompt that only rewrites verified information.
- Checking LLM output for invented numbers, reasons, units and safety claims.
- Testing the explanation system across normal, incomplete and failure cases.
- Completing plant-outage execution using the confirmed configuration method.
- Connecting scenarios, KPIs, baseline comparisons and explanations.
- Producing a response format that can be safely displayed by the dashboard.
- Completing end-to-end testing with the MILP and App & Delivery teams.

## 11. Final Sign-Off

Sprint 1 has successfully produced the required Analysis & AI foundation:

- Baseline strategy specifications
- Baseline hand calculations
- Demand research
- Scenario definitions
- KPI definitions
- Explanation templates
- A deterministic fallback explanation approach
- An LLM safety and evaluation rubric

Baseline calculations (Task 5), the KPI set (Task 12) and the LLM evaluation rubric (Task 13) are awaiting peer review and are not yet covered by this approval.

The completed deliverables are accepted as the basis for continued implementation and integration.

**Final status:** SPRINT 1 APPROVED

The submitted Sprint 1 specification and prototype work is accepted. Remaining execution, expanded testing and cross-team integration are recorded as future work.

**Approved by:** Yousef Al Ali  
**Role:** Analysis & AI Lead  
**Date:** 3 August 2026

