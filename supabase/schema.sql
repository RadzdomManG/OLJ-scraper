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
