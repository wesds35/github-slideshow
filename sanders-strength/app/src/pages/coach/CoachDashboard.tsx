import { useState } from "react";
import { Link } from "react-router-dom";
import { supabase } from "../../lib/supabaseClient";
import {
  toAthlete,
  toAssignment,
  toProgram,
  toScheduledSession,
  toLoggedSet,
  toEarnedBadge,
  toBadgeDefinition,
} from "../../lib/mappers";
import { useSupabaseData, useRefreshKey } from "../../lib/useSupabaseData";
import { useAuth } from "../../context/auth";
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
  const { fullName } = useAuth();
  const [refreshKey, refresh] = useRefreshKey();

  const athletes = useSupabaseData(async () => {
    const { data, error } = await supabase.from("athletes").select().order("name");
    if (error) throw error;
    return (data ?? []).map(toAthlete);
  }, [refreshKey]) ?? [];

  const assignments = useSupabaseData(async () => {
    const { data, error } = await supabase.from("assignments").select();
    if (error) throw error;
    return (data ?? []).map(toAssignment);
  }, [refreshKey]) ?? [];

  const programs = useSupabaseData(async () => {
    const { data, error } = await supabase.from("programs").select();
    if (error) throw error;
    return (data ?? []).map(toProgram);
  }, [refreshKey]) ?? [];

  const sessions = useSupabaseData(async () => {
    const { data, error } = await supabase.from("scheduled_sessions").select();
    if (error) throw error;
    return (data ?? []).map(toScheduledSession);
  }, [refreshKey]) ?? [];

  const sets = useSupabaseData(async () => {
    const { data, error } = await supabase.from("logged_sets").select();
    if (error) throw error;
    return (data ?? []).map(toLoggedSet);
  }, [refreshKey]) ?? [];

  const earned = useSupabaseData(async () => {
    const { data, error } = await supabase.from("earned_badges").select();
    if (error) throw error;
    return (data ?? []).map(toEarnedBadge);
  }, [refreshKey]) ?? [];

  const badgeDefs = useSupabaseData(async () => {
    const { data, error } = await supabase.from("badge_definitions").select();
    if (error) throw error;
    return (data ?? []).map(toBadgeDefinition);
  }, [refreshKey]) ?? [];

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
  const [newAthleteEmail, setNewAthleteEmail] = useState("");
  const [inviteError, setInviteError] = useState<string | null>(null);

  const addAthlete = async () => {
    const name = newAthleteName.trim();
    const email = newAthleteEmail.trim().toLowerCase();
    if (!name || !email) return;
    setInviteError(null);
    const { error } = await supabase.from("athletes").insert({ name, initials: initialsFor(name), email });
    if (error) {
      setInviteError(error.message.includes("duplicate") ? "That email is already on your roster." : error.message);
      return;
    }
    setNewAthleteName("");
    setNewAthleteEmail("");
    setAddingAthlete(false);
    refresh();
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
              <div className="avatar">{initialsFor(fullName ?? "Coach")}</div> {fullName ?? "Coach"}
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
        {roster.length === 0 ? (
          <div className="empty-state">
            <div className="rune-big">ᛋ</div>
            No athletes yet — add one to get started.
          </div>
        ) : (
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
                  <td>
                    {row.athlete.name}
                    {!row.athlete.userId && <span className="badge-pill" style={{ marginLeft: 8 }}>Invited</span>}
                  </td>
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
        )}
      </div>

      <hr className="rune-divider" />

      {addingAthlete && (
        <Modal title="Add Athlete" onClose={() => setAddingAthlete(false)}>
          <div className="field">
            <label>Full Name</label>
            <input value={newAthleteName} onChange={(e) => setNewAthleteName(e.target.value)} placeholder="e.g. Jordan Vik" autoFocus />
          </div>
          <div className="field">
            <label>Email</label>
            <input
              type="email"
              value={newAthleteEmail}
              onChange={(e) => setNewAthleteEmail(e.target.value)}
              placeholder="jordan@example.com"
            />
            <p className="muted" style={{ fontSize: ".72rem", marginTop: 4 }}>
              They'll sign up with this exact email to claim their account and see only their own data.
            </p>
          </div>
          {inviteError && (
            <p className="muted" style={{ color: "var(--red-bright)" }}>
              {inviteError}
            </p>
          )}
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
