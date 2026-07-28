import type {
  Athlete,
  Assignment,
  BadgeDefinition,
  EarnedBadge,
  LoggedSet,
  Program,
  ScheduledSession,
} from "../db";

const DAY_MS = 24 * 60 * 60 * 1000;

export function withinLastDays(timestamp: number, days: number): boolean {
  return timestamp >= Date.now() - days * DAY_MS;
}

/** Sums "load" track volume per week for the last `weeks` weeks (oldest first), for the team volume trend chart. */
export function weeklyLoadVolumeTrend(sets: LoggedSet[], weeks: number): number[] {
  const buckets = new Array(weeks).fill(0);
  const now = Date.now();
  for (const s of sets) {
    if (s.track !== "load") continue;
    const ageDays = (now - s.loggedAt) / DAY_MS;
    const weekIndexFromNow = Math.floor(ageDays / 7); // 0 = this week, 1 = last week, ...
    const bucket = weeks - 1 - weekIndexFromNow;
    if (bucket >= 0 && bucket < weeks) buckets[bucket] += s.volume;
  }
  return buckets;
}

export interface RecentPRRow {
  athleteName: string;
  exerciseName: string;
  weight: number;
  reps: number;
  loggedAt: number;
}

export function recentPRs(sets: LoggedSet[], athletes: Athlete[], limit: number): RecentPRRow[] {
  const nameById = new Map(athletes.map((a) => [a.id, a.name]));
  return sets
    .filter((s) => s.isPR && s.track === "load")
    .sort((a, b) => b.loggedAt - a.loggedAt)
    .slice(0, limit)
    .map((s) => ({
      athleteName: nameById.get(s.athleteId) ?? "Unknown",
      exerciseName: s.exerciseName,
      weight: s.weight ?? 0,
      reps: s.reps ?? 0,
      loggedAt: s.loggedAt,
    }));
}

export interface RosterRow {
  athlete: Athlete;
  programName: string | null;
  lastSessionLabel: string;
  volume7d: number;
  latestBadgeName: string | null;
}

function relativeDay(iso: string): string {
  const today = new Date().toISOString().slice(0, 10);
  const diffDays = Math.round(
    (new Date(today + "T00:00:00").getTime() - new Date(iso + "T00:00:00").getTime()) / DAY_MS,
  );
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays > 1) return `${diffDays} days ago`;
  if (diffDays === -1) return "Tomorrow";
  return iso;
}

export function buildRoster(
  athletes: Athlete[],
  assignments: Assignment[],
  programs: Program[],
  sessions: ScheduledSession[],
  sets: LoggedSet[],
  earned: EarnedBadge[],
  badgeDefs: BadgeDefinition[],
): RosterRow[] {
  const programNameById = new Map(programs.map((p) => [p.id, p.name]));
  const badgeNameById = new Map(badgeDefs.map((b) => [b.id, b.name]));

  return athletes.map((athlete) => {
    const athleteAssignments = assignments
      .filter((a) => a.athleteId === athlete.id)
      .sort((a, b) => b.createdAt - a.createdAt);
    const programName = athleteAssignments[0] ? programNameById.get(athleteAssignments[0].programId) ?? null : null;

    const athleteSessions = sessions
      .filter((s) => s.athleteId === athlete.id && s.status !== "scheduled")
      .sort((a, b) => (a.date < b.date ? 1 : -1));
    const lastSessionLabel = athleteSessions[0] ? relativeDay(athleteSessions[0].date) : "No sessions yet";

    const volume7d = sets
      .filter((s) => s.athleteId === athlete.id && s.track === "load" && withinLastDays(s.loggedAt, 7))
      .reduce((sum, s) => sum + s.volume, 0);

    const athleteBadges = earned
      .filter((b) => b.athleteId === athlete.id)
      .sort((a, b) => b.earnedAt - a.earnedAt);
    const latestBadgeName = athleteBadges[0] ? badgeNameById.get(athleteBadges[0].badgeDefinitionId) ?? null : null;

    return { athlete, programName, lastSessionLabel, volume7d, latestBadgeName };
  });
}

/** Completed vs. (completed + missed) among sessions that have already happened. */
export function adherence(sessions: ScheduledSession[]): { completed: number; total: number } {
  const past = sessions.filter((s) => s.status !== "scheduled");
  const completed = past.filter((s) => s.status === "completed").length;
  return { completed, total: past.length };
}
