// ─────────────────────────────────────────────
// jobPersistence.js – tiny localStorage wrapper for the ONE active
// BusinessMap processing job, so a page refresh (or an accidental tab
// close + reopen) can restore the UI and resume polling instead of
// making the user re-upload the video.
//
// Only plain, serializable fields are stored — never the actual File
// object (Files cannot survive a reload), just its name/size for display.
// ─────────────────────────────────────────────

const STORAGE_KEY = "nexaflow_businessmap_active_job";

/**
 * @typedef {Object} PersistedJobState
 * @property {string} jobId
 * @property {string} [jobName]
 * @property {string} [videoFileName]
 * @property {string} [audioFileName]
 * @property {number} progress
 * @property {number} stepIndex
 * @property {string} statusText
 * @property {string} statusType
 * @property {boolean} isRunning
 * @property {boolean} [awaitingAudioConfirmation]
 * @property {string} [noAudioMessage]
 */

/** Save (overwrite) the currently active job's state. */
export function saveJobState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // localStorage may be unavailable (private mode / quota) — degrade
    // gracefully, the app still works, it just won't survive a refresh.
  }
}

/** @returns {PersistedJobState | null} */
export function loadJobState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** Clear the persisted job — call once a job reaches a terminal state. */
export function clearJobState() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}
