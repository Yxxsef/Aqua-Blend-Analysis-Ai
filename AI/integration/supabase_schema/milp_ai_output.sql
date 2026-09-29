create table public.milp_ai_output (
  id uuid not null default gen_random_uuid (),
  origin_run_id integer null,
  milp_output_id uuid not null,
  scenario_id integer not null,
  status text not null default 'pending'::text,
  ai_provider text null,
  ai_model text null,
  ai_model_version text null,
  prompt_version text null,
  analysis_version text null,
  ai_contract_version text not null default '1.0'::text,
  milp_output_hash text not null,
  ai_cache_key text null,
  ai_input_json jsonb not null default '{}'::jsonb,
  executive_summary text null,
  decision_explanation text null,
  key_findings jsonb not null default '[]'::jsonb,
  anomalies jsonb not null default '[]'::jsonb,
  recommendations jsonb not null default '[]'::jsonb,
  warnings jsonb not null default '[]'::jsonb,
  risk_assessment jsonb not null default '{}'::jsonb,
  source_analysis jsonb not null default '{}'::jsonb,
  plant_analysis jsonb not null default '{}'::jsonb,
  quality_analysis jsonb not null default '{}'::jsonb,
  limitations jsonb not null default '[]'::jsonb,
  raw_ai_json jsonb not null default '{}'::jsonb,
  ai_output_hash text null,
  cache_reusable boolean not null default true,
  forced_recompute boolean not null default false,
  latency_ms double precision null,
  prompt_tokens integer null,
  completion_tokens integer null,
  total_tokens integer null,
  error_code text null,
  error_message text null,
  created_at timestamp with time zone not null default now(),
  started_at timestamp with time zone null,
  completed_at timestamp with time zone null,
  updated_at timestamp with time zone null,
constraint milp_ai_output_pkey primary key (id),
constraint FK_milp_ai_output_Scenarios_scenario_id foreign KEY (scenario_id) references "Scenarios" ("Id") on delete RESTRICT,
constraint FK_milp_ai_output_milp_model_output_milp_output_id foreign KEY (milp_output_id) references milp_model_output (id) on delete RESTRICT,
constraint FK_milp_ai_output_Runs_origin_run_id foreign KEY (origin_run_id) references "Runs" ("Id") on delete RESTRICT,
constraint fk_milp_ai_output_origin_run foreign KEY (origin_run_id) references "Runs" ("Id") on delete set null,
constraint fk_milp_ai_output_scenario foreign KEY (scenario_id) references "Scenarios" ("Id") on delete RESTRICT,
constraint fk_milp_ai_output_milp_output foreign KEY (milp_output_id) references milp_model_output (id) on delete RESTRICT,
constraint chk_milp_ai_output_raw_object check ((jsonb_typeof(raw_ai_json) = 'object'::text)),
constraint chk_milp_ai_output_input_object check ((jsonb_typeof(ai_input_json) = 'object'::text))
) TABLESPACE pg_default;

create index IF not exists idx_milp_ai_output_origin_run on public.milp_ai_output using btree (origin_run_id) TABLESPACE pg_default
where
(origin_run_id is not null);

create index IF not exists idx_milp_ai_output_milp_output on public.milp_ai_output using btree (milp_output_id) TABLESPACE pg_default;

create index IF not exists idx_milp_ai_output_scenario on public.milp_ai_output using btree (scenario_id) TABLESPACE pg_default;

create index IF not exists idx_milp_ai_output_cache_key on public.milp_ai_output using btree (ai_cache_key, created_at desc) TABLESPACE pg_default
where
(
(ai_cache_key is not null)
and (cache_reusable = true)
);

create index IF not exists idx_milp_ai_output_output_hash on public.milp_ai_output using btree (ai_output_hash) TABLESPACE pg_default
where
(ai_output_hash is not null);

create index IF not exists idx_milp_ai_output_status on public.milp_ai_output using btree (status) TABLESPACE pg_default;

create index IF not exists "IX_milp_ai_output_origin_run_id" on public.milp_ai_output using btree (origin_run_id) TABLESPACE pg_default;

create index IF not exists "IX_milp_ai_output_milp_output_id" on public.milp_ai_output using btree (milp_output_id) TABLESPACE pg_default;

create index IF not exists "IX_milp_ai_output_scenario_id" on public.milp_ai_output using btree (scenario_id) TABLESPACE pg_default;
