import { Navigate, useParams } from "react-router-dom";

/** 旧链接兼容：/grading/jobs/:id → 批改页内常驻进度区 */
export default function GradingProgressPage() {
  const { jobId } = useParams();
  if (!jobId) return <Navigate to="/grading" replace />;
  return <Navigate to={`/grading?job=${encodeURIComponent(jobId)}`} replace />;
}
