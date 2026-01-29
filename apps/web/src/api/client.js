import { useAuthStore } from "../store/auth";

function buildHeaders(options) {
  const token = useAuthStore.getState().token;

  const headers = { ...(options.headers || {}) };

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }

  if (token) headers.Authorization = `Bearer ${token}`;

  return headers;
}

async function request(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: buildHeaders(options),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Request failed: ${res.status}`);
  }

  if (res.status === 204) return null;

  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) return null;

  return res.json();
}

// Core API (service 1)
export function apiFetch(path, options) {
  return request(`/api${path}`, options);
}

// Chat API (service 2)
export function chatFetch(path, options) {
  return request(`/chat-api${path}`, options);
}
