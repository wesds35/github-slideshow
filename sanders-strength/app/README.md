# Sanders Strength — v1.0 Functional App

A local-first web app implementing the coach/athlete workout tracker described in
[`../REFERENCE.md`](../REFERENCE.md). Built with Vite + React + TypeScript, storing all data in
the browser via IndexedDB (Dexie) — no backend, no account system, nothing leaves the device.

## Run it

```
npm install
npm run dev
```

Open the printed local URL. On first load the app seeds a demo roster (5 athletes, 3 programs,
several weeks of logged history) so every screen has real data to show. Clearing site data / an
incognito window resets to a fresh seed.

## What's real vs. what's simulated

**Real (backed by IndexedDB, computed live):**
- Program builder: create programs, add/edit/delete weeks → days → exercises, assign to athletes
  (generates that athlete's own independent scheduled sessions from a chosen start date).
- Scheduler: week-by-week calendar for coach (all athletes) and athlete (their own sessions),
  driven entirely by scheduled-session records.
- Workout logging: athletes enter actual sets; volume (load / distance / wattage) is always
  derived from raw inputs, never entered directly.
- PR detection: Epley-formula estimated 1RM, flagged live against an athlete's own lift history.
- Badges: six Viking-tiered milestones per volume track, evaluated against real cumulative volume
  every time a set is logged; newly-crossed tiers surface as a toast.
- Dashboards (coach roster + individual athlete): volume trends, PRs, adherence, badge case — all
  computed from the same underlying tables, nothing hardcoded.

**Simulated for this version:**
- Coach and athlete share one browser's IndexedDB instance (switch between them via "Switch
  Role / Athlete" in the sidebar) rather than running as separate installs that sync over a
  network. A real deployment would run one instance per person with a thin sync/pairing layer
  between an athlete and their coach — the data model here (`Assignment` gives each athlete an
  independent progress copy of a program) is already shaped for that.
- No auth — role/athlete selection is a local convenience picker, not a login.

## Code layout

- `src/db.ts` — Dexie schema (athletes, programs/weeks/days/exercises, assignments, scheduled
  sessions, logged sets, badge definitions, earned badges).
- `src/lib/` — business logic: `volume.ts` (volume + Epley 1RM), `prs.ts`, `badges.ts`,
  `programs.ts` (program CRUD + assignment/scheduling), `logging.ts` (log a set → volume → PR →
  badge check), `scheduler.ts`, `dashboard.ts`, `seed.ts` (demo data).
- `src/pages/coach/`, `src/pages/athlete/` — route-level screens per role.
- `src/components/` — shared UI (sidebar, tabs, modal, badge case, toast host).
- `src/index.css` — the black/red, Viking-rune-inflected design system, ported from `../mockup`.
