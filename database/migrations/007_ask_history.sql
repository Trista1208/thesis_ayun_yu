-- Saved Ask Joule questions and answers, per member.
-- Run after 006_drop_slack.sql in the Supabase SQL editor.

create table if not exists ask_history (
  id          text        primary key,
  user_id     text        not null,
  question    text        not null default '',
  answer      text        not null default '',
  mode        text        default 'cited',
  citations   jsonb       default '[]',
  confidence  text        default '',
  created_at  timestamptz default now()
);

create index if not exists idx_ask_history_user
  on ask_history (user_id, created_at desc);

alter table ask_history enable row level security;
create policy "service_role_only_ask_history" on ask_history
  for all using (false) with check (false);
