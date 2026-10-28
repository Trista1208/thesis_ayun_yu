-- Link validated knowledge nodes back to their expert ticket
-- Run after 004_plan_reviews.sql in Supabase SQL Editor

alter table knowledge_nodes
  add column if not exists source_ticket_id text;

create index if not exists idx_knowledge_nodes_ticket
  on knowledge_nodes (source_ticket_id);
