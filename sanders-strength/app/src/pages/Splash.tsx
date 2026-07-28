import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useLiveQuery } from "dexie-react-hooks";
import { db } from "../db";
import { useIdentity } from "../context/identity";
import logo from "../assets/logo.svg";

export function Splash() {
  const navigate = useNavigate();
  const { setCoach, setAthlete } = useIdentity();
  const [pickingAthlete, setPickingAthlete] = useState(false);
  const athletes = useLiveQuery(() => db.athletes.orderBy("name").toArray(), []);

  const chooseCoach = () => {
    setCoach();
    navigate("/coach/dashboard");
  };

  const chooseAthlete = (athleteId: string) => {
    setAthlete(athleteId);
    navigate("/athlete/dashboard");
  };

  return (
    <div className="splash">
      <img className="logo-mark" src={logo} alt="Sanders Strength shield mark" />
      <div>
        <div className="wordmark">SANDERS STRENGTH</div>
        <div className="tagline">ᛊ Forge The Work ᛊ</div>
      </div>

      {!pickingAthlete ? (
        <div className="role-select">
          <div className="role-card" onClick={chooseCoach}>
            <div className="role-icon">⚒</div>
            <h4>I'm a Coach</h4>
            <p>Build programs, manage your roster, track team volume.</p>
          </div>
          <div className="role-card" onClick={() => setPickingAthlete(true)}>
            <div className="role-icon">🛡</div>
            <h4>I'm an Athlete</h4>
            <p>Log your lifts, chase PRs, earn your badges.</p>
          </div>
        </div>
      ) : (
        <div className="card" style={{ width: 320, textAlign: "left" }}>
          <h3>Who are you?</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {(athletes ?? []).map((a) => (
              <button key={a.id} className="btn btn-ghost" onClick={() => chooseAthlete(a.id)}>
                {a.name}
              </button>
            ))}
            {athletes && athletes.length === 0 && (
              <p className="muted">No athletes yet — sign in as a coach to add your roster.</p>
            )}
          </div>
          <button className="btn btn-ghost btn-sm" style={{ marginTop: 12 }} onClick={() => setPickingAthlete(false)}>
            ← Back
          </button>
        </div>
      )}

      <p className="footer-note">
        Your training data stays between you and your coach — nothing here is shared publicly or sold to anyone.
      </p>
    </div>
  );
}
