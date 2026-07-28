import type { Database } from "./database.types";
import type {
  Athlete,
  Program,
  ProgramWeek,
  ProgramDay,
  ProgramExercise,
  Assignment,
  ScheduledSession,
  LoggedSet,
  BadgeDefinition,
  EarnedBadge,
} from "../db";

type Row<T extends keyof Database["public"]["Tables"]> = Database["public"]["Tables"][T]["Row"];

export const toAthlete = (r: Row<"athletes">): Athlete => ({
  id: r.id,
  userId: r.user_id,
  name: r.name,
  initials: r.initials,
  email: r.email,
  createdAt: Date.parse(r.created_at),
});

export const toProgram = (r: Row<"programs">): Program => ({
  id: r.id,
  name: r.name,
  durationWeeks: r.duration_weeks,
  tags: r.tags,
  createdAt: Date.parse(r.created_at),
});

export const toProgramWeek = (r: Row<"program_weeks">): ProgramWeek => ({
  id: r.id,
  programId: r.program_id,
  weekNumber: r.week_number,
});

export const toProgramDay = (r: Row<"program_days">): ProgramDay => ({
  id: r.id,
  weekId: r.week_id,
  label: r.label,
  order: r.order,
});

export const toProgramExercise = (r: Row<"program_exercises">): ProgramExercise => ({
  id: r.id,
  dayId: r.day_id,
  name: r.name,
  track: r.track,
  prescribedSets: r.prescribed_sets,
  prescribedReps: r.prescribed_reps,
  prescriptionNote: r.prescription_note,
  restNote: r.rest_note,
  order: r.order,
});

export const toAssignment = (r: Row<"assignments">): Assignment => ({
  id: r.id,
  programId: r.program_id,
  athleteId: r.athlete_id,
  startDate: r.start_date,
  createdAt: Date.parse(r.created_at),
});

export const toScheduledSession = (r: Row<"scheduled_sessions">): ScheduledSession => ({
  id: r.id,
  assignmentId: r.assignment_id,
  athleteId: r.athlete_id,
  dayId: r.day_id,
  date: r.date,
  status: r.status,
});

export const toLoggedSet = (r: Row<"logged_sets">): LoggedSet => ({
  id: r.id,
  sessionId: r.session_id,
  exerciseId: r.exercise_id,
  athleteId: r.athlete_id,
  exerciseName: r.exercise_name,
  track: r.track,
  setNumber: r.set_number,
  weight: r.weight ?? undefined,
  reps: r.reps ?? undefined,
  distance: r.distance ?? undefined,
  load: r.load ?? undefined,
  watts: r.watts ?? undefined,
  durationSec: r.duration_sec ?? undefined,
  volume: r.volume,
  isPR: r.is_pr,
  loggedAt: Date.parse(r.logged_at),
});

export const toBadgeDefinition = (r: Row<"badge_definitions">): BadgeDefinition => ({
  id: r.id,
  track: r.track,
  tier: r.tier,
  name: r.name,
  threshold: r.threshold,
});

export const toEarnedBadge = (r: Row<"earned_badges">): EarnedBadge => ({
  id: r.id,
  athleteId: r.athlete_id,
  badgeDefinitionId: r.badge_definition_id,
  earnedAt: Date.parse(r.earned_at),
});
