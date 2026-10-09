import { Spin } from "antd";
import { Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import HomePage from "../pages/HomePage";
import { api } from "../api/client";

/** 管理员访问 / 时进教研后台；普通用户进首页 */
export default function RoleHomeRedirect() {
  const { data, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: () => api<{ role: string }>("/auth/me"),
  });
  if (isLoading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 48 }}>
        <Spin size="large" tip="加载中…" />
      </div>
    );
  }
  if (data?.role === "admin") return <Navigate to="/admin" replace />;
  return <HomePage />;
}
