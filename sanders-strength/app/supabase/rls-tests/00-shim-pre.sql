-- Faithful local shim of the Supabase machinery that supabase/schema.sql depends on.
-- In production these are provided by the platform:
--   * auth.users            — GoTrue's user table
--   * auth.uid(), auth.jwt() — read the JWT claims PostgREST sets per request
--   * role "authenticated"   — the non-owner role client queries run as (subject to RLS)
-- The definitions of uid()/jwt() below are copied from Supabase's own implementations.

create schema auth;

create table auth.users (
  id uuid primary key,
  email text unique,
  raw_user_meta_data jsonb default '{}'::jsonb
);

create function auth.uid() returns uuid
language sql stable
as $$
  select (nullif(current_setting('request.jwt.claims', true), '')::json ->> 'sub')::uuid
$$;

create function auth.jwt() returns jsonb
language sql stable
as $$
  select nullif(current_setting('request.jwt.claims', true), '')::jsonb
$$;

create role authenticated nologin;
grant usage on schema auth to authenticated;
grant execute on all functions in schema auth to authenticated;
