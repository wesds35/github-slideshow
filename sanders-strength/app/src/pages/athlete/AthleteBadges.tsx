import { useState } from "react";
import { useLiveQuery } from "dexie-react-hooks";
import type { VolumeTrack } from "../../db";
import { Topbar } from "../../components/Topbar";
import { Tabs } from "../../components/Tabs";
import { BadgeCase } from "../../components/BadgeCase";
import { badgeStatusesForAthlete } from "../../lib/badges";
import { useIdentity } from "../../context/identity";

const TRACK_LABEL: Record<VolumeTrack, string> = {
  load: "Rep (Load) Volume",
  distance: "Distance Volume",
  wattage: "Wattage Volume",
};

export function AthleteBadges() {
  const { athleteId } = useIdentity();
  const [track, setTrack] = useState<VolumeTrack>("load");
  const badges = useLiveQuery(() => (athleteId ? badgeStatusesForAthlete(athleteId, track) : []), [athleteId, track]) ?? [];

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
