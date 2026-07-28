import { db, uid, type LoggedSet, type ProgramExercise, type VolumeTrack, type BadgeDefinition } from "../db";
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
  loggedAt?: number;
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
    const priorSets = await db.loggedSets
      .where("[athleteId+exerciseName]")
      .equals([input.athleteId, input.exercise.name])
      .toArray();
    isPR = isNewPR(priorSets, input.weight, input.reps);
  }

  const set: LoggedSet = {
    id: uid(),
    sessionId: input.sessionId,
    exerciseId: input.exercise.id,
    athleteId: input.athleteId,
    exerciseName: input.exercise.name,
    track,
    setNumber: input.setNumber,
    weight: input.weight,
    reps: input.reps,
    distance: input.distance,
    load: input.load,
    watts: input.watts,
    durationSec: input.durationSec,
    volume,
    isPR,
    loggedAt: input.loggedAt ?? Date.now(),
  };

  await db.loggedSets.add(set);
  const newlyEarnedBadges = await evaluateBadgesForAthlete(input.athleteId, track);

  return { set, newlyEarnedBadges };
}
