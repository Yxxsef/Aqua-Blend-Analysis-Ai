# Batch Runner and Comparison Report (Task 26)

Runs approved scenarios through the optimiser and the three coded baselines,
applies the same KPIs and pass/fail gate to all of them, and produces one
comparison across scenarios.

The runner reports. It does not decide, rank, or recommend. Every value in the
output comes from the solver, a baseline, or the KPI calculator.

## Files

| File | What it does |
| --- | --- |
| `batch_runner.py` | Runs scenarios, writes run output and the manifest |
| `comparison_report.py` | Builds the comparison and writes it as JSON and CSV |
| `samples/` | A worked example from a real run |
| `../tests/test_batch_runner.py` | Tests for both modules |

## Usage

```python
import sys
sys.path.insert(0, "AI/evaluation")

from batch_runner import run_batch, write_run
from comparison_report import build_comparison, write_comparison

batch = run_batch("AI/scenarios")          # one file or a whole folder
run_dir = write_run(batch)                 # writes runs/<timestamp>/
write_comparison(build_comparison(batch), run_dir)
```

Run output goes to `runs/<timestamp>/`, which is gitignored. `raw/` holds the
solver output exactly as it arrived; `processed/` holds everything calculated
from it. The two are never mixed, so the original result is always recoverable.

## Mock mode

MILP v1 does not exist yet, so `run_batch` defaults to `mode="mock"` and reads a
stored Results JSON from
`AI/explanations/llm_reporting/fixtures/model_output_example.json`.

**Mock mode returns the same optimiser result for every scenario.** Optimiser
values in a mock run are not scenario-specific and must not be read as such.
Every manifest carries this warning in its `mock_warning` field.

When MILP v1 lands, only `get_optimiser_result` changes. Nothing else in the
runner or the comparison needs touching.

## What the comparison shows

Four measures, for the optimiser and every baseline: feasibility, total cost,
demand satisfaction, and the minimum safety margin.

Two things look like gaps and are not:

**Baselines have no safety margin.** They do not compute water quality, so the
cell carries the reason `baselines do not compute water quality` rather than a
blank or a zero. A blank invites a reader to assume it passed.

**Baselines are gated but cannot pass.** The KPI gate will not approve a result
whose safety condition it cannot check, so every baseline returns
`UNABLE_TO_EVALUATE` on a feasible scenario. That is the gate behaving
correctly. The task sheet requires gating every result, so the runner does, and
records why the verdict is what it is.

An infeasible baseline still appears in the comparison — infeasible is a result,
not a missing row. On the plant-outage scenario all three baselines return
`FAIL`, because they genuinely cannot meet demand.

**A scenario with no optimiser result still gets a row.** There is nothing to
compare the baselines against, so the row carries the reason in
`scenario_reason` and leaves the measure columns empty. Every row in the file
is the same width, so the CSV opens cleanly.

The comparison records `quality_stage` alongside the margin. In the current
fixture this is `blend_at_plant_inflow` — water before treatment, not final
drinking water.

## Failures

A scenario that fails is recorded in `failures` with its error type and message,
and the batch carries on. One bad file does not cost the other results.

## Sources of cost data

Scenario files with `data_source.type: "supabase"` carry no source rows offline,
so the baselines report no cost and the cost column is empty. To get real costs
without a database, use a scenario with `data_source.type: "inline"` and
embedded `source_rows`, as described in §3.2 of the MILP input specification.

## Tests

```
python -m pytest AI/tests/test_batch_runner.py -v
```

Covers both mock and unwired MILP mode, a single scenario, a folder, repeatable
ordering, a broken file mid-batch, infeasible baselines, the missing-optimiser
case, and the written output.
