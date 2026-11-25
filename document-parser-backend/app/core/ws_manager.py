"""
app/core/ws_manager.py
-----------------------------------------------
Minimal in-memory WebSocket pub/sub for live job-status updates.

Scope, deliberately: this broadcasts coarse job lifecycle events
(queued / processing / completed / failed / page-updated) to any
connected client watching a given extraction model's history. It does
NOT attempt to stream fine-grained progress from inside the OCR
pipeline (app/services/document_service.py) -- that pipeline runs
synchronously in a worker thread via loop.run_in_executor and is large
enough (and untested here against real models/DB) that instrumenting
it deeply was judged too risky to do blind. The event hooks below are
called only from the route layer (app/api/routes/document.py), at
points that already exist and are easy to reason about, which removes
polling for "did this job finish yet" without touching the pipeline
internals.

For a single-process deployment (the current `workers=1` setup in
run.py) an in-memory manager is sufficient. If this is ever scaled to
multiple worker processes, swap this for a real pub/sub backend (e.g.
Redis) so events reach clients connected to a different process.
"""
import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("document_pipeline")


class ConnectionManager:
    def __init__(self) -> None:
        # model_id -> set of connected websockets watching that model's history.
        # "*" is used for clients that didn't specify a model_id (watch everything).
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, model_id: str = "*") -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(model_id, set()).add(websocket)

    async def disconnect(self, websocket: WebSocket, model_id: str = "*") -> None:
        async with self._lock:
            conns = self._connections.get(model_id)
            if conns and websocket in conns:
                conns.discard(websocket)
                if not conns:
                    self._connections.pop(model_id, None)

    async def broadcast(self, model_id: str, message: dict[str, Any]) -> None:
        """Send `message` to every client watching `model_id`, plus every
        client watching "*" (all models)."""
        targets: set[WebSocket] = set()
        async with self._lock:
            targets |= self._connections.get(model_id, set())
            targets |= self._connections.get("*", set())

        stale: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                stale.append(ws)

        if stale:
            async with self._lock:
                for ws in stale:
                    for conns in self._connections.values():
                        conns.discard(ws)


job_events = ConnectionManager()


def broadcast_job_event(model_id: str, event: str, **payload: Any) -> None:
    """Fire-and-forget helper for use inside sync or async route code.

    Schedules the broadcast on the running event loop instead of awaiting
    it directly, so callers in exception/finally blocks don't need to be
    async-aware. Safe to call even if there are no listeners.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # no running loop (e.g. called outside a request) -- skip

    message = {"event": event, "model_id": model_id, **payload}
    loop.create_task(job_events.broadcast(model_id or "*", message))
