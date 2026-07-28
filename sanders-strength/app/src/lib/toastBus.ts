import type { BadgeDefinition } from "../db";

type Listener = (badge: BadgeDefinition) => void;

const listeners = new Set<Listener>();

export function onBadgeEarned(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function announceBadgesEarned(badges: BadgeDefinition[]): void {
  badges.forEach((b) => listeners.forEach((l) => l(b)));
}
