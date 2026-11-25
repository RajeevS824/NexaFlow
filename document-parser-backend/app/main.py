import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from app.api.routes.document import router, ws_router
from app.core.config import ALLOWED_ORIGINS, OUTPUT_ROOT
from app.core.logger import logger
from app.core.security import decode_access_token
from app.services.database import initialize_database


# ============================================================
# LIFESPAN — guaranteed to run before first request
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Only load if not already in sys.modules.
    # Guards against double-load when --reload is used.
    try:
        initialize_database()
    except Exception as exc:  # pragma: no cover - defensive startup handling
        logger.warning("Database initialization skipped: %s", exc)

    if "app.services.model_loading" not in sys.modules:

        logger.info("=" * 60)
        logger.info("SERVER STARTUP — loading all models...")
        logger.info("=" * 60)

        try:
            import app.services.model_loading  # noqa: F401
        except Exception as exc:  # pragma: no cover - defensive startup handling
            logger.warning("Model loading skipped during startup: %s", exc)
            logger.warning("OCR processing endpoints will remain unavailable until the model dependencies are installed.")
        else:
            logger.info("=" * 60)
            logger.info("ALL MODELS READY — accepting requests")
            logger.info("=" * 60)

    else:
        logger.info("Models already loaded — skipping reload")

    yield

    logger.info("Server shutting down")


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Document Extraction API",
    version="1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

output_root_path = Path(OUTPUT_ROOT)
output_root_path.mkdir(parents=True, exist_ok=True)

logger.info("OUTPUT_ROOT = %s", output_root_path)

def _authenticate_output_request(request: Request, token: str | None = Query(default=None)) -> None:
    """Require a valid NexaFlow-issued JWT before serving a generated
    output file.

    Every other endpoint in this service requires auth via
    `require_user` (Bearer header). This one previously did not: it was
    mounted as a bare `StaticFiles` directory, so anyone who obtained or
    guessed a file path (extracted images, request/response JSON, CSV
    exports) could read another user's processed documents with no
    login at all. Browsers can't attach a custom Authorization header
    to `<img src>`/`<a href>` requests though, so -- exactly like the
    `/document/ws/history` WebSocket above -- this also accepts the
    same signed token as a `?token=` query parameter.
    """
    auth_header = request.headers.get("authorization", "")
    bearer_token = (
        auth_header.split(" ", 1)[1]
        if auth_header.lower().startswith("bearer ")
        else None
    )
    supplied = bearer_token or token or ""
    if not decode_access_token(supplied):
        raise HTTPException(status_code=401, detail="Authentication required.")


@app.get("/output/{file_path:path}")
async def get_output_file(file_path: str, request: Request, token: str | None = Query(default=None)):
    """Serve a single generated output file to an authenticated user.

    Replaces the old anonymous `StaticFiles` mount. Resolves the
    requested path and rejects anything that escapes OUTPUT_ROOT (path
    traversal via `..` segments), so this can only ever serve files
    that already live under the configured output directory.
    """
    _authenticate_output_request(request, token)

    requested = (output_root_path / file_path).resolve()
    try:
        requested.relative_to(output_root_path.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid file path.")

    if not requested.is_file():
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(requested)


app.include_router(router)
app.include_router(ws_router)


@app.get("/health", tags=["system"])
async def health_check():
    """Lightweight liveness probe for load balancers / uptime monitors."""
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for anything that isn't already an HTTPException.

    Logs the full traceback server-side but returns a generic message to
    the client so internal details (file paths, DB errors, stack traces)
    are never leaked to the frontend.

    As a last-resort safety net, if the request path contains a job/history
    id, we attempt to mark that job as FAILED in the database so no job is
    ever left stuck in processing/pending when an unexpected exception
    occurs.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)

    # ----------------------------------------------------------------
    # LAST-RESORT FAILURE HANDLING
    # ----------------------------------------------------------------
    # Extract history_id/job_id from the request path when present, e.g.:
    #   /document/history/<history_id>/pages/<n>/submit
    #   /document/history/<history_id>/mark-invalid
    #   /document/history/<history_id>/pages/<n>/mark-invalid
    # and also try to parse it from a JSON request body when available.
    job_id = None
    try:
        path_parts = request.url.path.rstrip("/").split("/")
        if "history" in path_parts:
            idx = path_parts.index("history")
            if idx + 1 < len(path_parts):
                candidate = path_parts[idx + 1]
                # Skip generic segments like "pages", "0" etc. — the id
                # immediately follows /history/ in every history route.
                if candidate and candidate.lower() not in ("pages", "scan-images", "disconnect-cleanup"):
                    job_id = candidate
    except Exception:
        pass

    # Fallback: try to read job/history id from the JSON request body
    if not job_id:
        try:
            body = await request.body()
            if body:
                import json as _json
                try:
                    parsed = _json.loads(body)
                    if isinstance(parsed, dict):
                        job_id = (
                            parsed.get("history_id")
                            or parsed.get("historyid")
                            or parsed.get("job_id")
                        )
                except Exception:
                    pass
        except Exception:
            pass

    if job_id:
        try:
            from app.repositories.history_repository import HistoryRepository
            HistoryRepository.mark_job_failed(str(job_id), str(exc))
            logger.info(
                "[unhandled_exception_handler] Marked job %s as FAILED due to unhandled exception",
                job_id,
            )
        except Exception as db_exc:
            logger.error(
                "[unhandled_exception_handler] Failed to mark job %s as failed in DB: %s",
                job_id, db_exc,
            )

    return JSONResponse(
        status_code=500,
        content={"status": "error", "detail": "Internal server error."},
    )
