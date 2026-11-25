/**
 * utils/errorLogger.js
 * ------------------------------------------------------------
 * Frontend-only error logging.
 *
 * Fresh implementation: keeps errors in an in-memory array
 * (no localStorage / backend persistence).
 * ------------------------------------------------------------
 */

const MAX_ENTRIES = 300;

// In-memory log store.
let log = [];

/** Records one error entry. Safe to call from anywhere (services, contexts, components). */
export function logError(source, error, meta) {
  const entry = {
    timestamp: new Date().toISOString(),
    source: source || "unknown",
    message: error?.message || String(error),
    stack: error?.stack || null,
    meta: meta || null,
  };

  log = [...log, entry].slice(-MAX_ENTRIES);
  // Still surface it in the dev console for local debugging.
  // eslint-disable-next-line no-console
  console.error(`[${entry.source}]`, error, meta || "");
  return entry;
}

export function getErrorLog() {
  return log;
}

export function clearErrorLog() {
  log = [];
}

/** Triggers a browser download of the full log as a plain-text .log file. */
export function downloadErrorLog() {
  const entries = log;
  const contents = entries.length
    ? entries
        .map(
          (e) =>
            `[${e.timestamp}] (${e.source}) ${e.message}` +
            (e.meta ? `\n  meta: ${JSON.stringify(e.meta)}` : "") +
            (e.stack ? `\n  stack: ${e.stack}` : "")
        )
        .join("\n\n")
    : "No errors have been logged yet.";

  const blob = new Blob([contents], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `nexaflow-error-log-${new Date().toISOString().slice(0, 10)}.log`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Wires up global handlers. Call once, at app startup. */
export function initErrorLogging() {
  window.addEventListener("error", (event) => {
    logError("window.onerror", event.error || new Error(event.message), {
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    logError("unhandledrejection", reason instanceof Error ? reason : new Error(String(reason)));
  });
}