import { Navigate, Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { ToastHost } from "./ToastHost";
import { useIdentity } from "../context/identity";

export function CoachShell() {
  const { role } = useIdentity();
  if (role !== "coach") return <Navigate to="/" replace />;

  return (
    <div className="app-shell">
      <Sidebar role="coach" />
      <main className="main">
        <Outlet />
      </main>
      <ToastHost />
    </div>
  );
}

export function AthleteShell() {
  const { role, athleteId } = useIdentity();
  if (role !== "athlete" || !athleteId) return <Navigate to="/" replace />;

  return (
    <div className="app-shell">
      <Sidebar role="athlete" />
      <main className="main">
        <Outlet />
      </main>
      <ToastHost />
    </div>
  );
}
