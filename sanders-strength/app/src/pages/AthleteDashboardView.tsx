import { useLiveQuery } from "dexie-react-hooks";
import { db } from "../db";
import { Topbar } from "../components/Topbar";
import { BadgeCase } from "../components/BadgeCase";
import { adherence, weeklyLoadVolumeTrend } from "../lib/dashboard";
import { badgeStatusesForAthlete } from "../lib/badges";
import { currentPRsForAthlete } from "../lib/prs";
import { formatVolume } from "../lib/volume";
import { Link } from "react-router-dom";

export function AthleteDashboardView({ athleteId, badgesPath }: { athleteId: string; badgesPath: string }) {
  const athlete = useLiveQuery(() => db.athletes.get(athleteId), [athleteId]);
  const sets = useLiveQuery(() => db.loggedSets.where("athleteId").equals(athleteId).toArray(), [athleteId]) ?? [];
  const sessions = useLiveQuery(() => db.scheduledSessions.where("athleteId").equals(athleteId).toArray(), [athleteId]) ?? [];
  const loadBadges = useLiveQuery(() => badgeStatusesForAthlete(athleteId, "load"), [athleteId]) ?? [];
  const prs = useLiveQuery(() => currentPRsForAthlete(athleteId), [athleteId]) ?? [];
  const assignment = useLiveQuery(() => db.assignments.where("athleteId").equals(athleteId).last(), [athleteId]);
  const program = useLiveQuery(() => (assignment ? db.programs.get(assignment.programId) : undefined), [assignment]);

  const lifetimeLoad = sets.filter((s) => s.track === "load").reduce((sum, s) => sum + s.volume, 0);
  const lifetimeDistance = sets.filter((s) => s.track === "distance").reduce((sum, s) => sum + s.volume, 0);
  const lifetimeWattage = sets.filter((s) => s.track === "wattage").reduce((sum, s) => sum + s.volume, 0);

  const trend = weeklyLoadVolumeTrend(sets, 4);
  const trendMax = Math.max(1, ...trend);
  const { completed, total } = adherence(sessions);

  const topLoadBadge = [...loadBadges].reverse().find((b) => b.earned);

  if (!athlete) return null;

  return (
    <>
      <Topbar
        eyebrow="Athlete Dashboard"
        title={athlete.name}
        right={
          <div className="user-chip">
            <div className="avatar">{athlete.initials}</div>
            {program ? program.name : "No program assigned"}
          </div>
        }
      />

      <div className="grid grid-4" style={{ marginBottom: 20 }}>
        <div className="card stat-card">
          <div className="stat-label">Lifetime Rep Volume</div>
          <div className="stat-value">{formatVolume(lifetimeLoad, "load")}</div>
          {topLoadBadge && <div className="stat-delta up">{topLoadBadge.name} tier</div>}
        </div>
        <div className="card stat-card">
          <div className="stat-label">Lifetime Distance</div>
          <div className="stat-value">{formatVolume(lifetimeDistance, "distance")}</div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">Lifetime Wattage Work</div>
          <div className="stat-value">{formatVolume(lifetimeWattage, "wattage")}</div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">Adherence</div>
          <div className="stat-value">{total > 0 ? `${Math.round((completed / total) * 100)}%` : "—"}</div>
          <div className="stat-delta up">
            {completed}/{total} sessions
          </div>
        </div>
      </div>

      <div className="grid grid-2" style={{ marginBottom: 20, alignItems: "start" }}>
        <div className="card">
          <h3>Weekly Rep Volume</h3>
          <div className="bars">
            {trend.map((v, i) => (
              <div className="bar-col" key={i}>
                <div className="bar" style={{ height: `${Math.max(4, (v / trendMax) * 100)}%` }} />
                <div className="bar-label">Wk{i + 1}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h3>Current PRs</h3>
          {prs.length === 0 ? (
            <div className="empty-state">
              <div className="rune-big">ᛊ</div>
              No lifts logged yet.
            </div>
          ) : (
            <table>
              <tbody>
                {prs.map((pr) => (
                  <tr key={pr.exerciseName}>
                    <td>{pr.exerciseName}</td>
                    <td className="muted">
                      {pr.bestWeight} × {pr.bestWeightReps}
                    </td>
                    <td>
                      <span className="badge-pill pr">e1RM {Math.round(pr.bestE1RM)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="card">
        <h3>Badge Case</h3>
        <BadgeCase badges={loadBadges} />
        <p className="muted" style={{ marginTop: 14 }}>
          <Link to={badgesPath}>View full badge catalog →</Link>
        </p>
      </div>

      <hr className="rune-divider" />
    </>
  );
}
