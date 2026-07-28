import { supabase } from "./supabaseClient";
import {
  toProgram,
  toProgramWeek,
  toProgramDay,
  toProgramExercise,
  toAssignment,
} from "./mappers";
import type {
  Program,
  ProgramWeek,
  ProgramDay,
  ProgramExercise,
  Assignment,
  ScheduledSession,
  VolumeTrack,
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
  const { data: programRow, error: programError } = await supabase
    .from("programs")
    .insert({ name: spec.name, duration_weeks: spec.durationWeeks, tags: spec.tags })
    .select()
    .single();
  if (programError) throw programError;

  for (let weekIdx = 0; weekIdx < spec.weeks.length; weekIdx++) {
    const { data: weekRow, error: weekError } = await supabase
      .from("program_weeks")
      .insert({ program_id: programRow.id, week_number: weekIdx + 1 })
      .select()
      .single();
    if (weekError) throw weekError;

    const daySpecs = spec.weeks[weekIdx].days;
    for (let dayIdx = 0; dayIdx < daySpecs.length; dayIdx++) {
      const { data: dayRow, error: dayError } = await supabase
        .from("program_days")
        .insert({ program_id: programRow.id, week_id: weekRow.id, label: daySpecs[dayIdx].label, order: dayIdx })
        .select()
        .single();
      if (dayError) throw dayError;

      const exercises = daySpecs[dayIdx].exercises.map((ex, exIdx) => ({
        program_id: programRow.id,
        day_id: dayRow.id,
        name: ex.name,
        track: ex.track,
        prescribed_sets: ex.prescribedSets,
        prescribed_reps: ex.prescribedReps,
        prescription_note: ex.prescriptionNote,
        rest_note: ex.restNote,
        order: exIdx,
      }));
      if (exercises.length > 0) {
        const { error: exError } = await supabase.from("program_exercises").insert(exercises);
        if (exError) throw exError;
      }
    }
  }

  return toProgram(programRow);
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
  const { data: assignmentRow, error: assignmentError } = await supabase
    .from("assignments")
    .insert({ program_id: programId, athlete_id: athleteId, start_date: startDate })
    .select()
    .single();
  if (assignmentError) throw assignmentError;

  const { data: weekRows, error: weeksError } = await supabase
    .from("program_weeks")
    .select("id, week_number")
    .eq("program_id", programId)
    .order("week_number");
  if (weeksError) throw weeksError;

  const sessions: Array<{
    assignment_id: string;
    athlete_id: string;
    day_id: string;
    date: string;
  }> = [];

  for (const week of weekRows) {
    const weekStart = addDays(startDate, (week.week_number - 1) * 7);
    const { data: dayRows, error: daysError } = await supabase
      .from("program_days")
      .select("id, order")
      .eq("week_id", week.id)
      .order("order");
    if (daysError) throw daysError;

    dayRows.forEach((day, i) => {
      sessions.push({
        assignment_id: assignmentRow.id,
        athlete_id: athleteId,
        day_id: day.id,
        date: addDays(weekStart, i * 2),
      });
    });
  }

  if (sessions.length > 0) {
    const { error: sessionsError } = await supabase.from("scheduled_sessions").insert(sessions);
    if (sessionsError) throw sessionsError;
  }

  return toAssignment(assignmentRow);
}

export async function programDayDetail(dayId: string): Promise<{ day: ProgramDay | undefined; exercises: ProgramExercise[] }> {
  const [{ data: dayRow }, { data: exerciseRows, error: exError }] = await Promise.all([
    supabase.from("program_days").select().eq("id", dayId).maybeSingle(),
    supabase.from("program_exercises").select().eq("day_id", dayId).order("order"),
  ]);
  if (exError) throw exError;
  return {
    day: dayRow ? toProgramDay(dayRow) : undefined,
    exercises: (exerciseRows ?? []).map(toProgramExercise),
  };
}

export async function markSessionStatus(sessionId: string, status: ScheduledSession["status"]): Promise<void> {
  const { error } = await supabase.from("scheduled_sessions").update({ status }).eq("id", sessionId);
  if (error) throw error;
}

export async function addWeek(programId: string): Promise<ProgramWeek> {
  const { count } = await supabase
    .from("program_weeks")
    .select("id", { count: "exact", head: true })
    .eq("program_id", programId);
  const { data, error } = await supabase
    .from("program_weeks")
    .insert({ program_id: programId, week_number: (count ?? 0) + 1 })
    .select()
    .single();
  if (error) throw error;
  return toProgramWeek(data);
}

