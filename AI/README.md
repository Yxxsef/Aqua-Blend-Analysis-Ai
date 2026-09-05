# AquaBlend Analysis & AI

This folder contains all Analysis & AI Sprint 1 deliverables.

In this repository, the top-level team folder is:

```text
AI/
```

Do not create new top-level folders without raising it in the Analysis & AI team channel first.

## Integrated Pipeline Entry Point

`AI/main.py` is the Analysis & AI team's internal pipeline entry point. The
wider AquaBlend backend should call it after receiving structured MILP Results
JSON; the project-wide backend entry point remains separate.

Pipeline order:

1. Validate raw MILP Results JSON.
2. Adapt the result into the internal format.
3. Calculate KPIs and the KPI gate.
4. Determine confidence from provenance.
5. Generate the deterministic explanation.
6. Optionally run and validate an LLM rewrite.
7. Use the deterministic fallback when the LLM is unavailable or rejected.
8. Return the App & Delivery response contract.

`main.py` coordinates existing modules and does not replace their business
logic. Model configuration is optional; without it, the deterministic fallback
is used. Unvalidated LLM output is never returned for display.

```text
python AI/main.py AI/explanations/llm_reporting/fixtures/model_output_example.json
python AI/main.py <results.json> --output <response.json>
python AI/main.py <results.json> --model-config AI/explanations/model_config.example.json
python -m pytest AI/tests/test_main.py -q
```

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
