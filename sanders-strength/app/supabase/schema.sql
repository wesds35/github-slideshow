-- Sanders Strength — Supabase schema + Row-Level Security
--
-- Run this once in your Supabase project's SQL Editor (Dashboard → SQL Editor → New query →
-- paste this whole file → Run). It creates every table the app needs and locks them down so an
-- athlete's Postgres session can only ever touch rows tied to their own auth.uid() — enforced by
-- the database itself, not by app code, so a bug in the frontend can't leak one athlete's data
-- to another.
--
-- After running this, see ../README-DEPLOY.md for the one remaining manual step: promoting your
-- own account to the 'coach' role.

-- ── Extensions ────────────────────────────────────────────────────────────────────────────────
create extension if not exists pgcrypto; -- gen_random_uuid()

-- ── profiles ──────────────────────────────────────────────────────────────────────────────────
-- One row per auth user. New signups default to 'athlete'; you promote yourself to 'coach' once,
-- manually, after your own first sign-in (see README-DEPLOY.md).
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  role text not null default 'athlete' check (role in ('coach', 'athlete')),
  full_name text,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

-- Helper used throughout every policy below: is the current user the coach? Defined here, first,
-- since the trigger and policies that follow all depend on it.
create function public.is_coach()
returns boolean
language sql
stable
as $$
  select exists (select 1 from public.profiles where id = auth.uid() and role = 'coach');
$$;

create policy "profiles: self read" on public.profiles
  for select using (id = auth.uid());

create policy "profiles: self update" on public.profiles
  for update using (id = auth.uid()) with check (id = auth.uid());

-- Athletes may edit their own profile (e.g. full_name), but must never be able to grant
-- themselves the coach role by PATCHing their own row directly. A trigger — not the RLS check
-- above — enforces this, because it can safely compare against the pre-update value. Role
-- changes are allowed only when the updater is an existing coach, or when there is no JWT at
-- all (auth.uid() is null) — the latter is the Supabase SQL editor / service role, which is how
-- the very first coach gets promoted per README-DEPLOY.md. A client request always carries a
-- JWT, so this null-check never opens a path from the app.
create function public.prevent_role_self_escalation()
returns trigger
language plpgsql
as $$
begin
  if auth.uid() is not null and not public.is_coach() then
    new.role := old.role;
  end if;
  return new;
end;
$$;

create trigger profiles_prevent_role_escalation
  before update on public.profiles
  for each row execute procedure public.prevent_role_self_escalation();

-- Auto-create a profile row the moment someone signs up.
create function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, new.raw_user_meta_data ->> 'full_name');
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ── athletes ──────────────────────────────────────────────────────────────────────────────────
-- The coach creates a row (name + email, user_id null = "invited"). When that person signs up
-- with the matching email, they claim the row themselves by setting user_id = auth.uid() — see
-- the claim policy below. Until claimed, the row has no linked login and isn't visible to anyone
-- but the coach.
create table public.athletes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users (id) on delete set null,
  name text not null,
  initials text not null,
  email text not null unique,
  created_at timestamptz not null default now()
);

alter table public.athletes enable row level security;

create policy "athletes: coach full access" on public.athletes
  for all using (public.is_coach()) with check (public.is_coach());

create policy "athletes: self read" on public.athletes
  for select using (user_id = auth.uid());

-- The unclaimed invite matching your own verified email must be SELECT-visible: Postgres
-- requires UPDATE target rows referenced by a WHERE clause to pass SELECT policies too, so
-- without this the claim update below can never find the row it's claiming.
create policy "athletes: read own invite" on public.athletes
  for select using (user_id is null and email = auth.jwt() ->> 'email');

create policy "athletes: claim own invite" on public.athletes
  for update
  using (user_id is null and email = auth.jwt() ->> 'email')
  with check (user_id = auth.uid() and email = auth.jwt() ->> 'email');

-- Convenience view used by policies below: "does this athlete row belong to me?"
create function public.owns_athlete(athlete_id uuid)
returns boolean
language sql
stable
as $$
  select exists (
    select 1 from public.athletes where id = athlete_id and user_id = auth.uid()
  );
$$;

