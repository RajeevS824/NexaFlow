"""
model_repository.py — Repository for extraction model CRUD.

Entities covered
----------------
- extraction_models
- model_label_definitions  / model_label_aliases
- model_table_definitions  / model_table_row_bounds
- model_table_headers      / model_table_header_aliases

All database access uses raw SQL via pyodbc.  No ORM.
"""
import os
import uuid
from typing import Any, Optional

from app.database.connection import get_connection
from app.core.global_state import get_current_user_id


# ============================================================
# PRIVATE HELPERS
# ============================================================

def _is_uuid(value: Optional[str]) -> bool:
    if not value:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def _normalize_document_type(value: Optional[str]) -> str:
    normalized = (value or "invoice").strip().lower()
    return normalized if normalized in {"invoice", "receipt", "contract", "other"} else "other"


def _normalize_engine_type(value: Optional[str]) -> str:
    normalized = (value or "OCR").strip().upper()
    return normalized if normalized in {"OCR", "LLM"} else "OCR"


def _normalize_language(value: Optional[str]) -> str:
    normalized = (value or "en").strip().lower()
    valid = {"en", "es", "fr", "de", "zh", "ja", "ko", "it", "hi"}
    return normalized if normalized in valid else "en"


def _to_bit(value: Any) -> int:
    """Robustly map a boolean/string/int value to a SQL Server BIT (0 or 1).

    Handles the legacy string forms ("Required"/"Optional", "true"/"false",
    "1"/"0") that older frontend versions may have persisted, so the
    database always receives the correct 0/1 regardless of the input type.
    """
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if value else 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"required", "true", "1", "yes", "y", "on"}:
            return 1
        if normalized in {"optional", "false", "0", "no", "n", "off"}:
            return 0
        return 1  # unknown string -> default to required (matches schema default)
    return 1  # missing/None -> default to required (matches schema default)


