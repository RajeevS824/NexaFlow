/**
 * workspace/utils/childWindows.js
 * ------------------------------------------------------------
 * Tracks browser tabs/windows this app opened with window.open()
 * (currently just the Document Parser "Process" tab -- see
 * ProcessExtractionModel.jsx's handleProcess).
 *
 * WHY THIS EXISTS: a tab opened with window.open() gets its own
 * independent copy of sessionStorage at the moment it's created.
 * After that, the two tabs are NOT connected -- clearing the
 * opener tab's sessionStorage on logout does not touch the child
 * tab's copy, so the child tab would otherwise keep behaving as if
 * still signed in (e.g. a document still "processing") even after
 * the user logged out elsewhere. Registering the window reference
 * here lets AuthContext's logout() close it directly, alongside
 * the cross-tab BroadcastChannel signal used for tabs it doesn't
 * hold a direct reference to.
 * ------------------------------------------------------------
 */
const openChildWindows = new Set();

/** Call with the return value of window.open() right after opening it. */
export function registerChildWindow(win) {
  if (!win) return;
  openChildWindows.add(win);
}

/** Closes every still-open tracked child window (called on logout). */
export function closeAllChildWindows() {
  for (const win of openChildWindows) {
    try {
      if (!win.closed) win.close();
    } catch {
      // Window may already be gone, or closing was blocked -- nothing
      // more we can do from here, so just move on.
    }
  }
  openChildWindows.clear();
}
