Scenario Input Contract Notes

AquaBlend Analysis & AI — Sprint 2, Task 20Owner: Sravya TudiStatus: Review update aligned with the current MILP input contract.

1. Scope

Task 20 loads and validates the existing Sprint 1 AquaBlend toy scenarios:

normal-year-dry-year/scenario_normal.json

normal-year-dry-year/scenario_dry_year.json

high-demand-outage/scenario_high_demand.json

high-demand-outage/scenario_plant_outage.json

These scenario JSON files are upstream inputs. Task 20 does not make MILP decisions and does not fabricate optimiser outputs.

2. Task 20 files

AI/scenarios/
├── normal-year-dry-year/
├── high-demand-outage/
├── scenario_loader.py
├── scenario_validator.py
├── test_scenario_validator.py
└── Scenario_Input_Contract_Notes.md

scenario_plant_outage.json already existed from the Sprint 1 scenario work. Task 20 consumes and validates that existing file rather than adding a duplicate copy.

3. Loader behaviour

scenario_loader.py:

Reads JSON using strict UTF-8.

Rejects malformed JSON.

Requires a JSON object at the top level.

Discovers scenario_*.json files recursively in deterministic path order.

Leaves contract validation to scenario_validator.py.

4. Current MILP input-contract alignment

Task 20 uses the current MILP input contract/specification as the input authority.

Important current fields include:

network.demand_zones[].demand_ml_per_day

network.plants[].enabled

network.plants[].minimum_processing_capacity_ml_per_day

network.plants[].maximum_processing_capacity_ml_per_day

network.source_to_plant_links[].maximum_flow_ml_per_day

network.plant_to_zone_links[].maximum_flow_ml_per_day

sources[].minimum_withdrawal_ml_per_day

The current MILP specification documents minimum_operating_flow_ml_per_day as a legacy fallback for the plant minimum-capacity field. The existing Sprint 1 scenario files still use that legacy name. Task 20 therefore accepts it for compatibility and reports a warning, while treating minimum_processing_capacity_ml_per_day as the preferred current field.

Task 20 does not silently rewrite the upstream Sprint 1 scenario files.

5. ID-based comparison

The current MILP specification defines IDs as join keys. The updated validator therefore compares known arrays using stable IDs instead of relying on list positions.

Examples of the validator's internal path notation:

network.demand_zones[zone_id=zone_1].demand_ml_per_day
network.plants[plant_id=facility_1].enabled
network.source_to_plant_links[source_id=silvan_reservoir,plant_id=facility_1].maximum_flow_ml_per_day

This prevents harmless array reordering from being reported as a scenario change.

6. Stable scenario IDs and types

Internal type

Stable scenario ID

NORMAL

toy_model_normal_year

DRY_YEAR

toy_model_dry_year

HIGH_DEMAND

scenario_2026_07_17_high_demand

PLANT_OUTAGE

scenario_2026_07_17_plant_outage

The validator infers an internal scenario type from existing metadata and does not add a new scenario_type field to the input JSON.

7. Approved scenario changes

Scenario comparisons use the normal scenario as the reference. Metadata differences are limited to scenario_id, scenario_name, and description.

7.1 Normal

No operational field may differ from the approved reference input.

7.2 Dry year

The three approved source-to-plant maximum-flow changes are validated by source and plant IDs:

Source

Plant

Normal

Dry year

silvan_reservoir

facility_1

350 ML/day

280 ML/day

yarra_kew

facility_1

300 ML/day

240 ML/day

groundwater_bore_1

facility_1

60 ML/day

45 ML/day

Demand remains 500 ML/day.

7.3 High demand

For zone_1:

network.demand_zones[zone_id=zone_1].demand_ml_per_day

changes from 500 to 600 ML/day. Other operational fields must remain unchanged.

7.4 Plant outage

The existing Sprint 1 outage scenario uses the current contract's plant activation field:

network.plants[plant_id=facility_1].enabled

For facility_1, the value changes from true to false.

Task 20 validates this existing outage scenario, then checks active connectivity and remaining active capacity.

8. Pre-solve capacity check

The validator calculates:

active source-to-plant link capacity;

active plant processing capacity;

active plant-to-zone capacity;

mandatory demand;

aggregate effective capacity;

remaining aggregate capacity.

The aggregate effective capacity is the minimum of the three active capacity layers.

Expected current screening results:

Scenario

Effective capacity

Demand

Remaining

Normal

600 ML/day

500 ML/day

100 ML/day

Dry year

565 ML/day

500 ML/day

65 ML/day

High demand

600 ML/day

600 ML/day

0 ML/day

Plant outage

0 ML/day

500 ML/day

-500 ML/day

These are pre-solve screening checks only. Passing the static check does not prove MILP feasibility, and the validator never creates a solver status.

9. Connectivity check

For each positive mandatory-demand zone, the validator checks for an active path:

enabled source
→ enabled source-to-plant link
→ enabled plant
→ enabled plant-to-zone link
→ demand zone

With facility_1 disabled, the existing plant-outage scenario has no active treatment path to zone_1, so the validator reports possible infeasibility before solving.

10. No fake outputs

The validator rejects result/output-only fields from scenario input, including:

objective

total_cost

volume_drawn_ml_per_day

volume_supplied_ml_per_day

percent_of_blend

binding_constraints_summary

water_quality

diagnostics

data_flags

alternatives

sensitivity_to_key_assumptions

Task 20 does not generate selected volumes, blend shares, costs, binding constraints, quality results, or an OPTIMAL/INFEASIBLE solver result.

11. Tests

Run from AI/scenarios:

python -m unittest -v test_scenario_validator.py

The updated suite covers the original Task 20 tests plus contract/review regression cases, including:

valid normal, dry-year, high-demand and plant-outage scenarios;

UTF-8 and malformed JSON handling;

required and unknown fields;

duplicate IDs and unknown link references;

output-only field rejection;

scenario-specific change rules;

capacity and connectivity screening;

list-order independence through ID-based matching;

current minimum_processing_capacity_ml_per_day acceptance;

legacy plant minimum-capacity compatibility warning;

minimum_withdrawal_ml_per_day acceptance.

12. Review points addressed

Outage field: network.plants[].enabled is present in the current MILP input contract/specification. The existing Sprint 1 outage scenario sets facility_1.enabled to false.

Existing outage JSON: scenario_plant_outage.json already landed in the Sprint 1 scenario work and is reused by Task 20, so it was not newly added in the original Task 20 diff.

ID-based validation: approved scenario changes are now matched by stable source/plant/zone IDs rather than array positions.

Current plant minimum-capacity field: the validator accepts minimum_processing_capacity_ml_per_day and the documented legacy fallback used by the upstream Sprint 1 scenarios.