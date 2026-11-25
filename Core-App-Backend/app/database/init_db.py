"""
app/database/init_db.py
-----------------------------------------------
Database bootstrap (PostgreSQL): ensure the database exists, apply schema.sql,
then run idempotent seed data (organization, products, licenses, admin).

* Database missing  -> created automatically.
* Database exists   -> reused.
* Tables missing    -> created; existing tables and data are kept.
* Seed rows         -> inserted only if missing (no duplicates).
"""
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from psycopg2 import errors, sql

from app.core.config import DB_NAME, PG_USER
from app.core.security import hash_password
from app.database.connection import get_connection, pg_database_name

logger = logging.getLogger("uvicorn")

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"

# Arbitrary constant used with pg_advisory_xact_lock so two instances that
# start at the same moment do not run schema.sql at the same time.
_SCHEMA_LOCK_KEY = 702150201

# ------------------------------------------------------------------
# Seed data
# ------------------------------------------------------------------
SEED_ORGANIZATION = {
    "name": "onenextgen",
    "slug": "onenextgen",
    "code": "ONG-001",
    "email": "onenextgen@gmail.com",
    "address": "Bengaluru",
    "country": "India",
    "state": "Karnataka",
    "city": "Bengaluru",
    "status": True,
}

SEED_PRODUCTS = [
    {"name": "Business Process Mapper", "code": "BPM", "description": "Turn screen recordings into SOPs", "version": "1.0"},
    {"name": "Nextflow", "code": "NXT", "description": "Visual workflow automation", "version": "1.0"},
    {"name": "Document Parser", "code": "DOC", "description": "Invoice document extraction", "version": "1.0"},
]

SEED_ADMIN = {
    "full_name": "one-admin",
    "email": "onenextgen@gmail.com",
    "password": "1234567890",
}


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _ensure_database_exists(db_name: str) -> None:
    """Create the PostgreSQL database if it does not yet exist.

    Connects to the maintenance database ``postgres`` with autocommit (CREATE
    DATABASE cannot run inside a transaction) and checks ``pg_database`` first.
    If the login is not allowed to create databases, a clear error is logged
    and raised; the server keeps running (main.py logs that initialization was
    skipped).
    """
    target = pg_database_name(db_name)
    conn = get_connection("postgres", autocommit=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target,))
        if cursor.fetchone():
            return
        try:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)))
            logger.info("Created PostgreSQL database %s", target)
        except errors.DuplicateDatabase:
            pass  # another instance created it between the check and now
        except errors.InsufficientPrivilege as exc:
            message = (
                f"PostgreSQL login '{PG_USER}' is not allowed to create database '{target}'. "
                f"Create it once as a superuser (CREATE DATABASE {target};) or grant that login "
                f"the CREATEDB privilege, then restart."
            )
            logger.error(message)
            raise RuntimeError(message) from exc
    finally:
        conn.close()


def _run_schema_script(db_name: str) -> None:
    """Execute schema.sql (idempotent: CREATE TABLE IF NOT EXISTS ...)."""
    if not SCHEMA_PATH.exists():
        return

    sql_script = SCHEMA_PATH.read_text(encoding="utf-8")

    conn = get_connection(db_name)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (_SCHEMA_LOCK_KEY,))
        cursor.execute(sql_script)
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------
# Seed helpers
# ------------------------------------------------------------------

def _seed_organization(conn) -> int:
    """Insert default Organization if missing. Returns OrgID."""
    cursor = conn.cursor()
    cursor.execute("SELECT OrgID FROM Organization WHERE CompanyCode = %s LIMIT 1", (SEED_ORGANIZATION["code"],))
    row = cursor.fetchone()
    if row:
        return int(row[0])

    cursor.execute(
        """
        INSERT INTO Organization
            (OrganizationName, OrganizationSlug, CompanyCode, Email, Address, Country, State, City, Status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (CompanyCode) DO NOTHING
        RETURNING OrgID
        """,
        (
            SEED_ORGANIZATION["name"],
            SEED_ORGANIZATION["slug"],
            SEED_ORGANIZATION["code"],
            SEED_ORGANIZATION["email"],
            SEED_ORGANIZATION["address"],
            SEED_ORGANIZATION["country"],
            SEED_ORGANIZATION["state"],
            SEED_ORGANIZATION["city"],
            bool(SEED_ORGANIZATION["status"]),
        ),
    )
    row = cursor.fetchone()
    if row is None:  # inserted by another instance in the meantime
        cursor.execute("SELECT OrgID FROM Organization WHERE CompanyCode = %s LIMIT 1", (SEED_ORGANIZATION["code"],))
        row = cursor.fetchone()
    conn.commit()
    return int(row[0])


def _seed_products(conn) -> dict:
    """Insert default products if missing. Returns {code: ProductID}."""
    cursor = conn.cursor()
    result = {}
    for product in SEED_PRODUCTS:
        cursor.execute(
            "SELECT ProductID FROM Product WHERE ProductCode = %s LIMIT 1",
            (product["code"],),
        )
        row = cursor.fetchone()
        if row:
            result[product["code"]] = int(row[0])
        else:
            cursor.execute(
                """
                INSERT INTO Product (ProductName, ProductCode, Description, Version, IsActive)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT (ProductCode) DO NOTHING
                RETURNING ProductID
                """,
                (product["name"], product["code"], product["description"], product["version"]),
            )
            row = cursor.fetchone()
            if row is None:  # inserted by another instance in the meantime
                cursor.execute("SELECT ProductID FROM Product WHERE ProductCode = %s LIMIT 1", (product["code"],))
                row = cursor.fetchone()
            result[product["code"]] = int(row[0])
    conn.commit()
    return result


def _seed_licenses(conn, org_id: int, product_ids: dict) -> None:
    """Ensure the org owns all 3 products."""
    cursor = conn.cursor()
    for code, product_id in product_ids.items():
        cursor.execute(
            "SELECT LicenseID FROM License WHERE OrgID = %s AND ProductID = %s LIMIT 1",
            (org_id, product_id),
        )
        if not cursor.fetchone():
            license_key = f"ONG-{code}-{org_id}-{product_id}-{date.today().year}"
            cursor.execute(
                """
                INSERT INTO License (LicenseKey, OrgID, ProductID, PurchaseDate, Status)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT DO NOTHING
                """,
                (license_key, org_id, product_id, date.today()),
            )
    conn.commit()


def _seed_admin(conn, org_id: int) -> None:
    """Insert default Admin (one-admin / onenextgen@gmail.com / 1234567890)."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT AdminID FROM Admin WHERE Email = %s LIMIT 1",
        (SEED_ADMIN["email"],),
    )
    if cursor.fetchone():
        return

    password_hash = hash_password(SEED_ADMIN["password"])
    cursor.execute(
        """
        INSERT INTO Admin (OrgID, FullName, Email, PasswordHash)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (Email) DO NOTHING
        """,
        (org_id, SEED_ADMIN["full_name"], SEED_ADMIN["email"], password_hash),
    )
    conn.commit()


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def init_db() -> None:
    """Bootstrap the database: create DB -> apply schema -> seed data."""
    _ensure_database_exists(DB_NAME)
    _run_schema_script(DB_NAME)

    conn = get_connection(DB_NAME)
    try:
        org_id = _seed_organization(conn)
        product_ids = _seed_products(conn)
        _seed_licenses(conn, org_id, product_ids)
        _seed_admin(conn, org_id)
        conn.commit()
    finally:
        conn.close()
