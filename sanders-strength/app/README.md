# Sanders Strength — v1.1 Functional App

A real, deployable coach/athlete workout tracker implementing the spec in
[`../REFERENCE.md`](../REFERENCE.md). Built with Vite + React + TypeScript on top of Supabase
(Postgres + Auth), with row-level security enforcing at the database level that an athlete's
queries can only ever touch their own data — not just an app-level check.

## Run it

```
cp .env.example .env.local   # fill in your own Supabase project's URL + anon key
npm install
npm run dev
```

See [`README-DEPLOY.md`](./README-DEPLOY.md) for the full path from zero to a public URL your
athletes can log into: creating the Supabase project, running the schema, promoting your own
account to coach, and deploying to Vercel.

## What's real

- **Accounts, not a local picker.** Email + password login via Supabase Auth. You (the coach)
  add an athlete by name + email from your roster; they self-register with that exact email and
  it auto-links to the slot you created — they never see anyone else's programs or logs, enforced
  by Postgres row-level security policies (`supabase/schema.sql`), not just app code.
- **Program builder**: create programs, add/edit/delete weeks → days → exercises, assign to
  athletes (generates that athlete's own independent scheduled sessions from a chosen start date).
- **Scheduler**: week-by-week calendar for coach (all athletes) and athlete (their own sessions).
- **Workout logging**: athletes enter actual sets; volume (load / distance / wattage) is always
  derived from raw inputs, never entered directly.
- **PR detection**: Epley-formula estimated 1RM, flagged live against an athlete's own lift history.
- **Badges**: six Viking-tiered milestones per volume track, evaluated against real cumulative
  volume every time a set is logged; newly-crossed tiers surface as a toast.
- **Dashboards** (coach roster + individual athlete): volume trends, PRs, adherence, badge case —
  all computed from the same underlying tables, nothing hardcoded.

## Known v1.1 limitation

Data fetching is fetch-on-load-and-after-your-own-mutations, not truly live — if a different
athlete logs a set while you're looking at the coach dashboard, you won't see it until you
navigate or refresh. Supabase Realtime channels are the natural next step for push updates; not
wired up yet to keep this migration scoped. See `README-DEPLOY.md`'s "What's next" section.

## Code layout

- `supabase/schema.sql` — Postgres schema + row-level security policies. Run once in your
  Supabase project's SQL Editor.
- `src/lib/supabaseClient.ts`, `src/lib/database.types.ts` — the typed Supabase client.
- `src/context/auth.tsx` — session, role (`coach`/`athlete`), and linked athlete record.
- `src/db.ts` — camelCase domain types (`Athlete`, `Program`, `LoggedSet`, ...), independent of
  Postgres's snake_case columns.
- `src/lib/mappers.ts` — translates Postgres rows to those domain types at the data-access boundary.
- `src/lib/` — business logic: `volume.ts` (volume + Epley 1RM), `prs.ts`, `badges.ts`,
  `programs.ts` (program CRUD + assignment/scheduling), `logging.ts` (log a set → volume → PR →
  badge check), `scheduler.ts`, `dashboard.ts`.
- `src/lib/useSupabaseData.ts` — a small fetch-on-deps-change hook used throughout instead of a
  live-query subscription (see the limitation above).
- `src/pages/coach/`, `src/pages/athlete/` — route-level screens per role.
- `src/components/` — shared UI (sidebar, tabs, modal, badge case, toast host).
- `src/index.css` — the black/red, Viking-rune-inflected design system, ported from `../mockup`.
