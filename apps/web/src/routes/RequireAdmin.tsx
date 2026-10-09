import { Navigate, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export default function RequireAdmin() {
  const { data, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: () => api<{ role: string }>("/auth/me"),
  });
  if (isLoading) return null;
  if (data?.role !== "admin") return <Navigate to="/" replace />;
  return <Outlet />;
}
