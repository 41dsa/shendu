import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import RequireAuth from "./routes/RequireAuth";
import AdminCodesPage from "./pages/AdminCodesPage";
import AdminLayout from "./layouts/AdminLayout";
import RequireAdmin from "./routes/RequireAdmin";
import AdminHomePage from "./pages/admin/AdminHomePage";
import AdminQuestionsPage from "./pages/admin/AdminQuestionsPage";
import AdminPromptsPage from "./pages/admin/AdminPromptsPage";
import AdminGoldPage from "./pages/admin/AdminGoldPage";
import AdminDisputesPage from "./pages/admin/AdminDisputesPage";
import AdminJobsPage from "./pages/admin/AdminJobsPage";
import AdminEventsPage from "./pages/admin/AdminEventsPage";
import AdminStandardsPage from "./pages/admin/AdminStandardsPage";
import AdminAnchorEssaysPage from "./pages/admin/AdminAnchorEssaysPage";
import AdminAnchorAnnotationPage from "./pages/admin/AdminAnchorAnnotationPage";
import AdminActiveLearningPage from "./pages/admin/AdminActiveLearningPage";
import ActivatePage from "./pages/ActivatePage";
import GradingPage from "./pages/GradingPage";
import GradingProgressPage from "./pages/GradingProgressPage";
import RoleHomeRedirect from "./routes/RoleHomeRedirect";
import AdminLearnerGuard from "./routes/AdminLearnerGuard";
import RequireLicense from "./routes/RequireLicense";
import LoginPage from "./pages/LoginPage";
import PurchasePage from "./pages/PurchasePage";
import RegisterPage from "./pages/RegisterPage";
import ReportListPage from "./pages/ReportListPage";
import ReportPage from "./pages/ReportPage";
import RetryAnswerPage from "./pages/RetryAnswerPage";
import AbilitiesPage from "./pages/AbilitiesPage";
import IssueBookPage from "./pages/IssueBookPage";
import MePage from "./pages/MePage";
import SettingsAiPage from "./pages/SettingsAiPage";
import ExamProfilePage from "./pages/ExamProfilePage";

export default function App() {
  return (
    <BrowserRouter basename="/shendu">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<AdminLearnerGuard />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<RoleHomeRedirect />} />
              <Route path="/purchase" element={<PurchasePage />} />
              <Route path="/activate" element={<ActivatePage />} />
              <Route path="/settings/ai" element={<SettingsAiPage />} />
              <Route path="/grading" element={<GradingPage />} />
              <Route element={<RequireLicense />}>
                <Route path="/settings/exam" element={<ExamProfilePage />} />
                <Route path="/grading/jobs/:jobId" element={<GradingProgressPage />} />
                <Route path="/reports" element={<ReportListPage />} />
                <Route path="/reports/:reportId" element={<ReportPage />} />
                <Route path="/reports/:reportId/retry" element={<RetryAnswerPage />} />
                <Route path="/abilities" element={<AbilitiesPage />} />
                <Route path="/issues" element={<IssueBookPage />} />
                <Route path="/me" element={<MePage />} />
              </Route>
            </Route>
          </Route>
          <Route element={<RequireAdmin />}>
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<AdminHomePage />} />
              <Route path="questions" element={<AdminQuestionsPage />} />
              <Route path="prompts" element={<AdminPromptsPage />} />
              <Route path="gold" element={<AdminGoldPage />} />
              <Route path="disputes" element={<AdminDisputesPage />} />
              <Route path="jobs" element={<AdminJobsPage />} />
              <Route path="codes" element={<AdminCodesPage />} />
              <Route path="events" element={<AdminEventsPage />} />
              <Route path="standards" element={<AdminStandardsPage />} />
              <Route path="anchors" element={<AdminAnchorEssaysPage />} />
              <Route path="anchor-annotation" element={<AdminAnchorAnnotationPage />} />
              <Route path="active-learning" element={<AdminActiveLearningPage />} />
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
