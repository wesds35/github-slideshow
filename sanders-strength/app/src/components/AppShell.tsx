import { Navigate, Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { ToastHost } from "./ToastHost";
import { useAuth } from "../context/auth";

export function CoachShell() {
  const { loading, session, role } = useAuth();
  if (loading) return null;
  if (!session || role !== "coach") return <Navigate to="/" replace />;

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
  const { loading, session, role, athlete } = useAuth();
  if (loading) return null;
  if (!session || role !== "athlete" || !athlete) return <Navigate to="/" replace />;

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
