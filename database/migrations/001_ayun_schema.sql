-- =============================================================
-- AYUN Sport Recommendation — Initial Database Schema
-- Inspired by WearAware (Supabase Postgres) + digital-twin needs
-- Run in Supabase SQL Editor, or via Supabase CLI
-- =============================================================

create extension if not exists "pgcrypto";

-- ─────────────────────────────────────────────────────────────
-- MEMBERS (pseudonymized — link to AYUN archive / tokenization)
-- ─────────────────────────────────────────────────────────────
create table if not exists members (
  id            uuid        primary key default gen_random_uuid(),
  pseudonym     text        unique not null,
  sex           text,
  birth_year    int,
  notes         text,
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);

-- ─────────────────────────────────────────────────────────────
-- ASSESSMENTS (each clinic visit / app session snapshot)
-- ─────────────────────────────────────────────────────────────
create table if not exists assessments (
  id                      uuid        primary key default gen_random_uuid(),
  member_id               uuid        references members (id) on delete set null,
  assessed_at             timestamptz default now(),
  age                     int,
  sex                     text,
  member_data             jsonb       not null default '{}',
  personal_profile        jsonb       default '{}',
  triggered_recommendations jsonb     default '[]',
  parameter_ratings       jsonb       default '[]',
  training_zones          jsonb       default '{}',
  context_for_llm         text,
  source                  text        default 'app',
  created_at              timestamptz default now()
);

create index if not exists idx_assessments_member on assessments (member_id, assessed_at desc);

-- ─────────────────────────────────────────────────────────────
-- EXPERT REVIEWS (doctor sign-off — audit trail)
-- ─────────────────────────────────────────────────────────────
create table if not exists expert_reviews (
  id                uuid        primary key default gen_random_uuid(),
  assessment_id     uuid        references assessments (id) on delete cascade,
  reviewed_by       text        not null,
  review_date       date,
  recommendations   jsonb       not null default '[]',
  export_meta       jsonb       default '{}',
  knowledge_saved   boolean     default false,
  created_at        timestamptz default now()
);

-- ─────────────────────────────────────────────────────────────
-- KNOWLEDGE NODES (validated clinical knowledge corpus)
-- ─────────────────────────────────────────────────────────────
create table if not exists knowledge_nodes (
  id              text        primary key,
  title           text        not null,
  category        text        not null default 'General',
  summary         text        not null default '',
  passages        jsonb       default '[]',
  captured_by     text        not null default '',
  source          text        not null default 'manual',
  member_context  text        default '',
  tags            jsonb       default '[]',
  created_at      timestamptz default now()
);

create index if not exists idx_knowledge_nodes_created on knowledge_nodes (created_at desc);

-- ─────────────────────────────────────────────────────────────
-- EXPERT TICKETS (Q&A pipeline)
-- ─────────────────────────────────────────────────────────────
create table if not exists expert_tickets (
  id                  text        primary key,
  question            text        not null,
  from_role           text        not null default 'patient',
  from_name           text        not null default '',
  status              text        not null default 'open',
  draft_answer        text        default '',
  validated_by        text        default '',
  member_snapshot     jsonb       default '{}',
  chat_context        text        default '',
  assigned_expert_id  text        default 'general_pool',
  category            text        default 'General',
  source              text        default 'patient_direct',
  slack_notified      boolean     default false,
  created_at          timestamptz default now(),
  updated_at          timestamptz default now()
);

create index if not exists idx_expert_tickets_status on expert_tickets (status, updated_at desc);

-- ─────────────────────────────────────────────────────────────
-- AYUN HISTORICAL IMPORT (bulk rows from Excel / research archive)
-- ─────────────────────────────────────────────────────────────
create table if not exists ayun_import_batches (
  id            uuid        primary key default gen_random_uuid(),
  batch_name    text        not null,
  source_file   text,
  row_count     int         default 0,
  imported_by   text,
  imported_at   timestamptz default now()
);

create table if not exists ayun_import_rows (
  id            uuid        primary key default gen_random_uuid(),
  batch_id      uuid        not null references ayun_import_batches (id) on delete cascade,
  pseudonym     text,
  row_data      jsonb       not null,
  created_at    timestamptz default now()
);

create index if not exists idx_ayun_import_rows_batch on ayun_import_rows (batch_id);

-- ─────────────────────────────────────────────────────────────
-- RLS (research prototype — tighten before production)
-- Service role bypasses RLS; anon key should not be used from Streamlit
-- ─────────────────────────────────────────────────────────────
alter table members            enable row level security;
alter table assessments        enable row level security;
alter table expert_reviews     enable row level security;
alter table knowledge_nodes    enable row level security;
alter table expert_tickets     enable row level security;
alter table ayun_import_batches enable row level security;
alter table ayun_import_rows   enable row level security;

-- Deny all for anon/authenticated by default (service role only for prototype)
create policy "service_role_only_members" on members
  for all using (false) with check (false);
create policy "service_role_only_assessments" on assessments
  for all using (false) with check (false);
create policy "service_role_only_reviews" on expert_reviews
  for all using (false) with check (false);
create policy "service_role_only_knowledge" on knowledge_nodes
  for all using (false) with check (false);
create policy "service_role_only_tickets" on expert_tickets
  for all using (false) with check (false);
create policy "service_role_only_import_batches" on ayun_import_batches
  for all using (false) with check (false);
create policy "service_role_only_import_rows" on ayun_import_rows
  for all using (false) with check (false);
