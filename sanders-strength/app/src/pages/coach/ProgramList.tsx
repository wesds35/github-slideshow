import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../../lib/supabaseClient";
import { toProgram, toAssignment } from "../../lib/mappers";
import { useSupabaseData } from "../../lib/useSupabaseData";
import { Topbar } from "../../components/Topbar";
import { Modal } from "../../components/Modal";

export function ProgramList() {
  const navigate = useNavigate();

  const programs = useSupabaseData(async () => {
    const { data, error } = await supabase.from("programs").select().order("created_at", { ascending: false });
    if (error) throw error;
    return (data ?? []).map(toProgram);
  }, []) ?? [];

  const assignments = useSupabaseData(async () => {
    const { data, error } = await supabase.from("assignments").select();
    if (error) throw error;
    return (data ?? []).map(toAssignment);
  }, []) ?? [];

  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [durationWeeks, setDurationWeeks] = useState(8);
  const [tags, setTags] = useState("");

  const assignmentCount = (programId: string) => assignments.filter((a) => a.programId === programId).length;

  const createEmptyProgram = async () => {
    if (!name.trim()) return;
    const { data, error } = await supabase
      .from("programs")
      .insert({ name: name.trim(), duration_weeks: durationWeeks, tags: tags.trim() })
      .select()
      .single();
    if (error) throw error;
    setCreating(false);
    setName("");
    setDurationWeeks(8);
    setTags("");
    navigate(`/coach/programs/${data.id}`);
  };

  return (
    <>
      <Topbar
        eyebrow="Program Builder"
        title="Programs"
        right={
          <button className="btn btn-primary" onClick={() => setCreating(true)}>
            + New Program
          </button>
        }
      />

      {programs.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="rune-big">ᛏ</div>
            No programs yet. Create one to start building weeks and days.
          </div>
        </div>
      ) : (
        <div className="grid grid-3">
          {programs.map((p) => (
            <div className="card" key={p.id} style={{ cursor: "pointer" }} onClick={() => navigate(`/coach/programs/${p.id}`)}>
              <h3 style={{ marginBottom: 8 }}>{p.name}</h3>
              <p className="muted" style={{ margin: 0 }}>
                {p.durationWeeks} weeks · {p.tags || "Untagged"}
              </p>
              <p className="muted" style={{ margin: "6px 0 0" }}>
                {assignmentCount(p.id)} athlete{assignmentCount(p.id) === 1 ? "" : "s"} assigned
              </p>
            </div>
          ))}
        </div>
      )}

      {creating && (
        <Modal title="New Program" onClose={() => setCreating(false)}>
          <div className="field">
            <label>Program Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Off-Season Strength Block" autoFocus />
          </div>
          <div className="field">
            <label>Duration (weeks)</label>
            <input type="number" value={durationWeeks} onChange={(e) => setDurationWeeks(Number(e.target.value))} />
          </div>
          <div className="field">
            <label>Tags</label>
            <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="e.g. Strength" />
          </div>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={() => setCreating(false)}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={createEmptyProgram}>
              Create
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
