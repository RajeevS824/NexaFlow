/**
 * workspace/hooks/useDocumentParserHistorySocket.js
 * ------------------------------------------------------------
 * Live job-status updates for the Document Parser History page,
 * over the backend's /document/ws/history WebSocket (see
 * DP-backend/app/core/ws_manager.py and
 * DP-backend/app/api/routes/document.py's history_live_updates).
 *
 * The backend side of this was already built (auth-checked, scoped
 * per model, broadcasts job created/updated/failed/page-updated
 * events) but nothing in the frontend ever connected to it, so the
 * History page only ever showed a stale snapshot from the moment it
 * loaded. This hook is the missing other half: it opens the socket,
 * authenticates the same way the WS route expects (a `token` query
 * param, since browsers can't attach a custom Authorization header to
 * a WebSocket handshake), and reconnects with backoff if the
 * connection drops -- while leaving what to *do* with each event up
 * to the caller.
 * ------------------------------------------------------------
 */
import { useEffect, useRef } from "react";
import { API_BASE_URL } from "../config/api";

const AUTH_STORAGE_KEY = "nexaflow_auth";

function getAuthToken() {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw)?.token || null;
  } catch {
    return null;
  }
}

const RECONNECT_DELAY_MS = 3000;
const POLICY_VIOLATION_CLOSE_CODE = 4401; // matches websocket.close(code=4401) on the backend
const WebSocketImpl = typeof window !== "undefined" ? window.WebSocket : globalThis.WebSocket;

/**
 * @param {string|null|undefined} modelId - only receive events for this
 *   model's jobs; omit (or pass a falsy value) to watch every model.
 * @param {(message: object) => void} onEvent - called with each decoded
 *   `{event, model_id, job_id, status, ...}` message as it arrives.
 */
export function useDocumentParserHistorySocket(modelId, onEvent) {
  // Keep the latest callback in a ref so the effect below doesn't need
  // to reconnect the socket just because the caller passed a new
  // inline function on re-render.
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    const token = getAuthToken();
    if (!token || !WebSocketImpl) return undefined; // no token or browser websocket support -- nothing to watch

    let socket = null;
    let reconnectTimer = null;
    let cancelled = false;

    const wsUrl =
      (API_BASE_URL || window.location.origin).replace(/^http/i, "ws") +
      `/document/ws/history?model_id=${encodeURIComponent(modelId || "*")}` +
      `&token=${encodeURIComponent(token)}`;

    const connect = () => {
      if (cancelled) return;

      socket = new WebSocketImpl(wsUrl);

      socket.onmessage = (event) => {
        try {
          onEventRef.current?.(JSON.parse(event.data));
        } catch {
          // Ignore malformed/non-JSON frames rather than crash the page.
        }
      };

      socket.onclose = (event) => {
        if (cancelled || event.code === POLICY_VIOLATION_CLOSE_CODE) return;
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      };

      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelId]);
}
