# AquaBlend Analysis & AI

This folder contains all Analysis & AI Sprint 1 deliverables.

In this repository, the top-level team folder is:

```text
AI/
```

Do not create new top-level folders without raising it in the Analysis & AI team channel first.

## Integrated Pipeline Entry Point

`AI/main.py` is the Analysis & AI team's internal pipeline entry point. It reads
a MILP result from a file or from Supabase, and can write the App response back;
the project-wide backend entry point remains separate. All detailed Supabase
queries and insert mappings live in `AI/integration/supabase_repository.py` -
`main.py` only coordinates the pipeline.

Pipeline order:

1. Read a Results JSON file, or one `milp_model_output` row from Supabase.
   - When reading from Supabase, `raw_output_json` is used as the canonical
     analysis payload when it is complete; otherwise a documented,
     best-effort normalization of the flat `milp_model_output` columns is
     used instead (see `supabase_repository.normalize_output_columns`).
   - The linked `milp_model_input` row (via `input_id`) is also fetched, but
     **is not yet mapped into confidence/provenance analysis** - see "Known
     integration blocker" below. A read failure here is only a warning.
2. Validate raw MILP Results JSON.
3. Adapt the result into the internal format.
4. Calculate KPIs and the KPI gate.
5. Determine confidence from `data_flags.sources` already present in the
   canonical/normalized payload (empty in the flat-column fallback, which
   correctly yields `UNKNOWN` rather than a guess).
6. Generate the deterministic technical report (`detailed_explanation`) and a
   short deterministic executive summary (`executive_summary` source).
7. Optionally rewrite ONLY the short executive summary with an LLM, and
   validate it. The full detailed report is never sent to an LLM.
8. Use the deterministic summary when the LLM is unavailable or rejected.
9. Build deterministic `visualization_data` (chart-ready values) from the
   validated MILP result - never from LLM wording.
10. Return the App & Delivery response contract.
11. Optionally insert that response into `milp_ai_output`.

`main.py` coordinates existing modules and does not replace their business
logic. Model configuration is optional; without it, the deterministic fallback
is used. Unvalidated LLM output is never returned for display.

### Setup

Credentials are read from `AI/.env`, which is gitignored. Copy the example and
fill in `DB_KEY`:

```text
cp AI/.env.example AI/.env
pip install -r AI/requirements.txt
```

`DB_URL`/`DB_KEY` are only loaded and validated lazily, right before a
Supabase call is made (a read with no local file, or `--push`). **Local JSON
mode never needs them** - running the pipeline against a results file works
with no `AI/.env` at all. Never commit `AI/.env` or a real Supabase key.

### Commands

Input is either a Results JSON file or one Supabase row. With no argument the
newest row by `created_at` is used; the selectors name the `milp_model_output`
column they filter.

```text
# Local JSON file, deterministic output only (no LLM, no Supabase)
python AI/main.py <results.json>

# Local JSON file, with a local Ollama-compatible model rewriting only the
# short executive summary (see AI/explanations/model_config.example.json)
python AI/main.py <results.json> --model-config AI/explanations/model_config.example.json

# Read the newest milp_model_output row from Supabase (needs AI/.env)
python AI/main.py
python AI/main.py --run-id 6
python AI/main.py --scenario-db-id 8
python AI/main.py --scenario SCN-008

# Read from Supabase and write the computed App response back to milp_ai_output
python AI/main.py --scenario-db-id 8 --push

python AI/main.py --output <response.json>
python -m pytest tests/test_main.py -q   # run with AI/ as the working directory
```

### Required environment variables

| Variable | Required for | Notes |
|---|---|---|
| `DB_URL` | Supabase reads/`--push` only | Read from `AI/.env`, gitignored. |
| `DB_KEY` | Supabase reads/`--push` only | Never commit a real key. |

### Database input/output flow

```text
milp_model_input
      |
      v
  MILP solver
      |
      v
milp_model_output  --input_id-->  milp_model_input (fetched; not yet mapped - see below)
      |
      v
Analysis & AI pipeline (this folder)
      |
      v
milp_ai_output
      |
      v
  App dashboard
```

See `AI/integration/supabase_schema/README.md` for the reference table
schemas and `AI/integration/supabase_repository.py` for the read/write and
normalization logic.

#### Known integration blocker: `milp_model_input` provenance is not yet used

`supabase_repository.load_input_provenance` fetches the linked
`milp_model_input` row (`scenario_data_json`, `source_data_snapshot_json`,
`model_parameters_json`, `validation_policy`, `allow_estimated_values`), but
`main.run_from_source` currently **discards the fetched dict** and keeps only
its warnings. No real `milp_model_input` row has been seen yet, so the exact
JSON shape of those fields is unconfirmed - mapping them into
`data_flags.sources` now would mean guessing that shape, which could silently
fabricate a confidence signal. Confidence is therefore derived only from
whatever `data_flags.sources` the canonical (or normalized) MILP output
payload already carries; the flat-column fallback leaves that list empty,
which `confidence_flagger.determine_confidence` correctly reports as
`UNKNOWN` rather than `MEASURED`/`PROVISIONAL`. This should be revisited once
a real `milp_model_input` row is available to confirm the mapping.

### App response fields: executive_summary, detailed_explanation, visualization_data

