create table public.milp_model_input (
  id uuid not null default gen_random_uuid (),
  run_id integer not null,
  scenario_id integer not null,
  run_external_id text not null,
  scenario_external_id text not null,
  input_status text not null default 'pending'::text,
  input_contract_version text not null default '1.0'::text,
  milp_model_version text null,
  scenario_name text not null,
  scenario_status text not null,
  data_source_type text null,
  data_source_view text null,
  allow_estimated_values boolean not null,
  fail_if_source_missing_from_database boolean not null,
  fail_if_daily_availability_missing boolean not null,
  fail_if_required_quality_value_missing boolean not null,
  fail_if_demand_missing boolean not null,
  sources jsonb not null default '[]'::jsonb,
  plants jsonb not null default '[]'::jsonb,
  demand_zones jsonb not null default '[]'::jsonb,
  source_to_plant_links jsonb not null default '[]'::jsonb,
  plant_to_zone_links jsonb not null default '[]'::jsonb,
  quality_limits jsonb not null default '{}'::jsonb,
  validation_policy jsonb not null default '{}'::jsonb,
  frontend_input_json jsonb not null default '{}'::jsonb,
  canonical_input_json jsonb not null,
  source_data_snapshot_json jsonb not null default '[]'::jsonb,
  model_parameters_json jsonb null,
  solver_config_json jsonb not null default '{}'::jsonb,
  input_hash text null,
  solver_config_hash text null,
  execution_key text null,
  created_at timestamp with time zone not null default now(),
  resolved_at timestamp with time zone null,
  scenario_data_json jsonb null,
  scenario_data_schema_version text not null default '1.0'::text,
  model_parameters_schema_version text not null default '1.0'::text,
  canonical_input_hash text null,
  scenario_data_hash text null,
  model_parameters_hash text null,
  constraint milp_model_input_pkey primary key (id),
  constraint milp_model_input_run_id_key unique (run_id),
  constraint FK_milp_model_input_Runs_run_id foreign KEY (run_id) references "Runs" ("Id") on delete RESTRICT,
  constraint FK_milp_model_input_Scenarios_scenario_id foreign KEY (scenario_id) references "Scenarios" ("Id") on delete RESTRICT,
  constraint fk_milp_model_input_run foreign KEY (run_id) references "Runs" ("Id") on delete CASCADE,
  constraint fk_milp_model_input_scenario foreign KEY (scenario_id) references "Scenarios" ("Id") on delete RESTRICT,
  constraint chk_milp_model_input_scenario_data_object check (
    (
      (scenario_data_json is null)
      or (jsonb_typeof(scenario_data_json) = 'object'::text)
    )
  ),
  constraint chk_milp_model_input_solver_config_object check (
    (jsonb_typeof(solver_config_json) = 'object'::text)
  ),
  constraint chk_milp_model_input_validation_policy_object check (
    (jsonb_typeof(validation_policy) = 'object'::text)
  ),
  constraint chk_milp_model_input_frontend_json_object check (
    (
      jsonb_typeof(frontend_input_json) = 'object'::text
    )
  ),
  constraint chk_milp_model_input_canonical_json_object check (
    (
      jsonb_typeof(canonical_input_json) = 'object'::text
    )
  ),
  constraint chk_milp_model_input_model_parameters_object check (
    (
      (model_parameters_json is null)
      or (
        jsonb_typeof(model_parameters_json) = 'object'::text
      )
    )
  ),
  constraint chk_milp_model_input_quality_limits_object check ((jsonb_typeof(quality_limits) = 'object'::text))
) TABLESPACE pg_default;

create index IF not exists idx_milp_model_input_scenario_id on public.milp_model_input using btree (scenario_id) TABLESPACE pg_default;

create index IF not exists idx_milp_model_input_input_hash on public.milp_model_input using btree (input_hash) TABLESPACE pg_default
where
  (input_hash is not null);

create index IF not exists idx_milp_model_input_execution_key on public.milp_model_input using btree (execution_key) TABLESPACE pg_default
where
  (execution_key is not null);

create index IF not exists idx_milp_model_input_created_at on public.milp_model_input using btree (created_at desc) TABLESPACE pg_default;

create index IF not exists idx_milp_model_input_canonical_hash on public.milp_model_input using btree (canonical_input_hash) TABLESPACE pg_default
where
  (canonical_input_hash is not null);

create index IF not exists idx_milp_model_input_scenario_data_hash on public.milp_model_input using btree (scenario_data_hash) TABLESPACE pg_default
where
  (scenario_data_hash is not null);

create index IF not exists idx_milp_model_input_model_parameters_hash on public.milp_model_input using btree (model_parameters_hash) TABLESPACE pg_default
where
  (model_parameters_hash is not null);

create unique INDEX IF not exists "IX_milp_model_input_run_id" on public.milp_model_input using btree (run_id) TABLESPACE pg_default;

create index IF not exists "IX_milp_model_input_scenario_id" on public.milp_model_input using btree (scenario_id) TABLESPACE pg_default;
