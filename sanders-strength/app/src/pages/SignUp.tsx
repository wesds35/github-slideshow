import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";
import logo from "../assets/logo.svg";

export function SignUp() {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [checkEmail, setCheckEmail] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { full_name: fullName } },
    });
    setSubmitting(false);
    if (error) {
      setError(error.message);
      return;
    }
    if (data.session) {
      // Email confirmation is off for this project — we're signed in immediately.
      navigate("/");
    } else {
      // Email confirmation is on — no session yet until they click the link in their inbox.
      setCheckEmail(true);
    }
  };

  if (checkEmail) {
    return (
      <div className="splash">
        <img className="logo-mark" src={logo} alt="Sanders Strength shield mark" />
        <div className="card" style={{ width: 340, textAlign: "center" }}>
          <h3>Check Your Email</h3>
          <p className="muted">
            We sent a confirmation link to <strong style={{ color: "var(--text-primary)" }}>{email}</strong>. Click
            it, then come back and log in.
          </p>
          <Link className="btn btn-ghost" to="/login" style={{ marginTop: 10, display: "inline-block" }}>
            Back to Log In
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="splash">
      <img className="logo-mark" src={logo} alt="Sanders Strength shield mark" />
      <div>
        <div className="wordmark">SANDERS STRENGTH</div>
        <div className="tagline">ᛊ Forge The Work ᛊ</div>
      </div>

      <form className="card" style={{ width: 320, textAlign: "left" }} onSubmit={submit}>
        <h3>Create Your Account</h3>
        <div className="field">
          <label>Full Name</label>
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} required autoFocus />
        </div>
        <div className="field">
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <p className="muted" style={{ fontSize: ".72rem", marginTop: 4 }}>
            Use the exact email your coach added you with.
          </p>
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={6} required />
        </div>
        {error && (
          <p className="muted" style={{ color: "var(--red-bright)" }}>
            {error}
          </p>
        )}
        <button className="btn btn-primary" type="submit" disabled={submitting} style={{ width: "100%" }}>
          {submitting ? "Creating account…" : "Create Account"}
        </button>
      </form>

      <p className="footer-note">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </div>
  );
}
