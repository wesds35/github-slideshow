import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { supabase } from "../../lib/supabaseClient";
import { toScheduledSession } from "../../lib/mappers";
import { useSupabaseData } from "../../lib/useSupabaseData";
import { Topbar } from "../../components/Topbar";
import { enrichSessions, groupByDayLabel, weekDates, type SessionInfo } from "../../lib/scheduler";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function statusClass(statuses: string[]): string {
  if (statuses.every((s) => s === "completed")) return "done";
  if (statuses.every((s) => s === "missed")) return "missed";
  return "";
}

export function CoachScheduler() {
  const [anchor, setAnchor] = useState(() => new Date());
  const dates = useMemo(() => weekDates(anchor), [anchor]);
  const today = new Date().toISOString().slice(0, 10);

  const infos = useSupabaseData(
    async () => {
      const { data, error } = await supabase.from("scheduled_sessions").select().in("date", dates);
      if (error) throw error;
      return enrichSessions((data ?? []).map(toScheduledSession));
    },
    [dates.join(",")],
  ) ?? [];

  const [selectedDate, setSelectedDate] = useState(today);
  const selectedInfos = infos.filter((i) => i.session.date === selectedDate);

  const infosByDate = new Map<string, SessionInfo[]>();
  for (const info of infos) {
    const list = infosByDate.get(info.session.date) ?? [];
    list.push(info);
    infosByDate.set(info.session.date, list);
  }

  return (
    <>
      <Topbar
        eyebrow="Scheduler"
        title={`Week of ${dates[0]}`}
        right={
          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setAnchor(new Date(new Date(anchor).setDate(anchor.getDate() - 7)))}>
              ← Prev
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setAnchor(new Date())}>
              Today
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setAnchor(new Date(new Date(anchor).setDate(anchor.getDate() + 7)))}>
              Next →
            </button>
          </div>
        }
      />

      <div className="cal-grid" style={{ marginBottom: 8 }}>
        {dates.map((date, i) => (
          <div className="cal-day-name" key={date}>
            {DAY_NAMES[i]} {date.slice(8, 10)}
          </div>
        ))}
      </div>
      <div className="cal-grid">
        {dates.map((date) => {
          const dayInfos = infosByDate.get(date) ?? [];
          const groups = groupByDayLabel(dayInfos);
          return (
            <div
              className={"cal-cell" + (date === today ? " today" : "")}
              key={date}
              onClick={() => setSelectedDate(date)}
              style={{ cursor: "pointer" }}
            >
              <div className="cal-date">
                {date.slice(8, 10)}
                {date === today ? " · Today" : ""}
              </div>
              {groups.length === 0 && <span className="muted" style={{ fontSize: ".72rem" }}>Rest day</span>}
              {groups.map((g) => (
                <div className={"cal-event " + statusClass(g.statuses)} key={g.dayLabel}>
                  {g.dayLabel} — {g.count}
                </div>
              ))}
            </div>
          );
        })}
      </div>

      <hr className="rune-divider" />

      <div className="card">
        <h3>{selectedDate === today ? "Today" : selectedDate} — Detail</h3>
        {selectedInfos.length === 0 ? (
          <div className="empty-state">
            <div className="rune-big">ᛗ</div>
            No sessions scheduled this day.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Athlete</th>
                <th>Session</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {selectedInfos.map((info) => (
                <tr key={info.session.id}>
                  <td>{info.athleteName}</td>
                  <td className="muted">{info.dayLabel}</td>
                  <td>
                    <span
                      className="badge-pill"
                      style={
                        info.session.status === "completed"
                          ? { background: "rgba(76,175,106,.14)", color: "#4caf6a", borderColor: "rgba(76,175,106,.35)" }
                          : undefined
                      }
                    >
                      {info.session.status}
                    </span>
                  </td>
                  <td>
                    <Link className="btn btn-ghost btn-sm" to={`/coach/athletes/${info.session.athleteId}`}>
                      View Athlete
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
