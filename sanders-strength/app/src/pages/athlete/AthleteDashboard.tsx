import { useAuth } from "../../context/auth";
import { AthleteDashboardView } from "../AthleteDashboardView";

export function AthleteDashboard() {
  const { athlete } = useAuth();
  if (!athlete) return null;
  return <AthleteDashboardView athleteId={athlete.id} badgesPath="/athlete/badges" />;
}
