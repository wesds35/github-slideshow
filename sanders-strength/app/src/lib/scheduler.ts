import { supabase } from "./supabaseClient";
import type { ScheduledSession, SessionStatus } from "../db";

export function startOfWeek(date: Date): Date {
  const day = (date.getDay() + 6) % 7; // Monday = 0
  const monday = new Date(date);
  monday.setDate(date.getDate() - day);
  monday.setHours(0, 0, 0, 0);
  return monday;
}

export function weekDates(anchor: Date): string[] {
  const monday = startOfWeek(anchor);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d.toISOString().slice(0, 10);
  });
}

export interface SessionInfo {
  session: ScheduledSession;
  dayLabel: string;
  athleteName: string;
}

export async function enrichSessions(sessions: ScheduledSession[]): Promise<SessionInfo[]> {
  const dayIds = [...new Set(sessions.map((s) => s.dayId))];
  const athleteIds = [...new Set(sessions.map((s) => s.athleteId))];
  const [{ data: days, error: daysError }, { data: athletes, error: athletesError }] = await Promise.all([
    supabase.from("program_days").select("id, label").in("id", dayIds),
    supabase.from("athletes").select("id, name").in("id", athleteIds),
  ]);
  if (daysError) throw daysError;
  if (athletesError) throw athletesError;
  const labelByDayId = new Map((days ?? []).map((d) => [d.id, d.label]));
  const nameByAthleteId = new Map((athletes ?? []).map((a) => [a.id, a.name]));

  return sessions.map((session) => ({
    session,
    dayLabel: labelByDayId.get(session.dayId) ?? "Session",
    athleteName: nameByAthleteId.get(session.athleteId) ?? "Unknown",
  }));
}

export interface DayCellGroup {
  dayLabel: string;
  count: number;
  statuses: SessionStatus[];
}

export function groupByDayLabel(infos: SessionInfo[]): DayCellGroup[] {
  const map = new Map<string, DayCellGroup>();
  for (const info of infos) {
    const existing = map.get(info.dayLabel);
    if (existing) {
      existing.count += 1;
      existing.statuses.push(info.session.status);
    } else {
      map.set(info.dayLabel, { dayLabel: info.dayLabel, count: 1, statuses: [info.session.status] });
    }
  }
  return [...map.values()];
}
