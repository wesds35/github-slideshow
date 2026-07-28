import { useState } from "react";
import type { VolumeTrack } from "../../db";
import { Topbar } from "../../components/Topbar";
import { Tabs } from "../../components/Tabs";
import { BadgeCase } from "../../components/BadgeCase";
import { badgeStatusesForAthlete } from "../../lib/badges";
import { useSupabaseData } from "../../lib/useSupabaseData";
import { useAuth } from "../../context/auth";

const TRACK_LABEL: Record<VolumeTrack, string> = {
  load: "Rep (Load) Volume",
  distance: "Distance Volume",
  wattage: "Wattage Volume",
};

export function AthleteBadges() {
  const { athlete } = useAuth();
  const athleteId = athlete?.id;
  const [track, setTrack] = useState<VolumeTrack>("load");
  const badges = useSupabaseData(() => (athleteId ? badgeStatusesForAthlete(athleteId, track) : Promise.resolve([])), [athleteId, track]) ?? [];

  if (!athleteId) return null;

  return (
    <>
      <Topbar eyebrow="My Badges" title="Milestone Tiers" />

      <Tabs
        options={[
          { value: "load", label: TRACK_LABEL.load },
          { value: "distance", label: TRACK_LABEL.distance },
          { value: "wattage", label: TRACK_LABEL.wattage },
        ]}
        active={track}
        onChange={setTrack}
      />

      <BadgeCase badges={badges} />

      <hr className="rune-divider" />
    </>
  );
}
