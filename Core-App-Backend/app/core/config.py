"""
app/core/config.py
-----------------------------------------------
Central configuration for the NexaFlow RBAC backend.
All values are overridable via environment variables.

This backend and the Document Parser backend both read from ONE shared
`.env` file at the project root (see the comment block at the top of
that file). To make that actually work, the variable names read here
MUST match the names written in the shared file -- so this reads the
unprefixed names (DB_SERVER, DB_USER, ...) instead of NEXAFLOW_-prefixed
ones. A NEXAFLOW_-prefixed override is still honoured first for anyone
who wants to point *just* this service at a different value without
touching the shared file.
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger("uvicorn")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _env(primary: str, *fallbacks: str, default: str = "") -> str:
    """Return the first set environment variable among an optional
    NEXAFLOW_-prefixed override and the shared unprefixed name(s)."""
    for name in (primary, *fallbacks):
        value = os.getenv(name)
        if value is not None:
            return value
    return default


# ---- Database (MS SQL Server) ----
# Document Parser stays on SQL Server, and this backend still reads ITS
# database once (analytics). These variables keep their names, defaults and
# meaning - they are only used for that one read now.
DB_SERVER = _env("NEXAFLOW_DB_SERVER", "DB_SERVER", default="")
DB_NAME = _env("NEXAFLOW_DB_NAME", "NEXAFLOW_DB_NAME", default="")
DB_DRIVER = _env("NEXAFLOW_DB_DRIVER", "DB_DRIVER", default="")
DB_USER = _env("NEXAFLOW_DB_USER", "DB_USER", default="")
DB_PASSWORD = _env("NEXAFLOW_DB_PASSWORD", "DB_PASSWORD", default="")
DB_USE_WINDOWS_AUTH = _env("NEXAFLOW_DB_USE_WINDOWS_AUTH", "DB_USE_WINDOWS_AUTH", default="false").lower() in ("true", "1", "yes")
DB_TIMEOUT = int(_env("NEXAFLOW_DB_TIMEOUT", "DB_TIMEOUT", default="10"))

if not DB_USE_WINDOWS_AUTH and not DB_PASSWORD:
    logger.warning(
        "DB_PASSWORD is not set. Add it to the shared .env at the project "
        "root (see .env.example) -- falling back to an empty password will "
        "fail to connect to SQL Server."
    )

# ---- Database (PostgreSQL) ----
# NexaFlow's own database (NEXAFLOW_DB_NAME above) and the Business Map
# database (BUSINESSMAP_DB_NAME below) live on PostgreSQL. Both are created
# automatically on first start if they do not exist (database/init_db.py for
# NexaFlow, Business Map's database.py for its own).
PG_HOST = _env("NEXAFLOW_PG_HOST", "PG_HOST", default="localhost")
PG_PORT = int(_env("NEXAFLOW_PG_PORT", "PG_PORT", default="5432"))
PG_USER = _env("NEXAFLOW_PG_USER", "PG_USER", default="postgres")
PG_PASSWORD = _env("NEXAFLOW_PG_PASSWORD", "PG_PASSWORD", default="")
PG_CONNECT_TIMEOUT = int(_env("NEXAFLOW_PG_CONNECT_TIMEOUT", "PG_CONNECT_TIMEOUT", default="10"))

# ---- Other products' databases ----
# Used by app/repositories/analytics_repository.py to pull real, live usage
# numbers for the Admin Panel dashboard.
#   PRODUCT_DB_NAME     - Document Parser's database (SQL Server, read through
#                         the DB_* settings above).
#   BUSINESSMAP_DB_NAME - Business Map's database (PostgreSQL). Business Map
#                         reads the SAME variable, so both sides point at one
#                         database. DB_SCHEMA is the schema holding Business
#                         Map's tables (also the same variable Business Map
#                         reads); "public" is PostgreSQL's default schema.
PRODUCT_DB_NAME = os.getenv("PRODUCT_DB_NAME", "OnenextgenProductDB")
BUSINESSMAP_DB_NAME = os.getenv("BUSINESSMAP_DB_NAME", "suppi_db")
BUSINESSMAP_DB_SCHEMA = _env("NEXAFLOW_BUSINESSMAP_DB_SCHEMA", "DB_SCHEMA", default="public") or "public"

# ---- Security ----
# WARNING: For production, always set these via environment variables.
JWT_SECRET_KEY = _env("NEXAFLOW_JWT_SECRET", "JWT_SECRET_KEY", default="nexaflow-super-secret-change-me-in-production")
JWT_ALGORITHM = _env("NEXAFLOW_JWT_ALGORITHM", "JWT_ALGORITHM", default="HS256")
JWT_EXPIRE_MINUTES = int(_env("NEXAFLOW_JWT_EXPIRE_MINUTES", "JWT_EXPIRE_MINUTES", default="480"))  # 8 hours

if JWT_SECRET_KEY == "nexaflow-super-secret-change-me-in-production":
    logger.warning(
        "JWT_SECRET_KEY is still the sample value from .env.example. Set a "
        "unique, random JWT_SECRET_KEY in the shared .env before deploying "
        "(generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
    )

# ---- CORS ----
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in _env(
        "NEXAFLOW_ALLOWED_ORIGINS",
        "ALLOWED_ORIGINS",
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
    ).split(",")
    if origin.strip()
]

# ---- API ----
API_PREFIX = "/api"

# ---- Frontend (used to build links sent in emails) ----
FRONTEND_BASE_URL = os.getenv("NEXAFLOW_FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")

# ---- Password reset ----
RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("NEXAFLOW_RESET_TOKEN_EXPIRE_MINUTES", "10"))

# ---- SMTP / Email ----
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_SECURE = os.getenv("SMTP_SECURE", "false").lower() in ("true", "1", "yes")  # True = implicit SSL (port 465)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "OneNextGen Automation")
MAIL_FROM_EMAIL = os.getenv("MAIL_FROM_EMAIL", SMTP_USER)

# Inbox that "Contact us" / "Request a demo" submissions are forwarded to.
# Defaults to the same Gmail account used to send them (and the one used
# for password-reset emails) so nothing extra needs configuring.
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", MAIL_FROM_EMAIL)