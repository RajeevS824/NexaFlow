// Centralized API base URL for the Document Parser backend.
//
// Previously "http://127.0.0.1:8000" was hardcoded in five separate
// places inside ProcessDocument.jsx. That only works when the
// frontend is opened on the same machine the backend happens to be
// running on -- once this is hosted in the cloud (frontend served
// from one domain, backend API on another), every one of those calls
// would silently try to hit the developer's own laptop.
//
// The shared project-root .env defines TWO separate Vite variable
// names on purpose -- VITE_MAIN_API_BASE_URL for the NexaFlow backend
// (see src/services/api.js) and VITE_DOCUMENT_PARSER_API_BASE_URL for
// this, the Document Parser backend -- since Vite bakes one value per
// name into the build and a single shared name would silently point
// one of the two services at the wrong backend. This used to read a
// third name, VITE_API_BASE_URL, that the shared .env never set, so
// it always fell back to the localhost default even in production.
export const API_BASE_URL =
  import.meta.env.VITE_DOCUMENT_PARSER_API_BASE_URL || "http://127.0.0.1:8000";

const AUTH_STORAGE_KEY = "nexaflow_auth";

/** Read the current NexaFlow JWT (issued at login) from sessionStorage. */
function getAuthToken() {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.token || null;
  } catch {
    return null;
  }
}

/**
 * Drop-in replacement for `fetch()` that also attaches the logged-in
 * user's Bearer token. The Document Parser backend requires this
 * token on every /document/* route (see app/api/dependencies.py) and
 * uses it -- not anything the client claims -- to decide whose models,
 * history, and settings a request can see. Every call in this app to
 * the Document Parser backend should go through this instead of the
 * raw `fetch`, or it will simply get a 401.
 *
 * Behaves exactly like `fetch()` otherwise: still returns a Response,
 * still needs `.ok`/`.json()` handled by the caller, still accepts
 * FormData bodies untouched (this only ever adds an Authorization
 * header, never a Content-Type, so multipart uploads keep working).
 */
export async function authFetch(input, init = {}) {
  const token = getAuthToken();
  const headers = new Headers(init.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(input, { ...init, headers });
}

/**
 * Build an authenticated URL for resources that can't send headers
 * (e.g. `<img src>`, `<a href>` downloads) by appending the token as
 * a `?token=` query parameter instead. The backend's /output route
 * accepts either form -- see app/main.py.
 */
export function withAuthToken(url) {
  const token = getAuthToken();
  if (!token) return url;
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}token=${encodeURIComponent(token)}`;
}
