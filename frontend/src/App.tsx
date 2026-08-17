import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, RequireAuth, RequirePerm } from "./auth";
import { Shell } from "./layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Organizations from "./pages/Organizations";
import Nodes from "./pages/Nodes";
import Datasets from "./pages/Datasets";
import Training from "./pages/Training";
import TrainingDetail from "./pages/TrainingDetail";
import Coordinator from "./pages/Coordinator";
import Aggregation from "./pages/Aggregation";
import Models from "./pages/Models";
import Evaluation from "./pages/Evaluation";
import Explainability from "./pages/Explainability";
import Monitor from "./pages/Monitor";
import Analytics from "./pages/Analytics";
import Reports from "./pages/Reports";
import Audit from "./pages/Audit";
import Assistant from "./pages/Assistant";
import AI from "./pages/AI";
import Admin from "./pages/Admin";
import SettingsPage from "./pages/SettingsPage";
import Trainer from "./pages/Trainer";
import Lab from "./pages/Lab";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <Shell />
            </RequireAuth>
          }
        >
          <Route path="/" element={<Dashboard />} />
          <Route path="/trainer" element={<Trainer />} />
          <Route path="/organizations" element={<Organizations />} />
          <Route path="/nodes" element={<Nodes />} />
          <Route path="/datasets" element={<Datasets />} />
          <Route path="/monitor" element={<Monitor />} />
          <Route path="/training" element={<Training />} />
          <Route path="/training/:id" element={<TrainingDetail />} />
          <Route path="/coordinator" element={<Coordinator />} />
          <Route path="/aggregation" element={<Aggregation />} />
          <Route path="/models" element={<Models />} />
          <Route path="/evaluation" element={<Evaluation />} />
          <Route path="/explainability" element={<Explainability />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/audit" element={<Audit />} />
          <Route path="/assistant" element={<Assistant />} />
          <Route path="/ai" element={<AI />} />
          <Route path="/lab" element={<Lab />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
