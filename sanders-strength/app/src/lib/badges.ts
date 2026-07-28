import { supabase } from "./supabaseClient";
import { toBadgeDefinition } from "./mappers";
import type { BadgeDefinition, VolumeTrack } from "../db";

// Tier thresholds live in Postgres (see supabase/schema.sql's seed insert), not here, so a coach
// can tune them per roster without a redeploy.

export async function badgeDefinitionsByTrack(track: VolumeTrack): Promise<BadgeDefinition[]> {
  const { data, error } = await supabase.from("badge_definitions").select().eq("track", track).order("tier");
  if (error) throw error;
  return (data ?? []).map(toBadgeDefinition);
}

/** Cumulative volume for an athlete on a given track, across all logged sets. */
export async function athleteTrackVolume(athleteId: string, track: VolumeTrack): Promise<number> {
  const { data, error } = await supabase
    .from("logged_sets")
    .select("volume")
    .eq("athlete_id", athleteId)
    .eq("track", track);
  if (error) throw error;
  return (data ?? []).reduce((sum, s) => sum + s.volume, 0);
}

/** Checks an athlete's volume against thresholds and awards any newly-crossed badges. Returns the newly earned ones. */
export async function evaluateBadgesForAthlete(athleteId: string, track: VolumeTrack): Promise<BadgeDefinition[]> {
  const [volume, defs, { data: alreadyEarned, error: earnedError }] = await Promise.all([
    athleteTrackVolume(athleteId, track),
    badgeDefinitionsByTrack(track),
    supabase.from("earned_badges").select("badge_definition_id").eq("athlete_id", athleteId),
  ]);
  if (earnedError) throw earnedError;

  const earnedDefIds = new Set((alreadyEarned ?? []).map((b) => b.badge_definition_id));
  const toAward = defs.filter((def) => volume >= def.threshold && !earnedDefIds.has(def.id));
  if (toAward.length === 0) return [];

  const { error: insertError } = await supabase
    .from("earned_badges")
    .insert(toAward.map((def) => ({ athlete_id: athleteId, badge_definition_id: def.id })));
  if (insertError) throw insertError;

  return toAward;
}

export interface BadgeStatus extends BadgeDefinition {
  earned: boolean;
  earnedAt?: number;
  progress: number; // 0-1 toward this tier's threshold
}

export async function badgeStatusesForAthlete(athleteId: string, track: VolumeTrack): Promise<BadgeStatus[]> {
  const [defs, volume, { data: earnedRows, error: earnedError }] = await Promise.all([
    badgeDefinitionsByTrack(track),
    athleteTrackVolume(athleteId, track),
    supabase.from("earned_badges").select("badge_definition_id, earned_at").eq("athlete_id", athleteId),
  ]);
  if (earnedError) throw earnedError;

  const earnedMap = new Map((earnedRows ?? []).map((b) => [b.badge_definition_id, Date.parse(b.earned_at)]));
  return defs.map((def) => ({
    ...def,
    earned: earnedMap.has(def.id),
    earnedAt: earnedMap.get(def.id),
    progress: Math.min(1, volume / def.threshold),
  }));
}
