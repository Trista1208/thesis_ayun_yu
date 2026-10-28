-- App user accounts (member login + saved profile)
-- Run after 001_ayun_schema.sql when using Supabase

create table if not exists app_users (
  id                uuid        primary key default gen_random_uuid(),
  email             text        unique not null,
  password_hash     text        not null,
  display_name      text        default '',
  pseudonym         text        default '',
  member_data       jsonb       default '{}',
  personal_profile  jsonb       default '{}',
  enabled_sections  jsonb       default '{}',
  created_at        timestamptz default now(),
  updated_at        timestamptz default now()
);

create index if not exists idx_app_users_email on app_users (email);

alter table app_users enable row level security;
create policy "service_role_only_app_users" on app_users
  for all using (false) with check (false);
