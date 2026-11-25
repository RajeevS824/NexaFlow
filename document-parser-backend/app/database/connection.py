import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pyodbc

_conn_logger = logging.getLogger("document_pipeline")


# ============================================================
# CONNECTION SETTINGS  (all overridable via environment vars)
# ============================================================
# These read the SAME shared, unprefixed variable names as the NexaFlow
# backend (DB_SERVER, DB_USER, DB_PASSWORD, DB_DRIVER, DB_USE_WINDOWS_AUTH)
# from the one global .env file at the workspace root, so both products
# always point at the same SQL Server instance and login by construction.
# Only the database name differs per product (PRODUCT_DB_NAME here vs
# NEXAFLOW_DB_NAME for the other service).
#
# NOTE: there is no hardcoded server/username/password fallback here on
# purpose. If DB_PASSWORD isn't set, connections will fail loudly instead
# of silently succeeding against a guessable default credential.

DEFAULT_SERVER   = os.getenv("DB_SERVER", "localhost\\SQLEXPRESS")
DEFAULT_USER     = os.getenv("DB_USER", "")
DEFAULT_PASSWORD = os.getenv("DB_PASSWORD", "")
DEFAULT_NAME     = os.getenv("PRODUCT_DB_NAME", "OnenextgenProductDB")
DEFAULT_DRIVER   = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
USE_WINDOWS_AUTH = os.getenv("DB_USE_WINDOWS_AUTH", "false").lower() in ("true", "1", "yes")
CONNECTION_TIMEOUT_SECONDS = int(os.getenv("DB_TIMEOUT", "10"))
LOG_FILE = Path(__file__).resolve().parents[2] / "database" / "database.log"

if not USE_WINDOWS_AUTH and not DEFAULT_PASSWORD:
    _conn_logger.warning(
        "DB_PASSWORD is not set and DB_USE_WINDOWS_AUTH is not enabled. "
        "Set both in the shared .env before starting this service, or "
        "connections to %s will fail.", DEFAULT_SERVER,
    )


# ============================================================
# HELPERS
# ============================================================

def build_connection_string(database: Optional[str] = None) -> str:
    """Return a pyodbc connection string for *database* (defaults to DEFAULT_NAME)."""
    db_name = database or DEFAULT_NAME

    if USE_WINDOWS_AUTH:
        return (
            f"DRIVER={{{DEFAULT_DRIVER}}};"
            f"SERVER={DEFAULT_SERVER};"
            f"DATABASE={db_name};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
            "Encrypt=no;"
        )

    return (
        f"DRIVER={{{DEFAULT_DRIVER}}};"
        f"SERVER={DEFAULT_SERVER};"
        f"DATABASE={db_name};"
        f"UID={DEFAULT_USER};"
        f"PWD={DEFAULT_PASSWORD};"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )


def _append_db_log(message: str) -> None:
    """Append a database transaction trace entry to the backend log file."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def log_db_transaction(method_name: str, request_data: Optional[dict] = None, response_data: Optional[dict] = None) -> None:
    """Write a structured trace line for a database operation."""
    request_preview = request_data if request_data is not None else {}
    response_preview = response_data if response_data is not None else {}
    _append_db_log(
        f"method={method_name} request={request_preview} response={response_preview}"
    )


def get_connection(database: Optional[str] = None) -> pyodbc.Connection:
    """Open and return a new pyodbc connection.

    The caller is responsible for closing the connection (use a try/finally or
    a context manager).  Each repository method opens its own short-lived
    connection so we stay stateless and thread-safe without a connection pool.
    A connection timeout is set so a down/unreachable DB fails fast with a
    clear error instead of hanging the request indefinitely.
    """
    _append_db_log(f"method=get_connection database={database or DEFAULT_NAME}")
    try:
        return pyodbc.connect(
            build_connection_string(database or DEFAULT_NAME),
            timeout=CONNECTION_TIMEOUT_SECONDS,
        )
    except pyodbc.Error:
        _conn_logger.exception("Failed to connect to database %s", database or DEFAULT_NAME)
        raise