- `executive_summary` - a short, operator-readable summary. This is the ONLY
  text an LLM rewrite may touch; a failed/unavailable rewrite falls back to
  the deterministic summary text, never an empty or partial report.
- `detailed_explanation` - the complete deterministic technical report
  (`json_explainer.generate_explanation`). Always deterministic; never sent
  to or rewritten by an LLM.
- `display_explanation` - kept equal to `executive_summary`, for backward
  compatibility with earlier consumers of this field.
- `visualization_data` - deterministic chart-ready values (`blend_ratios`,
  `cost_breakdown`, `quality_margins`, `solution_costs`) built directly from
  the validated MILP result. Unknown values are `null` or omitted, never `0`.
  This pipeline does not render charts; the App team turns this data into
  graphs on their side.
- Both `executive_summary` and `detailed_explanation` are stored on the
  `milp_ai_output` row (`executive_summary`, `decision_explanation`); the
  complete response, including `visualization_data`, is stored in
  `raw_ai_json`.

## Task 64: LLM validation and automatic fallback

The pipeline always generates the deterministic explanation first. Any LLM
rewrite is untrusted until `validate_llm_output()` accepts it. `LLM_VALIDATED`
means the rewrite passed critical validation; `TEMPLATE_FALLBACK` means the
deterministic explanation is being used.

Model errors, timeouts, empty or malformed output, validator errors, and
critical validation failures all reject the rewrite and trigger deterministic
fallback. Unvalidated LLM text is never shown. The integration tests use
mocked model calls and do not require a live model.

Run the focused pipeline tests with:

```text
python -m pytest AI/tests/test_main.py -v
```

`--push` inserts the response into `milp_ai_output`, keyed to the
`milp_model_output` row it was computed from. It needs a Supabase row, so it
cannot be combined with a file input. Without it, nothing is written.

## Sprint 1 Required Files

| Folder | Required files |
|---|---|
| `AI/` | `README.md` |
| `AI/baselines/` | `Baseline_EqualBlend.md`, `Baseline_CheapestFirst.md`, `Baseline_FixedPriority.md`, `Baseline_HandCalculations.md`, `baseline_results.csv` |
| `AI/demand/` | `Demand_Research.md`, `toy_demand_value.json` |
| `AI/explanations/` | `Template_SourceSelection.md`, `Template_BindingConstraints.md`, `Template_QualityMargins.md`, `json_explainer.py`, `test_json_explainer.py`, `sample_explanations.txt`, `README.md` |
| `AI/scenarios/` | `Scenario_Normal_DryYear.md`, `Scenario_HighDemand_Outage.md`, `scenario_normal.json`, `scenario_dry_year.json`, `scenario_high_demand.json`, `scenario_plant_outage.json` |
| `AI/evaluation/` | `KPI_Set.md`, `sample_kpi_calculations.csv`, `LLM_Evaluation_Rubric.md`, `LLM_Evaluation_Results.csv` |
| `AI/review/` | `Review_Notes_Sprint1.md` |

## File Placement Rules

| File type | Goes in | Notes |
|---|---|---|
| `.md` | The subfolder matching its topic | Use one file per deliverable. Do not combine unrelated work into one document. |
| `.json` | The same subfolder as the `.md` file it supports | Must be reviewed for field consistency before being committed. |
| `.csv` | The subfolder matching its topic | Use for calculated results or tabular output intended for a spreadsheet. |
| `.py` | `explanations/` for Sprint 1 | Any script that processes JSON must include a matching `test_*.py` file. |
| `.txt` | The subfolder matching its topic | Use only when the task list specifically requires a text file. |

## Temporary JSON Rules (Sprint 1)

No final JSON schema or approved field list exists yet.

Until finalized:
- Use existing JSON files as drafts, not source of truth.
- Do not add/rename/remove fields without approval in the Analysis & AI channel.
- If naming conflicts appear, stop and raise them before continuing.

## Naming Rules

- Filenames must match the folder structure exactly.
- Do not rename deliverables.
- Do not add personal names, initials, version numbers, or suffixes.

Incorrect examples:

```text
Baseline_EqualBlend_v2.md
Baseline_EqualBlend_John.md
KPI_Set_Final.md
```

Correct examples:

```text
Baseline_EqualBlend.md
KPI_Set.md
scenario_dry_year.json
```

- If a task genuinely needs a new file that is not listed here, propose the filename in the team channel before creating it.

## GitHub Workflow

1. Sync your fork before starting work.
2. Create a separate branch for your task.
3. Add the deliverable to the correct folder using the exact filename.
4. Commit the work with a clear message.
5. Open a pull request into the team fork's main working branch.
6. Resolve review comments before merging.

### Branch Naming Convention

All task branches must follow this format:

`task-<task-number>-<short-description>`

Rules:
- Use lowercase letters
- Separate words using hyphens
- Include the Planner task number
- Use one branch for one task

Examples:

`task-01-equal-blend`
`task-04-demand-research`
`task-10-kpi-calculations`

Example commit messages:

```text
docs: add equal-blend baseline
docs: add demand research
feat: add fallback JSON explainer
test: add JSON explainer tests
```

## Sprint 1 Rules

- Use the same current working draft configuration across all deliverables.
- Clearly label assumptions and estimated values.
- Do not treat incomplete or unsafe results as successful.
- Keep work inside the listed team folders.
- Raise unclear fields, missing files, or naming changes in the team channel before continuing.
