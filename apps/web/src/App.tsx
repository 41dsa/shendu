import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import RequireAuth from "./routes/RequireAuth";
import AdminCodesPage from "./pages/AdminCodesPage";
import ActivatePage from "./pages/ActivatePage";
import GradingPage from "./pages/GradingPage";
import GradingProgressPage from "./pages/GradingProgressPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import PurchasePage from "./pages/PurchasePage";
import RegisterPage from "./pages/RegisterPage";
import ReportListPage from "./pages/ReportListPage";
import ReportPage from "./pages/ReportPage";
import RetryAnswerPage from "./pages/RetryAnswerPage";
import AbilitiesPage from "./pages/AbilitiesPage";
import IssueBookPage from "./pages/IssueBookPage";
import SettingsAiPage from "./pages/SettingsAiPage";
import ExamProfilePage from "./pages/ExamProfilePage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/purchase" element={<PurchasePage />} />
            <Route path="/activate" element={<ActivatePage />} />
            <Route path="/settings/ai" element={<SettingsAiPage />} />
            <Route path="/settings/exam" element={<ExamProfilePage />} />
            <Route path="/grading" element={<GradingPage />} />
            <Route path="/grading/jobs/:jobId" element={<GradingProgressPage />} />
            <Route path="/reports" element={<ReportListPage />} />
            <Route path="/reports/:reportId" element={<ReportPage />} />
            <Route path="/reports/:reportId/retry" element={<RetryAnswerPage />} />
            <Route path="/abilities" element={<AbilitiesPage />} />
            <Route path="/issues" element={<IssueBookPage />} />
            <Route path="/admin/codes" element={<AdminCodesPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
