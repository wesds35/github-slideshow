import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../../lib/supabaseClient";
import { toScheduledSession } from "../../lib/mappers";
import { useSupabaseData } from "../../lib/useSupabaseData";
import { Topbar } from "../../components/Topbar";
import { useAuth } from "../../context/auth";
import { enrichSessions, weekDates } from "../../lib/scheduler";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function AthleteSchedule() {
  const { athlete } = useAuth();
  const athleteId = athlete?.id;
  const navigate = useNavigate();
  const [anchor, setAnchor] = useState(() => new Date());
  const dates = useMemo(() => weekDates(anchor), [anchor]);
  const today = new Date().toISOString().slice(0, 10);

  const infos = useSupabaseData(
    async () => {
      if (!athleteId) return [];
      const { data, error } = await supabase
        .from("scheduled_sessions")
        .select()
        .eq("athlete_id", athleteId)
        .gte("date", dates[0])
        .lte("date", dates[6]);
      if (error) throw error;
      return enrichSessions((data ?? []).map(toScheduledSession));
    },
    [athleteId, dates.join(",")],
  ) ?? [];

  const infoByDate = new Map(infos.map((i) => [i.session.date, i]));

  if (!athleteId) return null;

  return (
    <>
      <Topbar
        eyebrow="My Schedule"
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
          const info = infoByDate.get(date);
          return (
            <div
              className={"cal-cell" + (date === today ? " today" : "")}
              key={date}
              style={{ cursor: info ? "pointer" : "default" }}
              onClick={() => info && navigate(`/athlete/log/${info.session.id}`)}
            >
              <div className="cal-date">
                {date.slice(8, 10)}
                {date === today ? " · Today" : ""}
              </div>
              {info ? (
                <div className={"cal-event " + (info.session.status === "completed" ? "done" : info.session.status === "missed" ? "missed" : "")}>
                  {info.dayLabel}
                </div>
              ) : (
                <span className="muted" style={{ fontSize: ".72rem" }}>Rest day</span>
              )}
            </div>
          );
        })}
      </div>

      <hr className="rune-divider" />
      <p className="muted">Tap a scheduled day to log your sets, or review a completed session.</p>
    </>
  );
}
