-- Run this once in Supabase: Dashboard > SQL Editor > New query > paste > Run.
create table if not exists public.scans (
  id               uuid primary key,
  client_id        text,
  created_at       timestamptz not null default now(),
  thumbnail        text,            -- small JPEG as a data URL (~15 KB)
  model            text,
  demo             boolean not null default false,
  total_items      integer not null default 0,
  recyclable_items integer not null default 0,
  co2_saved_kg     double precision not null default 0,
  points           integer not null default 0,
  level            text,
  analysis         jsonb not null
);

create index if not exists scans_client_created on public.scans (client_id, created_at desc);
create index if not exists scans_created on public.scans (created_at desc);

-- Lock the table down: only the Flask backend (service_role key, which bypasses RLS)
-- can read or write. The browser never talks to Supabase directly.
alter table public.scans enable row level security;
