import { db, uid, type BadgeDefinition, type VolumeTrack } from "../db";

// Default tier thresholds per REFERENCE.md — coach-configurable at runtime via badgeDefinitions table.
const DEFAULT_TIERS: Array<{ tier: number; name: string }> = [
  { tier: 1, name: "Thrall" },
  { tier: 2, name: "Karl" },
  { tier: 3, name: "Jarl" },
  { tier: 4, name: "Berserker" },
  { tier: 5, name: "Einherjar" },
  { tier: 6, name: "Valhalla" },
];

const DEFAULT_THRESHOLDS: Record<VolumeTrack, number[]> = {
  load: [10_000, 50_000, 150_000, 500_000, 1_000_000, 5_000_000],
  distance: [10, 50, 150, 400, 1_000, 5_000],
  wattage: [500, 2_000, 5_000, 15_000, 40_000, 150_000],
};

/**
 * Badge definition IDs are deterministic (not random) and seeding uses `bulkPut` (upsert) rather
 * than `bulkAdd`, so this is safe to call more than once concurrently — e.g. React StrictMode's
 * double-invoked effects in dev, or two tabs opening the app for the first time at once — without
 * ever producing duplicate tiers.
 */
export async function ensureBadgeDefinitionsSeeded(): Promise<void> {
  const rows: BadgeDefinition[] = [];
  (Object.keys(DEFAULT_THRESHOLDS) as VolumeTrack[]).forEach((track) => {
    DEFAULT_TIERS.forEach(({ tier, name }, i) => {
      rows.push({
        id: `${track}-${tier}`,
        track,
        tier,
        name,
        threshold: DEFAULT_THRESHOLDS[track][i],
      });
    });
  });
  await db.badgeDefinitions.bulkPut(rows);
}

export async function badgeDefinitionsByTrack(track: VolumeTrack): Promise<BadgeDefinition[]> {
  const defs = await db.badgeDefinitions.where("track").equals(track).toArray();
  return defs.sort((a, b) => a.tier - b.tier);
}

/** Cumulative volume for an athlete on a given track, across all logged sets. */
export async function athleteTrackVolume(athleteId: string, track: VolumeTrack): Promise<number> {
  const sets = await db.loggedSets.where("athleteId").equals(athleteId).toArray();
  return sets.filter((s) => s.track === track).reduce((sum, s) => sum + s.volume, 0);
}

/** Checks an athlete's volume against thresholds and awards any newly-crossed badges. Returns the newly earned ones. */
export async function evaluateBadgesForAthlete(athleteId: string, track: VolumeTrack): Promise<BadgeDefinition[]> {
  const volume = await athleteTrackVolume(athleteId, track);
  const defs = await badgeDefinitionsByTrack(track);
  const already = await db.earnedBadges.where("athleteId").equals(athleteId).toArray();
  const earnedDefIds = new Set(already.map((b) => b.badgeDefinitionId));

  const newlyEarned: BadgeDefinition[] = [];
  for (const def of defs) {
    if (volume >= def.threshold && !earnedDefIds.has(def.id)) {
      await db.earnedBadges.add({ id: uid(), athleteId, badgeDefinitionId: def.id, earnedAt: Date.now() });
      newlyEarned.push(def);
    }
  }
  return newlyEarned;
}

export interface BadgeStatus extends BadgeDefinition {
  earned: boolean;
  earnedAt?: number;
  progress: number; // 0-1 toward this tier's threshold
}

export async function badgeStatusesForAthlete(athleteId: string, track: VolumeTrack): Promise<BadgeStatus[]> {
  const [defs, volume, earned] = await Promise.all([
    badgeDefinitionsByTrack(track),
    athleteTrackVolume(athleteId, track),
    db.earnedBadges.where("athleteId").equals(athleteId).toArray(),
  ]);
  const earnedMap = new Map(earned.map((b) => [b.badgeDefinitionId, b.earnedAt]));
  return defs.map((def) => ({
    ...def,
    earned: earnedMap.has(def.id),
    earnedAt: earnedMap.get(def.id),
    progress: Math.min(1, volume / def.threshold),
  }));
}
