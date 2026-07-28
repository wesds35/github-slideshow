import { Navigate } from "react-router-dom";
import { useAuth } from "../context/auth";
import { Login } from "./Login";
import logo from "../assets/logo.svg";

/** Root route: sends a signed-in user to the right dashboard, or shows the login form. */
export function Gate() {
  const { loading, session, role, athlete, unclaimed, signOut } = useAuth();

  if (loading) return null;
  if (!session) return <Login />;

  if (role === "coach") return <Navigate to="/coach/dashboard" replace />;
  if (athlete) return <Navigate to="/athlete/dashboard" replace />;

  if (unclaimed) {
    return (
      <div className="splash">
        <img className="logo-mark" src={logo} alt="Sanders Strength shield mark" />
        <div className="card" style={{ width: 360, textAlign: "center" }}>
          <h3>Not on a Roster Yet</h3>
          <p className="muted">
            We couldn't find an athlete invite matching your email. Ask your coach to add you first, then log back
            in here.
          </p>
          <button className="btn btn-ghost" style={{ marginTop: 10 }} onClick={() => signOut()}>
            Log Out
          </button>
        </div>
      </div>
    );
  }

  return null;
}
