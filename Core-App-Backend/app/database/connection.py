"""
app/database/connection.py
-----------------------------------------------
Database connection helpers.

* get_connection()           -> PostgreSQL (psycopg2). Used by everything in
                                Core-App-Backend (the NexaFlow database) and by
                                the Business Map analytics read.
* get_sqlserver_connection() -> SQL Server (pyodbc). Used ONLY for the one read
                                of the Document Parser database in
                                analytics_repository.get_document_parser_stats.
                                Document Parser itself stays on SQL Server.

Identifier case: every table / column is created UNQUOTED in schema.sql, so
PostgreSQL stores it lower-case and the CamelCase names used in the SQL
strings (OrgID, RoleName, ...) keep working unchanged. The one exception is the
reserved word User, which is always written as "user" (quoted). For the same
reason PostgreSQL *database* names are used lower-case (see pg_database_name).
"""
import psycopg2

try:  # pyodbc is only needed for the Document Parser read in analytics
    import pyodbc
except ImportError:  # pragma: no cover - SQL Server driver not installed
    pyodbc = None

from app.core.config import (
    DB_DRIVER,
    DB_NAME,
    DB_PASSWORD,
    DB_SERVER,
    DB_TIMEOUT,
    DB_USER,
    DB_USE_WINDOWS_AUTH,
    PG_CONNECT_TIMEOUT,
    PG_HOST,
    PG_PASSWORD,
    PG_PORT,
    PG_USER,
)

# Errors that mean "SQL Server could not be used" (driver missing, server down,
# bad query). Analytics catches these and returns None, as before.
SQLSERVER_ERRORS = (pyodbc.Error, RuntimeError) if pyodbc is not None else (RuntimeError,)


# ------------------------------------------------------------------
# PostgreSQL
# ------------------------------------------------------------------

def pg_database_name(database: str | None = None) -> str:
    """Return the PostgreSQL database name for a configured name.

    PostgreSQL folds unquoted names to lower case (pgAdmin shows them that
    way), so e.g. ``onenextgenBusinessMapDB`` is used - and created - as
    ``onenextgenbusinessmapdb``.
    """
    return (database or DB_NAME).lower()


def get_connection(database: str | None = None, autocommit: bool = False):
    """Open and return a new PostgreSQL connection (psycopg2).

    The caller is responsible for closing the connection (use a try/finally).
    Each repository method opens its own short-lived connection so we stay
    stateless and thread-safe without a connection pool. ``autocommit=True`` is
    needed for CREATE DATABASE, which PostgreSQL cannot run in a transaction.
    """
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=pg_database_name(database),
        connect_timeout=PG_CONNECT_TIMEOUT,
    )
    conn.autocommit = autocommit
    return conn


# ------------------------------------------------------------------
# SQL Server - Document Parser read only
# ------------------------------------------------------------------

def build_connection_string(database: str | None = None) -> str:
    """Return a pyodbc connection string for *database* (defaults to DB_NAME)."""
    db_name = database or DB_NAME

    if DB_USE_WINDOWS_AUTH:
        return (
            f"DRIVER={{{DB_DRIVER}}};"
            f"SERVER={DB_SERVER};"
            f"DATABASE={db_name};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
            "Encrypt=no;"
        )

    return (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={db_name};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )


def get_sqlserver_connection(database: str | None = None):
    """Open and return a new pyodbc connection to SQL Server.

    Only used for the Document Parser analytics read. The caller closes it.
    """
    if pyodbc is None:
        raise RuntimeError("pyodbc is not installed; cannot read the Document Parser (SQL Server) database.")
    return pyodbc.connect(
        build_connection_string(database or DB_NAME),
        timeout=DB_TIMEOUT,
    )
