import json
import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    Path as PathParam,
)
from pydantic import BaseModel

from app.api.dependencies import require_user
from app.core.config import MAX_UPLOAD_SIZE_BYTES, OUTPUT_ROOT, UPLOAD_DIR
from app.core.security import decode_access_token
from app.core.ws_manager import broadcast_job_event, job_events
from app.core.logger import logger
from app.repositories.history_repository import HistoryRepository
from app.repositories.model_repository import ModelRepository
from app.repositories.setting_repository import SettingRepository
from app.schemas.request_schema import (
    CreateHistoryRequest,
    ProcessRequestSchema,
    SaveModelRequest,
    UpdateHistoryRequest,
)
from app.schemas.response_schema import (
    HistoryListResponse,
    ModelsListResponse,
    SingleHistoryResponse,
    SingleModelResponse,
    StatusResponse,
)

ALLOWED_UPLOAD_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/bmp",
    "image/webp",
}
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".webp"}

router = APIRouter(
    prefix="/document",
    tags=["Document"],
    # Every route in this file requires a valid NexaFlow-issued Bearer
    # token. This also scopes get_current_user_id() to the authenticated
    # user for the lifetime of the request (see require_user).
    dependencies=[Depends(require_user)],
)

# Separate router for the WebSocket endpoint: browsers cannot send a
# custom Authorization header on the WS handshake, so this authenticates
# via a `token` query parameter instead and therefore can't reuse the
# HTTPBearer-based `require_user` dependency above.
ws_router = APIRouter(prefix="/document", tags=["Document"])


@ws_router.websocket("/ws/history")
async def history_live_updates(websocket: WebSocket, model_id: str = "*", token: str = ""):
    """Live job-status channel for the History page.

    Connect with: ws(s)://<host>/document/ws/history?model_id=<id>&token=<jwt>
    Sends JSON messages shaped like:
      {"event": "job_created" | "job_updated" | "job_failed" | "page_updated",
       "model_id": "...", "job_id": "...", "status": "...", ...}
    Use model_id="*" (default) to receive events for every model.
    """
    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4401)  # policy violation / unauthorized
        return

    await job_events.connect(websocket, model_id)
    try:
        while True:
            # We don't expect messages from the client; just keep the
            # connection open and detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await job_events.disconnect(websocket, model_id)


# ============================================================
# MODEL-NAME RESOLUTION HELPERS
# ============================================================

