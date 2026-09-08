-- Migration v2: Add domain field to observations table
-- Run this in Supabase's SQL Editor if upgrading an existing database

alter table observations add column if not exists domain text;

-- Index for domain query patterns
create index if not exists idx_observations_domain on observations (domain);
