import { useState } from "react";
import type { VolumeTrack } from "../../db";
import { badgeDefinitionsByTrack } from "../../lib/badges";
import { useSupabaseData } from "../../lib/useSupabaseData";
import { Topbar } from "../../components/Topbar";
import { Tabs } from "../../components/Tabs";

const TRACK_LABEL: Record<VolumeTrack, string> = {
  load: "Rep (Load) Volume",
  distance: "Distance Volume",
  wattage: "Wattage Volume",
};

const TRACK_UNIT: Record<VolumeTrack, string> = { load: "lb", distance: "yd·lb", wattage: "W·s" };

export function BadgeCatalog() {
  const [track, setTrack] = useState<VolumeTrack>("load");
  const defs = useSupabaseData(() => badgeDefinitionsByTrack(track), [track]) ?? [];
  const sorted = [...defs].sort((a, b) => a.tier - b.tier);

  return (
    <>
      <Topbar eyebrow="Badge Catalog" title="Milestone Tiers" />

      <Tabs
        options={[
          { value: "load", label: TRACK_LABEL.load },
          { value: "distance", label: TRACK_LABEL.distance },
          { value: "wattage", label: TRACK_LABEL.wattage },
        ]}
        active={track}
        onChange={setTrack}
      />

      <div className="medallion-grid">
        {sorted.map((def) => (
          <div className={"medallion" + (def.name === "Valhalla" ? " gold" : "")} key={def.id}>
            <div className="medallion-icon">{def.name === "Thrall" ? "Þ" : def.name[0]}</div>
            <div className="medallion-name">{def.name}</div>
            <div className="medallion-meta">
              {def.threshold.toLocaleString()} {TRACK_UNIT[track]}
            </div>
          </div>
        ))}
      </div>

      <hr className="rune-divider" />
      <p className="muted" style={{ maxWidth: 640 }}>
        Thresholds are configurable per roster (youth / collegiate / pro). Badges are permanent once earned and
        track separately per volume type, plus per-lift for signature exercises.
      </p>
    </>
  );
}
