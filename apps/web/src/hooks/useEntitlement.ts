import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export type Entitlement = {
  licensed: boolean;
  sku: string | null;
  activated_at: string | null;
  has_primary_ai_key: boolean;
};

export function useEntitlement() {
  return useQuery({
    queryKey: ["entitlement"],
    queryFn: () => api<Entitlement>("/auth/me/entitlement"),
  });
}
