import { supabase } from "./supabaseClient";
import { toLoggedSet } from "./mappers";
import type { LoggedSet } from "../db";
import { epley1RM } from "./volume";

export interface LiftPR {
  exerciseName: string;
  bestWeight: number;
  bestWeightReps: number;
  bestE1RM: number;
  achievedAt: number;
}

/** Best set (by weight) and estimated 1RM for one "load" track lift, from all prior sets. */
export function bestOf(sets: LoggedSet[]): LiftPR | null {
  const loadSets = sets.filter((s) => s.track === "load" && s.weight != null && s.reps != null);
  if (loadSets.length === 0) return null;

  let best = loadSets[0];
  let bestE1RM = epley1RM(best.weight!, best.reps!);
  for (const s of loadSets) {
    const e = epley1RM(s.weight!, s.reps!);
    if (e > bestE1RM) {
      bestE1RM = e;
      best = s;
    }
  }
  return {
    exerciseName: best.exerciseName,
    bestWeight: best.weight!,
    bestWeightReps: best.reps!,
    bestE1RM,
    achievedAt: best.loggedAt,
  };
}

/** True if this candidate set beats every prior set logged for the same athlete + lift. */
export function isNewPR(priorSets: LoggedSet[], candidateWeight: number, candidateReps: number): boolean {
  const priorBest = bestOf(priorSets);
  if (!priorBest) return true;
  return epley1RM(candidateWeight, candidateReps) > priorBest.bestE1RM;
}

/** Current PR per lift name for an athlete, across all their "load" track logged sets. */
export async function currentPRsForAthlete(athleteId: string): Promise<LiftPR[]> {
  const { data, error } = await supabase.from("logged_sets").select().eq("athlete_id", athleteId);
  if (error) throw error;
  const sets = (data ?? []).map(toLoggedSet);
  const byLift = new Map<string, LoggedSet[]>();
  for (const s of sets) {
    if (s.track !== "load") continue;
    const list = byLift.get(s.exerciseName) ?? [];
    list.push(s);
    byLift.set(s.exerciseName, list);
  }
  const prs: LiftPR[] = [];
  for (const [, lifts] of byLift) {
    const pr = bestOf(lifts);
    if (pr) prs.push(pr);
  }
  return prs.sort((a, b) => b.achievedAt - a.achievedAt);
}
