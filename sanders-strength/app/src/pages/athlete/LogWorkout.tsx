import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { supabase } from "../../lib/supabaseClient";
import { toLoggedSet, toScheduledSession } from "../../lib/mappers";
import { useSupabaseData, useRefreshKey } from "../../lib/useSupabaseData";
import type { ProgramExercise } from "../../db";
import { Topbar } from "../../components/Topbar";
import { programDayDetail, markSessionStatus } from "../../lib/programs";
import { logSet } from "../../lib/logging";
import { formatVolume } from "../../lib/volume";
import { announceBadgesEarned } from "../../lib/toastBus";

function ExerciseLogger({ sessionId, athleteId, exercise }: { sessionId: string; athleteId: string; exercise: ProgramExercise }) {
  const [refreshKey, refresh] = useRefreshKey();
  const loggedSets = useSupabaseData(async () => {
    const { data, error } = await supabase
      .from("logged_sets")
      .select()
      .eq("session_id", sessionId)
      .eq("exercise_id", exercise.id)
      .order("set_number");
    if (error) throw error;
    return (data ?? []).map(toLoggedSet);
  }, [sessionId, exercise.id, refreshKey]) ?? [];

  const [weight, setWeight] = useState("");
  const [reps, setReps] = useState(String(exercise.prescribedReps ?? ""));
  const [distance, setDistance] = useState("");
  const [load, setLoad] = useState("");
  const [watts, setWatts] = useState("");
  const [durationSec, setDurationSec] = useState("");

  const nextSetNumber = loggedSets.length + 1;
  const doneAllPrescribed = loggedSets.length >= exercise.prescribedSets;

  const submit = async () => {
    const { newlyEarnedBadges } = await logSet({
      sessionId,
      athleteId,
      exercise,
      setNumber: nextSetNumber,
      weight: exercise.track === "load" ? Number(weight) || 0 : undefined,
      reps: exercise.track === "load" ? Number(reps) || 0 : undefined,
      distance: exercise.track === "distance" ? Number(distance) || 0 : undefined,
      load: exercise.track === "distance" ? Number(load) || 0 : undefined,
      watts: exercise.track === "wattage" ? Number(watts) || 0 : undefined,
      durationSec: exercise.track === "wattage" ? Number(durationSec) || 0 : undefined,
    });
    if (newlyEarnedBadges.length > 0) announceBadgesEarned(newlyEarnedBadges);
    setWeight("");
    setDistance("");
    setLoad("");
    setWatts("");
    setDurationSec("");
    refresh();
  };

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3>
        {exercise.name}{" "}
        <span className="muted" style={{ textTransform: "none", letterSpacing: 0, fontSize: ".8rem" }}>
          — prescribed {exercise.prescribedSets} × {exercise.prescribedReps ?? "—"} {exercise.prescriptionNote}
        </span>
      </h3>
      <table>
        <thead>
          <tr>
            <th>Set</th>
            {exercise.track === "load" && (
              <>
                <th>Weight (lb)</th>
                <th>Reps</th>
              </>
            )}
            {exercise.track === "distance" && (
              <>
                <th>Distance (yd)</th>
                <th>Load (lb)</th>
              </>
            )}
            {exercise.track === "wattage" && (
              <>
                <th>Watts</th>
                <th>Duration (s)</th>
              </>
            )}
            <th>Volume</th>
          </tr>
        </thead>
        <tbody>
          {loggedSets.map((s) => (
            <tr key={s.id}>
              <td>{s.setNumber}</td>
              {exercise.track === "load" && (
                <>
                  <td className="muted">{s.weight}</td>
                  <td className="muted">{s.reps}</td>
                </>
              )}
              {exercise.track === "distance" && (
                <>
                  <td className="muted">{s.distance}</td>
                  <td className="muted">{s.load}</td>
                </>
              )}
              {exercise.track === "wattage" && (
                <>
                  <td className="muted">{s.watts}</td>
                  <td className="muted">{s.durationSec}</td>
                </>
              )}
              <td>
                {s.isPR ? (
                  <span className="badge-pill pr">{formatVolume(s.volume, s.track)}</span>
                ) : (
                  <span className="muted">{formatVolume(s.volume, s.track)}</span>
                )}
              </td>
            </tr>
          ))}
          <tr>
            <td>{nextSetNumber}</td>
            {exercise.track === "load" && (
              <>
                <td>
                  <input type="number" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder="lb" />
                </td>
                <td>
                  <input type="number" value={reps} onChange={(e) => setReps(e.target.value)} placeholder="reps" />
                </td>
              </>
            )}
            {exercise.track === "distance" && (
              <>
                <td>
                  <input type="number" value={distance} onChange={(e) => setDistance(e.target.value)} placeholder="yd" />
                </td>
                <td>
                  <input type="number" value={load} onChange={(e) => setLoad(e.target.value)} placeholder="lb" />
                </td>
              </>
            )}
            {exercise.track === "wattage" && (
              <>
                <td>
                  <input type="number" value={watts} onChange={(e) => setWatts(e.target.value)} placeholder="watts" />
                </td>
                <td>
                  <input type="number" value={durationSec} onChange={(e) => setDurationSec(e.target.value)} placeholder="sec" />
                </td>
              </>
            )}
            <td>
              <button className="btn btn-primary btn-sm" onClick={submit}>
                Log Set
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      {doneAllPrescribed && <p className="muted" style={{ marginTop: 10 }}>Prescribed sets complete — log extra sets above if needed.</p>}
    </div>
  );
}

export function LogWorkout() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const session = useSupabaseData(async () => {
    if (!sessionId) return undefined;
    const { data, error } = await supabase.from("scheduled_sessions").select().eq("id", sessionId).maybeSingle();
    if (error) throw error;
    return data ? toScheduledSession(data) : undefined;
  }, [sessionId]);

  const dayDetail = useSupabaseData(() => (session ? programDayDetail(session.dayId) : Promise.resolve(undefined)), [session]);

  if (!sessionId || !session || !dayDetail?.day) return null;

  const finish = async () => {
    await markSessionStatus(sessionId, "completed");
    navigate("/athlete/schedule");
  };

  return (
    <>
      <Topbar
        eyebrow={`Session · ${session.date}`}
        title={dayDetail.day.label}
        right={
          <button className="btn btn-primary" onClick={finish}>
            Finish Session
          </button>
        }
      />

      {dayDetail.exercises.map((ex) => (
        <ExerciseLogger key={ex.id} sessionId={sessionId} athleteId={session.athleteId} exercise={ex} />
      ))}

      <hr className="rune-divider" />
    </>
  );
}
