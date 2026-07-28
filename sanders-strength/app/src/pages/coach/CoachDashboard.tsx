import { useState } from "react";
import { useLiveQuery } from "dexie-react-hooks";
import { Link } from "react-router-dom";
import { db, uid } from "../../db";
import { Topbar } from "../../components/Topbar";
import { Modal } from "../../components/Modal";
import { buildRoster, recentPRs, weeklyLoadVolumeTrend, withinLastDays } from "../../lib/dashboard";

function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "??";
}

function currentWeekRange(): { start: string; end: string } {
  const now = new Date();
  const day = (now.getDay() + 6) % 7; // Monday = 0
  const monday = new Date(now);
  monday.setDate(now.getDate() - day);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  return { start: monday.toISOString().slice(0, 10), end: sunday.toISOString().slice(0, 10) };
}

export function CoachDashboard() {
  const athletes = useLiveQuery(() => db.athletes.toArray(), []) ?? [];
  const assignments = useLiveQuery(() => db.assignments.toArray(), []) ?? [];
  const programs = useLiveQuery(() => db.programs.toArray(), []) ?? [];
  const sessions = useLiveQuery(() => db.scheduledSessions.toArray(), []) ?? [];
  const sets = useLiveQuery(() => db.loggedSets.toArray(), []) ?? [];
  const earned = useLiveQuery(() => db.earnedBadges.toArray(), []) ?? [];
  const badgeDefs = useLiveQuery(() => db.badgeDefinitions.toArray(), []) ?? [];

  const volume7d = sets
    .filter((s) => s.track === "load" && withinLastDays(s.loggedAt, 7))
    .reduce((sum, s) => sum + s.volume, 0);

  const { start, end } = currentWeekRange();
  const weekSessions = sessions.filter((s) => s.date >= start && s.date <= end);
  const completedThisWeek = weekSessions.filter((s) => s.status === "completed").length;

  const badgesEarned7d = earned.filter((b) => withinLastDays(b.earnedAt, 7)).length;

  const trend = weeklyLoadVolumeTrend(sets, 7);
  const trendMax = Math.max(1, ...trend);

  const prs = recentPRs(sets, athletes, 4);
  const roster = buildRoster(athletes, assignments, programs, sessions, sets, earned, badgeDefs);

  const [addingAthlete, setAddingAthlete] = useState(false);
  const [newAthleteName, setNewAthleteName] = useState("");

  const addAthlete = async () => {
    const name = newAthleteName.trim();
    if (!name) return;
    await db.athletes.add({ id: uid(), name, initials: initialsFor(name), createdAt: Date.now() });
    setNewAthleteName("");
    setAddingAthlete(false);
  };

  return (
    <>
      <Topbar
        eyebrow="Coach Dashboard"
        title="Roster Overview"
        right={
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button className="btn btn-primary btn-sm" onClick={() => setAddingAthlete(true)}>
              + Add Athlete
            </button>
            <div className="user-chip">
              <div className="avatar">CS</div> Coach Sanders
            </div>
          </div>
        }
      />

      <div className="grid grid-4" style={{ marginBottom: 20 }}>
        <div className="card stat-card">
          <div className="stat-label">Team Volume — 7d</div>
          <div className="stat-value">
            {Math.round(volume7d).toLocaleString()} <span style={{ fontSize: ".9rem", color: "var(--text-faint)" }}>lb</span>
          </div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">Active Athletes</div>
          <div className="stat-value">{athletes.length}</div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">Sessions Completed (this wk)</div>
          <div className="stat-value">
            {completedThisWeek} / {weekSessions.length}
          </div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">Badges Earned — 7d</div>
          <div className="stat-value">{badgesEarned7d}</div>
        </div>
      </div>

      <div className="grid grid-2" style={{ marginBottom: 20, alignItems: "start" }}>
        <div className="card">
          <h3>Team Volume Trend (weeks)</h3>
          <div className="bars">
            {trend.map((v, i) => (
              <div className="bar-col" key={i}>
                <div className="bar" style={{ height: `${Math.max(4, (v / trendMax) * 100)}%` }} />
                <div className="bar-label">W{i + 1}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h3>Recent PRs</h3>
          {prs.length === 0 ? (
            <div className="empty-state">
              <div className="rune-big">ᛊ</div>
              No PRs logged yet.
            </div>
          ) : (
            <table>
              <tbody>
                {prs.map((pr, i) => (
                  <tr key={i}>
                    <td>{pr.athleteName}</td>
                    <td className="muted">{pr.exerciseName}</td>
                    <td>
                      <span className="badge-pill pr">
                        {pr.weight}×{pr.reps}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="card">
        <h3>Athlete Roster</h3>
        <table>
          <thead>
            <tr>
              <th>Athlete</th>
              <th>Program</th>
              <th>Last Session</th>
              <th>7d Volume</th>
              <th>Latest Badge</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {roster.map((row) => (
              <tr key={row.athlete.id}>
                <td>{row.athlete.name}</td>
                <td className="muted">{row.programName ?? "Unassigned"}</td>
                <td className="muted">{row.lastSessionLabel}</td>
                <td>{Math.round(row.volume7d).toLocaleString()} lb</td>
                <td>{row.latestBadgeName ? <span className="badge-pill">{row.latestBadgeName}</span> : <span className="muted">—</span>}</td>
                <td>
                  <Link className="btn btn-ghost btn-sm" to={`/coach/athletes/${row.athlete.id}`}>
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <hr className="rune-divider" />

      {addingAthlete && (
        <Modal title="Add Athlete" onClose={() => setAddingAthlete(false)}>
          <div className="field">
            <label>Full Name</label>
            <input value={newAthleteName} onChange={(e) => setNewAthleteName(e.target.value)} placeholder="e.g. Jordan Vik" autoFocus />
          </div>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={() => setAddingAthlete(false)}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={addAthlete}>
              Add
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
