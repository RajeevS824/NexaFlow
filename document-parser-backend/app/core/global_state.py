"""
global_state.py -- per-request "current user" storage for the Document
Parser backend.

HISTORY / WHY THIS CHANGED
---------------------------
This used to be a single plain module-level variable, set by a separate
`/document/set-user-id` call from the frontend before every other request.
That is a real cross-user data leak under concurrency: while one user's
document is processing (a long-running operation that awaits, yielding
control back to the event loop), a second concurrent user's request could
overwrite the global, and when the first request resumed it would read
and write data under the SECOND user's id.

FIX
---
`contextvars.ContextVar` is task-local: asyncio gives every incoming
request its own Task, and a ContextVar set inside that Task is invisible
to, and unaffected by, every other concurrently-running Task -- including
across `await` points. This gives the exact same call signature as before
(`get_current_user_id()` / `set_current_user_id()`) so no other file
needs to change, but each request now safely sees only its own user id.

CAUTION -- loop.run_in_executor() does NOT inherit this context:
`asyncio`'s Task/`call_soon`/`call_later` machinery captures the current
context automatically, but a bare `loop.run_in_executor(None, func, ...)`
submits directly to a `concurrent.futures.ThreadPoolExecutor` and does
NOT copy the calling context into that thread -- `get_current_user_id()`
called from inside `func` would look up a context that was never set,
and previously silently returned the `default=1` fallback below (see the
next section for why that default is gone). `asyncio.to_thread(...)`
does copy context correctly and should be used instead of
`loop.run_in_executor()` for any offloaded work that touches
get_current_user_id() (directly, or via a repository call). As of this
fix, this codebase's `loop.run_in_executor(None, run_pipeline, ...)` call
in app/api/routes/document.py does NOT call into any repository code
from inside that thread -- all HistoryRepository/ModelRepository calls
happen before/after the executor call, back on the request's own task --
so it is currently safe, but this is a sharp edge for anyone adding new
offloaded work later.

The value itself is set once per request, from the verified JWT, by the
`require_user` dependency in app.api.dependencies -- not by a separate
`/set-user-id` round trip the client could race or forge.

WHY THERE'S NO DEFAULT ANYMORE
-------------------------------
This used to default to `1` when unset. That is exactly how a real user's
extraction models and processing jobs can silently end up owned by
"user 1" instead of themselves: if get_current_user_id() is ever called
on a code path that -- through a bug, a missing dependency, or a route
added later without `Depends(require_user)` -- runs before
set_current_user_id() has been called for that request, a `1` default
fails *silently* and every row it touches is now mis-attributed. Every
route in this service already goes through `require_user` (see the
router's `dependencies=[...]` in app/api/routes/document.py), so in
correct operation this is always set before any repository code runs.
Raising instead of defaulting turns any future gap into a loud, obvious
500 error at the point of the mistake, instead of quietly leaking data
onto the wrong account.
"""

import contextvars

_current_user_id: contextvars.ContextVar[int] = contextvars.ContextVar(
    "current_user_id"
)


def set_current_user_id(user_id) -> None:
    """Store the current (authenticated) user id for this request/task only."""
    _current_user_id.set(int(user_id))


def get_current_user_id() -> int:
    """Return the current request's authenticated user id.

    Raises RuntimeError if called before `require_user` has run for this
    request -- see the module docstring for why this doesn't fall back to
    a default user id.
    """
    try:
        return _current_user_id.get()
    except LookupError as exc:
        raise RuntimeError(
            "get_current_user_id() called with no authenticated user set "
            "for this request. This route is missing Depends(require_user), "
            "or is running DB access on a thread that didn't inherit the "
            "request's context (e.g. a bare loop.run_in_executor(...) call "
            "instead of asyncio.to_thread(...))."
        ) from exc
