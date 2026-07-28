import { NavLink, useNavigate } from "react-router-dom";
import logo from "../assets/logo.svg";
import { useIdentity } from "../context/identity";

const navClass = ({ isActive }: { isActive: boolean }) => "nav-link" + (isActive ? " active" : "");

export function Sidebar({ role }: { role: "coach" | "athlete" }) {
  const navigate = useNavigate();
  const { clear } = useIdentity();

  const switchRole = () => {
    clear();
    navigate("/");
  };

  return (
    <aside className="sidebar">
      <div className="brand">
        <img src={logo} alt="" />
        <div className="brand-name">
          <b>SANDERS</b>
          <span>STRENGTH</span>
        </div>
      </div>

      {role === "coach" ? (
        <nav className="nav-group">
          <div className="nav-label">Coach</div>
          <NavLink className={navClass} to="/coach/dashboard"><span className="dot" /> Dashboard</NavLink>
          <NavLink className={navClass} to="/coach/programs"><span className="dot" /> Program Builder</NavLink>
          <NavLink className={navClass} to="/coach/scheduler"><span className="dot" /> Scheduler</NavLink>
          <NavLink className={navClass} to="/coach/badges"><span className="dot" /> Badge Catalog</NavLink>
        </nav>
      ) : (
        <nav className="nav-group">
          <div className="nav-label">Athlete</div>
          <NavLink className={navClass} to="/athlete/dashboard"><span className="dot" /> My Dashboard</NavLink>
          <NavLink className={navClass} to="/athlete/schedule"><span className="dot" /> My Schedule</NavLink>
          <NavLink className={navClass} to="/athlete/badges"><span className="dot" /> My Badges</NavLink>
        </nav>
      )}

      <nav className="nav-group">
        <div className="nav-label">Session</div>
        <a className="nav-link" onClick={switchRole}><span className="dot" /> Switch Role / Athlete</a>
      </nav>

      <div className="sidebar-footer">Local-first. Athlete data is never shared or sold. v1.0</div>
    </aside>
  );
}
