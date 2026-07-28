import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Role = "coach" | "athlete";

interface IdentityState {
  role: Role | null;
  athleteId: string | null;
}

interface IdentityContextValue extends IdentityState {
  setCoach: () => void;
  setAthlete: (athleteId: string) => void;
  clear: () => void;
}

const STORAGE_KEY = "sanders-strength:identity";

const IdentityContext = createContext<IdentityContextValue | null>(null);

function readStored(): IdentityState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { role: null, athleteId: null };
    return JSON.parse(raw) as IdentityState;
  } catch {
    return { role: null, athleteId: null };
  }
}

export function IdentityProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<IdentityState>(() => readStored());

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const value = useMemo<IdentityContextValue>(
    () => ({
      ...state,
      setCoach: () => setState({ role: "coach", athleteId: null }),
      setAthlete: (athleteId: string) => setState({ role: "athlete", athleteId }),
      clear: () => setState({ role: null, athleteId: null }),
    }),
    [state],
  );

  return <IdentityContext.Provider value={value}>{children}</IdentityContext.Provider>;
}

export function useIdentity(): IdentityContextValue {
  const ctx = useContext(IdentityContext);
  if (!ctx) throw new Error("useIdentity must be used within IdentityProvider");
  return ctx;
}
