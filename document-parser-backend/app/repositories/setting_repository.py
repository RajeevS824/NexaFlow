"""
setting_repository.py — CRUD operations for the SettingConfig table.

Maps to the dbo.SettingConfig schema:
    setting_id       UNIQUEIDENTIFIER PK
    user_id          UNIQUEIDENTIFIER FK (no FK to a users table — the
                     Document Parser no longer owns a users table; the
                     nexaflow user id is stored as an integer)
    log_path         NVARCHAR(500)
    log_type         NVARCHAR(20)   (INFO / DEBUG / ERROR)
    checked          BIT
    file_max_size_mb INT
    OutputBasePath   NVARCHAR(500)  (default C:\\Users)
    created_at       DATETIME2
    updated_at       DATETIME2
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))

from app.database.connection import get_connection


class SettingRepository:

    # ------------------------------------------------------------------
    # GET by user_id
    # ------------------------------------------------------------------
    @staticmethod
    def get_by_user_id(user_id: str) -> Optional[dict]:
        """Return the SettingConfig row for *user_id*, or None."""
        sql = """
            SELECT
                setting_id,
                user_id,
                log_path,
                log_type,
                checked,
                file_max_size_mb,
                OutputBasePath,
                created_at,
                updated_at
            FROM dbo.SettingConfig
            WHERE user_id = ?
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (user_id,))
            row = cursor.fetchone()

        if not row:
            return None

        return SettingRepository._row_to_dict(row)

    @staticmethod
    def _row_to_dict(row) -> dict:
        return {
            "setting_id":       str(row.setting_id),
            "user_id":          str(row.user_id),
            "log_path":         row.log_path,
            "log_type":         row.log_type,
            "checked":          bool(row.checked),
            "file_max_size_mb": row.file_max_size_mb,
            "output_base_path": row.OutputBasePath if hasattr(row, "OutputBasePath") else "C:\\Users",
            "created_at":       row.created_at.isoformat() if row.created_at else None,
            "updated_at":       row.updated_at.isoformat() if row.updated_at else None,
        }

    # ------------------------------------------------------------------
    # GET-OR-CREATE (insert default values when the user has no row)
    # ------------------------------------------------------------------
    @staticmethod
    def get_or_create(user_id: str) -> dict:
        """Return the SettingConfig row for *user_id*.

        If the user does not have a SettingConfig row yet, a default row is
        inserted (so the user can later update it) and then returned.
        No DB trigger is used — the default insert is done in app code.
        """
        existing = SettingRepository.get_by_user_id(user_id)
        if existing:
            return existing

        now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
        sql = """
            INSERT INTO dbo.SettingConfig
                (user_id, log_path, log_type, checked, file_max_size_mb, OutputBasePath, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            user_id,
            "C:\\Program Files\\ONG\\logs",
            "INFO",
            0,
            50,
            "C:\\Users",
            now,
        )
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()

        return SettingRepository.get_by_user_id(user_id)

    # ------------------------------------------------------------------
    # UPSERT (insert or update)
    # ------------------------------------------------------------------
    @staticmethod
    def upsert(user_id: str, data: dict) -> dict:
        """
        Insert a new row or update the existing one for *user_id*.

        Accepted keys in *data*:
            log_path         (str)
            log_type         (str)   — INFO / DEBUG / ERROR
            checked          (bool)
            file_max_size_mb (int)
            output_base_path (str)   — default C:\\Users
        """
        # Store IST (India Standard Time, UTC+05:30) instead of naive UTC
        now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

        sql = """
            MERGE dbo.SettingConfig AS target
            USING (SELECT ? AS user_id) AS source
            ON target.user_id = source.user_id
            WHEN MATCHED THEN
                UPDATE SET
                    log_path         = ?,
                    log_type         = ?,
                    checked          = ?,
                    file_max_size_mb = ?,
                    OutputBasePath   = ?,
                    updated_at       = ?
            WHEN NOT MATCHED THEN
                INSERT (user_id, log_path, log_type, checked, file_max_size_mb, OutputBasePath, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
        """

        log_path         = data.get("log_path", "C:\\Program Files\\ONG\\logs")
        log_type         = data.get("log_type", "INFO").upper()
        checked          = 1 if data.get("checked", False) else 0
        file_max_size_mb = int(data.get("file_max_size_mb", 50))
        output_base_path = data.get("output_base_path", "C:\\Users")

        params = (
            user_id,                # source
            log_path,               # SET log_path
            log_type,               # SET log_type
            checked,                # SET checked
            file_max_size_mb,       # SET file_max_size_mb
            output_base_path,       # SET OutputBasePath
            now,                    # SET updated_at
            user_id,                # INSERT user_id
            log_path,               # INSERT log_path
            log_type,               # INSERT log_type
            checked,                # INSERT checked
            file_max_size_mb,       # INSERT file_max_size_mb
            output_base_path,       # INSERT OutputBasePath
            now,                    # INSERT updated_at
        )

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()

        # Return the freshly-upserted row
        return SettingRepository.get_by_user_id(user_id)
