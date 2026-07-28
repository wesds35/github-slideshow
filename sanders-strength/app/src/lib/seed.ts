import { db, uid, type Athlete, type VolumeTrack } from "../db";
import { ensureBadgeDefinitionsSeeded } from "./badges";
import { createProgram, assignProgramToAthlete, programDayDetail, type ProgramSpec } from "./programs";
import { logSet } from "./logging";

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

const offSeasonSpec: ProgramSpec = {
  name: "Off-Season Strength Block",
  durationWeeks: 8,
  tags: "Strength",
  weeks: [1, 2, 3, 4].map(() => ({
    days: [
      {
        label: "Lower Power",
        exercises: [
          { name: "Back Squat", track: "load", prescribedSets: 5, prescribedReps: 3, prescriptionNote: "% 1RM", restNote: "Rest 3:00" },
          { name: "Trap Bar Jump", track: "load", prescribedSets: 4, prescribedReps: 5, prescriptionNote: "RPE 6", restNote: "Rest 2:00" },
          { name: "Sled Drag — 40yd", track: "distance", prescribedSets: 6, prescribedReps: null, prescriptionNote: "Distance", restNote: "Rest 1:30" },
        ],
      },
      {
        label: "Upper Push / Pull",
        exercises: [
          { name: "Bench Press", track: "load", prescribedSets: 5, prescribedReps: 5, prescriptionNote: "% 1RM", restNote: "Rest 2:30" },
          { name: "Weighted Pull-Up", track: "load", prescribedSets: 4, prescribedReps: 6, prescriptionNote: "RPE 7", restNote: "Rest 2:00" },
        ],
      },
      {
        label: "Engine",
        exercises: [
          { name: "Bike Erg Intervals", track: "wattage", prescribedSets: 8, prescribedReps: null, prescriptionNote: "Wattage", restNote: "Rest 2:00" },
        ],
      },
    ],
  })),
};

const inSeasonSpec: ProgramSpec = {
  name: "In-Season Maintenance",
  durationWeeks: 3,
  tags: "Maintenance",
  weeks: [1, 2, 3].map(() => ({
    days: [
      {
        label: "Full Body",
        exercises: [
          { name: "Front Squat", track: "load", prescribedSets: 4, prescribedReps: 4, prescriptionNote: "% 1RM", restNote: "Rest 2:30" },
          { name: "Bench Press", track: "load", prescribedSets: 4, prescribedReps: 4, prescriptionNote: "% 1RM", restNote: "Rest 2:30" },
        ],
      },
      {
        label: "Conditioning",
        exercises: [
          { name: "Row Erg", track: "wattage", prescribedSets: 6, prescribedReps: null, prescriptionNote: "Wattage", restNote: "Rest 1:30" },
        ],
      },
    ],
  })),
};

const returnToPlaySpec: ProgramSpec = {
  name: "Return-to-Play",
  durationWeeks: 2,
  tags: "Rehab",
  weeks: [1, 2].map(() => ({
    days: [
      {
        label: "Light Circuit",
        exercises: [
          { name: "Goblet Squat", track: "load", prescribedSets: 3, prescribedReps: 10, prescriptionNote: "RPE 5", restNote: "Rest 1:30" },
          { name: "Walking Lunge", track: "distance", prescribedSets: 3, prescribedReps: null, prescriptionNote: "Distance", restNote: "Rest 1:30" },
        ],
      },
    ],
  })),
};

const BASE_LOAD: Record<string, number> = {
  "Back Squat": 315,
  "Trap Bar Jump": 135,
  "Bench Press": 205,
  "Weighted Pull-Up": 35,
  "Front Squat": 185,
  "Goblet Squat": 45,
};

function nameOffset(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 23;
  return h;
}

async function logHistoricalDay(
  athleteId: string,
  sessionId: string,
  dayId: string,
  weekNumber: number,
  athleteOffset: number,
  daysAgo: number,
) {
  const { exercises } = await programDayDetail(dayId);
  for (const ex of exercises) {
    const loggedAt = new Date(isoDaysAgo(daysAgo) + "T12:00:00").getTime();
    if (ex.track === "load") {
      const base = (BASE_LOAD[ex.name] ?? 135) + athleteOffset;
      for (let s = 1; s <= ex.prescribedSets; s++) {
        const isTopSet = s === ex.prescribedSets;
        const weight = base + weekNumber * 5 + (isTopSet ? 10 : 0);
        const reps = (ex.prescribedReps ?? 5) - (isTopSet ? Math.max(0, 3 - weekNumber) : 0);
        await logSet({
          sessionId,
          athleteId,
          exercise: ex,
          setNumber: s,
          weight,
          reps: Math.max(1, reps),
          loggedAt,
        });
      }
    } else if (ex.track === "distance") {
      for (let s = 1; s <= ex.prescribedSets; s++) {
        await logSet({
          sessionId,
          athleteId,
          exercise: ex,
          setNumber: s,
          distance: 40,
          load: 90 + weekNumber * 5,
          loggedAt,
        });
      }
    } else {
      for (let s = 1; s <= ex.prescribedSets; s++) {
        await logSet({
          sessionId,
          athleteId,
          exercise: ex,
          setNumber: s,
          watts: 240 + weekNumber * 10 + athleteOffset,
          durationSec: 30,
          loggedAt,
        });
      }
    }
  }
}

