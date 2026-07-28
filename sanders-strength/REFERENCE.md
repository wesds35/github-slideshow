# Sanders Strength — Product Reference (v1.0)

This document is the single source of truth for the Sanders Strength workout-tracking app. It captures the product concept, data model, feature set, and brand/UI system established for the 1.0 mockup so future work (design or engineering) can pick up without re-deriving decisions.

Mockup: `sanders-strength/mockup/index.html` (open any `.html` file in the folder directly in a browser, no build step required).

---

## 1. Concept

Sanders Strength is a coach-run athlete workout tracker in the spirit of TrainHeroic: a coach builds programs, assigns them to athletes (individually or by program/group), and athletes log their actual work. The app converts logged work into **volume** metrics, awards **milestone badges** as volume accumulates, and gives both coach and athlete a dashboard of trends and PRs.

Core principles:
- **Coach-authored, athlete-executed.** Programs are built by the coach; athletes only log results against what's assigned (or ad hoc if unassigned).
- **Local-first, private.** Athlete data is never shared to third parties or across athletes. Data lives on-device/in the coach's own system and syncs only between an athlete and their coach.
- **Progress over time.** Every metric (volume, PRs, badges) is a time series — the point is to show an athlete their own trajectory.

---

## 2. Users & Roles

| Role | Capabilities |
|---|---|
| **Coach** | Create/edit programs, assign programs to athletes or groups, view all athletes' schedules/volume/PRs, manage the badge system, view roster-wide dashboard. |
| **Athlete** | View assigned program & schedule, log sets/reps/weight (or distance/wattage) per exercise, view own dashboard (volume, PRs, badges), log ad hoc/unassigned workouts. |

A coach can have many athletes; an athlete belongs to one coach (v1.0 scope — no multi-coach sharing).

---

## 3. Volume Model

Volume is the core metric. Three volume types, all tracked per-exercise, per-session, and rolled up over time (weekly/monthly/all-time):