export async function addDay(weekId: string, label: string): Promise<ProgramDay> {
  const { data: week, error: weekError } = await supabase
    .from("program_weeks")
    .select("program_id")
    .eq("id", weekId)
    .single();
  if (weekError) throw weekError;

  const { count } = await supabase.from("program_days").select("id", { count: "exact", head: true }).eq("week_id", weekId);
  const { data, error } = await supabase
    .from("program_days")
    .insert({ program_id: week.program_id, week_id: weekId, label, order: count ?? 0 })
    .select()
    .single();
  if (error) throw error;
  return toProgramDay(data);
}

export async function addExercise(dayId: string, spec: ExerciseSpec): Promise<ProgramExercise> {
  const { data: day, error: dayError } = await supabase
    .from("program_days")
    .select("program_id")
    .eq("id", dayId)
    .single();
  if (dayError) throw dayError;

  const { count } = await supabase.from("program_exercises").select("id", { count: "exact", head: true }).eq("day_id", dayId);
  const { data, error } = await supabase
    .from("program_exercises")
    .insert({
      program_id: day.program_id,
      day_id: dayId,
      order: count ?? 0,
      name: spec.name,
      track: spec.track,
      prescribed_sets: spec.prescribedSets,
      prescribed_reps: spec.prescribedReps,
      prescription_note: spec.prescriptionNote,
      rest_note: spec.restNote,
    })
    .select()
    .single();
  if (error) throw error;
  return toProgramExercise(data);
}

export async function updateExercise(exerciseId: string, patch: Partial<ExerciseSpec>): Promise<void> {
  const { error } = await supabase
    .from("program_exercises")
    .update({
      name: patch.name,
      track: patch.track,
      prescribed_sets: patch.prescribedSets,
      prescribed_reps: patch.prescribedReps,
      prescription_note: patch.prescriptionNote,
      rest_note: patch.restNote,
    })
    .eq("id", exerciseId);
  if (error) throw error;
}

export async function deleteExercise(exerciseId: string): Promise<void> {
  const { error } = await supabase.from("program_exercises").delete().eq("id", exerciseId);
  if (error) throw error;
}

export async function deleteDay(dayId: string): Promise<void> {
  // program_exercises has ON DELETE CASCADE from program_days, so deleting the day is enough.
  const { error } = await supabase.from("program_days").delete().eq("id", dayId);
  if (error) throw error;
}

export async function deleteWeek(weekId: string): Promise<void> {
  // program_days (and, cascading, program_exercises) delete automatically via ON DELETE CASCADE.
  const { error } = await supabase.from("program_weeks").delete().eq("id", weekId);
  if (error) throw error;
}

export async function deleteProgram(programId: string): Promise<void> {
  // Every child table (weeks, days, exercises, assignments, scheduled_sessions, logged_sets)
  // cascades from programs via ON DELETE CASCADE foreign keys.
  const { error } = await supabase.from("programs").delete().eq("id", programId);
  if (error) throw error;
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
  const [{ data: weekRows, error: weeksError }, { data: dayRows, error: daysError }, { data: exerciseRows, error: exError }] =
    await Promise.all([
      supabase.from("program_weeks").select().eq("program_id", programId).order("week_number"),
      supabase.from("program_days").select().eq("program_id", programId).order("order"),
      supabase.from("program_exercises").select().eq("program_id", programId).order("order"),
    ]);
  if (weeksError) throw weeksError;
  if (daysError) throw daysError;
  if (exError) throw exError;

  const daysByWeek = new Map<string, typeof dayRows>();
  for (const day of dayRows ?? []) {
    const list = daysByWeek.get(day.week_id) ?? [];
    list.push(day);
    daysByWeek.set(day.week_id, list);
  }
  const exercisesByDay = new Map<string, typeof exerciseRows>();
  for (const ex of exerciseRows ?? []) {
    const list = exercisesByDay.get(ex.day_id) ?? [];
    list.push(ex);
    exercisesByDay.set(ex.day_id, list);
  }

  return (weekRows ?? []).map((week) => ({
    week: toProgramWeek(week),
    days: (daysByWeek.get(week.id) ?? []).map((day) => ({
      day: toProgramDay(day),
      exercises: (exercisesByDay.get(day.id) ?? []).map(toProgramExercise),
    })),
  }));
}
