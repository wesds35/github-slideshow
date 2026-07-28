import {
  db,
  uid,
  type Program,
  type ProgramWeek,
  type ProgramDay,
  type ProgramExercise,
  type Assignment,
  type ScheduledSession,
  type VolumeTrack,
} from "../db";

export interface ExerciseSpec {
  name: string;
  track: VolumeTrack;
  prescribedSets: number;
  prescribedReps: number | null;
  prescriptionNote: string;
  restNote: string;
}

export interface DaySpec {
  label: string;
  exercises: ExerciseSpec[];
}

export interface WeekSpec {
  days: DaySpec[];
}

export interface ProgramSpec {
  name: string;
  durationWeeks: number;
  tags: string;
  weeks: WeekSpec[];
}

/** Persists a full program tree (weeks -> days -> exercises) in one pass. */
export async function createProgram(spec: ProgramSpec): Promise<Program> {
  const program: Program = {
    id: uid(),
    name: spec.name,
    durationWeeks: spec.durationWeeks,
    tags: spec.tags,
    createdAt: Date.now(),
  };

  const weeks: ProgramWeek[] = [];
  const days: ProgramDay[] = [];
  const exercises: ProgramExercise[] = [];

  spec.weeks.forEach((weekSpec, weekIdx) => {
    const week: ProgramWeek = { id: uid(), programId: program.id, weekNumber: weekIdx + 1 };
    weeks.push(week);
    weekSpec.days.forEach((daySpec, dayIdx) => {
      const day: ProgramDay = { id: uid(), weekId: week.id, label: daySpec.label, order: dayIdx };
      days.push(day);
      daySpec.exercises.forEach((exSpec, exIdx) => {
        exercises.push({
          id: uid(),
          dayId: day.id,
          name: exSpec.name,
          track: exSpec.track,
          prescribedSets: exSpec.prescribedSets,
          prescribedReps: exSpec.prescribedReps,
          prescriptionNote: exSpec.prescriptionNote,
          restNote: exSpec.restNote,
          order: exIdx,
        });
      });
    });
  });

  await db.transaction(
    "rw",
    db.programs,
    db.programWeeks,
    db.programDays,
    db.programExercises,
    async () => {
      await db.programs.add(program);
      await db.programWeeks.bulkAdd(weeks);
      await db.programDays.bulkAdd(days);
      await db.programExercises.bulkAdd(exercises);
    },
  );

  return program;
}

