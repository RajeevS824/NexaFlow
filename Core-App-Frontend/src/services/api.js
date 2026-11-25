/**
 * src/services/api.js
 * ------------------------------------------------------------
 * Centralized API base URL and request helper for the NexaFlow
 * frontend.
 *
 * Reads VITE_MAIN_API_BASE_URL (set in the shared project-root .env)
 * to the backend's real public URL, e.g.:
 *   VITE_MAIN_API_BASE_URL=https://api.yourdomain.com
 * A separate VITE_DOCUMENT_PARSER_API_BASE_URL name is used for the
 * Document Parser backend (see src/workspace/config/api.js) -- Vite
 * only lets a build see one value per name, so sharing a single name
 * between the two backends would silently break whichever one you
 * didn't mean to point at your deployed URL.
 */
function resolveBaseUrl(raw, fallback = "") {
  if (!raw) return fallback;
  if (
    typeof window !== "undefined" &&
    /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/i.test(raw)
  ) {
    const isLocalHost =
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1";
    if (!isLocalHost || window.location.port === "3000") {
      return fallback;
    }
  }
  return raw;
}

export const API_BASE_URL = resolveBaseUrl(import.meta.env.VITE_MAIN_API_BASE_URL, "");
/**
 * Generic fetch wrapper that attaches the Authorization header
 * when a token is provided, and returns parsed JSON or throws
 * a descriptive Error on non-2xx responses.
 */
export async function apiFetch(path, options = {}) {
  const token = typeof window !== "undefined" ? sessionStorage.getItem("nexaflow_token") : null;

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  const isJSON = response.headers.get("content-type")?.includes("application/json");

  if (!response.ok) {
    const body = isJSON ? await response.json().catch(() => ({})) : {};
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }

  return isJSON ? response.json() : response.text();
}