-- ── programs / weeks / days / exercises ──────────────────────────────────────────────────────
-- Coach-authored content. Athletes only ever read the structure of a program that's actually
-- been assigned to them (checked via the assignments table), never the coach's full library.
create table public.programs (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  duration_weeks integer not null,
  tags text not null default '',
  created_at timestamptz not null default now()
);

create table public.program_weeks (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references public.programs (id) on delete cascade,
  week_number integer not null
);

create table public.program_days (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references public.programs (id) on delete cascade, -- denormalized for simpler RLS
  week_id uuid not null references public.program_weeks (id) on delete cascade,
  label text not null,
  "order" integer not null
);

create table public.program_exercises (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references public.programs (id) on delete cascade, -- denormalized for simpler RLS
  day_id uuid not null references public.program_days (id) on delete cascade,
  name text not null,
  track text not null check (track in ('load', 'distance', 'wattage')),
  prescribed_sets integer not null,
  prescribed_reps integer,
  prescription_note text not null default '',
  rest_note text not null default '',
  "order" integer not null
);

alter table public.programs enable row level security;
alter table public.program_weeks enable row level security;
alter table public.program_days enable row level security;
alter table public.program_exercises enable row level security;

create policy "programs: coach full access" on public.programs
  for all using (public.is_coach()) with check (public.is_coach());
create policy "program_weeks: coach full access" on public.program_weeks
  for all using (public.is_coach()) with check (public.is_coach());
create policy "program_days: coach full access" on public.program_days
  for all using (public.is_coach()) with check (public.is_coach());
create policy "program_exercises: coach full access" on public.program_exercises
  for all using (public.is_coach()) with check (public.is_coach());

-- ── assignments / scheduled_sessions ──────────────────────────────────────────────────────────
create table public.assignments (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references public.programs (id) on delete cascade,
  athlete_id uuid not null references public.athletes (id) on delete cascade,
  start_date date not null,
  created_at timestamptz not null default now()
);

create table public.scheduled_sessions (
  id uuid primary key default gen_random_uuid(),
  assignment_id uuid not null references public.assignments (id) on delete cascade,
  athlete_id uuid not null references public.athletes (id) on delete cascade,
  day_id uuid not null references public.program_days (id) on delete cascade,
  date date not null,
  status text not null default 'scheduled' check (status in ('scheduled', 'completed', 'missed'))
);

alter table public.assignments enable row level security;
alter table public.scheduled_sessions enable row level security;

create policy "assignments: coach full access" on public.assignments
  for all using (public.is_coach()) with check (public.is_coach());
create policy "assignments: self read" on public.assignments
  for select using (public.owns_athlete(athlete_id));

create policy "scheduled_sessions: coach full access" on public.scheduled_sessions
  for all using (public.is_coach()) with check (public.is_coach());
create policy "scheduled_sessions: self read" on public.scheduled_sessions
  for select using (public.owns_athlete(athlete_id));
create policy "scheduled_sessions: self update status" on public.scheduled_sessions
  for update using (public.owns_athlete(athlete_id)) with check (public.owns_athlete(athlete_id));

-- An athlete may read a program's structure only if it's assigned to them right now. These
-- policies live here — after assignments exists — because Postgres validates the tables a policy
-- references at creation time.
create policy "programs: read if assigned to me" on public.programs
  for select using (
    exists (
      select 1 from public.assignments a
      where a.program_id = programs.id and public.owns_athlete(a.athlete_id)
    )
  );
create policy "program_weeks: read if assigned to me" on public.program_weeks
  for select using (
    exists (
      select 1 from public.assignments a
      where a.program_id = program_weeks.program_id and public.owns_athlete(a.athlete_id)
    )
  );
create policy "program_days: read if assigned to me" on public.program_days
  for select using (
    exists (
      select 1 from public.assignments a
      where a.program_id = program_days.program_id and public.owns_athlete(a.athlete_id)
    )
  );
create policy "program_exercises: read if assigned to me" on public.program_exercises
  for select using (
    exists (
      select 1 from public.assignments a
      where a.program_id = program_exercises.program_id and public.owns_athlete(a.athlete_id)
    )
  );

