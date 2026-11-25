"""
database.py — Database bootstrap / schema initialisation helper.

Responsibilities
----------------
1. Ensure the target SQL Server database exists (creates it if not).
2. Execute every T-SQL batch in schema.sql against that database.

NOTE: No seed user is inserted anymore. User identity now comes from the
NexaFlow RBAC backend (nexaflow-backend), whose user IDs are integers. The
Document Parser backend scopes all data by the currently logged-in user id
(see app.core.global_state).

This module purposely contains NO business logic — only DDL concerns.
"""
import os
import re
from pathlib import Path
from typing import Optional

import pyodbc

from app.database.connection import build_connection_string, DEFAULT_NAME

BASE_DIR    = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _get_raw_connection(database: Optional[str] = None, autocommit: bool = False) -> pyodbc.Connection:
    """Return a low-level pyodbc connection (bypasses the normal DEFAULT_NAME env)."""
    return pyodbc.connect(build_connection_string(database), autocommit=autocommit)


def _ensure_database_exists(db_name: str) -> None:
    """Create the database on the SQL Server instance if it does not yet exist."""
    conn = _get_raw_connection("master", autocommit=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sys.databases WHERE name = ?", db_name)
        if not cursor.fetchone():
            cursor.execute(f"CREATE DATABASE [{db_name}]")
    finally:
        conn.close()


def _run_schema_script(db_name: str) -> None:
    """Parse schema.sql into GO-separated batches and execute each one."""
    if not SCHEMA_PATH.exists():
        return

    sql_script = SCHEMA_PATH.read_text(encoding="utf-8")
    batches = [b.strip() for b in re.split(r"\s*GO\s*", sql_script) if b and b.strip()]

    conn = _get_raw_connection(db_name)
    try:
        cursor = conn.cursor()

        for batch in batches:
            # Strip blank lines and comment-only lines
            cleaned_lines = [
                line for line in batch.splitlines()
                if line.strip() and not line.strip().startswith("--")
            ]
            cleaned = "\n".join(cleaned_lines).strip()
            if not cleaned:
                continue

            first_keyword = cleaned.split()[0].lower()
            allowed = ("create", "insert", "alter", "update", "delete",
                       "with", "set", "declare", "exec")
            if not any(first_keyword.startswith(kw) for kw in allowed):
                continue

            try:
                cursor.execute(cleaned)
            except pyodbc.Error as exc:
                msg = str(exc).lower()
                ignorable = (
                    "already exists",
                    "already an object named",
                    "there is already an object named",
                    "does not exist",
                    "is not a recognized",
                    "incorrect syntax near",
                )
                if any(tok in msg for tok in ignorable):
                    continue
                raise

        conn.commit()
    finally:
        conn.close()


def _seed_default_user(db_name: str) -> None:
    """No-op placeholder retained for backward compatibility.

    The `users` table has been removed from the schema. User identity is now
    supplied by the NexaFlow RBAC backend, so there is nothing to seed here.
    """
    return


# ============================================================
# PUBLIC API
# ============================================================

def init_db() -> None:
    """Bootstrap the database: create DB → apply schema."""
    db_name = os.getenv("TABLEDOC_DB_NAME", DEFAULT_NAME)
    _ensure_database_exists(db_name)
    _run_schema_script(db_name)
