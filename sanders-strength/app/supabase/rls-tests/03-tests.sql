-- RLS verification suite for supabase/schema.sql.
-- Simulates GoTrue signups (inserts into auth.users, firing handle_new_user), then runs queries
-- as the `authenticated` role with per-user JWT claims, exactly as PostgREST does in production.
-- Every check prints "PASS: ..." or "FAIL: ...".

\set QUIET on
\pset footer off
\pset tuples_only on

-- ── Fixture: three signups (coach + two athletes), coach promoted via "SQL editor" ─────────────
insert into auth.users (id, email, raw_user_meta_data) values
  ('00000000-0000-0000-0000-000000000001', 'coach@ss.test',  '{"full_name":"Coach Sanders"}'),
  ('00000000-0000-0000-0000-0000000000aa', 'anna@ss.test',   '{"full_name":"Anna Athlete"}'),
  ('00000000-0000-0000-0000-0000000000bb', 'bjorn@ss.test',  '{"full_name":"Bjorn Athlete"}');

select case when count(*) = 3 then 'PASS: signup trigger created 3 profiles'
            else 'FAIL: expected 3 profiles, got ' || count(*) end
from public.profiles;

update public.profiles set role = 'coach' where id = '00000000-0000-0000-0000-000000000001';

select case when (select role from public.profiles where id = '00000000-0000-0000-0000-000000000001') = 'coach'
            then 'PASS: SQL-editor coach promotion sticks (no JWT context)'
            else 'FAIL: coach promotion was reverted by the anti-escalation trigger' end;

-- ── Coach session ──────────────────────────────────────────────────────────────────────────────
set role authenticated;
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-000000000001","email":"coach@ss.test"}', false);

-- Coach invites two athletes
insert into public.athletes (id, name, initials, email) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'Anna Athlete',  'AA', 'anna@ss.test'),
  ('aaaaaaaa-0000-0000-0000-000000000002', 'Bjorn Athlete', 'BA', 'bjorn@ss.test');

select case when count(*) = 2 then 'PASS: coach sees full roster (2 athletes)'
            else 'FAIL: coach roster count ' || count(*) end
from public.athletes;

-- Coach builds a program assigned ONLY to Anna, and a second program assigned to nobody
insert into public.programs (id, name, duration_weeks) values
  ('bbbbbbbb-0000-0000-0000-000000000001', 'Anna Block', 1),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'Unassigned Secret Block', 1);
insert into public.program_weeks (id, program_id, week_number) values
  ('cccccccc-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000001', 1);
insert into public.program_days (id, program_id, week_id, label, "order") values
  ('dddddddd-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000001',
   'cccccccc-0000-0000-0000-000000000001', 'Day 1', 0);
insert into public.program_exercises (id, program_id, day_id, name, track, prescribed_sets, prescribed_reps, "order") values
  ('eeeeeeee-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000001',
   'dddddddd-0000-0000-0000-000000000001', 'Back Squat', 'load', 5, 3, 0);
insert into public.assignments (id, program_id, athlete_id, start_date) values
  ('ffffffff-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000001',
   'aaaaaaaa-0000-0000-0000-000000000001', current_date);
insert into public.scheduled_sessions (id, assignment_id, athlete_id, day_id, date) values
  ('99999999-0000-0000-0000-000000000001', 'ffffffff-0000-0000-0000-000000000001',
   'aaaaaaaa-0000-0000-0000-000000000001', 'dddddddd-0000-0000-0000-000000000001', current_date);

-- ── Anna's session: claim + isolation checks ───────────────────────────────────────────────────
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-0000000000aa","email":"anna@ss.test"}', false);

-- Before claiming, Anna sees exactly one row: her own pending invite (needed for the claim
-- update to find its target), and nobody else's.
select case when count(*) = 1 and min(email) = 'anna@ss.test'
            then 'PASS: unclaimed athlete sees only her own invite'
            else 'FAIL: unclaimed athlete sees ' || count(*) || ' athlete rows' end
from public.athletes;

-- Claim (exactly what src/context/auth.tsx runs)
update public.athletes
set user_id = '00000000-0000-0000-0000-0000000000aa'
where email = 'anna@ss.test' and user_id is null;

select case when count(*) = 1 and min(email) = 'anna@ss.test'
            then 'PASS: Anna claimed her invite and sees only her own row'
            else 'FAIL: post-claim roster wrong (' || count(*) || ' rows)' end
from public.athletes;

-- Anna tries to claim/steal Bjorn's invite -> USING clause filters it out, 0 rows
update public.athletes
set user_id = '00000000-0000-0000-0000-0000000000aa'
where email = 'bjorn@ss.test';

select case when count(*) = 0
            then 'PASS: Anna cannot hijack Bjorn''s invite'
            else 'FAIL: Bjorn''s invite was modified by Anna' end
from public.athletes where email = 'bjorn@ss.test' and user_id is not null;

-- Anna sees her assigned program, and ONLY that one
select case when count(*) = 1 and min(name) = 'Anna Block'
            then 'PASS: athlete sees only programs assigned to them'
            else 'FAIL: athlete program visibility (' || count(*) || ' rows)' end
from public.programs;

select case when count(*) = 1 then 'PASS: athlete reads exercises of assigned program'
            else 'FAIL: exercise visibility (' || count(*) || ' rows)' end
from public.program_exercises;

-- Anna logs a set for herself: allowed
do $$
begin
  insert into public.logged_sets (session_id, exercise_id, athlete_id, exercise_name, track, set_number, weight, reps, volume, is_pr)
  values ('99999999-0000-0000-0000-000000000001', 'eeeeeeee-0000-0000-0000-000000000001',
          'aaaaaaaa-0000-0000-0000-000000000001', 'Back Squat', 'load', 1, 315, 3, 945, true);
  raise notice 'PASS: athlete can log her own set';
