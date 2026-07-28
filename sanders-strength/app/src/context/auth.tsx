import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../lib/supabaseClient";
import type { Role } from "../lib/database.types";

interface AthleteRecord {
  id: string;
  name: string;
  initials: string;
  email: string;
}

interface AuthState {
  loading: boolean;
  session: Session | null;
  role: Role | null;
  fullName: string | null;
  /** The linked athletes row for this user, once claimed. Null while loading or if this account
   *  has no matching coach-created invite yet (role is still 'athlete' either way). */
  athlete: AthleteRecord | null;
  /** True once we've finished trying to claim an invite and still found no matching athlete row —
   *  distinct from `loading`/`athlete === null` mid-check, so the UI can show the right message. */
  unclaimed: boolean;
}

interface AuthContextValue extends AuthState {
  signOut: () => Promise<void>;
  refreshAthlete: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const initialState: AuthState = {
  loading: true,
  session: null,
  role: null,
  fullName: null,
  athlete: null,
  unclaimed: false,
};

/** Loads (and, if unclaimed, attempts to claim) this user's role + athlete record. */
async function loadProfileAndAthlete(session: Session): Promise<Omit<AuthState, "loading" | "session">> {
  const { data: profile } = await supabase
    .from("profiles")
    .select("role, full_name")
    .eq("id", session.user.id)
    .maybeSingle();

  const role = profile?.role ?? "athlete";
  const fullName = profile?.full_name ?? null;

  if (role === "coach") {
    return { role, fullName, athlete: null, unclaimed: false };
  }

  let { data: athlete } = await supabase
    .from("athletes")
    .select("id, name, initials, email")
    .eq("user_id", session.user.id)
    .maybeSingle();

  if (!athlete && session.user.email) {
    // First login after signup: claim the coach-created invite row that matches our own email.
    await supabase
      .from("athletes")
      .update({ user_id: session.user.id })
      .eq("email", session.user.email)
      .is("user_id", null);

    const retry = await supabase
      .from("athletes")
      .select("id, name, initials, email")
      .eq("user_id", session.user.id)
      .maybeSingle();
    athlete = retry.data;
  }

  return { role, fullName, athlete: athlete ?? null, unclaimed: !athlete };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(initialState);

  const applySession = async (session: Session | null) => {
    if (!session) {
      setState({ ...initialState, loading: false });
      return;
    }
    const rest = await loadProfileAndAthlete(session);
    setState({ loading: false, session, ...rest });
  };

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => applySession(data.session));

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      applySession(session);
    });

    return () => subscription.subscription.unsubscribe();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      signOut: async () => {
        await supabase.auth.signOut();
      },
      refreshAthlete: async () => {
        if (state.session) await applySession(state.session);
      },
    }),
    [state],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
