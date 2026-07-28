import type { BadgeStatus } from "../lib/badges";

function initial(name: string): string {
  return name === "Thrall" ? "Þ" : name[0];
}

export function BadgeCase({ badges }: { badges: BadgeStatus[] }) {
  return (
    <div className="medallion-grid">
      {badges.map((b) => {
        const isTopTier = b.name === "Valhalla";
        const classes = ["medallion", !b.earned ? "locked" : "", isTopTier ? "gold" : ""].filter(Boolean).join(" ");
        return (
          <div className={classes} key={b.id}>
            <div className="medallion-icon">{initial(b.name)}</div>
            <div className="medallion-name">{b.name}</div>
            <div className="medallion-meta">
              {b.earned ? "Earned" : `${Math.round(b.progress * 100)}% to ${b.threshold.toLocaleString()}`}
            </div>
            {!b.earned && (
              <div className="medallion-progress">
                <div style={{ width: `${Math.round(b.progress * 100)}%` }} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
