# Supabase schema references

This folder holds **read-only reference copies** of the Supabase (Postgres)
schema for the three tables the Analysis & AI pipeline reads from and writes
to. They are snapshots taken from the project's Supabase database for
engineers to read while working on `AI/integration/`; they are **not run
automatically** by any part of this repository, and copying them here does
not create, alter, or execute anything in a real database.

| File | Table | Purpose |
|---|---|---|
| `milp_model_input.sql` | `public.milp_model_input` | Stores the original scenario, provenance and solver input for one MILP run. |
| `milp_model_output.sql` | `public.milp_model_output` | Stores the MILP result consumed by the Analysis & AI pipeline. |
| `milp_ai_output.sql` | `public.milp_ai_output` | Stores the final, App-ready AI analysis produced from a `milp_model_output` row. |

## Data flow

```text
milp_model_input
      |
      v
  MILP solver
      |
      v
milp_model_output
      |
      v
Analysis & AI pipeline (AI/main.py, AI/integration/supabase_repository.py)
      |
      v
milp_ai_output
      |
      v
  App dashboard
```

`milp_model_output.input_id` links back to the `milp_model_input` row that
produced it, so provenance (scenario data, source snapshots, model
parameters, validation policy) can be retrieved separately when needed - see
`AI/integration/supabase_repository.py::load_milp_input`.

## Important notes

- **Do not execute these files.** They describe tables that already exist in
  the Supabase project; running them again is unnecessary and could conflict
  with the live schema.
- These are **reference snapshots**, not the source of truth for the live
  database. The live Supabase schema can change independently of this
  folder.
- **Schema changes must be coordinated with the database owners** before any
  code in this repository is written to depend on a new or renamed column.
  If a mismatch is found between these files and the real database, raise it
  with the database owners rather than guessing at the difference.
- Column names used by `AI/integration/supabase_repository.py` are taken
  directly from these files. If you update a table's real schema, refresh the
  matching `.sql` file here in the same change.
