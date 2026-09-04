# Infeasibility AI Interface

**AquaBlend | Analysis & AI | Sprint 3 | Task 71**
**Covers:** `diagnostics_adapter.py`, `tests/test_diagnostics_adapter.py`

## 1. Purpose

When the MILP solver returns `INFEASIBLE`, the AI explanation layer must
not guess why. This document defines the interface that enforces that
rule, and the module (`diagnostics_adapter.py`) that implements it.

The governing principle, from the task description itself:

> The AI may explain supplied diagnostics; otherwise it should remain
> status-only.

This is enforced in code, not just as a prompt instruction. A caller
cannot hand the AI a fabricated cause, because `diagnostics_adapter.py`
is the only thing that decides whether a cause is safe to expose, and it
only ever does so when a real diagnostics payload was actually supplied
and at least one entry in it was well-formed.

## 2. A naming collision worth reading before anything else

This document's "infeasibility diagnostics" - likely causes, severities,
affected IDs - is a **completely different thing** from the `diagnostics.*`
object already defined in `Results_JSON_Field_Map.md`:

| Existing `diagnostics.*` (already in the contract) | This task's infeasibility diagnostics |
|---|---|
| `diagnostics.solver` | not part of this object |
| `diagnostics.solve_time_seconds` | not part of this object |
| `diagnostics.optimality_gap` | not part of this object |
| `diagnostics.num_continuous_variables` / `num_binary_variables` / `num_integer_variables` | not part of this object |
| `diagnostics.num_constraints` | not part of this object |
| Solver run metadata - exists for every run, feasible or not | Cause-of-infeasibility explanation - only exists for INFEASIBLE runs, only when the external framework supplies it |

`diagnostics_adapter.py`'s functions take the infeasibility-cause payload
as an explicitly, separately-named parameter (`infeasibility_diagnostics`)
for exactly this reason - never a key literally named `diagnostics`.
Passing the existing solver-metadata object in by mistake does not crash
the adapter (it has no `likely_causes` key, so it simply parses to zero
causes and the result is status-only) but it is still worth getting right
at the call site. `TestSolverMetadataDiagnosticsCollisionIsHarmless` in
the test suite exists specifically to prove this failure mode is safe,
not to encourage relying on it.

## 3. The payload this interface expects

**This shape is provisional, not confirmed.** It is sourced directly from
`integration_v1_3.md` section 20's own "conceptual diagnostic result"
example - that document's own word, "conceptual," not "final." Treat
every field name below as subject to change once the diagnostics/
feasibility workstream confirms their real contract.

```json
{
  "likely_causes": [
    {
      "type": "insufficient_source_supply",
      "severity": "high",
      "details": "Available source capacity is below total required demand."
    },
    {
      "type": "plant_capacity_limit",
      "severity": "medium",
      "plant_id": "plant_01"
    }
  ]
}
```

- **`type`** (string, required) - the one field this interface actually
  requires per cause. An entry missing it is dropped, not treated as
  fatal to the whole payload.
- **`severity`** (string, optional) - passed through as given, defaulting
  to `"unspecified"` if missing or not a string. Deliberately **not**
  validated against a fixed set of allowed values (e.g. high/medium/low),
  since the real contract hasn't confirmed one yet.
- **`details`** (string, optional) - a human-readable explanation of the
  cause, if supplied. A non-string value here is dropped, not coerced
  into text.
- **Any other field** (e.g. `plant_id`, `source_id`, `zone_id`, `link_id`)
  - collected generically into `affected_ids`, so a real contract's ID
    field, whatever it turns out to be called, is preserved without this
    module needing a code change for each new field name.

## 4. The three outcomes

Every call to `build_infeasibility_context()` resolves to exactly one of
three outcomes:

| Outcome | When | What the AI may say |
|---|---|---|
| `TECHNICAL_FAILURE` | Status is `ERROR`, `OPTIMAL`, `TIME_LIMIT`, or anything unrecognised | A safe, generic note that this is a tooling failure, not a proof of infeasibility - never treated as a mathematical result |
| `INFEASIBLE_WITH_DIAGNOSTICS` | Status is `INFEASIBLE` and at least one well-formed cause was supplied | The specific, supplied causes only - nothing inferred beyond them |
| `INFEASIBLE_STATUS_ONLY` | Status is `INFEASIBLE` or `UNBOUNDED`, and no usable diagnostics were supplied | Nothing. `render_diagnostics_section()` returns `None`, and callers must not substitute their own guess for it |

### Why `ERROR` is its own bucket, not folded into infeasibility

A solver that crashes, times out at the tooling level, or otherwise fails
to reach a real conclusion has told you nothing about whether the
scenario is mathematically solvable. Describing `ERROR` the same way as
a genuine `INFEASIBLE` result would misrepresent a technical problem as a
mathematical finding - exactly the kind of overclaim this whole interface
exists to prevent.

### Why `UNBOUNDED` always lands in `INFEASIBLE_STATUS_ONLY`

