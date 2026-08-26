import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "../features/auth/AuthProvider";
import { LoginPage } from "../features/auth/LoginPage";
import { RegisterPage } from "../features/auth/RegisterPage";
import { ProjectListPage } from "../features/projects/ProjectListPage";
import { ProjectPage } from "../features/projects/ProjectPage";
import { RequirementReviewPage } from "../features/requirements/RequirementReviewPage";
import { CompliancePage } from "../features/compliance/CompliancePage";
import { AnalysisSettingsPage } from "../features/settings/AnalysisSettingsPage";

function RequireAuth({ children }: { children: React.ReactElement }): React.ReactElement {
  const { user, isLoading } = useAuth();
  if (isLoading) return <p className="route-loading">세션을 확인하는 중…</p>;
  return user ? children : <Navigate to="/login" replace />;
}

function GuestOnly({ children }: { children: React.ReactElement }): React.ReactElement {
  const { user, isLoading } = useAuth();
  if (isLoading) return <p className="route-loading">세션을 확인하는 중…</p>;
  return user ? <Navigate to="/projects" replace /> : children;
}

export function AppRouter(): React.ReactElement {
  return <Routes>
    <Route path="/login" element={<GuestOnly><LoginPage /></GuestOnly>} />
    <Route path="/register" element={<GuestOnly><RegisterPage /></GuestOnly>} />
    <Route path="/projects" element={<RequireAuth><ProjectListPage /></RequireAuth>} />
    <Route path="/projects/:projectId" element={<RequireAuth><ProjectPage /></RequireAuth>} />
    <Route path="/projects/:projectId/review" element={<RequireAuth><RequirementReviewPage /></RequireAuth>} />
    <Route path="/projects/:projectId/compliance" element={<RequireAuth><CompliancePage /></RequireAuth>} />
    <Route path="/settings" element={<RequireAuth><AnalysisSettingsPage /></RequireAuth>} />
    <Route path="*" element={<Navigate to="/projects" replace />} />
  </Routes>;
}