1. **Rep (load) volume** — `sets × reps × weight`. Standard for barbell/dumbbell/machine lifts. Unit: lb·reps (or kg·reps).
2. **Distance volume** — `distance × load` (e.g., sled drag, farmer's carry, weighted walk) or raw distance for bodyweight conditioning (runs, rows). Unit: ft/mi (or m/km), optionally load-weighted.
3. **Wattage volume** — `average watts × duration`, for erg/bike/rower/sprint work with power output. Unit: watt-seconds (kJ).

Each logged set stores its raw inputs (reps, weight, distance, time, watts as applicable) — volume is always derived, never hand-entered, so historical formulas can be recomputed if the model changes.

**Roll-ups:** per-lift lifetime volume, per-session volume, weekly/monthly totals, and program-to-date totals. These feed both the milestone badge engine and the dashboard charts.

**PRs:** tracked per exercise as (a) heaviest weight for any rep count, and (b) estimated 1RM via the Epley formula (`weight × (1 + reps/30)`), recalculated on every logged set and flagged when a set beats the standing record.

---

## 4. Milestone Badges

Badges are awarded automatically when an athlete's cumulative volume crosses a threshold. Tiered, Viking-themed naming to match brand:

| Tier | Badge Name | Rep Volume Threshold (lb·reps, example) |
|---|---|---|
| 1 | **Thrall** | 10,000 |
| 2 | **Karl** | 50,000 |
| 3 | **Jarl** | 150,000 |
| 4 | **Berserker** | 500,000 |
| 5 | **Einherjar** | 1,000,000 |
| 6 | **Valhalla** | 5,000,000 |

Distance and wattage volume have their own parallel badge tracks (same tier names, different thresholds/units — e.g., distance tiers in cumulative miles moved, wattage tiers in cumulative kJ), so an athlete can hold badges across three tracks (Iron/load, Road/distance, Engine/wattage), plus per-lift badges (e.g., first badge on Squat specifically vs. total-body volume). Badges are awarded per-athlete, are permanent once earned, and appear on both the athlete's and coach's dashboards with the date earned.

v1.0 scope: badge thresholds are configurable by the coach (not hardcoded), so they can be tuned per athlete population (youth vs. collegiate vs. pro).

---

## 5. Program Builder

Coach-facing tool to construct reusable training programs.

Hierarchy: **Program → Weeks → Days → Exercises → Prescription.**

- **Program**: name, description, duration (weeks), tags (e.g., "Off-Season Strength", "In-Season Maintenance").
- **Day**: label (e.g., "Day 1 — Lower Power"), ordered list of exercises.
- **Exercise entry**: exercise name (from a shared library, or custom), prescribed sets × reps, load prescription (absolute weight, %1RM, or RPE/RIR), rest, and coach notes.
- **Assignment**: a program is assigned to one or more athletes, or to a named group/team. Each athlete gets their own independent progress copy (completing sets doesn't affect other assignees). Assignment places the program's days onto the athlete's scheduler automatically, starting from a chosen start date.

Coaches can duplicate/version programs, and swap an exercise for a whole group at once (e.g., swap "Back Squat" → "Trap Bar Deadlift" across every athlete on a program).

---

## 6. Scheduler

Calendar view (week and month) showing scheduled workouts.

- **Coach view**: all athletes' scheduled sessions, filterable by athlete/group/program; a day cell shows how many athletes are scheduled and completion status at a glance.
- **Athlete view**: personal week/month calendar; each day shows the assigned session (if any); tapping a day opens the log-workout screen for that session. Athletes can also log an unscheduled/ad hoc session.
- Completed sessions are visually distinguished from upcoming/missed ones (status: scheduled → completed / missed).

---

## 7. Workout Logging (Athlete)

For each exercise in a session, the athlete enters actual performance set-by-set:

- Strength lifts: weight + reps per set (prescribed target shown alongside for reference).
- Conditioning/distance work: distance (+ optional load) and/or time.
- Engine/wattage work: average watts + duration (or the app accepts total work directly if the source device reports it).

On save: volume is computed for the set, rolled into session/lift/lifetime totals, compared against standing PRs, and checked against badge thresholds — any newly crossed threshold triggers a badge-earned moment.

---

## 8. Dashboards

**Athlete dashboard**: volume over time (by lift and total, weekly/monthly), current PRs per lift, badge case (earned + next-up progress bars), adherence (sessions completed vs. scheduled).

**Coach dashboard**: roster overview (athletes, their current program, last logged session), team-wide volume trends, recent PRs across the roster, recently earned badges, quick links into any athlete's individual dashboard or program.

---

## 9. Privacy Model

- No athlete data is shared across athletes, and nothing is shared to third parties.
- Data is local-first: stored on-device / within the coach's own system, syncing only between a given athlete and their own coach.
- No public leaderboards or cross-team visibility in v1.0.

---

## 10. Brand & Visual System

**Name / logo:** "Sanders Strength" — wordmark pairs a bold slab/serif display face for "SANDERS" with a slightly wider-tracked "STRENGTH" beneath it, flanked by a Viking rune-inspired mark (a shield/axe motif rendered in angular, rune-carved strokes). Runic accent characters (Elder Futhark, Unicode Runic block, e.g. ᛊ ᛏ ᚱ) are used sparingly as dividers/accents, not for body copy.

**Color palette:**

| Token | Hex | Use |
|---|---|---|
| `--bg-void` | `#0a0a0c` | App background |
| `--bg-surface` | `#151517` | Cards/panels |
| `--bg-surface-raised` | `#1e1e21` | Elevated cards, inputs |
| `--border-rune` | `#2c2c30` | Hairline borders |
| `--red-primary` | `#c81e2c` | Primary accent, CTAs, active states |
| `--red-bright` | `#ff2f3e` | Highlights, badges-earned glow, PR flags |
| `--red-deep` | `#7a0f18` | Pressed states, gradients |
| `--text-primary` | `#f2f0ec` | Primary text (warm off-white, like bone/parchment) |
| `--text-muted` | `#9a9a9e` | Secondary text |
| `--gold-accent` | `#c9a24b` | Reserved for top-tier badge (Valhalla) only |

**Typography:** display headings in a bold, slightly condensed serif/slab (Cinzel/Trajan-like character — carved stone feel) for a Viking/runic tone; UI/body text in a clean geometric sans for legibility (Train Heroic-style contrast between a rugged display face and a modern, clean UI face).

**Aesthetic direction:** black canvas, blood-red accents, thin rune-carved hairline borders, angular card corners (small bevel, not fully rounded), subtle diagonal-scratch/stone texture in hero sections, runic glyphs as micro-decoration. Should read as clean and modern first, "Viking" second — a subtle motif, not a costume.

---

## 11. Information Architecture (mockup pages)

| Page | File | Purpose |
|---|---|---|
| Splash / sign-in | `mockup/index.html` | Brand entry point, role selection (Coach / Athlete) |
| Coach dashboard | `mockup/dashboard.html` | Roster, team volume, recent PRs/badges |
| Program builder | `mockup/program-builder.html` | Build a program: weeks → days → exercises |
| Scheduler | `mockup/scheduler.html` | Calendar of all scheduled workouts |
| Log workout | `mockup/log-workout.html` | Athlete enters sets/reps/weight for today's session |
| Athlete dashboard | `mockup/athlete.html` | Individual volume charts, PRs, badge case |
| Badges | `mockup/badges.html` | Full badge catalog across tiers/tracks |

Shared assets: `mockup/assets/styles.css` (design system), `mockup/assets/app.js` (nav/tab interaction only — no backend), `mockup/assets/logo.svg` (wordmark + mark).

---

## 12. Out of Scope for v1.0

- Real backend/auth/sync (mockup is static/local, no persistence beyond the current page)
- Multi-coach athlete sharing, public leaderboards
- Native mobile shell (mockup is responsive web; native wrapper is a future decision)
- Wearable/device integrations for auto-logging distance/wattage (manual entry only in v1.0)
