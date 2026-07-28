import { useState } from "react";
import { useLiveQuery } from "dexie-react-hooks";
import { useNavigate, useParams } from "react-router-dom";
import { db, type VolumeTrack, type ProgramExercise } from "../../db";
import { Topbar } from "../../components/Topbar";
import { Modal } from "../../components/Modal";
import {
  addDay,
  addExercise,
  addWeek,
  deleteDay,
  deleteExercise,
  deleteProgram,
  deleteWeek,
  programTree,
  updateExercise,
  assignProgramToAthlete,
  type ExerciseSpec,
} from "../../lib/programs";

const TRACK_OPTIONS: Array<{ value: VolumeTrack; label: string }> = [
  { value: "load", label: "Load (sets × reps × weight)" },
  { value: "distance", label: "Distance" },
  { value: "wattage", label: "Wattage" },
];

const emptyExerciseForm: ExerciseSpec = {
  name: "",
  track: "load",
  prescribedSets: 3,
  prescribedReps: 5,
  prescriptionNote: "",
  restNote: "",
};

export function ProgramDetail() {
  const { programId } = useParams<{ programId: string }>();
  const navigate = useNavigate();

  const program = useLiveQuery(() => (programId ? db.programs.get(programId) : undefined), [programId]);
  const tree = useLiveQuery(() => (programId ? programTree(programId) : []), [programId]) ?? [];
  const athletes = useLiveQuery(() => db.athletes.toArray(), []) ?? [];
  const assignments = useLiveQuery(() => (programId ? db.assignments.where("programId").equals(programId).toArray() : []), [programId]) ?? [];

  const [addingDayToWeek, setAddingDayToWeek] = useState<string | null>(null);
  const [dayLabel, setDayLabel] = useState("");

  const [exerciseModal, setExerciseModal] = useState<{ dayId: string; editingId?: string } | null>(null);
  const [exerciseForm, setExerciseForm] = useState<ExerciseSpec>(emptyExerciseForm);

  const [assigning, setAssigning] = useState(false);
  const [selectedAthletes, setSelectedAthletes] = useState<Set<string>>(new Set());
  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10));

  if (!programId || !program) return null;

  const openAddExercise = (dayId: string) => {
    setExerciseForm(emptyExerciseForm);
    setExerciseModal({ dayId });
  };

  const openEditExercise = (dayId: string, ex: ProgramExercise) => {
    setExerciseForm({
      name: ex.name,
      track: ex.track,
      prescribedSets: ex.prescribedSets,
      prescribedReps: ex.prescribedReps,
      prescriptionNote: ex.prescriptionNote,
      restNote: ex.restNote,
    });
    setExerciseModal({ dayId, editingId: ex.id });
  };

  const saveExercise = async () => {
    if (!exerciseModal || !exerciseForm.name.trim()) return;
    if (exerciseModal.editingId) {
      await updateExercise(exerciseModal.editingId, exerciseForm);
    } else {
      await addExercise(exerciseModal.dayId, exerciseForm);
    }
    setExerciseModal(null);
  };

  const handleAddDay = async () => {
    if (!addingDayToWeek || !dayLabel.trim()) return;
    await addDay(addingDayToWeek, dayLabel.trim());
    setAddingDayToWeek(null);
    setDayLabel("");
  };

  const toggleAthlete = (id: string) => {
    setSelectedAthletes((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const submitAssignment = async () => {
    for (const athleteId of selectedAthletes) {
      await assignProgramToAthlete(programId, athleteId, startDate);
    }
    setAssigning(false);
    setSelectedAthletes(new Set());
  };

  const handleDeleteProgram = async () => {
    if (!confirm(`Delete "${program.name}"? This also removes its assignments and scheduled sessions.`)) return;
    await deleteProgram(programId);
    navigate("/coach/programs");
  };

  return (
    <>
      <Topbar
        eyebrow="Program Builder"
        title={program.name}
        right={
          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn btn-ghost" onClick={handleDeleteProgram}>
              Delete
            </button>
            <button className="btn btn-primary" onClick={() => setAssigning(true)}>
              Assign to Athletes
            </button>
          </div>
        }
      />

      <p className="muted" style={{ marginTop: -12, marginBottom: 20 }}>
        {program.durationWeeks} weeks · {program.tags || "Untagged"} · {assignments.length} athlete
        {assignments.length === 1 ? "" : "s"} assigned
      </p>

      {tree.map(({ week, days }) => (
        <div className="builder-week" key={week.id}>
          <div className="builder-week-head">
            <strong>Week {week.weekNumber}</strong>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setAddingDayToWeek(week.id)}>
                + Add Day
              </button>
              <button className="icon-btn" onClick={() => deleteWeek(week.id)}>
                Remove Week
              </button>
            </div>
          </div>

          {days.map(({ day, exercises }) => (
            <div className="builder-day" key={day.id}>
              <div className="builder-day-title">
                <span>{day.label}</span>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn btn-ghost btn-sm" onClick={() => openAddExercise(day.id)}>
                    + Add Exercise
                  </button>
                  <button className="icon-btn" onClick={() => deleteDay(day.id)}>
                    Remove Day
                  </button>
                </div>
              </div>

              {exercises.length === 0 && <p className="muted">No exercises yet.</p>}

              {exercises.map((ex) => (
                <div className="exercise-row" key={ex.id}>
                  <div className="ex-name">{ex.name}</div>
                  <div className="ex-meta">
                    {ex.prescribedSets} × {ex.prescribedReps ?? "—"}
                  </div>
                  <div className="ex-meta">{ex.prescriptionNote}</div>
                  <div className="ex-meta">{ex.restNote}</div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => openEditExercise(day.id, ex)}>
                      Edit
                    </button>
                    <button className="icon-btn" onClick={() => deleteExercise(ex.id)}>
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      ))}

      <button className="btn btn-ghost" onClick={() => addWeek(programId)}>
        + Add Week
      </button>

      <hr className="rune-divider" />
      <p className="muted" style={{ maxWidth: 640 }}>
        Assigning a program places its days onto each athlete's scheduler starting from a chosen date. Every
        assignee gets an independent progress copy — logging a set never affects another athlete's copy of the
        same program.
      </p>

      {addingDayToWeek && (
        <Modal title="Add Day" onClose={() => setAddingDayToWeek(null)}>
          <div className="field">
            <label>Day Label</label>
            <input value={dayLabel} onChange={(e) => setDayLabel(e.target.value)} placeholder="e.g. Lower Power" autoFocus />
          </div>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={() => setAddingDayToWeek(null)}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={handleAddDay}>
              Add Day
            </button>
          </div>
        </Modal>
      )}

      {exerciseModal && (
        <Modal title={exerciseModal.editingId ? "Edit Exercise" : "Add Exercise"} onClose={() => setExerciseModal(null)}>
          <div className="field">
            <label>Exercise Name</label>
            <input
              value={exerciseForm.name}
              onChange={(e) => setExerciseForm({ ...exerciseForm, name: e.target.value })}
              placeholder="e.g. Back Squat"
              autoFocus
            />
          </div>
          <div className="field">
            <label>Volume Track</label>
            <select
              value={exerciseForm.track}
              onChange={(e) => setExerciseForm({ ...exerciseForm, track: e.target.value as VolumeTrack })}
            >
              {TRACK_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field-row">
            <div className="field">
              <label>Sets</label>
              <input
                type="number"
                value={exerciseForm.prescribedSets}
                onChange={(e) => setExerciseForm({ ...exerciseForm, prescribedSets: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label>Reps</label>
              <input
                type="number"
                value={exerciseForm.prescribedReps ?? ""}
                onChange={(e) =>
                  setExerciseForm({ ...exerciseForm, prescribedReps: e.target.value ? Number(e.target.value) : null })
                }
              />
            </div>
            <div className="field">
              <label>Rest</label>
              <input
                value={exerciseForm.restNote}
                onChange={(e) => setExerciseForm({ ...exerciseForm, restNote: e.target.value })}
                placeholder="Rest 2:00"
              />
            </div>
          </div>
          <div className="field">
            <label>Prescription Note</label>
            <input
              value={exerciseForm.prescriptionNote}
              onChange={(e) => setExerciseForm({ ...exerciseForm, prescriptionNote: e.target.value })}
              placeholder="e.g. 78% 1RM or RPE 7"
            />
          </div>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={() => setExerciseModal(null)}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={saveExercise}>
              Save
            </button>
          </div>
        </Modal>
      )}

      {assigning && (
        <Modal title="Assign to Athletes" onClose={() => setAssigning(false)}>
          <div className="field">
            <label>Start Date (Week 1 / Day 1)</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </div>
          <div className="field">
            <label>Athletes</label>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {athletes.map((a) => (
                <label key={a.id} style={{ display: "flex", alignItems: "center", gap: 8, textTransform: "none", letterSpacing: 0, color: "var(--text-primary)", fontSize: "0.85rem" }}>
                  <input type="checkbox" style={{ width: "auto" }} checked={selectedAthletes.has(a.id)} onChange={() => toggleAthlete(a.id)} />
                  {a.name}
                </label>
              ))}
            </div>
          </div>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={() => setAssigning(false)}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={submitAssignment} disabled={selectedAthletes.size === 0}>
              Assign
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
