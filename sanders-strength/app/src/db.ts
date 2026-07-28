import Dexie, { type EntityTable } from "dexie";

export type VolumeTrack = "load" | "distance" | "wattage";
export type SessionStatus = "scheduled" | "completed" | "missed";

export interface Athlete {
  id: string;
  name: string;
  initials: string;
  createdAt: number;
}

export interface Program {
  id: string;
  name: string;
  durationWeeks: number;
  tags: string;
  createdAt: number;
}

export interface ProgramWeek {
  id: string;
  programId: string;
  weekNumber: number;
}

export interface ProgramDay {
  id: string;
  weekId: string;
  label: string;
  order: number;
}

export interface ProgramExercise {
  id: string;
  dayId: string;
  name: string;
  track: VolumeTrack;
  prescribedSets: number;
  prescribedReps: number | null;
  prescriptionNote: string; // e.g. "78% 1RM", "RPE 7", "Distance"
  restNote: string;
  order: number;
}

export interface Assignment {
  id: string;
  programId: string;
  athleteId: string;
  startDate: string; // ISO date of week-1/day-1
  createdAt: number;
}

export interface ScheduledSession {
  id: string;
  assignmentId: string;
  athleteId: string;
  dayId: string;
  date: string; // ISO date (yyyy-mm-dd)
  status: SessionStatus;
}

export interface LoggedSet {
  id: string;
  sessionId: string;
  exerciseId: string;
  athleteId: string;
  exerciseName: string;
  track: VolumeTrack;
  setNumber: number;
  weight?: number;
  reps?: number;
  distance?: number;
  load?: number;
  watts?: number;
  durationSec?: number;
  volume: number;
  isPR: boolean;
  loggedAt: number;
}

export interface BadgeDefinition {
  id: string;
  track: VolumeTrack;
  tier: number;
  name: string;
  threshold: number;
}

export interface EarnedBadge {
  id: string;
  athleteId: string;
  badgeDefinitionId: string;
  earnedAt: number;
}

export const db = new Dexie("sanders-strength") as Dexie & {
  athletes: EntityTable<Athlete, "id">;
  programs: EntityTable<Program, "id">;
  programWeeks: EntityTable<ProgramWeek, "id">;
  programDays: EntityTable<ProgramDay, "id">;
  programExercises: EntityTable<ProgramExercise, "id">;
  assignments: EntityTable<Assignment, "id">;
  scheduledSessions: EntityTable<ScheduledSession, "id">;
  loggedSets: EntityTable<LoggedSet, "id">;
  badgeDefinitions: EntityTable<BadgeDefinition, "id">;
  earnedBadges: EntityTable<EarnedBadge, "id">;
};

db.version(1).stores({
  athletes: "id, name",
  programs: "id, name, createdAt",
  programWeeks: "id, programId, [programId+weekNumber]",
  programDays: "id, weekId, order",
  programExercises: "id, dayId, order",
  assignments: "id, programId, athleteId",
  scheduledSessions: "id, assignmentId, athleteId, date, [athleteId+date]",
  loggedSets: "id, sessionId, athleteId, exerciseId, exerciseName, [athleteId+exerciseName]",
  badgeDefinitions: "id, track, tier",
  earnedBadges: "id, athleteId, badgeDefinitionId, [athleteId+badgeDefinitionId]",
});

export const uid = (): string => crypto.randomUUID();
