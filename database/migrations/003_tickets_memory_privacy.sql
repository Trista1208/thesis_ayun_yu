-- Tickets linked to member accounts, episodic memory, privacy settings
-- Run after 002_app_users.sql in Supabase SQL Editor

alter table expert_tickets
  add column if not exists member_user_id text;

create index if not exists idx_expert_tickets_member
  on expert_tickets (member_user_id, updated_at desc);

alter table app_users
  add column if not exists privacy_settings jsonb default '{}';

-- Episodic memory (Tier 2) — per-member session summaries with TTL
create table if not exists member_memory (
  id              text        primary key,
  user_id         text        not null,
  session_id      text        default '',
  summary         text        not null default '',
  topics          jsonb       default '[]',
  turn_count      int         default 0,
  confidence_avg  text        default 'medium',
  created_at      timestamptz default now(),
  expires_at      timestamptz
);

create index if not exists idx_member_memory_user
  on member_memory (user_id, created_at desc);

alter table member_memory enable row level security;
create policy "service_role_only_member_memory" on member_memory
  for all using (false) with check (false);
