import type { VolumeTrack } from "../db";

export interface SetInput {
  track: VolumeTrack;
  weight?: number;
  reps?: number;
  distance?: number;
  load?: number;
  watts?: number;
  durationSec?: number;
}

/** Volume is always derived from raw inputs, never entered directly. */
export function calcVolume(set: SetInput): number {
  switch (set.track) {
    case "load":
      return (set.weight ?? 0) * (set.reps ?? 0);
    case "distance":
      return (set.distance ?? 0) * (set.load ?? 1);
    case "wattage":
      return (set.watts ?? 0) * (set.durationSec ?? 0);
  }
}

/** Epley formula: estimated 1-rep max from any weight x reps pair. */
export function epley1RM(weight: number, reps: number): number {
  if (reps <= 1) return weight;
  return weight * (1 + reps / 30);
}

export function formatVolume(volume: number, track: VolumeTrack): string {
  const rounded = Math.round(volume).toLocaleString();
  switch (track) {
    case "load":
      return `${rounded} lb`;
    case "distance":
      return `${rounded} yd·lb`;
    case "wattage":
      return `${rounded} W·s`;
  }
}
