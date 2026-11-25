/**
 * workspace/utils/documentParserUser.js
 * ------------------------------------------------------------
 * Helper for reading which NexaFlow user is currently logged in.
 *
 * HISTORY: This used to also POST that id to a
 * `/document/set-user-id` endpoint so the Document Parser backend
 * could remember "the current user" in a process-global variable.
 * That endpoint no longer exists -- it was a real cross-user data
 * leak under concurrency (see app/core/global_state.py on the
 * backend) and has been replaced with proper per-request scoping:
 * every Document Parser request now carries the user's signed JWT in
 * an Authorization header (see workspace/config/api.js's authFetch),
 * and the backend derives the user id from that token itself rather
 * than trusting a value the client could set for anyone. Calling the
 * old endpoint here was a silent no-op (404, caught and ignored) --
 * this file now only reads the id for display/UI purposes.
 *
 * The NexaFlow user id is an integer stored in the `nexaflow_auth`
 * sessionStorage entry (see src/services/authService.js).
 * ------------------------------------------------------------
 */
const AUTH_STORAGE_KEY = "nexaflow_auth";

/** Read the currently logged-in NexaFlow user id from sessionStorage. */
export function getNexaflowUserId() {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const id = parsed?.user?.id;
    if (id === undefined || id === null || id === "") return null;
    return Number(id);
  } catch {
    return null;
  }
}