async function seedAssignmentHistory(athleteId: string, athleteOffset: number) {
  const assignment = await db.assignments.where("athleteId").equals(athleteId).last();
  if (!assignment) return;

  const sessions = await db.scheduledSessions.where("assignmentId").equals(assignment.id).toArray();
  const today = new Date().toISOString().slice(0, 10);

  for (const session of sessions) {
    if (session.date >= today) continue; // leave future/today sessions as "scheduled"

    const week = await db.programWeeks.get((await db.programDays.get(session.dayId))!.weekId);
    const weekNumber = week?.weekNumber ?? 1;
    const daysAgo = Math.round(
      (new Date().getTime() - new Date(session.date + "T12:00:00").getTime()) / (1000 * 60 * 60 * 24),
    );

    // Small chance an older session was missed rather than completed.
    const missed = daysAgo > 3 && (nameOffset(session.id) % 11 === 0);
    if (missed) {
      await db.scheduledSessions.update(session.id, { status: "missed" });
      continue;
    }

    await logHistoricalDay(athleteId, session.id, session.dayId, weekNumber, athleteOffset, daysAgo);
    await db.scheduledSessions.update(session.id, { status: "completed" });
  }
}

export async function seedDemoDataIfEmpty(): Promise<void> {
  await ensureBadgeDefinitionsSeeded();

  const athleteSeeds: Array<Omit<Athlete, "id" | "createdAt">> = [
    { name: "Erik Halvorsen", initials: "EH" },
    { name: "Astrid Lund", initials: "AL" },
    { name: "Marcus Kade", initials: "MK" },
    { name: "Devon Price", initials: "DP" },
    { name: "Nadia Okafor", initials: "NO" },
  ];
  const athletes: Athlete[] = athleteSeeds.map((a) => ({ ...a, id: uid(), createdAt: Date.now() }));

  // The count-check and insert run inside one transaction so two concurrent first-run callers
  // (React StrictMode's double-invoked effect, or two tabs opening the empty app at once) can't
  // both pass the emptiness check and double-seed the roster.
  const wonSeedingRace = await db.transaction("rw", db.athletes, async () => {
    if ((await db.athletes.count()) > 0) return false;
    await db.athletes.bulkAdd(athletes);
    return true;
  });
  if (!wonSeedingRace) return;

  const byName = new Map(athletes.map((a) => [a.name, a]));

  const offSeason = await createProgram(offSeasonSpec);
  const inSeason = await createProgram(inSeasonSpec);
  const returnToPlay = await createProgram(returnToPlaySpec);

  const erik = byName.get("Erik Halvorsen")!;
  const astrid = byName.get("Astrid Lund")!;
  const marcus = byName.get("Marcus Kade")!;
  const devon = byName.get("Devon Price")!;
  const nadia = byName.get("Nadia Okafor")!;

  await assignProgramToAthlete(offSeason.id, erik.id, isoDaysAgo(28));
  await assignProgramToAthlete(offSeason.id, marcus.id, isoDaysAgo(14));
  await assignProgramToAthlete(offSeason.id, nadia.id, isoDaysAgo(21));
  await assignProgramToAthlete(inSeason.id, astrid.id, isoDaysAgo(21));
  await assignProgramToAthlete(returnToPlay.id, devon.id, isoDaysAgo(7));

  await seedAssignmentHistory(erik.id, nameOffset(erik.name));
  await seedAssignmentHistory(marcus.id, nameOffset(marcus.name));
  await seedAssignmentHistory(nadia.id, nameOffset(nadia.name));
  await seedAssignmentHistory(astrid.id, nameOffset(astrid.name));
  await seedAssignmentHistory(devon.id, nameOffset(devon.name));
}

export const DEMO_TRACKS: VolumeTrack[] = ["load", "distance", "wattage"];
