import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ADMIN_BLOCKED_LEARNER_PATHS } from "../config/sidebarMenu";
import { api } from "../api/client";

/** 管理员误开购买/激活/考试目标时重定向到教研后台 */
export default function AdminLearnerGuard() {
  const location = useLocation();
  const { data } = useQuery({
    queryKey: ["me"],
    queryFn: () => api<{ role: string }>("/auth/me"),
  });

  if (
    data?.role === "admin" &&
    ADMIN_BLOCKED_LEARNER_PATHS.some((p) => location.pathname === p || location.pathname.startsWith(`${p}/`))
  ) {
    return <Navigate to="/admin" replace />;
  }
  return <Outlet />;
}
