import { useIdentity } from "../../context/identity";
import { AthleteDashboardView } from "../AthleteDashboardView";

export function AthleteDashboard() {
  const { athleteId } = useIdentity();
  if (!athleteId) return null;
  return <AthleteDashboardView athleteId={athleteId} badgesPath="/athlete/badges" />;
}