exception when others then
  raise notice 'FAIL: athlete could not log her own set (%)', sqlerrm;
end $$;

-- Anna tries to log a set as Bjorn: must be rejected by RLS with-check
do $$
begin
  insert into public.logged_sets (session_id, exercise_id, athlete_id, exercise_name, track, set_number, weight, reps, volume)
  values ('99999999-0000-0000-0000-000000000001', 'eeeeeeee-0000-0000-0000-000000000001',
          'aaaaaaaa-0000-0000-0000-000000000002', 'Back Squat', 'load', 1, 999, 1, 999);
  raise notice 'FAIL: cross-athlete logged_sets insert was allowed';
exception when insufficient_privilege then
  raise notice 'PASS: cross-athlete logged_sets insert blocked';
end $$;

-- Anna marks her own session complete: allowed
update public.scheduled_sessions set status = 'completed'
where id = '99999999-0000-0000-0000-000000000001';
select case when (select status from public.scheduled_sessions where id = '99999999-0000-0000-0000-000000000001') = 'completed'
            then 'PASS: athlete can complete her own session'
            else 'FAIL: session status update did not apply' end;

-- Anna awards herself a badge (self insert is allowed by design), then cannot award one to Bjorn
do $$
begin
  insert into public.earned_badges (athlete_id, badge_definition_id)
  values ('aaaaaaaa-0000-0000-0000-000000000001', 'load-1');
  raise notice 'PASS: athlete can insert her own earned badge';
exception when others then
  raise notice 'FAIL: athlete could not insert her own earned badge (%)', sqlerrm;
end $$;

do $$
begin
  insert into public.earned_badges (athlete_id, badge_definition_id)
  values ('aaaaaaaa-0000-0000-0000-000000000002', 'load-1');
  raise notice 'FAIL: cross-athlete earned_badges insert was allowed';
exception when insufficient_privilege then
  raise notice 'PASS: cross-athlete earned_badges insert blocked';
end $$;

-- Anna tries to promote herself to coach: trigger must silently keep role = athlete
update public.profiles set role = 'coach' where id = '00000000-0000-0000-0000-0000000000aa';
select case when (select role from public.profiles where id = '00000000-0000-0000-0000-0000000000aa') = 'athlete'
            then 'PASS: athlete cannot self-promote to coach'
            else 'FAIL: role escalation succeeded!' end;

-- Anna tries to read the whole profiles table
select case when count(*) = 1 then 'PASS: athlete sees only her own profile'
            else 'FAIL: athlete sees ' || count(*) || ' profiles' end
from public.profiles;

-- ── Bjorn's session: he must see none of Anna's data ──────────────────────────────────────────
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-0000000000bb","email":"bjorn@ss.test"}', false);

update public.athletes
set user_id = '00000000-0000-0000-0000-0000000000bb'
where email = 'bjorn@ss.test' and user_id is null;

select case when count(*) = 0 then 'PASS: Bjorn sees no programs (none assigned)'
            else 'FAIL: Bjorn sees ' || count(*) || ' programs' end
from public.programs;

select case when count(*) = 0 then 'PASS: Bjorn cannot see Anna''s logged sets'
            else 'FAIL: Bjorn sees ' || count(*) || ' foreign logged sets' end
from public.logged_sets;

select case when count(*) = 0 then 'PASS: Bjorn cannot see Anna''s sessions'
            else 'FAIL: Bjorn sees ' || count(*) || ' foreign sessions' end
from public.scheduled_sessions;

select case when count(*) = 0 then 'PASS: Bjorn cannot see Anna''s badges'
            else 'FAIL: Bjorn sees ' || count(*) || ' foreign earned badges' end
from public.earned_badges;

-- Badge definitions are readable by any signed-in user (by design)
select case when count(*) = 18 then 'PASS: badge catalog readable (18 tiers)'
            else 'FAIL: badge catalog count ' || count(*) end
from public.badge_definitions;

-- Bjorn tries to create a program (coach-only)
do $$
begin
  insert into public.programs (name, duration_weeks) values ('Bjorn''s Rogue Program', 1);
  raise notice 'FAIL: athlete created a program';
exception when insufficient_privilege then
  raise notice 'PASS: athlete cannot create programs';
end $$;

-- ── Anonymous session (no JWT): must see nothing ──────────────────────────────────────────────
select set_config('request.jwt.claims', '', false);
select case when count(*) = 0 then 'PASS: anonymous sees no athletes' else 'FAIL: anonymous sees athletes' end from public.athletes;
select case when count(*) = 0 then 'PASS: anonymous sees no programs' else 'FAIL: anonymous sees programs' end from public.programs;
select case when count(*) = 0 then 'PASS: anonymous sees no logged sets' else 'FAIL: anonymous sees logged sets' end from public.logged_sets;
select case when count(*) = 0 then 'PASS: anonymous sees no badge definitions' else 'FAIL: anonymous sees badge definitions' end from public.badge_definitions;

-- ── Coach again: verify full visibility including athlete-generated data ──────────────────────
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-000000000001","email":"coach@ss.test"}', false);

select case when count(*) = 1 then 'PASS: coach sees athlete logged sets'
            else 'FAIL: coach logged-set visibility (' || count(*) || ')' end
from public.logged_sets;

select case when count(*) = 2 then 'PASS: coach still sees both athletes'
            else 'FAIL: coach roster visibility (' || count(*) || ')' end
from public.athletes;

reset role;
select 'SUITE COMPLETE';