def _resolve_model_name_for_job(job_id: str) -> str:
    """Resolve the model_name for a job by joining processing_jobs →
    extraction_models. Returns a fallback string if the job or model
    cannot be found (e.g. legacy jobs created before model scoping)."""
    try:
        from app.database.connection import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT em.model_name
                FROM dbo.processing_jobs pj
                LEFT JOIN dbo.extraction_models em ON em.model_id = pj.model_id
                WHERE pj.job_id = ?
                """,
                (job_id,),
            )
            row = cursor.fetchone()
            if row and row[0]:
                return str(row[0])
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(f"[_resolve_model_name_for_job] Failed to resolve model for {job_id}: {exc}")
    return "default_model"


def _resolve_model_name(model_id: str) -> str:
    """Resolve the model_name for a model_id. Returns a fallback if not found."""
    try:
        from app.repositories.model_repository import ModelRepository
        model = ModelRepository.get_by_id(model_id)
        if model and model.get("name"):
            return str(model["name"])
    except Exception as exc:
        logger.warning(f"[_resolve_model_name] Failed to resolve model {model_id}: {exc}")
    return "default_model"


# ============================================================
# SETTINGS (SettingConfig)
# ============================================================

class SettingRequest(BaseModel):
    log_path: str = ""
    log_type: str = "INFO"
    checked: bool = False
    file_max_size_mb: int = 50
    output_base_path: str = "C:\\Users"


@router.get("/settings/{user_id}")
async def get_settings(user_id: str):
    """Return the SettingConfig row for the current user.

    NOTE: `user_id` in the path is kept only so existing frontend URLs
    keep working -- it is NOT trusted. The row returned is always scoped
    to the user id proven by the request's Bearer token (see
    require_user), so one user can no longer read another user's
    settings by editing the URL.

    If the current user has no SettingConfig row yet, a default row is
    inserted first (no DB trigger) and then returned.
    """
    from app.core.global_state import get_current_user_id
    settings = SettingRepository.get_or_create(str(get_current_user_id()))
    return {"status": "success", "settings": settings}


@router.put("/settings/{user_id}")
async def upsert_settings(user_id: str, data: SettingRequest):
    """Create or update the SettingConfig row for the current (token-authenticated) user."""
    from app.core.global_state import get_current_user_id
    updated = SettingRepository.upsert(str(get_current_user_id()), data.model_dump())
    return {"status": "success", "settings": updated}


# ============================================================
# MODELS
# ============================================================

@router.get("/models", response_model=ModelsListResponse)
async def get_models():
    return {"status": "success", "models": ModelRepository.list_all()}


@router.post("/models", response_model=SingleModelResponse)
async def create_or_update_model(payload: SaveModelRequest):
    saved = ModelRepository.save(payload.to_dict())
    return {"status": "success", "model": saved}


@router.delete("/models/{model_id}", response_model=StatusResponse)
async def delete_model_route(model_id: str, force: bool = False):
    """Delete a model. If the model has processing jobs, the client must
    pass `force=true` to remove those jobs as well. Otherwise a 409 is returned
    with a helpful message and the number of jobs.
    """
    try:
        ModelRepository.delete(model_id, force=force)
    except ValueError as exc:
        # Inform client that jobs exist and a forced delete is required
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {"status": "success"}


# ============================================================
# HISTORY
# ============================================================

@router.get("/history", response_model=HistoryListResponse)
async def get_history(model_id: str | None = None):
    return {"status": "success", "history": HistoryRepository.list_all(model_id)}


@router.post("/history", response_model=SingleHistoryResponse)
async def create_history(payload: CreateHistoryRequest):
    entry = HistoryRepository.create(payload.model_dump())
    return {"status": "success", "history": entry}


@router.get("/history/{history_id}")
async def get_history_detail(history_id: str):
    result = HistoryRepository.get_by_id(history_id)
    if not result:
        logger.warning(f"[GET /history/{history_id}] no processing_jobs row found for this id")
        raise HTTPException(status_code=404, detail="History record not found.")
    logger.debug(
        f"[GET /history/{history_id}] found job, status={result['history'].get('status')}, "
        f"pages={len(result['pages'])}"
    )
    return {"status": "success", **result}


@router.patch("/history/{history_id}", response_model=StatusResponse)
async def update_history(history_id: str, payload: UpdateHistoryRequest):
    HistoryRepository.update(history_id, payload.model_dump())
    return {"status": "success"}


@router.get("/history/{history_id}/scan-images")
async def scan_history_images(history_id: str):
    """Scan Output/<history_id>/page_*/images/ on disk and return image paths.

    Iterates over each page_N/images/ directory under the job folder.
    Used as a fallback by the frontend when the DB has pages=0 (finalize
    failed) but the pipeline succeeded and images exist on disk.
    """
    result = HistoryRepository.scan_job_images(history_id)
    return {"status": "success", **result}


@router.post("/history/{history_id}/disconnect-cleanup")
async def disconnect_cleanup(history_id: str):
    """Clean up after a client disconnect: delete generated files and update DB.

    Preserves the request/ folder and request.json.
    Deletes all generated page artifacts and updates the job status to failed.
    """
    from pathlib import Path as _Path
    from app.core.config import OUTPUT_ROOT

    model_name = _resolve_model_name_for_job(history_id)
    job_path = _Path(OUTPUT_ROOT) / model_name / history_id

    # Delete generated page artifacts but preserve request/
    if job_path.exists():
        for item in job_path.iterdir():
            if not item.is_dir():
                continue
            # Skip the request/ folder — preserve request.json
            if item.name.lower() == "request":
                continue
            # Remove entire page_* directories and any other generated folders
            import shutil as _shutil
            try:
                _shutil.rmtree(item)
            except Exception as exc:
                logger.warning(f"[disconnect-cleanup] Failed to remove {item}: {exc}")

    # Update database: delete job_pages, set status to failed
    HistoryRepository.handle_disconnect(history_id)

    return {"status": "success", "job_id": history_id}


@router.get("/history/{history_id}/pages/pending")
async def get_pending_pages(history_id: str):
    """Return only the pending pages for a job (for resume processing)."""
    result = HistoryRepository.get_by_id(history_id)
    if not result:
        raise HTTPException(status_code=404, detail="History record not found.")

    pending_pages = HistoryRepository.get_pending_pages(history_id)
    return {"status": "success", "pages": pending_pages}


class SubmitPageRequest(BaseModel):
    output_folder: str
    csv_content: str
    input_filename: str = "export"
    # 1-based page numbers of every page in this page's page-stream-
    # segmentation group (including page_number itself). Omitted/empty or a
    # single-element list means "not grouped" -- behaves exactly as before.
    group_pages: list[int] = []


def _group_label(page_number: int, group_pages: list[int]) -> str:
    """"page_3" for an ungrouped page, "Page_1,2" for a grouped page."""
    pages = sorted(set(group_pages)) if group_pages else [page_number]
    if len(pages) <= 1:
        return f"page_{page_number}"
    return "Page_" + ",".join(str(p) for p in pages)


@router.post("/history/{history_id}/pages/{page_number}/submit")
async def submit_page(
    history_id: str,
    page_number: int = PathParam(..., ge=1),
    data: SubmitPageRequest = None,
):
    """Submit a page (or, when it belongs to a page-stream-segmentation
    group, the *whole group*): save one CSV, update the status of every
    page in the group to Completed, and check if the entire job is done.

    CSV is saved on the server (never client-side) under:
      Output/<model_name>/<history_id>/extractedoutput/success/
    as: <input_filename>_<history_id>_page_<page_number>.csv for a lone
    page, or <input_filename>_<history_id>_Page_1,2.csv for a group --
    ONE file per group, never one per page.
    """
    import shutil as _shutil
    from pathlib import Path as _Path
    from datetime import datetime
    from app.core.config import OUTPUT_ROOT

    if data is None:
        raise HTTPException(status_code=400, detail="Request body is required.")

    # Verify the job exists
    result = HistoryRepository.get_by_id(history_id)
    if not result:
        raise HTTPException(status_code=404, detail="History record not found.")

    group_pages = sorted(set(data.group_pages)) if data.group_pages else [page_number]
    if page_number not in group_pages:
        group_pages.append(page_number)
        group_pages.sort()

    # Resolve the server-side extracted-output/success folder for this job.
    # The client's output_folder is ignored — every file lives on the
    # server, nothing is written or downloaded on the client side.
    model_name = _resolve_model_name_for_job(history_id)
    output_path = _Path(OUTPUT_ROOT) / model_name / history_id / "extractedoutput" / "success"
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid output folder: {exc}")

    base_name = _Path(data.input_filename).stem if data.input_filename else "export"

    # Save ONE CSV for the whole group (or the single page, when ungrouped)
    csv_filename = f"{base_name}_{history_id}_{_group_label(page_number, group_pages)}.csv"
    csv_path = output_path / csv_filename
    try:
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(data.csv_content or "")
    except Exception as exc:
        # Mark the job and page as FAILED before returning the error
        logger.error(f"[submit_page ERROR] Failed to write CSV for job {history_id} page {page_number}: {exc}")
        try:
            HistoryRepository.mark_job_failed(history_id, f"Failed to write CSV: {exc}")
        except Exception as db_exc:
            logger.error(f"[submit_page ERROR] Failed to mark job {history_id} as failed in DB: {db_exc}")
        raise HTTPException(status_code=500, detail=f"Failed to write CSV: {exc}")

    # Update page status to Completed for every page in the group so the
    # group advances (and completes) as a single unit.
    for grouped_page_number in group_pages:
        HistoryRepository.update_page_status(history_id, grouped_page_number, "Completed")

    # Check if job is fully completed
    is_completed = HistoryRepository.check_and_update_job_completion(history_id)

    broadcast_job_event(
        (result.get("history") or {}).get("modelid") or "*", "page_updated",
        job_id=history_id, page_number=page_number, group_pages=group_pages,
        status="completed" if is_completed else "processing",
    )

    return {
        "status": "success",
        "csv_file": str(csv_path),
        "page_number": page_number,
        "group_pages": group_pages,
        "job_completed": is_completed,
    }


class MarkPageInvalidRequest(BaseModel):
    output_folder: str
    csv_content: str = ""
    input_filename: str = "export"
    # 1-based page numbers of every page in this page's page-stream-
    # segmentation group (including page_number itself). Omitted/empty or a
    # single-element list means "not grouped" -- behaves exactly as before.
    group_pages: list[int] = []


@router.post("/history/{history_id}/pages/{page_number}/mark-invalid")
async def mark_page_invalid(
    history_id: str,
    page_number: int = PathParam(..., ge=1),
    data: MarkPageInvalidRequest = None,
):
    """Mark a page (or, when it belongs to a page-stream-segmentation
    group, the *whole group*) as invalid: save ONE CSV for the group,
    update every group page's status to 'Marked as Invalid', and check
    job completion. Images are intentionally left untouched -- only the
    CSV needs to be saved here.

    CSV is saved on the server (never client-side) under:
      Output/<model_name>/<history_id>/extractedoutput/invalid/
    """
    from pathlib import Path as _Path
    from app.core.config import OUTPUT_ROOT

    if data is None:
        raise HTTPException(status_code=400, detail="Request body is required.")

    # Verify the job exists
    result = HistoryRepository.get_by_id(history_id)
    if not result:
        raise HTTPException(status_code=404, detail="History record not found.")

    group_pages = sorted(set(data.group_pages)) if data.group_pages else [page_number]
    if page_number not in group_pages:
        group_pages.append(page_number)
        group_pages.sort()

    base_name = _Path(data.input_filename).stem if data.input_filename else "export"

    # Resolve the server-side job directory. The client's output_folder is
    # ignored — every file lives on the server, nothing is written or
    # downloaded on the client side.
    model_name = _resolve_model_name_for_job(history_id)
    job_root = _Path(OUTPUT_ROOT) / model_name / history_id

    # Extracted-output/invalid folder for CSVs
    extracted_dir = job_root / "extractedoutput" / "invalid"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    # Save ONE CSV for the whole group (or the single page, when ungrouped)
    # into extractedoutput/invalid/ -- never one CSV per page in the group.
    # The folder name already says "invalid", so the filename itself just
    # mirrors the submit-path naming (Page_1,2.csv / page_3.csv).
    csv_filename = f"{base_name}_{history_id}_{_group_label(page_number, group_pages)}.csv"
    csv_path = extracted_dir / csv_filename
    try:
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(data.csv_content or "")
    except Exception as exc:
        # Mark the job and page as FAILED before returning the error
        logger.error(f"[mark_page_invalid ERROR] Failed to write CSV for job {history_id} page {page_number}: {exc}")
        try:
            HistoryRepository.mark_job_failed(history_id, f"Failed to write CSV: {exc}")
        except Exception as db_exc:
            logger.error(f"[mark_page_invalid ERROR] Failed to mark job {history_id} as failed in DB: {db_exc}")
        raise HTTPException(status_code=500, detail=f"Failed to write CSV: {exc}")

    # Update page status to Marked as Invalid for every page in the group.
    for grouped_page_number in group_pages:
        HistoryRepository.update_page_status(history_id, grouped_page_number, "Marked as Invalid")

    # Check if job is fully completed
    is_completed = HistoryRepository.check_and_update_job_completion(history_id)

    broadcast_job_event(
        (result.get("history") or {}).get("modelid") or "*", "page_updated",
        job_id=history_id, page_number=page_number, group_pages=group_pages,
        status="completed" if is_completed else "processing",
    )

    return {
        "status": "success",
        "csv_file": str(csv_path),
        "page_number": page_number,
        "group_pages": group_pages,
        "job_completed": is_completed,
    }


class MarkInvalidRequest(BaseModel):
    output_folder: str
    csv_content: str = ""
    page_csvs: dict[str, str] = {}  # "page_1": "csv_content", "page_2": "csv_content", ...
    input_filename: str = "export"


@router.post("/history/{history_id}/mark-invalid")
async def mark_history_invalid(history_id: str, data: MarkInvalidRequest):
    """Mark a job as invalid: copy images to an invalid/<name>_<id>/ sub-folder
    organized per-page, save CSV per page, and set status = marked_as_invalid.

    All files are stored on the server under:
      Output/<model_name>/<history_id>/
        extractedoutput/            (all CSV files)
        invalid/<imagename>_<jobid>/page_1/images/...
        invalid/<imagename>_<jobid>/page_2/images/...
    """
    import re as _re
    import shutil as _shutil
    from pathlib import Path as _Path
    from app.core.config import OUTPUT_ROOT

    # Determine base_name and timestamp from input_filename
    base_name = os.path.splitext(os.path.basename(data.input_filename or "export"))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Resolve the server-side job directory. The client's output_folder is
    # ignored — all files are stored on the server.
    model_name = _resolve_model_name_for_job(history_id)
    job_root = _Path(OUTPUT_ROOT) / model_name / history_id

    # Extracted-output folder for all CSVs
    extracted_dir = job_root / "extractedoutput"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    folder_name = f"{base_name}_{history_id}"
    invalid_root = job_root / "invalid" / folder_name
    invalid_root.mkdir(parents=True, exist_ok=True)

    # Collect per-page image files by scanning page_N/images/ directories
    def _collect_per_page_images(job_id: str) -> dict[str, list[str]]:
        """Walk Output/<model_name>/<job_id>/page_*/images/ and return {page_key: [filenames]}."""
        result: dict[str, list[str]] = {}
        job_dir = job_root
        if not job_dir.exists():
            return result
        for pd in sorted(job_dir.iterdir()):
            if not pd.is_dir() or not pd.name.startswith("page_"):
                continue
            img_dir = pd / "images"
            if not img_dir.exists():
                continue
            fnames = []
            for f in sorted(img_dir.iterdir()):
                if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg"):
                    fnames.append(f.name)
            if fnames:
                result[pd.name] = fnames
        return result

    per_page_images = _collect_per_page_images(history_id)

    # ---- NEW per-page structure (page_csvs provided) ----
    if data.page_csvs:
        # Merge all page keys from both images and CSV data
        all_page_keys = set(per_page_images.keys()) | set(data.page_csvs.keys())
        if not all_page_keys:
            all_page_keys = {"page_1"}

        saved_image_files = []
        saved_csv_files = []

        for page_key in sorted(all_page_keys, key=lambda k: int(_re.search(r'\d+', k).group()) if _re.search(r'\d+', k) else 0):
            page_dir = invalid_root / page_key / "images"
            page_dir.mkdir(parents=True, exist_ok=True)

            # Copy images for this page
            for img_name in per_page_images.get(page_key, []):
                src = job_root / page_key / "images" / img_name
                dst = page_dir / img_name
                _shutil.copy2(src, dst)
                saved_image_files.append(img_name)

            # Save CSV for this page into extractedoutput/
            csv_content = data.page_csvs.get(page_key, "")
            csv_filename = f"{base_name}_{timestamp}_{page_key}_invalid.csv"
            csv_path = extracted_dir / csv_filename
            try:
                with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                    f.write(csv_content)
                saved_csv_files.append(f"{page_key}/{csv_filename}")
            except Exception as exc:
                # Mark the job and page as FAILED before returning the error
                logger.error(f"[mark_history_invalid ERROR] Failed to write CSV for job {history_id} page {page_key}: {exc}")
                try:
                    HistoryRepository.mark_job_failed(history_id, f"Failed to write CSV for {page_key}: {exc}")
                except Exception as db_exc:
                    logger.error(f"[mark_history_invalid ERROR] Failed to mark job {history_id} as failed in DB: {db_exc}")
                raise HTTPException(status_code=500, detail=f"Failed to write CSV for {page_key}: {exc}")

        # Update DB status
        HistoryRepository.mark_as_invalid(history_id)

        return {
            "status": "success",
            "save_dir": str(invalid_root),
            "saved_images": saved_image_files,
            "saved_csvs": saved_csv_files,
        }

    # ---- Fallback: copy all images from all page directories ----
    images_dest_dir = invalid_root / "images"
    images_dest_dir.mkdir(parents=True, exist_ok=True)

    copied_images = []
    for page_key, fnames in per_page_images.items():
        for img_name in fnames:
            src = job_root / page_key / "images" / img_name
            dest = images_dest_dir / img_name
            _shutil.copy2(src, dest)
            copied_images.append(img_name)

    # Save CSV into extractedoutput/
    csv_filename = f"{base_name}_{timestamp}_invalid.csv"
    csv_path = extracted_dir / csv_filename
    try:
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(data.csv_content or "")
    except Exception as exc:
        # Mark the job and page as FAILED before returning the error
        logger.error(f"[mark_history_invalid ERROR] Failed to write CSV for job {history_id}: {exc}")
        try:
            HistoryRepository.mark_job_failed(history_id, f"Failed to write CSV: {exc}")
        except Exception as db_exc:
            logger.error(f"[mark_history_invalid ERROR] Failed to mark job {history_id} as failed in DB: {db_exc}")
        raise HTTPException(status_code=500, detail=f"Failed to write CSV: {exc}")

    # Update DB status
    HistoryRepository.mark_as_invalid(history_id)

    return {
        "status": "success",
        "save_dir": str(invalid_root),
        "copied_images": copied_images,
        "csv_file": csv_filename,
    }


# FILE UPLOAD UTILITIES
# ============================================================

os.makedirs(UPLOAD_DIR, exist_ok=True)


async def _validate_uploaded_file(request: Request, file: UploadFile) -> dict:
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    safe_filename = os.path.basename(filename)
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid file name.")

    extension    = Path(safe_filename).suffix.lower()
    content_type = (getattr(file, "content_type", "") or "").lower()
    if content_type not in ALLOWED_UPLOAD_TYPES or extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_UPLOAD_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"File exceeds the maximum allowed size of "
                        f"{MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB."
                    ),
                )
        except ValueError:
            pass

    return {"safe_filename": safe_filename, "content_type": content_type}


def _resolve_output_folder(output_folder: str) -> Path:
    folder_value = (output_folder or "").strip()

    if not folder_value:
        raise HTTPException(status_code=400, detail="Please enter a valid output folder path.")

    try:
        output_path = Path(folder_value).expanduser()
        if not output_path.is_absolute():
            output_path = (Path.cwd() / output_path).resolve()
        else:
            output_path = output_path.resolve()

        if output_path.exists() and not output_path.is_dir():
            raise HTTPException(status_code=400, detail="The selected output path is not a folder.")

        output_path.mkdir(parents=True, exist_ok=True)

        if not os.access(output_path, os.W_OK):
            raise HTTPException(status_code=400, detail="The selected output path is not writable.")
    except PermissionError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"The selected output path is not writable: {exc}",
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Please enter a valid output folder path: {exc}",
        ) from exc

    return output_path


# ============================================================
# SHARED PIPELINE RUNNER
# ============================================================

async def _run_pipeline_in_workspace(
    request: Request,
    request_dict: dict,
    base_name: str,
    job_id: str | None = None,
) -> dict:
    """
    Creates a per-request workspace keyed by model_name and job_id
    (Output/<model_name>/<job_id>/), writes request.json into it, runs the
    OCR pipeline, and returns a response shaped identically regardless of
    which endpoint called this. Supports client-disconnection polling to
    abort long-running OCR.

    NOTE: `base_name` (the source file name) is intentionally NOT baked into
    the workspace folder name anymore -- the folder is
    Output/<model_name>/<job_id>/ and everything page-specific lives under
    Output/<model_name>/<job_id>/page_<n>/.
    """
    import asyncio

    job_id        = job_id or str(uuid.uuid4())
    model_id      = (request_dict.get("extrcation_model") or {}).get("model_id") or ""
    model_name    = _resolve_model_name(model_id)
    workspace_dir = Path("Output") / model_name / job_id

    logger.debug("workspace_dir = %s", workspace_dir.resolve())

    workspace_dir.mkdir(parents=True, exist_ok=True)

    request_dir = workspace_dir / "request"
    request_dir.mkdir(parents=True, exist_ok=True)

    request_file = request_dir / "request.json"
    output_dir   = workspace_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve the current user HERE, on the request's own task, where
    # get_current_user_id() is guaranteed to work. The pipeline itself
    # runs in run_pipeline() below via loop.run_in_executor(), which does
    # NOT copy this task's context into the worker thread -- so if we
    # waited and let process_document() call get_current_user_id() from
    # inside that thread, it would raise (see global_state.py). Baking
    # the user id into request.json means the pipeline can read it back
    # via request_data.get("user_id") without ever touching the
    # context-local lookup from a thread that doesn't have it.
    from app.core.global_state import get_current_user_id
    request_dict = {**request_dict, "user_id": get_current_user_id()}

    with open(request_file, "w", encoding="utf-8") as f:
        json.dump(request_dict, f, indent=2, ensure_ascii=False)

    from app.services.document_pipeline import run_pipeline

    class CancellationToken:
        def __init__(self):
            self.is_cancelled = False

    token = CancellationToken()

    async def check_disconnect():
        while not token.is_cancelled:
            if await request.is_disconnected():
                token.is_cancelled = True
                logger.info("Client disconnect detected in ASGI monitoring loop.")
                break
            await asyncio.sleep(0.5)

    monitor_task = asyncio.create_task(check_disconnect())

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None,
            run_pipeline,
            request_file,
            output_dir,
            lambda: token.is_cancelled
        )
    except Exception as exc:
        from app.services.document_service import PipelineCancelledException
        if isinstance(exc, PipelineCancelledException) or "cancelled by client disconnect" in str(exc).lower():
            logger.info("Pipeline execution aborted: client disconnected.")

            # ============================================================
            # CLEANUP ON CLIENT DISCONNECT
            # ============================================================
            # Preserve request/request.json, delete all generated page artifacts,
            # and update the database to mark the job as failed.
            logger.info(f"[disconnect cleanup] Cleaning up generated files for job {job_id}...")
            from pathlib import Path as _Path
            from app.core.config import OUTPUT_ROOT as _OUTPUT_ROOT

            job_path = _Path(_OUTPUT_ROOT) / model_name / job_id
            if job_path.exists():
                for item in job_path.iterdir():
                    if not item.is_dir():
                        continue
                    # Skip the request/ folder — preserve request.json
                    if item.name.lower() == "request":
                        continue
                    try:
                        import shutil as _shutil
                        _shutil.rmtree(item)
                    except Exception as cleanup_exc:
                        logger.warning(f"[disconnect cleanup] Failed to remove {item}: {cleanup_exc}")

            # Update database: delete job_pages, set status to failed
            HistoryRepository.handle_disconnect(job_id)
            logger.info(f"[disconnect cleanup] Completed for job {job_id}")

            raise HTTPException(status_code=499, detail="Client Disconnected")

        # ============================================================
        # ANY OTHER EXCEPTION — mark the job as FAILED in the DB
        # before re-raising so it never stays stuck in processing.
        # ============================================================
        logger.error(f"[pipeline ERROR] Pipeline failed for job {job_id}: {exc}")
        try:
            HistoryRepository.mark_job_failed(job_id, str(exc))
        except Exception as db_exc:
            logger.error(f"[pipeline ERROR] Failed to mark job {job_id} as failed in DB: {db_exc}")
        raise exc
    finally:
        token.is_cancelled = True
        await monitor_task

    return {
        "status":          "success",
        "job_id":          job_id,
        "data":            result["response_data"],
        "annotated_images": result["annotated_images"],
        "raw_results":     result["raw_results"],
        "page_statuses":   result.get("page_statuses") or {},
    }


# ============================================================
# PROCESS ENDPOINTS
# ============================================================

@router.post("/process")
async def process_document(process_req: ProcessRequestSchema, request: Request):
    """
    Path-only endpoint — NO file upload.

    Use this when the frontend and backend share the same local filesystem:
    request.document.url must already be an absolute path the backend
    process can read directly (e.g. "D:\\Input\\invoice.pdf").
    """
    request_dict = process_req.model_dump(by_alias=False)

    doc_url = (request_dict.get("document") or {}).get("url", "").strip()

    if not doc_url:
        raise HTTPException(
            status_code=400,
            detail="document.url is required and must be a local file path.",
        )
    if not os.path.isfile(doc_url):
        raise HTTPException(
            status_code=400,
            detail=f"File not found on the server at: {doc_url}",
        )

    if not request_dict["document"].get("file_name"):
        request_dict["document"]["file_name"] = Path(doc_url).name

    base_name = Path(doc_url).stem
    return await _run_pipeline_in_workspace(request, request_dict, base_name)


@router.post("/process-upload")
async def process_upload(
    request: Request,
    file: UploadFile = File(...),
    request_json: str = Form(...),
    job_id: str = Form(""),
):
    """
    Upload endpoint — use this only when the frontend and backend do NOT
    share a filesystem (e.g. browser client on a different machine than
    the API server).

    When `job_id` is provided (non-empty), the backend reuses the existing
    job_id for reprocessing instead of creating a new history entry.
    """
    validated     = await _validate_uploaded_file(request, file)
    safe_filename = validated["safe_filename"]
    unique_name   = f"{uuid.uuid4()}_{safe_filename}"
    saved_path    = os.path.join(UPLOAD_DIR, unique_name)

    try:
        history_id = None
        with open(saved_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        try:
            request_dict = json.loads(request_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid request payload.") from exc

        request_dict["document"]["url"]       = saved_path
        request_dict["document"]["file_name"] = safe_filename

        base_name = Path(safe_filename).stem
        model_id_for_ws = request_dict.get("extrcation_model", {}).get("model_id") or "*"

        # Check if this is a reprocess (existing job_id provided)
        existing_job_id = (job_id or "").strip()

        if existing_job_id:
            # Reprocess: reuse existing job_id, do NOT create a new history entry
            history_id = existing_job_id
            # Set status back to processing in case it was 'failed'
            HistoryRepository.update(history_id, {"status": "processing"})
            broadcast_job_event(model_id_for_ws, "job_updated", job_id=history_id, status="processing")
        else:
            # New job: create a history / processing job placeholder
            history_payload = {
                "model_id": request_dict.get("extrcation_model", {}).get("model_id") or "",
                "model_name": "",
                "document_type": request_dict.get("document", {}).get("document_type") or "",
                "createddate": "",
                "processdate": datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d-%m-%Y %H:%M:%S"),
                "status": "processing",
                # Store the actual uploaded file name so the History page's
                # "Document Name" column shows the real filename instead of
                # the "document.pdf" default in documents.original_filename.
                "document_name": safe_filename,
            }

            history_entry = HistoryRepository.create(history_payload)
            history_id = history_entry.get("historyid")
            broadcast_job_event(model_id_for_ws, "job_created", job_id=history_id, status="processing")

        result = await _run_pipeline_in_workspace(
            request, request_dict, base_name, job_id=history_id
        )

        # Persist job pages and mark the job as pending (safe for reprocess)
        # HistoryRepository.finalize() already deletes existing job_pages and re-inserts.
        try:
            HistoryRepository.finalize(
                history_id,
                result.get("annotated_images"),
                result.get("raw_results"),
                page_statuses=result.get("page_statuses"),
            )
            # Some/all groups may already be "Completed" from backend STP
            # (see document_service.py's per-group auto-submit). Roll that
            # up to the job's overall status right away instead of leaving
            # it stuck on "processing" until the frontend visits it.
            job_fully_done = HistoryRepository.check_and_update_job_completion(history_id, stp=True)
            if not job_fully_done:
                HistoryRepository.update(history_id, {"status": "pending"})
            broadcast_job_event(
                model_id_for_ws, "job_updated", job_id=history_id,
                status="completed" if job_fully_done else "pending",
            )
        except Exception:
            import traceback as _tb
            logger.error(f"[finalize ERROR] Failed to persist job pages for history_id={history_id}:\n{_tb.format_exc()}")
            # If finalize fails, the job has no pages to display — mark it FAILED
            try:
                HistoryRepository.mark_job_failed(history_id, "Failed to persist job pages")
                broadcast_job_event(model_id_for_ws, "job_failed", job_id=history_id, status="failed")
            except Exception as db_exc:
                logger.error(f"[finalize ERROR] Failed to mark job {history_id} as failed in DB: {db_exc}")

        result["uploaded_file"] = saved_path
        result["historyid"] = history_id
        return result
    except HTTPException:
        # HTTPExceptions (e.g. validation failures) re-raise as-is so the
        # correct status code is returned to the client.
        raise
    except Exception as exc:
        # Any unexpected exception during upload/processing — mark the job
        # as FAILED before re-raising so it never stays stuck in processing.
        if history_id:
            logger.error(f"[process_upload ERROR] Upload/processing failed for job {history_id}: {exc}")
            try:
                HistoryRepository.mark_job_failed(history_id, str(exc))
                broadcast_job_event(
                    request_dict.get("extrcation_model", {}).get("model_id") or "*",
                    "job_failed", job_id=history_id, status="failed",
                )
            except Exception as db_exc:
                logger.error(f"[process_upload ERROR] Failed to mark job {history_id} as failed in DB: {db_exc}")
        raise
    finally:
        if os.path.exists(saved_path):
            os.remove(saved_path)


# ============================================================
# OUTPUT PATH VALIDATION
# ============================================================

class ValidateOutputPathRequest(BaseModel):
    output_folder: str


@router.post("/validate-output-path", response_model=dict)
async def validate_output_path(data: ValidateOutputPathRequest):
    """No-op validation — outputs are always stored on the server, so the
    client-provided folder is never written to. This endpoint is retained
    for backward compatibility with the frontend."""
    return {"status": "success", "output_folder": str(Path(OUTPUT_ROOT))}


# ============================================================
# CSV EXPORT
# ============================================================

class SaveCsvRequest(BaseModel):
    output_folder: str
    csv_content:   str
    input_filename: str
    history_id:    str = ""
    page_number:   int | None = None


@router.post("/save-csv", response_model=dict)
async def save_csv(data: SaveCsvRequest):
    # All CSVs are stored on the server under the job's extractedoutput/ folder.
    # The client-provided output_folder is ignored — no client-path writes.
    if data.history_id:
        model_name = _resolve_model_name_for_job(data.history_id)
        output_path = _Path(OUTPUT_ROOT) / model_name / data.history_id / "extractedoutput"
    else:
        output_path = _Path(OUTPUT_ROOT) / "default_model" / "extractedoutput"
    output_path.mkdir(parents=True, exist_ok=True)

    base_name  = os.path.splitext(os.path.basename(data.input_filename))[0]
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"{base_name}_{timestamp}.csv"
    csv_path   = output_path / csv_filename

    try:
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(data.csv_content)
    except Exception as exc:
        # Mark the job (and its pages) as FAILED before returning the error.
        # The frontend may not know the job_id at this point, so it is
        # optional — if provided we can update the DB so the job never
        # stays stuck in processing/pending.
        logger.error(f"[save_csv ERROR] Failed to write CSV for job {data.history_id}: {exc}")
        if data.history_id:
            try:
                HistoryRepository.mark_job_failed(data.history_id, f"Failed to write CSV: {exc}")
            except Exception as db_exc:
                logger.error(f"[save_csv ERROR] Failed to mark job {data.history_id} as failed in DB: {db_exc}")
        raise HTTPException(status_code=500, detail=f"Failed to write CSV: {exc}")

    return {"status": "success", "csv_file": csv_path}