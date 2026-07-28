import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/auth";
import { Gate } from "./pages/Gate";
import { Login } from "./pages/Login";
import { SignUp } from "./pages/SignUp";
import { CoachShell, AthleteShell } from "./components/AppShell";
import { CoachDashboard } from "./pages/coach/CoachDashboard";
import { ProgramList } from "./pages/coach/ProgramList";
import { ProgramDetail } from "./pages/coach/ProgramDetail";
import { CoachScheduler } from "./pages/coach/CoachScheduler";
import { BadgeCatalog } from "./pages/coach/BadgeCatalog";
import { AthleteDetail } from "./pages/coach/AthleteDetail";
import { AthleteDashboard } from "./pages/athlete/AthleteDashboard";
import { AthleteSchedule } from "./pages/athlete/AthleteSchedule";
import { LogWorkout } from "./pages/athlete/LogWorkout";
import { AthleteBadges } from "./pages/athlete/AthleteBadges";

function App() {
  return (
    <AuthProvider>
      <HashRouter>
        <Routes>
          <Route path="/" element={<Gate />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<SignUp />} />

          <Route path="/coach" element={<CoachShell />}>
            <Route path="dashboard" element={<CoachDashboard />} />
            <Route path="programs" element={<ProgramList />} />
            <Route path="programs/:programId" element={<ProgramDetail />} />
            <Route path="scheduler" element={<CoachScheduler />} />
            <Route path="badges" element={<BadgeCatalog />} />
            <Route path="athletes/:athleteId" element={<AthleteDetail />} />
            <Route index element={<Navigate to="dashboard" replace />} />
          </Route>

          <Route path="/athlete" element={<AthleteShell />}>
            <Route path="dashboard" element={<AthleteDashboard />} />
            <Route path="schedule" element={<AthleteSchedule />} />
            <Route path="log/:sessionId" element={<LogWorkout />} />
            <Route path="badges" element={<AthleteBadges />} />
            <Route index element={<Navigate to="dashboard" replace />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </HashRouter>
    </AuthProvider>
  );
}

export default App;
