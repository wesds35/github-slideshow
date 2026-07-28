import { supabase } from "./supabaseClient";
import { toLoggedSet } from "./mappers";
import type { LoggedSet, ProgramExercise, VolumeTrack, BadgeDefinition } from "../db";
import { calcVolume } from "./volume";
import { isNewPR } from "./prs";
import { evaluateBadgesForAthlete } from "./badges";

export interface SetLogInput {
  sessionId: string;
  athleteId: string;
  exercise: Pick<ProgramExercise, "id" | "name" | "track">;
  setNumber: number;
  weight?: number;
  reps?: number;
  distance?: number;
  load?: number;
  watts?: number;
  durationSec?: number;
}

export interface LogSetResult {
  set: LoggedSet;
  newlyEarnedBadges: BadgeDefinition[];
}

/** Logs one set: derives volume, flags PRs against prior history, persists, then re-evaluates badges. */
export async function logSet(input: SetLogInput): Promise<LogSetResult> {
  const track: VolumeTrack = input.exercise.track;
  const volume = calcVolume({
    track,
    weight: input.weight,
    reps: input.reps,
    distance: input.distance,
    load: input.load,
    watts: input.watts,
    durationSec: input.durationSec,
  });

  let isPR = false;
  if (track === "load" && input.weight != null && input.reps != null) {
    const { data: priorRows, error: priorError } = await supabase
      .from("logged_sets")
      .select()
      .eq("athlete_id", input.athleteId)
      .eq("exercise_name", input.exercise.name);
    if (priorError) throw priorError;
    isPR = isNewPR((priorRows ?? []).map(toLoggedSet), input.weight, input.reps);
  }

  const { data: setRow, error: insertError } = await supabase
    .from("logged_sets")
    .insert({
      session_id: input.sessionId,
      exercise_id: input.exercise.id,
      athlete_id: input.athleteId,
      exercise_name: input.exercise.name,
      track,
      set_number: input.setNumber,
      weight: input.weight,
      reps: input.reps,
      distance: input.distance,
      load: input.load,
      watts: input.watts,
      duration_sec: input.durationSec,
      volume,
      is_pr: isPR,
    })
    .select()
    .single();
  if (insertError) throw insertError;

  const newlyEarnedBadges = await evaluateBadgesForAthlete(input.athleteId, track);

  return { set: toLoggedSet(setRow), newlyEarnedBadges };
}
