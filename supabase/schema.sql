-- Run in the Supabase SQL editor. Only the Vercel server's service role may access this table.
create table if not exists public.access_codes (
  id uuid primary key default gen_random_uuid(),
  code_hash text not null unique,
  label text not null,
  status text not null default 'active' check (status in ('active','revoked')),
  expires_at timestamptz,
  max_uses integer check (max_uses is null or max_uses > 0),
  used_count integer not null default 0 check (used_count >= 0),
  created_at timestamptz not null default now(),
  created_by uuid,
  last_used_at timestamptz
);
alter table public.access_codes enable row level security;
revoke all on public.access_codes from anon, authenticated;

-- Atomic admission prevents concurrent requests from exceeding max_uses.
create or replace function public.admit_access_code(p_id uuid)
returns boolean
language plpgsql
security invoker
set search_path = public
as $$
begin
  update public.access_codes
  set used_count = used_count + 1, last_used_at = now()
  where id = p_id and status = 'active'
    and (expires_at is null or expires_at > now())
    and (max_uses is null or used_count < max_uses);
  return found;
end;
$$;
revoke all on function public.admit_access_code(uuid) from public, anon, authenticated;
grant execute on function public.admit_access_code(uuid) to service_role;

-- Each customer receives a distinct access code. Its niche choices stay with
-- that membership and remain editable while the code is active.
create table if not exists public.viewer_preferences (
  code_id uuid primary key references public.access_codes(id) on delete cascade,
  niches jsonb not null default '[]'::jsonb check (jsonb_typeof(niches) = 'array'),
  keywords jsonb not null default '[]'::jsonb check (jsonb_typeof(keywords) = 'array'),
  updated_at timestamptz not null default now()
);
alter table public.viewer_preferences enable row level security;
revoke all on public.viewer_preferences from anon, authenticated;
grant select, insert, update, delete on public.viewer_preferences to service_role;

-- The watcher mirrors its local archive here. Browser clients have no direct
-- table access; authenticated Next.js routes authorize and filter every view.
create table if not exists public.jobs (
  event_key text primary key,
  source text not null,
  source_job_id text,
  source_url text,
  title text not null,
  company text,
  description text,
  skills jsonb not null default '[]'::jsonb,
  location text,
  category text,
  tags jsonb not null default '[]'::jsonb,
  salary_raw text,
  salary_min numeric,
  salary_max numeric,
  salary_currency text,
  salary_period text,
  work_type_raw text,
  work_type text,
  source_posted_raw text,
  source_posted_at timestamptz,
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  detail_checked_at timestamptz,
  primary_niche text,
  niches text[] not null default '{}',
  niche_scores jsonb not null default '{}'::jsonb,
  normalized_tags text[] not null default '{}',
  quality_flags text[] not null default '{}',
  stage text not null default 'new',
  notification_sent boolean not null default false,
  owner_score numeric,
  owner_priority text,
  updated_at timestamptz not null default now()
);
create index if not exists jobs_first_seen_idx on public.jobs(first_seen_at desc);
create index if not exists jobs_posted_idx on public.jobs(source_posted_at desc);
create index if not exists jobs_niches_idx on public.jobs using gin(niches);
create index if not exists jobs_source_idx on public.jobs(source);
alter table public.jobs enable row level security;
revoke all on public.jobs from anon, authenticated;
grant select, insert, update, delete on public.jobs to service_role;

create table if not exists public.niche_taxonomy (
  id text primary key,
  group_name text not null,
  label text not null,
  aliases text[] not null default '{}'
);
alter table public.niche_taxonomy enable row level security;
revoke all on public.niche_taxonomy from anon, authenticated;
grant select, insert, update, delete on public.niche_taxonomy to service_role;

create table if not exists public.owner_sessions (
  token_hash text primary key,
  user_id uuid not null,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  revoked_at timestamptz
);
create index if not exists owner_sessions_user_idx on public.owner_sessions(user_id);
alter table public.owner_sessions enable row level security;
revoke all on public.owner_sessions from anon, authenticated;
grant select, insert, update, delete on public.owner_sessions to service_role;

-- Run once after creating jobs; subscription uses server-side service role only.
do $$ begin
  alter publication supabase_realtime add table public.jobs;
exception when duplicate_object then null;
end $$;

create or replace function public.customer_jobs(p_niches text[], p_min_score integer default 1)
returns setof public.jobs
language sql stable security invoker
set search_path = public
as $$
  select j.* from public.jobs j
  where j.niches && p_niches
    and (select coalesce(max(coalesce((j.niche_scores ->> n)::integer, 0)), 0)
         from unnest(p_niches) as n) >= p_min_score;
$$;
revoke all on function public.customer_jobs(text[], integer) from public, anon, authenticated;
grant execute on function public.customer_jobs(text[], integer) to service_role;

create or replace function public.customer_jobs_ranked(p_niches text[], p_min_score integer default 1)
returns setof public.jobs
language sql stable security invoker
set search_path = public
as $$
  select j.* from public.jobs j
  cross join lateral (
    select coalesce(max(coalesce((j.niche_scores ->> n)::integer, 0)), 0) as score
    from unnest(p_niches) as n
  ) match
  where j.niches && p_niches and match.score >= p_min_score
  order by match.score desc, j.first_seen_at desc;
$$;
revoke all on function public.customer_jobs_ranked(text[], integer) from public, anon, authenticated;
grant execute on function public.customer_jobs_ranked(text[], integer) to service_role;