`Results_JSON_Field_Map.md`'s "do not report a recommended blend" rule
applies to both `INFEASIBLE` and `UNBOUNDED`, so both are treated as
infeasibility-shaped. But the integration doc's example is written for
`INFEASIBLE` specifically - nothing confirms an `UNBOUNDED` diagnostics
payload would use the same `likely_causes` shape, or mean the same thing
if it did. Until that's confirmed, `UNBOUNDED` always resolves to
status-only here, **even if a diagnostics payload is supplied for it**.
This is a deliberate, documented scope limitation, not an oversight - see
section 7.

## 5. What the module does not do

- **Does not duplicate `json_explainer.py`'s existing INFEASIBLE
  handling.** `explain_result_availability()` already produces the
  generic "Solver status is INFEASIBLE. This result is not confirmed as
  usable for a final recommendation" sentence for every non-`OPTIMAL`
  status. This module is strictly additive to that - it only ever
  concerns the diagnostics-specific content layered on top.
- **Does not call `json_explainer.py`, `model_runner.py`, or
  `llm_validator.py`**, and does not import anything from them - the same
  standalone-module pattern those three already use. It operates on
  plain dicts and strings so it can be tested and used entirely on its
  own.
- **Does not validate `severity` against a fixed set of values.** Doing
  so now, before the real contract is confirmed, risks rejecting a
  genuinely valid value the eventual contract turns out to use.
- **Does not raise on malformed diagnostics content.** The only case
  this module raises on is a missing or empty `solver_status` - a
  genuine caller programming error, not a real-world data-quality gap.
  Everything else in the diagnostics payload degrades safely to
  status-only or to dropping the one malformed entry - see section 6.

## 6. Malformed-input handling, in full

Consistent with `json_explainer.py`'s own "deliberately tolerant" input
philosophy (see that module's docstring):

| Situation | Result |
|---|---|
| `infeasibility_diagnostics` is not a mapping (e.g. a string or list) | Treated as no diagnostics supplied |
| No `likely_causes` key at all | Treated as no diagnostics supplied |
| `likely_causes` is present but not a list | Treated as no diagnostics supplied |
| `likely_causes` is an empty list | Treated as no diagnostics supplied |
| An individual cause entry is not a mapping | That entry is skipped; other well-formed entries are still used |
| A cause entry is missing `type`, or `type` is empty/whitespace | That entry is skipped; other well-formed entries are still used |
| Every entry in `likely_causes` is malformed | Falls back to `INFEASIBLE_STATUS_ONLY`, not an empty `INFEASIBLE_WITH_DIAGNOSTICS` |
| `severity` missing or not a string | Defaults to `"unspecified"` |
| `details` present but not a string | Dropped (set to `None`), not coerced into text |
| Extra fields beyond `type`/`severity`/`details` | Collected into `affected_ids` generically |

## 7. Open questions for the diagnostics/feasibility workstream

These are genuinely unresolved, not just left implicit:

1. **Is `severity` a fixed enum, and if so, what are the allowed
   values?** The integration doc's example only shows `"high"` and
   `"medium"`. This interface currently passes any string through
   unvalidated.
2. **Which ID field(s) actually appear on a cause entry?** The example
   only shows `plant_id`. This interface's `affected_ids` mechanism is
   built to be agnostic to this, but the eventual documentation/UI layer
   consuming `affected_ids` will need to know the real field names to
   label them meaningfully.
3. **Does `UNBOUNDED` get its own diagnostics payload, and if so, does it
   share this shape?** Not confirmed - see section 4's `UNBOUNDED` note.
   Until confirmed, this interface will keep treating `UNBOUNDED` as
   status-only regardless of what's supplied for it.
4. **Is the diagnostics payload delivered inline with the run result, or
   fetched separately?** `integration_v1_3.md` section 38 documents a
   distinct `GET /api/runs/:runId/diagnostics` endpoint, while section
   20's flow diagram shows diagnostics happening inline, before the AI
   layer is ever invoked. The document does not fully reconcile these two
   descriptions. `diagnostics_adapter.py` is agnostic to this - it just
   takes whatever payload it's given - but the calling code that fetches
   or receives that payload will need this resolved.

## 8. Testing

`tests/test_diagnostics_adapter.py` - 38 tests, organised by scenario:

- Statuses this module doesn't treat as infeasibility-shaped (`OPTIMAL`,
  `TIME_LIMIT`, an unrecognised future status) degrade safely
- `ERROR` is kept distinct from a genuine infeasibility finding, even if
  a diagnostics payload is accidentally supplied alongside it
- The core safety guarantee: `INFEASIBLE` with nothing supplied always
  renders `None`, never a guessed explanation
- The integration doc's own example, checked field by field, including
  the generic `affected_ids` mechanism with a *different* ID field name
  than the example uses, proving the design isn't hard-coded to `plant_id`
  specifically
- `UNBOUNDED`'s scope limitation, including the case where a diagnostics
  payload is supplied but must still be ignored
- Every malformed-input case from section 6's table, individually
- The solver-metadata naming-collision failure mode, confirmed harmless
- Basic dataclass shape/default-value checks
