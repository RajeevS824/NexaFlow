/**
 * workspace/utils/businessMapLogoutCancel.js
 * ------------------------------------------------------------
 * Used by AuthContext.logout() so that EVERY Logout button in the app
 * (main NexaFlow sidebar, admin sidebar, profile menus, Business Map's own
 * buttons ...) treats a running Business Map job the same way: the job is
 * cancelled first, then the user is logged out.
 *
 * The browser remembers the ONE active Business Map job in localStorage
 * (see businessMapJobPersistence.js), and localStorage is shared by every
 * tab, so this also works when the job runs in the Business Map tab and the
 * Logout is pressed in another tab. If no job is remembered, nothing is
 * called and logout stays instant (exactly as before).
 *
 * The backend POST /cancel-active only touches the logged-in user's own
 * active jobs. Errors and time-outs never block the logout.
 * ------------------------------------------------------------
 */
import { cancelActiveJobs } from "../config/businessMapApi";
import { loadJobState, clearJobState } from "./businessMapJobPersistence";

const CANCEL_TIMEOUT_MS = 35000;

/** True when this browser has a Business Map job that may still be running. */
export function hasActiveBusinessMapJob() {
  try {
    return !!loadJobState();
  } catch {
    return false;
  }
}

/** Cancel the user's active Business Map jobs. Always resolves (never throws). */
export async function cancelBusinessMapJobsBeforeLogout() {
  let timer;
  try {
    await Promise.race([
      cancelActiveJobs(),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("cancel timed out")), CANCEL_TIMEOUT_MS);
      }),
    ]);
  } catch (err) {
    console.warn("Business Map job cancellation failed before logout:", err);
  } finally {
    clearTimeout(timer);
    clearJobState();
  }
}
