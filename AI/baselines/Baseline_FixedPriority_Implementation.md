# baseline_fixed_priority.py — notes

Implements `Baseline_FixedPriority.md`. Tests: `../tests/test_baseline_fixed_priority.py` (35).

## What it does

Draws water from sources in a fixed order — Silvan Reservoir, then Yarra Kew, then Groundwater Bore 1 — and never anything else. Cost plays no part in the ordering; a source is filled to its usable capacity before the next one is even considered. It's a deliberately dumb comparison point, not a real strategy, so don't read anything into how much it costs.

Like the other two baselines in this folder, it doesn't touch water quality and never reports `OPTIMAL` — only `FEASIBLE` or `INFEASIBLE`.

## Running it

```bash
python3 baseline_fixed_priority.py <scenario.json> [zone_id]
python3 -m pytest ../tests/test_baseline_fixed_priority.py -v
```

Or from Python directly:

```python
from baseline_fixed_priority import run_fixed_priority
result = run_fixed_priority(scenario_dict)
```

`zone_id` only matters if the scenario has more than one demand zone. If you just want the raw allocation rule without any scenario parsing, `allocate_fixed_priority(sources, demand, priority_order)` does that on its own.

## The ordering rule

`priority_rank()` decides everything: a source's position in `priority_order` first, `source_id` alphabetically as the tie-break. Anything not in the approved list falls to the very back, sorted alphabetically among itself — which only comes up if the scenario has a source outside the three we know about, and it gets a warning when it happens.

Worth noting this is a different kind of tie-break than `baseline_cheapest_first.py` uses. There, `source_id` only kicks in when cost is genuinely unknown. Here, being outside the priority list is the reason a source loses out, not a fallback for missing data.

## Reading the scenario

Takes a full scenario dict in the shape `MILP/docs/data_loader.md` defines. The essentials:

- `demand_zones[].demand_ml_per_day` — what needs to be supplied
- `sources[].enabled` / `.forced_inactive` — whether a source can be used at all
- `sources[].maximum_withdrawal_ml_per_day` (or its `_override`, or the legacy `max_available_ml_per_day_override`) — source-side capacity
- `data_source.source_rows[]` — names, types, activity status, and cost, when available
- `network.source_to_plant_links[]` / `network.plant_to_zone_links[]` — whether a source can actually reach the zone, and how much it can carry

Anything else in the scenario is ignored. Override precedence follows the loader doc exactly, and an explicit `null` is treated as "not provided," same as the loader does.

One gotcha: `source_rows[]` only exists for `inline` scenarios. The team's `supabase` scenario files don't carry it, so no source has a known cost on those — which doesn't break the ordering (it never depended on cost), but it does mean `cost_per_ml` and `draw_cost` come back empty for every source when you run against those files.

## What comes back

The result dict deliberately reuses the same field names the real solver output uses (`volume_drawn_ml_per_day`, `capacity_ml_per_day`, `sources.selected[]` / `.unused[]`, etc.) — same choice `baseline_equal_blend.py` and `baseline_cheapest_first.py` made, so any of the three can be dropped into a comparison against the MILP's own output without renaming anything.

Shape, roughly:

- `status` / `feasible` — `"FEASIBLE"` or `"INFEASIBLE"`
- `demand_zones[]` — what was asked for vs what got supplied
- `sources.selected[]` — volume, share of blend, capacity used, cost where known
- `sources.unused[]` — everything left out, and why
- `objective` — cost breakdown, plus a `total_cost_lower_bound` for when the total can't be fully confirmed
- `priority_order` — the order that was actually applied
- `metadata` — the heuristic's label and a short justification for why it exists, per the Task 17 checklist
- `warnings[]` — anything worth flagging that didn't change the result

On `total_cost`: if any cost component is missing, the total comes back as `null` rather than guessing — the lower bound carries whatever's actually known. In practice, on the toy config the total is complete, since Groundwater Bore 1 (the one source with no confirmed cost) never gets drawn from anyway.

## The 290 vs 300 question

`Baseline_HandCalculations.md` section 3 flagged that Yarra Kew's capacity could be read two ways — the link's stated 300 ML/day, or its own database limit of 290. The model constrains both, so this just takes whichever is smaller:

```text
capacity = min(withdrawal limit, sum of enabled link limits)
```

Same approach the other two baselines settled on. At the standard 500 ML/day demand it makes no difference here — Yarra Kew only ever draws 150 ML either way — but it does bite at higher demand, where the 10 ML gap between 290 and 300 has to be picked up by Groundwater Bore 1 instead.

## Rounding, briefly

Everything computes at full precision internally; rounding (one decimal for volumes and percentages, two for money) happens once, right at the end, on output only.

## Things flagged but not fixed

Per the approved rule, these get reported as warnings rather than silently corrected:

- a source outside the approved priority order
- a draw that falls below a source's minimum withdrawal
- flow that breaches a plant's processing band
- a missing withdrawal or link limit
- a zone fed by more than one plant (treatment cost can't be split fairly in that case)

## Still open

- No water-quality check — the per-source data just isn't available yet.
- `FEASIBLE` as a status hasn't been confirmed as acceptable downstream — same question the other two baselines are waiting on.
- Scenario parsing is copy-pasted across all three baseline files right now. Fine for now, but a shared module would cut a lot of duplication once all three are settled.
- The three tests against the team's real committed scenario files were actually run against reconstructed stand-ins, with link capacities guessed from what `baseline_equal_blend.py` and `baseline_cheapest_first.py`'s own tests implied — not read from the real files directly. Needs a real run against the actual files before this is trusted.