-- ── logged_sets ───────────────────────────────────────────────────────────────────────────────
create table public.logged_sets (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.scheduled_sessions (id) on delete cascade,
  exercise_id uuid not null references public.program_exercises (id) on delete cascade,
  athlete_id uuid not null references public.athletes (id) on delete cascade,
  exercise_name text not null,
  track text not null check (track in ('load', 'distance', 'wattage')),
  set_number integer not null,
  weight numeric,
  reps integer,
  distance numeric,
  load numeric,
  watts numeric,
  duration_sec numeric,
  volume numeric not null,
  is_pr boolean not null default false,
  logged_at timestamptz not null default now()
);

alter table public.logged_sets enable row level security;

create policy "logged_sets: coach read all" on public.logged_sets
  for select using (public.is_coach());
create policy "logged_sets: self read" on public.logged_sets
  for select using (public.owns_athlete(athlete_id));
create policy "logged_sets: self insert" on public.logged_sets
  for insert with check (public.owns_athlete(athlete_id));

-- ── badge_definitions / earned_badges ─────────────────────────────────────────────────────────
create table public.badge_definitions (
  id text primary key, -- deterministic, e.g. 'load-1' .. 'load-6'
  track text not null check (track in ('load', 'distance', 'wattage')),
  tier integer not null,
  name text not null,
  threshold numeric not null
);

create table public.earned_badges (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athletes (id) on delete cascade,
  badge_definition_id text not null references public.badge_definitions (id) on delete cascade,
  earned_at timestamptz not null default now(),
  unique (athlete_id, badge_definition_id)
);

alter table public.badge_definitions enable row level security;
alter table public.earned_badges enable row level security;

create policy "badge_definitions: any signed-in read" on public.badge_definitions
  for select using (auth.uid() is not null);
create policy "badge_definitions: coach write" on public.badge_definitions
  for all using (public.is_coach()) with check (public.is_coach());

create policy "earned_badges: coach read all" on public.earned_badges
  for select using (public.is_coach());
create policy "earned_badges: self read" on public.earned_badges
  for select using (public.owns_athlete(athlete_id));
create policy "earned_badges: self insert" on public.earned_badges
  for insert with check (public.owns_athlete(athlete_id));

-- ── seed the badge tiers (matches sanders-strength/REFERENCE.md) ────────────────────────────
insert into public.badge_definitions (id, track, tier, name, threshold) values
  ('load-1', 'load', 1, 'Thrall', 10000),
  ('load-2', 'load', 2, 'Karl', 50000),
  ('load-3', 'load', 3, 'Jarl', 150000),
  ('load-4', 'load', 4, 'Berserker', 500000),
  ('load-5', 'load', 5, 'Einherjar', 1000000),
  ('load-6', 'load', 6, 'Valhalla', 5000000),
  ('distance-1', 'distance', 1, 'Thrall', 5000),
  ('distance-2', 'distance', 2, 'Karl', 25000),
  ('distance-3', 'distance', 3, 'Jarl', 75000),
  ('distance-4', 'distance', 4, 'Berserker', 250000),
  ('distance-5', 'distance', 5, 'Einherjar', 750000),
  ('distance-6', 'distance', 6, 'Valhalla', 3000000),
  ('wattage-1', 'wattage', 1, 'Thrall', 5000),
  ('wattage-2', 'wattage', 2, 'Karl', 25000),
  ('wattage-3', 'wattage', 3, 'Jarl', 75000),
  ('wattage-4', 'wattage', 4, 'Berserker', 250000),
  ('wattage-5', 'wattage', 5, 'Einherjar', 750000),
  ('wattage-6', 'wattage', 6, 'Valhalla', 3000000)
on conflict (id) do nothing;

-- ── indexes ───────────────────────────────────────────────────────────────────────────────────
-- Postgres does not auto-index foreign-key columns (unlike primary keys), and every query pattern
-- in the app filters by exactly these columns.
create index on public.athletes (email);
create index on public.program_weeks (program_id);
create index on public.program_days (week_id);
create index on public.program_days (program_id);
create index on public.program_exercises (day_id);
create index on public.program_exercises (program_id);
create index on public.assignments (program_id);
create index on public.assignments (athlete_id);
create index on public.scheduled_sessions (assignment_id);
create index on public.scheduled_sessions (athlete_id, date);
create index on public.scheduled_sessions (day_id);
create index on public.logged_sets (session_id);
create index on public.logged_sets (athlete_id, exercise_name);
create index on public.logged_sets (exercise_id);
create index on public.earned_badges (athlete_id);
