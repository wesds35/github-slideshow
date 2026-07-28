import { NavLink } from "react-router-dom";
import logo from "../assets/logo.svg";
import { useAuth } from "../context/auth";

const navClass = ({ isActive }: { isActive: boolean }) => "nav-link" + (isActive ? " active" : "");

export function Sidebar({ role }: { role: "coach" | "athlete" }) {
  const { signOut } = useAuth();

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
        <a className="nav-link" onClick={() => signOut()}><span className="dot" /> Log Out</a>
      </nav>

      <div className="sidebar-footer">Private by design — your data is walled off at the database. v1.0</div>
    </aside>
  );
}
