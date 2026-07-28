import { useParams } from "react-router-dom";
import { AthleteDashboardView } from "../AthleteDashboardView";

export function AthleteDetail() {
  const { athleteId } = useParams<{ athleteId: string }>();
  if (!athleteId) return null;
  return <AthleteDashboardView athleteId={athleteId} badgesPath="/coach/badges" />;
}
