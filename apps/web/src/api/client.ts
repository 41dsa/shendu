import { parseApiError } from "./errors";

const TOKEN_KEY = "shendu_token";

export { ApiError, getApiErrorCode, showApiError } from "./errors";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function logout() {
  setToken(null);
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`/api${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    const detailStr = typeof detail === "string" ? detail : JSON.stringify(detail);
    throw parseApiError(res.status, detailStr);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
