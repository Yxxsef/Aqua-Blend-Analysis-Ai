# Task 57 — Real MILP Provenance and Confidence Behaviour

## Purpose

Sprint 3 Task 57 connects the existing confidence flagger to the latest available MILP Output JSON Contract v1.0 and the current `ScenarioData` provenance structure.

The important contract change is that MILP Output JSON v1 no longer contains the old `data_flags.sources[]`, `has_estimated_values`, or `provenance` fields. Those values are scenario inputs and are owned by `ScenarioData`, while the MILP output keeps source IDs and solver decisions. Confidence is therefore calculated by joining the two structures on `source_id`.

## Data flow

```text
Scenario JSON + Supabase / inline source rows
                |
                v
          data_loader.py
                |
                v
        ScenarioData.sources
        - source_id
        - has_estimated_values
        - provenance
                \
                 \
                  \ join on source_id
                   \
                    v
              confidence_flagger.py
                    ^
                   /
                  /
                 /
        MILP Output v1
        - sources[].source_id
        - sources[].withdrawal_ml_per_day
        - sources[].selection_status
        - sources[].activated
                    |
                    v
             Confidence result
        PROVISIONAL / MEASURED / UNKNOWN
```

## Contributing-source rule

Only sources that contributed to the solved result affect confidence.

The implementation uses solved `withdrawal_ml_per_day` as the strongest contribution signal. When withdrawal is unavailable, it uses `selection_status` (`SELECTED`, `UNUSED`, `EXCLUDED`, `PENDING`) and then `activated` where available. `PENDING`/missing solver evidence is treated as unclear rather than guessed.

Unused or excluded sources do not reduce confidence even if their input data contains estimates.

## Provenance source

The flagger reads provenance from `ScenarioData.sources` / `SourceInput`, not from the MILP Output JSON.

`data_loader.py` derives `has_estimated_values` from estimated/overridden source inputs and builds provenance containing the current base entries:

- `storage_capacity`
- `reference_flow`
- `minimum_withdrawal`
- `maximum_withdrawal`
- `cost`

It also adds `quality.<parameter_id>` entries for the configured quality parameters. The flagger does not hard-code the quality parameter names; it checks the quality provenance entries supplied by the loader.

## Confidence decision rules

| Condition | Confidence | Behaviour |
|---|---|---|
| At least one contributing source has `has_estimated_values = true` | `PROVISIONAL` | Return the affected real `source_id` values in `estimated_sources`. |
| Every contributing source has `has_estimated_values = false` and complete provenance | `MEASURED` | No estimated source IDs are returned. |
| Contributing-source provenance is missing, incomplete, invalid, or cannot be joined by `source_id` | `UNKNOWN` | Do not invent provenance or estimated source IDs. |
| MILP source contribution is not yet known (for example `PENDING` / unsolved fixture) | `UNKNOWN` | Do not assume a source was used. |
| One contributing source is confirmed estimated while another has unclear provenance | `PROVISIONAL` | Confirmed estimated data takes precedence; only confirmed estimated IDs are listed. |

## Non-blocking UNKNOWN behaviour

`UNKNOWN` is a valid confidence result and is intentionally non-fatal. Missing or unclear provenance does not stop baseline/KPI/comparison processing. Only invalid top-level API usage (for example passing a string instead of a source sequence) raises `ConfidenceError`.

## Sprint 2 compatibility

The previous Task 21 flagger accepted a list of provenance records and a separate list that already represented selected sources. The Sprint 3 implementation keeps compatibility with that minimal selected-source shape while supporting the real MILP v1 source decision structure.

## Tests

The updated tests cover:

- `PROVISIONAL` for estimated contributing sources;
- `MEASURED` for complete measured contributing sources;
- unused estimated sources being ignored;
- incomplete provenance returning `UNKNOWN`;
- missing `ScenarioData` join records returning `UNKNOWN`;
- mixed estimated + unknown provenance returning `PROVISIONAL`;
- the current Task 56 unsolved/PENDING v1 source shape returning `UNKNOWN` without failure;
- source contribution based on solved withdrawal;
- backwards compatibility with the Sprint 2 selected-source shape;
- clear errors only for invalid top-level containers.

## Current integration status

Task 57 was implemented against the latest available MILP Output JSON Contract v1.0 and the current `ScenarioData` provenance structure. The available Task 56 v1 fixture represents an unsolved run (`NOT_SOLVED` with `PENDING` sources), rather than a genuine solved MILP result. Because of this, the implementation has been tested against the confirmed v1 structure and representative source decisions, but final integration should be rechecked once a genuine solved MILP v1 output is available. Until then, unresolved contribution or provenance correctly produces `UNKNOWN` confidence.