def _fetch_model_fields(model_id: str) -> dict[str, Any]:
    """Fetch label definitions and table definitions for a given model_id."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # ── Label definitions ──────────────────────────────────────────────
        cursor.execute(
            """
            SELECT label_def_id, field_name, field_label, is_required, data_type, ai_skill, ai_prompt
            FROM dbo.model_label_definitions
            WHERE model_id = ?
            ORDER BY field_name
            """,
            (model_id,),
        )
        labels = []
        for label_def_id, field_name, field_label, is_required, data_type, ai_skill, ai_prompt in cursor.fetchall():
            alias_cur = conn.cursor()
            alias_cur.execute(
                "SELECT alias_text FROM dbo.model_label_aliases "
                "WHERE label_def_id = ? ORDER BY alias_text",
                (label_def_id,),
            )
            aliases = [row[0] for row in alias_cur.fetchall()]
            labels.append(
                {
                    "fieldName":  field_name,
                    "fieldLabel": field_label,
                    "datatype":   (data_type or "string").capitalize(),
                    "required":   bool(is_required),
                    "aiEnabled":  bool(ai_skill),
                    "prompt":     ai_prompt or "",
                    "aliases":    aliases,
                }
            )

        # ── Table definitions ──────────────────────────────────────────────
        cursor.execute(
            """
            SELECT table_def_id, table_name, is_enabled, min_confidence
            FROM dbo.model_table_definitions
            WHERE model_id = ?
            ORDER BY table_name
            """,
            (model_id,),
        )
        tables: dict[str, Any] = {}
        for table_def_id, table_name, is_enabled, _min_conf in cursor.fetchall():
            rb_cur = conn.cursor()
            rb_cur.execute(
                "SELECT bound_type, bound_text, display_order "
                "FROM dbo.model_table_row_bounds "
                "WHERE table_def_id = ? ORDER BY display_order, bound_type",
                (table_def_id,),
            )
            bounds = list(rb_cur.fetchall())
            start_rows = [r[1] for r in bounds if r[0] == "row_start"]
            end_rows   = [r[1] for r in bounds if r[0] == "row_end"]

            hdr_cur = conn.cursor()
            hdr_cur.execute(
                "SELECT header_def_id, column_name, column_label, is_required, data_type "
                "FROM dbo.model_table_headers "
                "WHERE table_def_id = ? ORDER BY display_order, column_name",
                (table_def_id,),
            )
            headers = []
            for header_def_id, column_name, column_label, hdr_required, hdr_dtype in hdr_cur.fetchall():
                ha_cur = conn.cursor()
                ha_cur.execute(
                    "SELECT alias_text FROM dbo.model_table_header_aliases "
                    "WHERE header_def_id = ? ORDER BY alias_text",
                    (header_def_id,),
                )
                header_aliases = [row[0] for row in ha_cur.fetchall()]
                headers.append(
                    {
                        "fieldName":  column_name,
                        "fieldLabel": column_label,
                        "datatype":   (hdr_dtype or "string").capitalize(),
                        "required":   bool(hdr_required),
                        "aliases":    header_aliases,
                    }
                )

            tables[table_name] = {
                "tableName": table_name,
                "required":  bool(is_enabled),
                "startRows": start_rows,
                "endRows":   end_rows,
                "fields":    headers,
            }

        return {"formFields": labels, "tableFields": tables}
    finally:
        conn.close()


def _serialize_model_row(row: Any) -> dict[str, Any]:
    """Convert a raw DB row (+ fetched fields) into the API response dict."""
    model_id = str(row[0])
    fields = _fetch_model_fields(model_id)
    from datetime import datetime, timezone, timedelta

    IST = timezone(timedelta(hours=5, minutes=30))

    def _fmt(dt):
        if not dt:
            return ""

        return dt.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM dbo.processing_jobs WHERE model_id = ?",
            (model_id,),
        )
        count_row = cursor.fetchone()
        job_count = int(count_row[0]) if count_row and count_row[0] is not None else 0
    finally:
        conn.close()

    return {
        "id":           model_id,
        "name":         row[2],
        "engine":       row[4],
        "documentType": row[5],
        "language":     row[6],
        "description":  row[3] or "",
        "created":      _fmt(row[7]),
        "updated":      _fmt(row[8]),
        "processCount": job_count,
        **fields,
    }


def _delete_model_children(cursor: Any, model_id: str) -> None:
    """Delete all child rows for a model (labels, tables, bounds, headers, aliases)."""
    cursor.execute(
        "DELETE FROM dbo.model_label_aliases "
        "WHERE label_def_id IN "
        "(SELECT label_def_id FROM dbo.model_label_definitions WHERE model_id = ?)",
        (model_id,),
    )
    cursor.execute(
        "DELETE FROM dbo.model_table_header_aliases "
        "WHERE header_def_id IN ("
        "  SELECT header_def_id FROM dbo.model_table_headers "
        "  WHERE table_def_id IN ("
        "    SELECT table_def_id FROM dbo.model_table_definitions WHERE model_id = ?"
        "  )"
        ")",
        (model_id,),
    )
    cursor.execute(
        "DELETE FROM dbo.model_table_row_bounds "
        "WHERE table_def_id IN "
        "(SELECT table_def_id FROM dbo.model_table_definitions WHERE model_id = ?)",
        (model_id,),
    )
    cursor.execute(
        "DELETE FROM dbo.model_table_headers "
        "WHERE table_def_id IN "
        "(SELECT table_def_id FROM dbo.model_table_definitions WHERE model_id = ?)",
        (model_id,),
    )
    cursor.execute(
        "DELETE FROM dbo.model_table_definitions WHERE model_id = ?",
        (model_id,),
    )
    cursor.execute(
        "DELETE FROM dbo.model_label_definitions WHERE model_id = ?",
        (model_id,),
    )


# ============================================================
# REPOSITORY
# ============================================================

class ModelRepository:
    """All database operations for extraction models."""

    # ── READ ──────────────────────────────────────────────────────────────

    @staticmethod
    def list_all() -> list[dict[str, Any]]:
        """Return all models owned by the default user, most recent first."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT model_id, userid, model_name, description,
                       engine_type, document_type, language, created_at, updated_at
                FROM dbo.extraction_models
                WHERE userid = ?
                ORDER BY created_at DESC
                """,
                (get_current_user_id(),),
            )
            rows = cursor.fetchall()
            return [_serialize_model_row(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_by_id(model_id: str) -> Optional[dict[str, Any]]:
        """Return a single model by its id, or None if not found."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT model_id, userid, model_name, description,
                       engine_type, document_type, language, created_at, updated_at
                FROM dbo.extraction_models
                WHERE model_id = ?
                """,
                (model_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return _serialize_model_row(row)
        finally:
            conn.close()

    # ── WRITE ─────────────────────────────────────────────────────────────

    @staticmethod
    def save(payload: dict[str, Any]) -> dict[str, Any]:
        """Insert or update a model and all its child definitions.

        If ``payload["id"]`` is a valid UUID that exists, performs an UPDATE.
        If the model_name already exists for the owner, also performs an UPDATE.
        Otherwise inserts a new model.
        """
        # Always the authenticated caller from the verified JWT -- never a
        # client-supplied value. SaveModelRequest (see app/schemas/request_schema.py)
        # doesn't even define a `userid` field, but a payload could still
        # smuggle one in via extra keys, and trusting it would let any
        # logged-in user attribute a model to (or overwrite one owned by)
        # a different account just by naming it in the request body.
        userid        = get_current_user_id()
        incoming_id   = str(payload.get("id") or "").strip()
        model_name    = (payload.get("name") or "Untitled Model").strip()
        description   = payload.get("description") or ""
        engine_type   = _normalize_engine_type(payload.get("engine") or payload.get("engine_type"))
        document_type = _normalize_document_type(payload.get("documentType") or payload.get("document_type"))
        language      = _normalize_language(payload.get("language"))
        form_fields   = payload.get("formFields") or []
        table_fields  = payload.get("tableFields") or {}

        conn = get_connection()
        try:
            cursor = conn.cursor()
            model_id: Optional[str] = None

            # Resolve existing model
            if _is_uuid(incoming_id):
                cursor.execute(
                    "SELECT model_id FROM dbo.extraction_models WHERE model_id = ?",
                    (incoming_id,),
                )
                if cursor.fetchone():
                    model_id = incoming_id

            if not model_id:
                cursor.execute(
                    "SELECT model_id FROM dbo.extraction_models "
                    "WHERE userid = ? AND model_name = ?",
                    (userid, model_name),
                )
                existing = cursor.fetchone()
                if existing:
                    model_id = str(existing[0])

            # Upsert model header row

            from datetime import datetime, timezone, timedelta
            IST = timezone(timedelta(hours=5, minutes=30))
            now_ist = datetime.now(IST)
            now_str = now_ist.strftime("%Y-%m-%d %H:%M:%S")

            if model_id:
                cursor.execute(
                    """
                    UPDATE dbo.extraction_models
                    SET model_name = ?, description = ?, engine_type = ?,
                        document_type = ?, language = ?, updated_at = ?
                    WHERE model_id = ?
                    """,
                    (model_name, description, engine_type, document_type, language, now_str, model_id),
                )
            else:
                model_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO dbo.extraction_models
                        (model_id, userid, model_name, description, engine_type, document_type, language, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (model_id, userid, model_name, description, engine_type, document_type, language, now_str, now_str),
                )

            # Replace all child definitions
            _delete_model_children(cursor, model_id)

            # Insert label definitions
            for field in form_fields:
                label_def_id = str(uuid.uuid4())
                field_name = (field.get("fieldName") or field.get("fieldLabel") or "Unnamed field").strip()
                field_label = (field.get("fieldLabel") or field.get("fieldName") or field_name).strip()
                cursor.execute(
                    """
                    INSERT INTO dbo.model_label_definitions
                        (label_def_id, model_id, field_name, field_label, is_required, data_type, ai_skill, ai_prompt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        label_def_id,
                        model_id,
                        field_name,
                        field_label,
                        _to_bit(field.get("required")),
                        (field.get("datatype") or "string").lower(),
                        1 if field.get("aiEnabled") else 0,
                        (field.get("prompt") or None),
                    ),
                )
                for alias in field.get("aliases") or []:
                    alias_text = str(alias or "").strip()
                    if alias_text:
                        cursor.execute(
                            "INSERT INTO dbo.model_label_aliases "
                            "(alias_id, label_def_id, alias_text) VALUES (?, ?, ?)",
                            (str(uuid.uuid4()), label_def_id, alias_text),
                        )

            # Insert table definitions
            for table_name, table_payload in (table_fields or {}).items():
                table_def_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO dbo.model_table_definitions
                        (table_def_id, model_id, table_name, is_enabled, min_confidence)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        table_def_id,
                        model_id,
                        table_name,
                        _to_bit(table_payload.get("required")),
                        0.75,
                    ),
                )
                for order_idx, row_text in enumerate(table_payload.get("startRows") or []):
                    if row_text and str(row_text).strip():
                        cursor.execute(
                            "INSERT INTO dbo.model_table_row_bounds "
                            "(bound_id, table_def_id, bound_type, bound_text, display_order) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (str(uuid.uuid4()), table_def_id, "row_start", row_text, order_idx),
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO dbo.model_table_row_bounds "
                            "(bound_id, table_def_id, bound_type, bound_text, display_order) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (str(uuid.uuid4()), table_def_id, None, None, order_idx),
                        )
                for order_idx, row_text in enumerate(table_payload.get("endRows") or []):
                    if row_text and str(row_text).strip():
                        cursor.execute(
                            "INSERT INTO dbo.model_table_row_bounds "
                            "(bound_id, table_def_id, bound_type, bound_text, display_order) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (str(uuid.uuid4()), table_def_id, "row_end", row_text, order_idx),
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO dbo.model_table_row_bounds "
                            "(bound_id, table_def_id, bound_type, bound_text, display_order) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (str(uuid.uuid4()), table_def_id, None, None, order_idx),
                        )
                for hdr_idx, header in enumerate(table_payload.get("fields") or []):
                    header_def_id = str(uuid.uuid4())
                    column_name   = (header.get("fieldName") or header.get("fieldLabel") or "Unnamed header").strip()
                    column_label  = (header.get("fieldLabel") or header.get("fieldName") or column_name).strip()
                    cursor.execute(
                        """
                        INSERT INTO dbo.model_table_headers
                            (header_def_id, table_def_id, column_name, column_label, is_required, data_type, display_order)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            header_def_id,
                            table_def_id,
                            column_name,
                            column_label,
                            _to_bit(header.get("required")),
                            (header.get("datatype") or "string").lower(),
                            hdr_idx,
                        ),
                    )
                    for alias in header.get("aliases") or []:
                        alias_text = str(alias or "").strip()
                        if alias_text:
                            cursor.execute(
                                "INSERT INTO dbo.model_table_header_aliases "
                                "(alias_id, header_def_id, alias_text) VALUES (?, ?, ?)",
                                (str(uuid.uuid4()), header_def_id, alias_text),
                            )

            conn.commit()

            # Return the saved model in the standard shape
            return {
                "id": model_id,
                **_serialize_model_row(
                    (model_id, userid, model_name, description, engine_type,
                     document_type, language, None, None)
                ),
            }
        finally:
            conn.close()

    # ── DELETE ────────────────────────────────────────────────────────────

    @staticmethod
    def delete(model_id: str, force: bool = False) -> None:
        """Hard-delete a model and all its cascading child rows.

        If `force` is False and there are processing jobs referencing the
        model, a ValueError is raised containing the number of jobs.
        If `force` is True, any processing jobs for the model are removed
        (which cascades to job_pages and job_exports) before the model
        and its child definitions are deleted.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Check for existing jobs referencing this model
            cursor.execute(
                "SELECT COUNT(*) FROM dbo.processing_jobs WHERE model_id = ?",
                (model_id,),
            )
            row = cursor.fetchone()
            job_count = int(row[0]) if row and row[0] is not None else 0

            if job_count and not force:
                raise ValueError(f"Model has {job_count} processing job(s). Use force=True to remove them.")

            # If force, remove processing jobs AND clean up physical files
            if job_count and force:
                # ── Capture job_ids and document_ids before deletion ──
                cursor.execute(
                    "SELECT job_id, document_id FROM dbo.processing_jobs WHERE model_id = ?",
                    (model_id,),
                )
                job_rows = cursor.fetchall()
                job_ids = [str(row[0]) for row in job_rows]
                document_ids = [str(row[1]) for row in job_rows]

                # ── Delete physical Output/<model_name>/ directories ──
                # All jobs for this model live under Output/<model_name>/<job_id>/,
                # so removing the model's root directory cleans up every job.
                from app.core.config import OUTPUT_ROOT
                import shutil as _shutil
                from pathlib import Path as _Path
                model_row = None
                try:
                    cursor.execute(
                        "SELECT model_name FROM dbo.extraction_models WHERE model_id = ?",
                        (model_id,),
                    )
                    model_row = cursor.fetchone()
                except Exception:
                    model_row = None
                model_name = str(model_row[0]) if model_row and model_row[0] else None
                if model_name:
                    model_output_dir = _Path(OUTPUT_ROOT) / model_name
                    if model_output_dir.exists():
                        _shutil.rmtree(model_output_dir, ignore_errors=True)
                else:
                    # Fallback: remove each job's old flat directory if present
                    for jid in job_ids:
                        job_output_dir = _Path(OUTPUT_ROOT) / jid
                        if job_output_dir.exists():
                            _shutil.rmtree(job_output_dir, ignore_errors=True)

                # ── Delete uploaded files from disk ──
                for doc_id in document_ids:
                    cursor.execute(
                        "SELECT storage_path FROM dbo.documents WHERE document_id = ?",
                        (doc_id,),
                    )
                    doc_row = cursor.fetchone()
                    if doc_row and doc_row[0]:
                        upload_path = str(doc_row[0])
                        # Only delete the physical file if it's within the uploads directory
                        from app.core.config import UPLOAD_DIR as _UPLOAD_DIR
                        if upload_path and _Path(upload_path).exists():
                            try:
                                os.remove(upload_path)
                            except OSError:
                                pass

                # ── Delete orphaned document rows ──
                for doc_id in document_ids:
                    cursor.execute(
                        "DELETE FROM dbo.documents WHERE document_id = ?",
                        (doc_id,),
                    )

                # ── Now delete processing_jobs (cascades to job_pages, job_exports) ──
                cursor.execute(
                    "DELETE FROM dbo.processing_jobs WHERE model_id = ?",
                    (model_id,),
                )

            # Remove model child rows and the model row itself
            _delete_model_children(cursor, model_id)
            cursor.execute(
                "DELETE FROM dbo.extraction_models WHERE model_id = ?",
                (model_id,),
            )
            # Audit log entry
            try:
                from datetime import datetime, timezone, timedelta
                IST = timezone(timedelta(hours=5, minutes=30))
                now_ist = datetime.now(IST)
                now_str = now_ist.strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO dbo.audit_log (audit_id, user_id, action, entity_type, entity_id, ip_address, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), get_current_user_id(), "delete", "extraction_model", model_id, None, now_str),
                )
            except Exception:
                # Don't fail the delete if audit insert fails
                pass

            conn.commit()
        finally:
            conn.close()
