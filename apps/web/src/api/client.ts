import { parseApiError } from "./errors";

const TOKEN_KEY = "shendu_token";

export {
  ApiError,
  formatApiErrorMessage,
  formatUserFacingError,
  getApiErrorCode,
  showApiError,
} from "./errors";

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

/** 带登录态下载文件（勿用 `<a href="/api/...">` 新开标签，会丢 Authorization） */
export async function apiDownload(path: string, filename: string): Promise<void> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`/api${path}`, { headers });
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
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
