-- Run this in Supabase's SQL Editor (Dashboard -> SQL Editor -> New query)

create table if not exists observations (
    id bigint generated always as identity primary key,
    entity_name text not null,
    entity_type text not null,
    entity_resolution_method text,
    domain text,
    year integer not null,
    indicator text not null,
    value double precision,
    unit text,
    source_document text,
    source_page text,
    extraction_method text,
    confidence double precision,
    extracted_at timestamptz,
    validation_flag boolean default false,
    validation_reason text
);

-- Useful indexes for the query patterns your API uses
create index if not exists idx_observations_entity_name on observations (entity_name);
create index if not exists idx_observations_indicator on observations (indicator);
create index if not exists idx_observations_year on observations (year);
create index if not exists idx_observations_domain on observations (domain);

-- Row Level Security: lock the table down, then allow read-only public access.
-- This is required before exposing the anon key in a frontend app.
alter table observations enable row level security;

create policy "Public read access"
    on observations for select
    using (true);

-- No insert/update/delete policy is created for the anon/public role,
-- so the frontend (chatbot + viewer) can only ever read, never modify data.
-- Your pipeline should write using the SERVICE ROLE key (kept secret,
-- never shipped to the frontend), which bypasses RLS entirely.
