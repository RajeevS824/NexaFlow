"""
history_repository.py â€” Repository for processing job (history) CRUD.

Entities covered
----------------
- documents        (created as a placeholder per job)
- processing_jobs  (the actual history entries)
- job_pages        (per-page entries with individual status)

All database access uses raw SQL via pyodbc.  No ORM.
"""
import uuid
import json
from typing import Any, Optional

from app.database.connection import get_connection, log_db_transaction
from app.core.logger import logger
from app.core.global_state import get_current_user_id
from app.core.paths import (
    job_dir,
    page_images_dir,
    relative_image_path,
)

_STATUS_MAP = {
    "queued":           "queued",
    "processing":       "processing",
    "pending":          "pending",
    "success":          "completed",
    "completed":        "completed",
    "failed":           "failed",
    "cancelled":        "cancelled",
    "marked_as_invalid": "marked_as_invalid",
}


def _map_status(raw: Optional[str]) -> str:
    return _STATUS_MAP.get((raw or "").lower(), "queued")


def _normalize_stp(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if int(value) != 0 else 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return 1
        if text in {"0", "false", "no", "n", "off", ""}:
            return 0
    return 0


class HistoryRepository:
    """All database operations for processing job history."""

    # â”€â”€ READ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @staticmethod
    def list_all(model_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Return all jobs for the default user, optionally filtered by model."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            log_db_transaction("HistoryRepository.list_all", {"model_id": model_id})
            # query = """
            #     SELECT pj.job_id, pj.model_id, pj.status,
            #            em.model_name, em.document_type,
            #            pj.queued_at, pj.completed_at
            #     FROM dbo.processing_jobs pj
            #     LEFT JOIN dbo.extraction_models em ON em.model_id = pj.model_id
            #     WHERE pj.ProcessedUserID = ?
            # """
            query = """
                SELECT pj.job_id, pj.model_id, pj.status,
                       em.model_name, em.document_type,
                       pj.queued_at, pj.completed_at,
                       doc.original_filename, pj.stp, pj.error_message
                FROM dbo.processing_jobs pj
                LEFT JOIN dbo.extraction_models em ON em.model_id = pj.model_id
                LEFT JOIN dbo.documents doc ON doc.document_id = pj.document_id
                WHERE pj.ProcessedUserID = ?
            """
            params: list[Any] = [get_current_user_id()]
            if model_id:
                query += " AND pj.model_id = ?"
                params.append(model_id)
            query += " ORDER BY pj.queued_at DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            from datetime import datetime, timezone, timedelta

            IST = timezone(timedelta(hours=5, minutes=30))

            def fmt(dt):
                if not dt:
                    return ""
                return dt.strftime("%Y-%m-%d %H:%M:%S")

            return [
                {
                    "historyid":    str(row[0]),
                    "modelid":      str(row[1]),
                    "status":       row[2],
                    "modelname":    row[3] or "",
                    "documenttype": row[4] or "",
                    "createddate":  fmt(row[5]),
                    "processdate":  (fmt(row[6]) if row[6] else (fmt(row[5]) if row[5] else "")),
                    "documentname": row[7] or "",
                    "stp":          bool(row[8]),
                    "error_message": row[9] or "",
                }
                for row in rows
            ]
        finally:
            conn.close()

    @staticmethod
    def get_by_id(job_id: str) -> Optional[dict[str, Any]]:
        """Return a single job's history record plus its page rows.

        Returns None if no job with that id exists for the default owner.
        Shape: {"history": {...same fields as list_all()...}, "pages": [...]}
        Each page now includes a 'status' field.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            log_db_transaction("HistoryRepository.get_by_id", {"job_id": job_id})

            cursor.execute(
                """
                SELECT pj.job_id, pj.model_id, pj.status,
                       em.model_name, em.document_type,
                       pj.queued_at, pj.completed_at,
                       doc.original_filename, pj.stp, pj.error_message
                FROM dbo.processing_jobs pj
                LEFT JOIN dbo.extraction_models em ON em.model_id = pj.model_id
                LEFT JOIN dbo.documents doc ON doc.document_id = pj.document_id
                WHERE pj.job_id = ? AND pj.ProcessedUserID = ?
                """,
                (job_id, get_current_user_id()),
            )
            row = cursor.fetchone()
            if not row:
                return None

            from datetime import datetime, timezone, timedelta

            IST = timezone(timedelta(hours=5, minutes=30))

            def fmt(dt):
                if not dt:
                    return ""
                return dt.strftime("%Y-%m-%d %H:%M:%S")

            history = {
                "historyid":    str(row[0]),
                "modelid":      str(row[1]),
                "status":       row[2],
                "modelname":    row[3] or "",
                "documenttype": row[4] or "",
                "createddate":  fmt(row[5]),
                "processdate":  (fmt(row[6]) if row[6] else (fmt(row[5]) if row[5] else "")),
                "documentname": row[7] or "",
                "stp":          bool(row[8]),
                "error_message": row[9] or "",
            }

            cursor.execute(
                """
                SELECT page_number, enhanced_image_path, annotated_image_path,
                       ocr_tokens, created_at, status, error_message, completed_at
                FROM dbo.job_pages
                WHERE job_id = ?
                ORDER BY page_number ASC
                """,
                (job_id,),
            )
            page_rows = cursor.fetchall()

            pages = []
            for prow in page_rows:
                try:
                    ocr_tokens = json.loads(prow[3]) if prow[3] else []
                except (TypeError, ValueError):
                    ocr_tokens = []

                pages.append(
                    {
                        "page_number":          prow[0],
                        "enhanced_image_path":  prow[1],
                        "annotated_image_path": prow[2],
                        "ocr_tokens":           ocr_tokens,
                        "created_at":           fmt(prow[4]) if prow[4] else "",
                        "status":               prow[5] or "Pending",
                        "error_message":        prow[6] or "",
                        "completed_at":         fmt(prow[7]) if prow[7] else "",
                    }
                )

            return {"history": history, "pages": pages}
        finally:
            conn.close()

    @staticmethod
    def get_pending_pages(job_id: str) -> list[dict[str, Any]]:
        """Return only pages with status = 'Pending' for the given job."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            log_db_transaction("HistoryRepository.get_pending_pages", {"job_id": job_id})

            cursor.execute(
                """
                SELECT page_number, enhanced_image_path, annotated_image_path,
                       ocr_tokens, created_at, status, error_message, completed_at
                FROM dbo.job_pages
                WHERE job_id = ? AND status = 'Pending'
                ORDER BY page_number ASC
                """,
                (job_id,),
            )
            page_rows = cursor.fetchall()

            from datetime import datetime, timezone, timedelta
            IST = timezone(timedelta(hours=5, minutes=30))

            def fmt(dt):
                if not dt:
                    return ""
                return dt.strftime("%Y-%m-%d %H:%M:%S")

            pages = []
            for prow in page_rows:
                try:
                    ocr_tokens = json.loads(prow[3]) if prow[3] else []
                except (TypeError, ValueError):
                    ocr_tokens = []

                pages.append(
                    {
                        "page_number":          prow[0],
                        "enhanced_image_path":  prow[1],
                        "annotated_image_path": prow[2],
                        "ocr_tokens":           ocr_tokens,
                        "created_at":           fmt(prow[4]) if prow[4] else "",
                        "status":               prow[5] or "Pending",
                        "error_message":        prow[6] or "",
                        "completed_at":         fmt(prow[7]) if prow[7] else "",
                    }
                )

            return pages
        finally:
            conn.close()

    # â”€â”€ WRITE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @staticmethod
    def create(payload: dict[str, Any]) -> dict[str, Any]:
        """Create a placeholder document and a new processing job."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # â”€â”€ Create a fresh document record for each new job â”€â”€â”€â”€â”€â”€â”€â”€â”€
            document_name = payload.get("document_name") or "document.pdf"
            from datetime import datetime, timezone, timedelta
            IST = timezone(timedelta(hours=5, minutes=30))
            now_ist = datetime.now(IST)
            now_str = now_ist.strftime("%Y-%m-%d %H:%M:%S")
            document_id = str(uuid.uuid4())
            try:
                cursor.execute(
                    """
                    INSERT INTO dbo.documents
                        (document_id, uploaded_by, original_filename, storage_path,
                         file_size_bytes, mime_type, status, uploaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (document_id, get_current_user_id(), document_name, "backend", 0, "application/pdf", "uploaded", now_str),
                )
            except Exception as exc:
                logger.exception("Failed to insert documents row for %s: %s", document_name, exc)
                raise

            # â”€â”€ Insert the processing job â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            model_id      = payload.get("model_id") or ""
            job_id        = str(uuid.uuid4())
            mapped_status = _map_status(payload.get("status"))
            initial_stp = _normalize_stp(payload.get("stp", 0))

            try:
                cursor.execute(
                    """
                    INSERT INTO dbo.processing_jobs
                        (job_id, document_id, model_id, ProcessedUserID,
                         status, stp, queued_at, started_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (job_id, document_id, model_id, get_current_user_id(), mapped_status, initial_stp, now_str, now_str),
                )
            except Exception as exc:
                logger.exception("Failed to insert processing_jobs row for document %s: %s", document_name, exc)
                raise
            conn.commit()

            # Audit log: job created
            try:
                cursor.execute(
                    "INSERT INTO dbo.audit_log (audit_id, user_id, action, entity_type, entity_id, ip_address, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), get_current_user_id(), "create", "processing_job", job_id, None, now_str),
                )
                conn.commit()
            except Exception:
                pass

            from datetime import datetime, timezone, timedelta
            IST = timezone(timedelta(hours=5, minutes=30))
            now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
            response_payload = {
                "historyid":    job_id,
                "modelid":      model_id,
                "status":       mapped_status,
                "modelname":    payload.get("model_name") or "",
                "documenttype": payload.get("document_type") or "",
                "createddate":  payload.get("createddate") or now,
                "processdate":  payload.get("processdate") or now,
                "stp":          initial_stp,
            }
            log_db_transaction("HistoryRepository.create", payload, response_payload)
            return response_payload
        finally:
            conn.close()

    @staticmethod
    def finalize(job_id: str, annotated_images: list[str] | None = None, raw_results: list[Any] | None = None, page_statuses: dict | None = None) -> None:
        """Persist job page rows and mark the job as 'pending'.

        This will remove any existing job_pages for the job (safe for
        reprocess/resume flows) and insert a fresh set of rows for each
        annotated image. `raw_results` may be used to persist OCR tokens
        per page when available.

        `page_statuses` (optional): {page_number(1-based): "Completed" |
        "Pending"}, produced by document_service.py's per-group
        straight-through-processing check. A page/group whose required
        fields were already all present when the pipeline finished is
        inserted as "Completed" (its CSV already saved to
        extractedoutput/success/ by the pipeline itself) instead of the
        default "Pending", so it never shows up for manual validation.

        The paths stored in enhanced_image_path and annotated_image_path
        are in the format: <job_id>/page_<N>/images/<filename>
        (relative to OUTPUT_ROOT), which matches the new per-page directory
        structure produced by the pipeline.
        """
        page_statuses = page_statuses or {}
        conn = get_connection()
        try:
            cursor = conn.cursor()
            from datetime import datetime, timezone, timedelta
            IST = timezone(timedelta(hours=5, minutes=30))
            now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
            log_db_transaction("HistoryRepository.finalize", {"job_id": job_id, "annotated_images": annotated_images, "raw_results": raw_results})

            # Remove any existing pages for a reprocess
            cursor.execute("DELETE FROM dbo.job_pages WHERE job_id = ?", (job_id,))

            annotated_images = annotated_images or []
            raw_results = raw_results or []

            for idx, annotated_rel in enumerate(annotated_images, start=1):
                # annotated_rel comes from the pipeline as:
                #   <job_id>/page_<N>/images/annotated_<...>.png
                # Store it directly â€” the new per-page path format.
                annotated_path = annotated_rel

                enhanced_path = None
                ocr_tokens = None
                page_created_at = now_str

                # Try to pick enhanced image path and OCR tokens from raw_results
                try:
                    page_raw = raw_results[idx - 1] if idx - 1 < len(raw_results) else None
                    if page_raw:
                        ocr_tokens = json.dumps(page_raw.get("ocr", []), ensure_ascii=False)
                        # raw_results[idx-1]["image"] is an absolute path like:
                        #   D:\...\Output\<job_id>\page_N\images\<file>.png
                        # Convert to relative format matching the new structure:
                        #   <job_id>/page_N/images/<file>.png
                        raw_image = page_raw.get("image") or ""
                        if raw_image:
                            import re as _re
                            norm = raw_image.replace("\\", "/")
                            # Path is Output/<model_name>/<job_id>/page_N/images/<file>.png
                            m = _re.search(
                                r"(?:output/)?" + _re.escape(job_id) + r"/(.+)$",
                                norm,
                                _re.IGNORECASE,
                            )
                            if m:
                                # The segment immediately before the job_id in
                                # the normalized path is the model_name, giving:
                                #   <model_name>/<job_id>/page_N/images/<file>.png
                                parts = norm.rstrip("/").split("/")
                                model_seg = ""
                                for i, part in enumerate(parts):
                                    if part == job_id and i > 0:
                                        model_seg = parts[i - 1]
                                        break
                                if model_seg and model_seg != job_id:
                                    enhanced_path = f"{model_seg}/{job_id}/{m.group(1)}"
                                else:
                                    enhanced_path = f"{job_id}/{m.group(1)}"
                            else:
                                # Fallback: keep just the last three segments
                                # (page_N/images/<file>.png) prefixed by job_id
                                parts = norm.rstrip("/").split("/")
                                if len(parts) >= 3:
                                    enhanced_path = f"{job_id}/{'/'.join(parts[-3:])}"
                                else:
                                    enhanced_path = norm
                except Exception:
                    ocr_tokens = None

                cursor.execute(
                    "INSERT INTO dbo.job_pages (process_id, job_id, page_number, enhanced_image_path, annotated_image_path, ocr_tokens, created_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), job_id, idx, enhanced_path, annotated_path, ocr_tokens, page_created_at, page_statuses.get(idx, "Pending")),
                )

            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def update(history_id: str, payload: dict[str, Any]) -> None:
        """Update the status (and completed_at if terminal) of a processing job."""
        mapped_status = _map_status(payload.get("status"))
        conn = get_connection()
        try:
            cursor = conn.cursor()
            log_db_transaction("HistoryRepository.update", {"history_id": history_id, "payload": payload})

            fields: list[str] = []
            params: list[Any] = []

            if mapped_status:
                fields.append("status = ?")
                params.append(mapped_status)

            if "stp" in payload:
                fields.append("stp = ?")
                params.append(_normalize_stp(payload.get("stp")))
            elif mapped_status == "pending":
                fields.append("stp = ?")
                params.append(0)

            if "error_message" in payload and payload.get("error_message") is not None:
                fields.append("error_message = ?")
                params.append(payload.get("error_message"))

            if fields:
                params.append(history_id)
                cursor.execute(
                    f"UPDATE dbo.processing_jobs SET {', '.join(fields)} WHERE job_id = ?",
                    params,
                )

            # If the new status is terminal, set completed_at to IST now
            if mapped_status in ("completed", "failed", "cancelled", "marked_as_invalid"):
                from datetime import datetime, timezone, timedelta
                IST = timezone(timedelta(hours=5, minutes=30))
                now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "UPDATE dbo.processing_jobs SET completed_at = ? WHERE job_id = ?",
                    (now_str, history_id),
                )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def scan_job_images(job_id: str) -> dict[str, Any]:
        """Scan Output/<model_name>/<job_id>/page_*/images/ on disk and return
        relative image paths.

        Iterates over each page_N/images/ directory under the job folder and
        collects all enhanced (non-annotated) and annotated images.

        Returns {"enhanced": [...], "annotated": [...]} with paths relative to
        OUTPUT_ROOT so the frontend can build /output/... URLs directly.
        Used as fallback when finalize() failed and job_pages has 0 rows.
        """
        import os as _os
        from pathlib import Path as _Path
        from app.core.config import OUTPUT_ROOT

        # Resolve the model_name for the job from the DB
        model_name = "default_model"
        try:
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
                    model_name = str(row[0])
            finally:
                conn.close()
        except Exception:
            model_name = "default_model"

        jd = _Path(OUTPUT_ROOT) / model_name / job_id
        enhanced = []
        annotated = []

        if not jd.exists():
            return {"enhanced": enhanced, "annotated": annotated}

        # Scan each page_N/images/ directory
        for page_dir in sorted(jd.iterdir()):
            if not page_dir.is_dir() or not page_dir.name.startswith("page_"):
                continue
            images_dir = page_dir / "images"
            if not images_dir.exists():
                continue
            for fname in sorted(images_dir.iterdir()):
                if not fname.is_file():
                    continue
                # Build relative path: <model_name>/<job_id>/page_N/images/<filename>
                rel = f"{model_name}/{job_id}/{page_dir.name}/images/{fname.name}"
                if fname.name.startswith("annotated_"):
                    annotated.append(rel)
                else:
                    enhanced.append(rel)

        return {"enhanced": enhanced, "annotated": annotated}

    @staticmethod
    def mark_as_invalid(job_id: str) -> None:
        """Set job status to marked_as_invalid and set completed_at."""
        conn = get_connection()
        try:
            from datetime import datetime, timezone, timedelta
            IST = timezone(timedelta(hours=5, minutes=30))
            now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
            cursor = conn.cursor()
            log_db_transaction("HistoryRepository.mark_as_invalid", {"job_id": job_id})
            cursor.execute(
                "UPDATE dbo.processing_jobs SET status = ?, stp = ?, completed_at = ? WHERE job_id = ?",
                ("marked_as_invalid", 0, now_str, job_id),
            )
            conn.commit()
        finally:
            conn.close()

    # â”€â”€ PER-PAGE METHODS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @staticmethod
    def update_page_status(job_id: str, page_number: int, status: str, error_message: str | None = None) -> None:
        """Update the status of a specific page in a job.

        Valid statuses: 'Completed', 'Marked as Invalid', 'Failed'
        Optionally stores an error message and sets completed_at for terminal states.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            log_db_transaction("HistoryRepository.update_page_status", {
                "job_id": job_id, "page_number": page_number, "status": status, "error_message": error_message
            })

            from datetime import datetime, timezone, timedelta
            IST = timezone(timedelta(hours=5, minutes=30))
            now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

            if error_message is not None:
                cursor.execute(
                    "UPDATE dbo.job_pages SET status = ?, error_message = ?, completed_at = ? WHERE job_id = ? AND page_number = ?",
                    (status, error_message, now_str, job_id, page_number),
                )
            else:
                cursor.execute(
                    "UPDATE dbo.job_pages SET status = ?, completed_at = ? WHERE job_id = ? AND page_number = ?",
                    (status, now_str, job_id, page_number),
                )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def mark_job_failed(job_id: str, error_message: str | None = None) -> None:
        """Mark a job and all its pages as FAILED in a single transaction.

        Sets processing_jobs.status = 'failed', completed_at = now, and
        error_message. Also updates every job_pages row to status = 'Failed'
        with completed_at and error_message.

        This is the central failure handler used by the API layer so that
        no exception ever leaves a job stuck in processing/pending.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            from datetime import datetime, timezone, timedelta
            IST = timezone(timedelta(hours=5, minutes=30))
            now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

            log_db_transaction("HistoryRepository.mark_job_failed", {
                "job_id": job_id, "error_message": error_message
            })

            # Update the processing job
            cursor.execute(
                "UPDATE dbo.processing_jobs SET status = ?, stp = ?, completed_at = ?, error_message = ? WHERE job_id = ?",
                ("failed", 0, now_str, error_message, job_id),
            )

            # Update all pages for the job
            cursor.execute(
                "UPDATE dbo.job_pages SET status = ?, error_message = ?, completed_at = ? WHERE job_id = ?",
                ("Failed", error_message, now_str, job_id),
            )

            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def check_and_update_job_completion(job_id: str, stp: bool = False) -> bool:
        """Check if ALL pages for the job have been processed (Completed or Marked as Invalid).

        Returns True if the job was fully processed, False otherwise.
        If all pages are done, sets processing_jobs.status to the appropriate value:
          - 'completed' if all pages are Completed
          - 'marked_as_invalid' if any page was Marked as Invalid
        Also sets completed_at timestamp.

        `stp` flags Straight-Through Processing: pass True (auto-completion, e.g. from
        process_upload after the pipeline auto-extracted every group) so the stored
        `stp` column becomes 1; leave False (manual completion, e.g. from submit_page /
        mark_page_invalid) so it stays 0.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            log_db_transaction("HistoryRepository.check_and_update_job_completion", {"job_id": job_id, "stp": stp})

            # Count total pages, done pages, and pages marked as invalid
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_pages,
                    SUM(CASE WHEN status IN ('Completed', 'Marked as Invalid') THEN 1 ELSE 0 END) AS done_pages,
                    SUM(CASE WHEN status = 'Marked as Invalid' THEN 1 ELSE 0 END) AS invalid_pages
                FROM dbo.job_pages
                WHERE job_id = ?
                """,
                (job_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False

            total_pages = row[0] or 0
            done_pages = row[1] or 0
            invalid_pages = row[2] or 0

            if total_pages > 0 and done_pages >= total_pages:
                from datetime import datetime, timezone, timedelta
                IST = timezone(timedelta(hours=5, minutes=30))
                now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

                # Always set status to completed regardless of invalid pages
                final_status = "completed"

                cursor.execute(
                    "UPDATE dbo.processing_jobs SET status = ?, stp = ?, completed_at = ? WHERE job_id = ?",
                    (final_status, 1 if stp else 0, now_str, job_id),
                )
                conn.commit()
                return True

            return False
        finally:
            conn.close()


    @staticmethod
    def get_page_status(job_id: str, page_number: int) -> Optional[str]:
        """Get the status of a specific page."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status FROM dbo.job_pages WHERE job_id = ? AND page_number = ?",
                (job_id, page_number),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    @staticmethod
    def handle_disconnect(job_id: str) -> None:
        """Clean up DB records after a client disconnect.

        Deletes all job_pages records for the job and sets the
        processing_jobs status to 'cancelled' with a completed_at timestamp.
        Preserves the job_id and all other job metadata.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            from datetime import datetime, timezone, timedelta
            IST = timezone(timedelta(hours=5, minutes=30))
            now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

            log_db_transaction("HistoryRepository.handle_disconnect", {"job_id": job_id})

            # Delete all job_pages records for this job
            cursor.execute(
                "DELETE FROM dbo.job_pages WHERE job_id = ?",
                (job_id,),
            )

            # Update processing_jobs status to cancelled with completed_at
            cursor.execute(
                "UPDATE dbo.processing_jobs SET status = ?, stp = ?, completed_at = ? WHERE job_id = ?",
                ("cancelled", 0, now_str, job_id),
            )

            conn.commit()
        finally:
            conn.close()
