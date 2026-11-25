import { useEffect, useRef } from "react";
import { API_BASE_URL } from "../config/api";
import { getNexaflowToken } from "./documentParserUser";

function toWsUrl(httpUrl) {
  return httpUrl.replace(/^http/, "ws");
}

/**
 * useJobUpdates({ modelId = "*", onEvent })
 * ------------------------------------------------------------
 * Opens a single, authorized, per-user WebSocket to the Document Parser
 * "/document/ws/history" channel and forwards live job-lifecycle events to
 * `onEvent`. It auto-reconnects (with a short backoff) after an unexpected
 * close and cleans up on unmount.
 *
 * Received events look like:
 *   { event: "job_created"|"job_updated"|"job_failed"|"page_updated",
 *     model_id, job_id, status, ... }
 *
 * The backend authenticates via the `token` query parameter (browsers can't
 * set an Authorization header on the WS handshake) and — because the token's
 * user id is used to scope the channel — only delivers events for THIS
 * user's jobs, so other users' data is never leaked over the socket.
 */
export function useJobUpdates({ modelId = "*", onEvent } = {}) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    const token = getNexaflowToken();
    if (!token) return undefined; // not logged in - nothing to stream

    let socket = null;
    let closedByUs = false;
    let retryTimer = null;

    const connect = () => {
      const params = new URLSearchParams({ model_id: modelId, token });
      const wsBase = toWsUrl(API_BASE_URL || window.location.origin);
      socket = new WebSocket(`${wsBase}/document/ws/history?${params.toString()}`);

      socket.onmessage = (event) => {
        try {
          onEventRef.current?.(JSON.parse(event.data));
        } catch {
          /* ignore malformed frames */
        }
      };

      socket.onclose = () => {
        socket = null;
        if (closedByUs) return;
        retryTimer = setTimeout(connect, 3000);
      };

      // onerror is followed by onclose, which handles reconnection.
      socket.onerror = () => {};
    };

    connect();

    return () => {
      closedByUs = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (socket) {
        try {
          socket.close();
        } catch {
          /* ignore */
        }
      }
    };
  }, [modelId]);
}