function addDays(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

/**
 * Assigns a program to an athlete starting from `startDate` (the date of week 1 / day 1),
 * generating that athlete's own independent scheduled sessions on a Mon/Wed/Fri-style cadence
 * (each day in a week lands 2 days after the previous; each week starts 7 days after the last).
 */
export async function assignProgramToAthlete(
  programId: string,
  athleteId: string,
  startDate: string,
): Promise<Assignment> {
  const assignment: Assignment = {
    id: uid(),
    programId,
    athleteId,
    startDate,
    createdAt: Date.now(),
  };

  const weeks = (await db.programWeeks.where("programId").equals(programId).toArray()).sort(
    (a, b) => a.weekNumber - b.weekNumber,
  );

  const sessions: ScheduledSession[] = [];
  for (const week of weeks) {
    const weekStart = addDays(startDate, (week.weekNumber - 1) * 7);
    const days = (await db.programDays.where("weekId").equals(week.id).toArray()).sort(
      (a, b) => a.order - b.order,
    );
    days.forEach((day, i) => {
      sessions.push({
        id: uid(),
        assignmentId: assignment.id,
        athleteId,
        dayId: day.id,
        date: addDays(weekStart, i * 2),
        status: "scheduled",
      });
    });
  }

  await db.transaction("rw", db.assignments, db.scheduledSessions, async () => {
    await db.assignments.add(assignment);
    await db.scheduledSessions.bulkAdd(sessions);
  });

  return assignment;
}

export interface DayNode {
  day: ProgramDay;
  exercises: ProgramExercise[];
}

export interface WeekNode {
  week: ProgramWeek;
  days: DayNode[];
}

export async function programTree(programId: string): Promise<WeekNode[]> {
  const weeks = (await db.programWeeks.where("programId").equals(programId).toArray()).sort(
    (a, b) => a.weekNumber - b.weekNumber,
  );

  const weekNodes: WeekNode[] = [];
  for (const week of weeks) {
    const days = (await db.programDays.where("weekId").equals(week.id).toArray()).sort((a, b) => a.order - b.order);
    const dayNodes: DayNode[] = [];
    for (const day of days) {
      const exercises = (await db.programExercises.where("dayId").equals(day.id).toArray()).sort(
        (a, b) => a.order - b.order,
      );
      dayNodes.push({ day, exercises });
    }
    weekNodes.push({ week, days: dayNodes });
  }
  return weekNodes;
}

export async function programDayDetail(dayId: string) {
  const day = await db.programDays.get(dayId);
  const exercises = (await db.programExercises.where("dayId").equals(dayId).toArray()).sort(
    (a, b) => a.order - b.order,
  );
  return { day, exercises };
}

export async function markSessionStatus(sessionId: string, status: ScheduledSession["status"]) {
  await db.scheduledSessions.update(sessionId, { status });
}

export async function addWeek(programId: string): Promise<ProgramWeek> {
  const existing = await db.programWeeks.where("programId").equals(programId).toArray();
  const week: ProgramWeek = { id: uid(), programId, weekNumber: existing.length + 1 };
  await db.programWeeks.add(week);
  return week;
}

export async function addDay(weekId: string, label: string): Promise<ProgramDay> {
  const existing = await db.programDays.where("weekId").equals(weekId).toArray();
  const day: ProgramDay = { id: uid(), weekId, label, order: existing.length };
  await db.programDays.add(day);
  return day;
}

export async function addExercise(dayId: string, spec: ExerciseSpec): Promise<ProgramExercise> {
  const existing = await db.programExercises.where("dayId").equals(dayId).toArray();
  const exercise: ProgramExercise = {
    id: uid(),
    dayId,
    order: existing.length,
    name: spec.name,
    track: spec.track,
    prescribedSets: spec.prescribedSets,
    prescribedReps: spec.prescribedReps,
    prescriptionNote: spec.prescriptionNote,
    restNote: spec.restNote,
  };
  await db.programExercises.add(exercise);
  return exercise;
}

export async function updateExercise(exerciseId: string, patch: Partial<ExerciseSpec>): Promise<void> {
  await db.programExercises.update(exerciseId, patch);
}

export async function deleteExercise(exerciseId: string): Promise<void> {
  await db.programExercises.delete(exerciseId);
}

export async function deleteDay(dayId: string): Promise<void> {
  await db.transaction("rw", db.programDays, db.programExercises, async () => {
    await db.programExercises.where("dayId").equals(dayId).delete();
    await db.programDays.delete(dayId);
  });
}

export async function deleteWeek(weekId: string): Promise<void> {
  const days = await db.programDays.where("weekId").equals(weekId).toArray();
  await db.transaction("rw", db.programWeeks, db.programDays, db.programExercises, async () => {
    for (const day of days) {
      await db.programExercises.where("dayId").equals(day.id).delete();
    }
    await db.programDays.where("weekId").equals(weekId).delete();
    await db.programWeeks.delete(weekId);
  });
}

export async function deleteProgram(programId: string): Promise<void> {
  const weeks = await db.programWeeks.where("programId").equals(programId).toArray();
  await db.transaction(
    "rw",
    [db.programs, db.programWeeks, db.programDays, db.programExercises, db.assignments, db.scheduledSessions],
    async () => {
      for (const week of weeks) {
        const days = await db.programDays.where("weekId").equals(week.id).toArray();
        for (const day of days) {
          await db.programExercises.where("dayId").equals(day.id).delete();
        }
        await db.programDays.where("weekId").equals(week.id).delete();
      }
      await db.programWeeks.where("programId").equals(programId).delete();
      const assignments = await db.assignments.where("programId").equals(programId).toArray();
      for (const a of assignments) {
        await db.scheduledSessions.where("assignmentId").equals(a.id).delete();
      }
      await db.assignments.where("programId").equals(programId).delete();
      await db.programs.delete(programId);
    },
  );
}
