-- Slack notifications were removed from the application.
alter table if exists expert_tickets drop column if exists slack_notified;
