-- Expert Plan review inbox (full SavedAssessment payload)
-- Run after 003_tickets_memory_privacy.sql in Supabase SQL Editor

create table if not exists plan_reviews (
  id                   text        primary key,
  payload              jsonb       not null default '{}',
  published            boolean     default false,
  archived_from_inbox  boolean     default false,
  created_at           text        default '',
  member_user_id       text,
  member_name          text
);

create index if not exists idx_plan_reviews_created
  on plan_reviews (created_at desc);

create index if not exists idx_plan_reviews_member
  on plan_reviews (member_user_id);

alter table plan_reviews enable row level security;
create policy "service_role_only_plan_reviews" on plan_reviews
  for all using (false) with check (false);
