import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";
import logo from "../assets/logo.svg";

export function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setSubmitting(false);
    if (error) setError(error.message);
    // On success, AuthProvider's onAuthStateChange picks up the session and the root route
    // redirects to the right dashboard once the role/athlete record resolves.
  };

  return (
    <div className="splash">
      <img className="logo-mark" src={logo} alt="Sanders Strength shield mark" />
      <div>
        <div className="wordmark">SANDERS STRENGTH</div>
        <div className="tagline">ᛊ Forge The Work ᛊ</div>
      </div>

      <form className="card" style={{ width: 320, textAlign: "left" }} onSubmit={submit}>
        <h3>Log In</h3>
        <div className="field">
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {error && (
          <p className="muted" style={{ color: "var(--red-bright)" }}>
            {error}
          </p>
        )}
        <button className="btn btn-primary" type="submit" disabled={submitting} style={{ width: "100%" }}>
          {submitting ? "Logging in…" : "Log In"}
        </button>
      </form>

      <p className="footer-note">
        First time here as an athlete? <Link to="/signup">Create your account</Link> — your coach needs to have
        added you to the roster first.
      </p>
    </div>
  );
}
