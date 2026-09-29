create table public.milp_model_output (
  id uuid not null default gen_random_uuid (),
  schema_version character varying(16) not null,
  scenario_id character varying(128) not null,
  scenario_status character varying(32) not null default 'draft'::character varying,
  data_source_type character varying(32) null,
  data_source_view character varying(256) null,
  allow_estimated_values boolean not null default false,
  fail_if_source_missing_from_database boolean not null default true,
  fail_if_daily_availability_missing boolean not null default true,
  fail_if_required_quality_value_missing boolean not null default true,
  fail_if_demand_missing boolean not null default true,
  loader_status character varying(32) not null default 'NOT_RUN'::character varying,
  loader_scenario_ready boolean null,
  loader_validation_issues jsonb not null default '[]'::jsonb,
  loader_checks jsonb not null default '[]'::jsonb,
  preprocessing_status character varying(32) not null default 'NOT_RUN'::character varying,
  preprocessing_warnings jsonb not null default '[]'::jsonb,
  preprocessing_checks jsonb not null default '[]'::jsonb,
  output_consistency_status character varying(32) not null default 'NOT_RUN'::character varying,
  output_consistency_tolerance numeric(18, 10) null default 0.000001,
  output_consistency_checks jsonb not null default '[]'::jsonb,
  solver_status character varying(32) not null default 'NOT_SOLVED'::character varying,
  solver_is_feasible boolean null,
  solver_is_optimal boolean null,
  solver_objective_value numeric(18, 4) null,
  solver_version character varying(16) null,
  total_demand_ml_per_day numeric(18, 4) null,
  total_withdrawal_ml_per_day numeric(18, 4) null,
  total_treated_ml_per_day numeric(18, 4) null,
  total_delivered_ml_per_day numeric(18, 4) null,
  selected_source_count integer null,
  active_plant_count integer null,
  total_source_fixed_cost numeric(18, 4) null,
  total_source_variable_cost numeric(18, 4) null,
  total_plant_fixed_cost numeric(18, 4) null,
  total_plant_variable_cost numeric(18, 4) null,
  reconstructed_total_cost numeric(18, 4) null,
  total_cost numeric(18, 4) null,
  cost_reconciles boolean null,
  sources jsonb not null default '[]'::jsonb,
  plants jsonb not null default '[]'::jsonb,
  demand_zones jsonb not null default '[]'::jsonb,
  flows_source_to_plant jsonb not null default '[]'::jsonb,
  flows_plant_to_zone jsonb not null default '[]'::jsonb,
  quality jsonb not null default '{}'::jsonb,
  binding_constraints_summary jsonb not null default '[]'::jsonb,
  warnings jsonb not null default '[]'::jsonb,
  created_at timestamp with time zone not null default now(),
  origin_run_id integer null,
  input_id uuid null,
  scenario_db_id integer null,
  execution_key text null,
  input_hash text null,
  model_parameters_hash text null,
  milp_model_version text null,
  solver_name text null,
  solver_config_hash text null,
  solver_termination_condition text null,
  solver_message text null,
  solve_time_ms double precision null,
  raw_output_json jsonb not null default '{}'::jsonb,
  output_hash text null,
  cache_reusable boolean not null default true,
  forced_recompute boolean not null default false,
  started_at timestamp with time zone null,
  completed_at timestamp with time zone null,
  updated_at timestamp with time zone null,
  constraint milp_model_output_pkey primary key (id),
  constraint FK_milp_model_output_Scenarios_scenario_db_id foreign KEY (scenario_db_id) references "Scenarios" ("Id") on delete RESTRICT,
  constraint FK_milp_model_output_milp_model_input_input_id foreign KEY (input_id) references milp_model_input (id) on delete RESTRICT,
  constraint FK_milp_model_output_Runs_origin_run_id foreign KEY (origin_run_id) references "Runs" ("Id") on delete RESTRICT,
  constraint fk_milp_model_output_origin_run foreign KEY (origin_run_id) references "Runs" ("Id") on delete set null,
  constraint fk_milp_model_output_scenario foreign KEY (scenario_db_id) references "Scenarios" ("Id") on delete RESTRICT,
  constraint fk_milp_model_output_input foreign KEY (input_id) references milp_model_input (id) on delete RESTRICT,
  constraint chk_milp_model_output_raw_json_object check ((jsonb_typeof(raw_output_json) = 'object'::text))
) TABLESPACE pg_default;

create index IF not exists idx_milp_model_output_scenario on public.milp_model_output using btree (scenario_id) TABLESPACE pg_default;

create index IF not exists idx_milp_model_output_solver_status on public.milp_model_output using btree (solver_status) TABLESPACE pg_default;

create index IF not exists idx_milp_model_output_created_at on public.milp_model_output using btree (created_at) TABLESPACE pg_default;

create index IF not exists idx_milp_model_output_sources_gin on public.milp_model_output using gin (sources) TABLESPACE pg_default;

create index IF not exists idx_milp_model_output_flows_sp_gin on public.milp_model_output using gin (flows_source_to_plant) TABLESPACE pg_default;

create index IF not exists idx_milp_model_output_origin_run on public.milp_model_output using btree (origin_run_id) TABLESPACE pg_default
where
  (origin_run_id is not null);

create index IF not exists idx_milp_model_output_input_id on public.milp_model_output using btree (input_id) TABLESPACE pg_default
where
  (input_id is not null);

create index IF not exists idx_milp_model_output_scenario_db_id on public.milp_model_output using btree (scenario_db_id) TABLESPACE pg_default
where
  (scenario_db_id is not null);

create index IF not exists idx_milp_model_output_execution_key on public.milp_model_output using btree (execution_key, created_at desc) TABLESPACE pg_default
where
  (
    (execution_key is not null)
    and (cache_reusable = true)
  );

create index IF not exists idx_milp_model_output_output_hash on public.milp_model_output using btree (output_hash) TABLESPACE pg_default
where
  (output_hash is not null);

create index IF not exists "IX_milp_model_output_origin_run_id" on public.milp_model_output using btree (origin_run_id) TABLESPACE pg_default;

create index IF not exists "IX_milp_model_output_input_id" on public.milp_model_output using btree (input_id) TABLESPACE pg_default;

create index IF not exists "IX_milp_model_output_scenario_db_id" on public.milp_model_output using btree (scenario_db_id) TABLESPACE pg_default;
