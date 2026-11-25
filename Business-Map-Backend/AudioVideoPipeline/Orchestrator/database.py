###############################################################
# ORCHESTRATOR — DATABASE LAYER (PostgreSQL)
#
# Replaces the in-memory-only JOBS dict in integrated_pipeline.py
# with durable storage, and adds a Users table so jobs can be
# attributed to whoever submitted them.
#
# Connection settings come from config.yaml's `database:` section,
# with the PG_* env vars (PG_HOST, PG_PORT, PG_USER, PG_PASSWORD) always
# overriding config.yaml — same pattern as EMAIL_SENDER_PASSWORD.
#
# On the first start the database is created automatically (if the
# PostgreSQL login may create databases); if it already exists it is
# reused, and only the missing schema/tables/columns are added.
###############################################################

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

# Load repo-root .env (if present) so DB_ENABLED/DB_SERVER/etc. are set
# correctly whether this module is imported as part of the running app
# (integrated_pipeline.py already loads .env before this would be
# imported) or on its own, e.g. for a standalone connection test.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, DateTime, ForeignKey, Text, Boolean, text,
)
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

logger = logging.getLogger("Database")

# ==================================================
# CONFIG (mirrors job_manager.py's _load_config pattern)
# ==================================================

_DEFAULT_CONFIG_PATH = str(
    Path(__file__).resolve().parent.parent / "Configuration" / "config.yaml"
)


def _load_config(path: str = None) -> dict:
    path = path or os.environ.get("CONFIG_PATH", _DEFAULT_CONFIG_PATH)
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Failed to load config from {path}: {e}")
        return {"database": {"enabled": False}}


_config = _load_config()
DB_CFG = _config.get("database", {}) or {}
LLM_CFG = _config.get("llm", {}) or {}
DEFAULT_LLM_PROVIDER = "openrouter"
DEFAULT_LLM_MODEL = (
    (LLM_CFG.get("primary", {}) or {}).get("model")
    or LLM_CFG.get("model")
    or "cohere/north-mini:free"
)

def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# Every setting below can be supplied via a local .env file (see
# .env.example at the repo root) — env vars always win over config.yaml,
# so the same config.yaml can be committed to git while real connection
# details/secrets stay only in the untracked .env file.
DB_ENABLED    = _env_bool("DB_ENABLED", bool(DB_CFG.get("enabled", False)))
# PostgreSQL connection. PG_* env vars win over config.yaml. The old SQL
# Server settings (DB_SERVER / DB_USERNAME / DB_PASSWORD / DB_DRIVER ...) are
# NOT used here any more — they belong to SQL Server, which only Document
# Parser still uses.
DB_SERVER     = os.environ.get("PG_HOST") or DB_CFG.get("server", "localhost")
DB_PORT       = int(os.environ.get("PG_PORT") or DB_CFG.get("port", 5432))
# Same variable Core-App-Backend reads (BUSINESSMAP_DB_NAME), so both always
# point at the same database. PostgreSQL folds unquoted names to lower case,
# so the name is used — and created — in lower case (same as Core).
DB_NAME       = (os.environ.get("BUSINESSMAP_DB_NAME") or DB_CFG.get("database", "suppi_db")).lower()
DB_USERNAME   = os.environ.get("PG_USER") or DB_CFG.get("username", "postgres")
# Environment variable ALWAYS wins over config.yaml — never commit a real
# database password.
DB_PASSWORD   = os.environ.get("PG_PASSWORD") or DB_CFG.get("password", "")
# The schema this app's tables live under. Core-App-Backend reads the same
# DB_SCHEMA variable (default "public") for its Business Map analytics, so
# keep both on the same value.
DB_SCHEMA     = os.environ.get("DB_SCHEMA") or DB_CFG.get("schema", "public")
DB_CONNECT_TIMEOUT = int(os.environ.get("PG_CONNECT_TIMEOUT") or DB_CFG.get("connect_timeout", 10))


def _build_connection_url(database: str = None) -> URL:
    """SQLAlchemy URL for *database* (defaults to the Business Map database)."""
    return URL.create(
        "postgresql+psycopg2",
        username=DB_USERNAME,
        password=DB_PASSWORD,
        host=DB_SERVER,
        port=DB_PORT,
        database=database or DB_NAME,
        query={"connect_timeout": str(DB_CONNECT_TIMEOUT)},
    )


def _quote_ident(name: str) -> str:
    """Quote a PostgreSQL identifier (schema / table / column name)."""
    return '"' + str(name).replace('"', '""') + '"'


# ==================================================
# ENGINE / SESSION
# ==================================================

Base = declarative_base()
engine = None
SessionLocal = None

if DB_ENABLED:
    try:
        engine = create_engine(_build_connection_url(), pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    except Exception as e:
        # A misconfigured/unreachable DB must never take the whole
        # orchestrator down — log and fall back to DB-disabled mode.
        # Every helper below already no-ops when SessionLocal is None.
        logger.error(f"Could not create database engine — DB persistence disabled: {e}")
        engine = None
        SessionLocal = None
else:
    logger.info("Database persistence disabled (database.enabled=false in config.yaml)")


# ==================================================
# MODELS
# ==================================================

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": DB_SCHEMA}

    id         = Column(Integer, primary_key=True, autoincrement=True)
    username   = Column(String(255), nullable=False, index=True)
    email      = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    jobs = relationship("Job", back_populates="user")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = {"schema": DB_SCHEMA}

    # job_id is the UUID string generated in integrated_pipeline.py —
    # reused as the primary key so DB rows line up 1:1 with JOBS entries.
    id            = Column(String(36), primary_key=True)
    job_name      = Column(String(500), nullable=True)
    user_id       = Column(Integer, ForeignKey(f"{DB_SCHEMA}.users.id"), nullable=True, index=True)

    status        = Column(String(50), nullable=False, default="QUEUED", index=True)
    phase         = Column(String(50), nullable=True)
    progress      = Column(Float, nullable=False, default=0)

    video_filename = Column(String(500), nullable=True)
    audio_filename = Column(String(500), nullable=True)
    video_size_bytes = Column(Integer, nullable=True)
    recipient_email = Column(String(255), nullable=True)

    error         = Column(Text, nullable=True)
    latency_sec   = Column(Float, nullable=True)

    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at  = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="jobs")


class UserLogSettings(Base):
    """
    Log Configuration (Settings page). `user_id` identifies a user in an
    EXTERNAL login system (a separate project), not necessarily a row in
    our own `users` table above — deliberately no ForeignKey to
    `users.id`, since that table is scoped to people who've submitted a
    video job through *this* app, an unrelated set of IDs.

    Currently used as a single shared settings row (user_id=1, see
    DEFAULT_SETTINGS_USER_ID in integrated_pipeline.py) since real
    per-user identification isn't wired up yet — the schema already
    supports true multi-user rows whenever that's ready, with no
    migration needed then either.
    """
    __tablename__ = "user_log_settings"
    __table_args__ = {"schema": DB_SCHEMA}

    id              = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(Integer, nullable=False, unique=True, index=True)
    log_level       = Column(String(20), nullable=False, default="DEBUG")
    log_folder_path = Column(String(500), nullable=False)
    enabled         = Column(Boolean, nullable=False, default=True)
    max_size_mb     = Column(Integer, nullable=False, default=50)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserLlmSettings(Base):
    """
    LLM Configuration (Settings page). Lets a user/customer choose between
    the application's default OpenRouter credentials or their own provider,
    model, and custom API key.

    Rows are keyed to the gateway-verified user ID and deliberately have no
    ForeignKey to `users.id`, which is owned by the external identity system.

    primary_api_key is stored ENCRYPTED at rest (see
    _encrypt_secret/_decrypt_secret below) — never plaintext, and never
    returned to the frontend (see llm_config_response() / mask_api_key()).
    """
    __tablename__ = "user_llm_settings"
    __table_args__ = {"schema": DB_SCHEMA}

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    user_id            = Column(Integer, nullable=False, unique=True, index=True)
    use_custom_key     = Column(Boolean, nullable=False, default=False)
    provider           = Column(String(32), nullable=False, default=DEFAULT_LLM_PROVIDER)
    model              = Column(String(255), nullable=True, default=DEFAULT_LLM_MODEL)
    # Encrypted ciphertext (or NULL if never configured).
    primary_api_key    = Column(Text, nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserUploadSettings(Base):
    """
    Maximum Upload File Size (Settings page) — separate limits for video
    and audio uploads. Same pattern as UserLogSettings above — single
    shared row for now (user_id=1, see DEFAULT_SETTINGS_USER_ID in
    integrated_pipeline.py), no FK to our own `users` table for the same
    reason (external identity source).
    """
    __tablename__ = "user_upload_settings"
    __table_args__ = {"schema": DB_SCHEMA}

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    user_id                  = Column(Integer, nullable=False, unique=True, index=True)
    max_upload_size_mb       = Column(Integer, nullable=False, default=500)  # video
    max_audio_upload_size_mb = Column(Integer, nullable=False, default=50)
    created_at               = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at               = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ==================================================
# INIT
# ==================================================

def _ensure_database_exists() -> None:
    """Create the Business Map database if it is missing; reuse it if it exists.

    Connects to the maintenance database ``postgres`` with autocommit (PostgreSQL
    cannot run CREATE DATABASE inside a transaction) and checks ``pg_database``
    first. If the login is not allowed to create databases, a clear error is
    raised (the caller logs it and falls back to in-memory job tracking).
    """
    admin_engine = create_engine(
        _build_connection_url("postgres"), isolation_level="AUTOCOMMIT", pool_pre_ping=True
    )
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": DB_NAME}
            ).scalar()
            if exists:
                logger.info(f"Database '{DB_NAME}' already exists — reusing it.")
                return
            try:
                conn.execute(text(f"CREATE DATABASE {_quote_ident(DB_NAME)}"))
            except Exception as e:
                raise RuntimeError(
                    f"PostgreSQL login '{DB_USERNAME}' could not create database '{DB_NAME}' "
                    f"({e}). Create it once as a superuser (CREATE DATABASE {DB_NAME};) or grant "
                    f"that login the CREATEDB permission."
                ) from e
            logger.info(f"Created database '{DB_NAME}'.")
    finally:
        admin_engine.dispose()


def init_db() -> None:
    """Create the database, schema and tables that don't exist yet. Safe to call on every startup."""
    if engine is None:
        logger.warning("init_db() skipped — no database engine configured.")
        return
    _ensure_database_exists()
    with engine.begin() as conn:
        conn.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {_quote_ident(DB_SCHEMA)}")
    logger.info(f"Ensured schema '{DB_SCHEMA}' exists.")
    Base.metadata.create_all(bind=engine)
    _migrate_add_missing_columns()
    logger.info("Database tables verified/created.")


def _migrate_add_missing_columns() -> None:
    """
    create_all() only creates tables that don't exist yet — it never
    alters an existing table to add a newly-added model column. This is
    a minimal, hand-rolled migration step for exactly that situation
    (e.g. video_size_bytes was added to the Job model after some
    databases already had a jobs table without it). Safe to call on
    every startup because each schema change is idempotent.
    """
    migrations = [
        ("jobs", "video_size_bytes", "BIGINT NULL"),
        ("user_log_settings", "enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("user_log_settings", "max_size_mb", "INTEGER NOT NULL DEFAULT 50"),
        ("user_upload_settings", "max_audio_upload_size_mb", "INTEGER NOT NULL DEFAULT 500"),
        ("user_llm_settings", "provider", "VARCHAR(32) NOT NULL DEFAULT 'openrouter'"),
        ("user_llm_settings", "model", "VARCHAR(255) NULL"),
    ]
    with engine.begin() as conn:
        for table, column, coltype in migrations:
            conn.exec_driver_sql(
                f"ALTER TABLE {_quote_ident(DB_SCHEMA)}.{_quote_ident(table)} "
                f"ADD COLUMN IF NOT EXISTS {_quote_ident(column)} {coltype}"
            )
        conn.exec_driver_sql(
            f"ALTER TABLE {_quote_ident(DB_SCHEMA)}.{_quote_ident('user_llm_settings')} "
            "DROP COLUMN IF EXISTS secondary_api_key"
        )


# ==================================================
# HELPERS
# All helpers below no-op (and log a warning) instead of raising when
# the DB isn't configured/reachable, so a DB outage never breaks job
# processing — the in-memory JOBS dict in integrated_pipeline.py
# remains the source of truth for the running app either way.
# ==================================================

def _session() -> Optional[Session]:
    if SessionLocal is None:
        return None
    return SessionLocal()


def get_or_create_user(username: str, email: str = "") -> Optional[int]:
    """Look up a user by username (+email), creating one if needed. Returns user id."""
    username = (username or "").strip() or "anonymous"
    email = (email or "").strip()

    db = _session()
    if db is None:
        return None
    try:
        user = db.query(User).filter(User.username == username, User.email == email).first()
        if user is None:
            user = User(username=username, email=email or None)
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.last_seen_at = datetime.utcnow()
            db.commit()
        return user.id
    except Exception as e:
        logger.error(f"get_or_create_user failed: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def job_id_exists(job_id: str) -> bool:
    """Used by the orchestrator's short job-ID generator to avoid collisions."""
    db = _session()
    if db is None:
        return False
    try:
        return db.query(Job.id).filter(Job.id == job_id).first() is not None
    except Exception as e:
        logger.error(f"job_id_exists({job_id}) failed: {e}")
        return False
    finally:
        db.close()


def create_job(job_id: str, job_name: str, username: str = "", email: str = "",
                video_filename: str = "", audio_filename: str = "",
                video_size_bytes: int = None) -> None:
    db = _session()
    if db is None:
        return
    try:
        user_id = get_or_create_user(username, email)
        job = Job(
            id=job_id,
            job_name=job_name,
            user_id=user_id,
            status="QUEUED",
            phase="validating",
            progress=0,
            video_filename=video_filename,
            audio_filename=audio_filename,
            video_size_bytes=video_size_bytes,
            recipient_email=email or None,
        )
        db.merge(job)  # merge so re-creating an existing job_id updates instead of erroring
        db.commit()
    except Exception as e:
        logger.error(f"create_job({job_id}) failed: {e}")
        db.rollback()
    finally:
        db.close()


def update_job_progress(job_id: str, progress: float, phase: str) -> None:
    db = _session()
    if db is None:
        return
    try:
        job = db.query(Job).get(job_id)
        if job is None:
            return
        job.progress = progress
        job.phase = phase
        job.status = "RUNNING"
        db.commit()
    except Exception as e:
        logger.error(f"update_job_progress({job_id}) failed: {e}")
        db.rollback()
    finally:
        db.close()


def finalize_job(job_id: str, status: str, error: str = None, latency_sec: float = None) -> None:
    db = _session()
    if db is None:
        return
    try:
        job = db.query(Job).get(job_id)
        if job is None:
            return
        job.status = status
        job.error = error
        job.latency_sec = latency_sec
        job.completed_at = datetime.utcnow()
        if status in ("SUCCESS", "PARTIAL", "FAILED", "CANCELLED"):
            job.progress = 100 if status in ("SUCCESS", "PARTIAL") else job.progress
        db.commit()
    except Exception as e:
        logger.error(f"finalize_job({job_id}) failed: {e}")
        db.rollback()
    finally:
        db.close()


def load_all_jobs() -> list:
    """
    Read every job row (most recent first) back out of the database,
    joined with its uploader's username. Called once on orchestrator
    startup to repopulate the in-memory JOBS/JOB_META dicts that the
    Dashboard's /jobs and /stats endpoints read from — without this,
    a restart would otherwise make the Dashboard look empty even though
    the database still has the full history.

    Returns a list of dicts shaped for direct use in JOBS[id] / JOB_META[id]:
        {
          "job_id", "job_name", "status", "phase", "progress", "error",
          "latency_sec", "video_filename", "audio_filename",
          "recipient_email", "username", "created_at" (isoformat str),
          "processed_at" (isoformat str or None),
        }
    Returns [] if the database is disabled/unreachable — safe to call
    unconditionally.
    """
    db = _session()
    if db is None:
        return []
    try:
        rows = (
            db.query(Job)
            .outerjoin(User, Job.user_id == User.id)
            .order_by(Job.created_at.desc())
            .all()
        )
        out = []
        for job in rows:
            out.append({
                "job_id":          job.id,
                "job_name":        job.job_name or "",
                "status":          job.status,
                "phase":           job.phase,
                "progress":        job.progress,
                "error":           job.error,
                "latency_sec":     job.latency_sec,
                "video_filename":  job.video_filename or "",
                "audio_filename":  job.audio_filename or "",
                "video_size_bytes": job.video_size_bytes,
                "recipient_email": job.recipient_email or "",
                "username":        job.user.username if job.user else "anonymous",
                "created_at":      job.created_at.isoformat() if job.created_at else "",
                "processed_at":    job.completed_at.isoformat() if job.completed_at else None,
            })
        return out
    except Exception as e:
        logger.error(f"load_all_jobs() failed: {e}")
        return []
    finally:
        db.close()


# ==================================================
# LOG CONFIGURATION (Settings page — per-user log level + folder)
# ==================================================

VALID_LOG_LEVELS = {"DEBUG", "INFO", "ERROR"}
DEFAULT_MAX_SIZE_MB = 50


def default_log_folder() -> str:
    """
    Default log folder: <home>/Documents/ApplicationLogs on whichever
    machine actually runs this backend process. In this project's
    local deployment model, Path.home() correctly resolves to that
    person's own home directory.
    """
    return str(Path.home() / "Documents" / "ApplicationLogs")


def get_log_settings(user_id: int) -> Optional[dict]:
    """Returns {level, folder_path, enabled, max_size_mb} for user_id, or None if never configured."""
    db = _session()
    if db is None:
        return None
    try:
        row = db.query(UserLogSettings).filter(UserLogSettings.user_id == user_id).first()
        if row is None:
            return None
        return {
            "level":       row.log_level,
            "folder_path": row.log_folder_path,
            "enabled":     bool(row.enabled),
            "max_size_mb": row.max_size_mb,
        }
    except Exception as e:
        logger.error(f"get_log_settings({user_id}) failed: {e}")
        return None
    finally:
        db.close()


def get_or_create_log_settings(user_id: int) -> dict:
    """
    Returns this user's saved settings, creating a default row (level
    DEBUG, enabled, default folder — created on disk too) the first
    time this user is ever seen. Always returns a usable dict, even if
    the database is disabled/unreachable (falls back to an
    in-memory-only default).
    """
    existing = get_log_settings(user_id)
    if existing is not None:
        return existing

    default_path = default_log_folder()
    try:
        os.makedirs(default_path, exist_ok=True)
    except OSError as e:
        logger.error(f"Could not create default log folder {default_path}: {e}")

    db = _session()
    if db is not None:
        try:
            row = UserLogSettings(
                user_id=user_id, log_level="DEBUG", log_folder_path=default_path,
                enabled=True, max_size_mb=DEFAULT_MAX_SIZE_MB,
            )
            db.add(row)
            db.commit()
        except Exception as e:
            logger.error(f"get_or_create_log_settings({user_id}) insert failed: {e}")
            db.rollback()
        finally:
            db.close()

    return {"level": "DEBUG", "folder_path": default_path, "enabled": True, "max_size_mb": DEFAULT_MAX_SIZE_MB}


def save_log_settings(user_id: int, level: str, folder_path: str,
                        enabled: bool = True, max_size_mb: int = DEFAULT_MAX_SIZE_MB) -> None:
    level = (level or "DEBUG").upper()
    if level not in VALID_LOG_LEVELS:
        raise ValueError(f"Invalid log level {level!r}; must be one of {sorted(VALID_LOG_LEVELS)}")
    if not isinstance(max_size_mb, int) or max_size_mb <= 0:
        raise ValueError(f"max_size_mb must be a positive integer, got {max_size_mb!r}")

    db = _session()
    if db is None:
        return
    try:
        row = db.query(UserLogSettings).filter(UserLogSettings.user_id == user_id).first()
        if row is None:
            row = UserLogSettings(user_id=user_id, log_level=level, log_folder_path=folder_path,
                                   enabled=enabled, max_size_mb=max_size_mb)
            db.add(row)
        else:
            row.log_level = level
            row.log_folder_path = folder_path
            row.enabled = enabled
            row.max_size_mb = max_size_mb
        db.commit()
    except Exception as e:
        logger.error(f"save_log_settings({user_id}) failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def reset_log_settings(user_id: int) -> dict:
    """Resets this user's settings back to level=DEBUG, enabled, default folder/size."""
    default_path = default_log_folder()
    try:
        os.makedirs(default_path, exist_ok=True)
    except OSError as e:
        logger.error(f"Could not create default log folder {default_path}: {e}")

    save_log_settings(user_id, "DEBUG", default_path, enabled=True, max_size_mb=DEFAULT_MAX_SIZE_MB)
    return {"level": "DEBUG", "folder_path": default_path, "enabled": True, "max_size_mb": DEFAULT_MAX_SIZE_MB}


# ==================================================
# UPLOAD CONFIGURATION (Settings page — max upload file size)
# ==================================================

MIN_UPLOAD_SIZE_MB = 1
MAX_UPLOAD_SIZE_MB = 500
DEFAULT_UPLOAD_SIZE_MB = 500


def get_upload_settings(user_id: int) -> Optional[dict]:
    """Returns {max_upload_size_mb, max_audio_upload_size_mb} for user_id, or None if never configured."""
    db = _session()
    if db is None:
        return None
    try:
        row = db.query(UserUploadSettings).filter(UserUploadSettings.user_id == user_id).first()
        if row is None:
            return None
        return {
            "max_upload_size_mb": row.max_upload_size_mb,
            "max_audio_upload_size_mb": row.max_audio_upload_size_mb,
        }
    except Exception as e:
        logger.error(f"get_upload_settings({user_id}) failed: {e}")
        return None
    finally:
        db.close()


def get_or_create_upload_settings(user_id: int) -> dict:
    """
    Returns the saved upload limits, creating a default row (500 MB for
    both video and audio) the first time this user_id is ever seen.
    Always returns a usable dict, even if the database is
    disabled/unreachable (falls back to the in-memory default so upload
    validation still has a sane limit).
    """
    existing = get_upload_settings(user_id)
    if existing is not None:
        return existing

    db = _session()
    if db is not None:
        try:
            row = UserUploadSettings(
                user_id=user_id,
                max_upload_size_mb=DEFAULT_UPLOAD_SIZE_MB,
                max_audio_upload_size_mb=DEFAULT_UPLOAD_SIZE_MB,
            )
            db.add(row)
            db.commit()
        except Exception as e:
            logger.error(f"get_or_create_upload_settings({user_id}) insert failed: {e}")
            db.rollback()
        finally:
            db.close()

    return {"max_upload_size_mb": DEFAULT_UPLOAD_SIZE_MB, "max_audio_upload_size_mb": DEFAULT_UPLOAD_SIZE_MB}


def _validate_upload_mb(value: int, field_name: str) -> None:
    if not isinstance(value, int) or not (MIN_UPLOAD_SIZE_MB <= value <= MAX_UPLOAD_SIZE_MB):
        raise ValueError(
            f"{field_name} must be an integer between {MIN_UPLOAD_SIZE_MB} and {MAX_UPLOAD_SIZE_MB}, got {value!r}"
        )


def save_upload_settings(user_id: int, max_upload_size_mb: int, max_audio_upload_size_mb: int) -> None:
    _validate_upload_mb(max_upload_size_mb, "max_upload_size_mb")
    _validate_upload_mb(max_audio_upload_size_mb, "max_audio_upload_size_mb")

    db = _session()
    if db is None:
        return
    try:
        row = db.query(UserUploadSettings).filter(UserUploadSettings.user_id == user_id).first()
        if row is None:
            row = UserUploadSettings(
                user_id=user_id,
                max_upload_size_mb=max_upload_size_mb,
                max_audio_upload_size_mb=max_audio_upload_size_mb,
            )
            db.add(row)
        else:
            row.max_upload_size_mb = max_upload_size_mb
            row.max_audio_upload_size_mb = max_audio_upload_size_mb
        db.commit()
    except Exception as e:
        logger.error(f"save_upload_settings({user_id}) failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def reset_upload_settings(user_id: int) -> dict:
    """Resets both upload limits back to the default (500 MB each)."""
    save_upload_settings(user_id, DEFAULT_UPLOAD_SIZE_MB, DEFAULT_UPLOAD_SIZE_MB)
    return {"max_upload_size_mb": DEFAULT_UPLOAD_SIZE_MB, "max_audio_upload_size_mb": DEFAULT_UPLOAD_SIZE_MB}


# ==================================================
# LLM CONFIGURATION (Settings page — default vs. custom API keys)
# ==================================================
#
# Custom keys are encrypted at rest with Fernet (symmetric encryption)
# using a key read from PROCESSIQ_LLM_ENCRYPTION_KEY (see
# .env.example). This is intentionally separate from DB_PASSWORD/etc. —
# losing the DB doesn't leak usable API keys, only ciphertext.
#
# SECURITY: these keys are never logged, never included in any API
# response, and never written back into config.yaml/.env — see
# mask_api_key() / llm_config_response() for what's safe to expose.

_fernet = None
_fernet_warned = False


def _get_fernet():
    """
    Lazily builds the Fernet cipher from PROCESSIQ_LLM_ENCRYPTION_KEY. Returns
    None (and logs a one-time warning) if the key isn't set or is invalid —
    callers must treat that as "encryption unavailable" and refuse to
    store/read custom keys rather than silently falling back to plaintext.
    """
    global _fernet, _fernet_warned
    if _fernet is not None:
        return _fernet
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        if not _fernet_warned:
            logger.error(
                "The 'cryptography' package is not installed — custom LLM "
                "API keys cannot be encrypted/decrypted. Run "
                "'pip install -r AudioVideoPipeline/Orchestrator/requirements_orchestrator.txt'."
            )
            _fernet_warned = True
        return None

    key = (
        os.environ.get("PROCESSIQ_LLM_ENCRYPTION_KEY")
        or os.environ.get("LLM_CONFIG_ENCRYPTION_KEY", "")
    )
    if not key:
        if not _fernet_warned:
            logger.error(
                "PROCESSIQ_LLM_ENCRYPTION_KEY is not set — custom LLM API keys "
                "cannot be encrypted, so 'Use My Own API Key' is disabled "
                "until this is configured. The legacy LLM_CONFIG_ENCRYPTION_KEY "
                "is accepted as a transition fallback. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" "
                "and put it in your .env file (see .env.example)."
            )
            _fernet_warned = True
        return None

    try:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        if not _fernet_warned:
            logger.error(f"Configured LLM encryption key is invalid — {e}")
            _fernet_warned = True
        return None
    return _fernet


def llm_encryption_available() -> bool:
    """Whether custom LLM keys can currently be encrypted/decrypted/stored."""
    return _get_fernet() is not None


def _encrypt_secret(plaintext: str) -> Optional[str]:
    """Encrypts a plaintext API key for storage. Returns None if encryption is unavailable."""
    if not plaintext:
        return None
    fernet = _get_fernet()
    if fernet is None:
        return None
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def _decrypt_secret(ciphertext: Optional[str]) -> str:
    """Decrypts a stored API key. Returns '' if unset, undecryptable, or encryption unavailable."""
    if not ciphertext:
        return ""
    fernet = _get_fernet()
    if fernet is None:
        return ""
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception as e:
        # A stale/rotated encryption key, or corrupted data —
        # never crash the pipeline over this; caller falls back to the
        # application default credentials instead.
        logger.error(f"Failed to decrypt stored LLM API key: {type(e).__name__}")
        return ""


def mask_api_key(plaintext: str) -> str:
    """
    Masks a secret for display, e.g. 'sk-or-v1-abcd...wxyz'. Never returns
    the full key. Short values are fully masked rather than partially shown.
    """
    if not plaintext:
        return ""
    if len(plaintext) <= 8:
        return "*" * len(plaintext)
    return f"{plaintext[:4]}{'*' * 12}{plaintext[-4:]}"


def get_llm_settings(user_id: int) -> Optional[dict]:
    """
    Returns {use_custom_key, provider, model, primary_api_key} (decrypted
    plaintext, for INTERNAL use only — e.g. building an LLMClient) for
    user_id, or None if never configured. Never expose this dict's key
    values directly in an API response — use llm_config_response() instead.
    """
    db = _session()
    if db is None:
        return None
    try:
        row = db.query(UserLlmSettings).filter(UserLlmSettings.user_id == user_id).first()
        if row is None:
            return None
        return {
            "use_custom_key":    bool(row.use_custom_key),
            "provider":          row.provider or DEFAULT_LLM_PROVIDER,
            "model":             row.model or DEFAULT_LLM_MODEL,
            "primary_api_key":   _decrypt_secret(row.primary_api_key),
        }
    except Exception as e:
        logger.error(f"get_llm_settings({user_id}) failed: {e}")
        return None
    finally:
        db.close()


def llm_config_response(user_id: int) -> dict:
    """
    Builds the SAFE payload for GET /settings/llm-config — mode +
    booleans/masked previews only, never the actual secret values. Used
    directly by the API route.
    """
    settings = get_llm_settings(user_id)
    if settings is None:
        return {
            "user_id": user_id,
            "mode": "default",
            "provider": DEFAULT_LLM_PROVIDER,
            "model": DEFAULT_LLM_MODEL,
            "primary_key_configured": False,
            "primary_key_masked": "",
            "encryption_available": llm_encryption_available(),
        }
    is_custom = settings["use_custom_key"]
    return {
        "user_id": user_id,
        "mode": "custom" if is_custom else "default",
        "provider": settings["provider"] if is_custom else DEFAULT_LLM_PROVIDER,
        "model": settings["model"] if is_custom else DEFAULT_LLM_MODEL,
        "primary_key_configured": bool(settings["primary_api_key"]),
        "primary_key_masked": mask_api_key(settings["primary_api_key"]),
        "encryption_available": llm_encryption_available(),
    }


def get_or_create_llm_settings(user_id: int) -> dict:
    """
    Returns this user's saved LLM settings (internal/decrypted form),
    creating a default row (mode=default, no custom keys) the first time
    this user_id is ever seen. Always returns a usable dict, even if the
    database is disabled/unreachable, so callers can always fall back to
    the application default credentials.
    """
    existing = get_llm_settings(user_id)
    if existing is not None:
        return existing

    db = _session()
    if db is not None:
        try:
            row = UserLlmSettings(
                user_id=user_id,
                use_custom_key=False,
                provider=DEFAULT_LLM_PROVIDER,
                model=DEFAULT_LLM_MODEL,
                primary_api_key=None,
            )
            db.add(row)
            db.commit()
        except Exception as e:
            logger.error(f"get_or_create_llm_settings({user_id}) insert failed: {e}")
            db.rollback()
        finally:
            db.close()

    return {
        "use_custom_key": False,
        "provider": DEFAULT_LLM_PROVIDER,
        "model": DEFAULT_LLM_MODEL,
        "primary_api_key": "",
    }


def save_llm_settings(user_id: int, use_custom_key: bool,
                       provider: Optional[str] = None,
                       model: Optional[str] = None,
                       primary_api_key: Optional[str] = None) -> None:
    """
    Saves the LLM configuration mode and (optionally) new custom keys.

    primary_api_key is treated as "leave unchanged" when None — pass an
    explicit empty string "" to intentionally clear a previously-stored key.

    Raises ValueError if use_custom_key is True but encryption is
    unavailable, or if custom mode is selected with no primary key ever
    configured.
    """
    db = _session()
    if db is None:
        return
    try:
        row = db.query(UserLlmSettings).filter(UserLlmSettings.user_id == user_id).first()
        if row is None:
            row = UserLlmSettings(
                user_id=user_id,
                use_custom_key=False,
                provider=DEFAULT_LLM_PROVIDER,
                model=DEFAULT_LLM_MODEL,
                primary_api_key=None,
            )
            db.add(row)

        if use_custom_key and not llm_encryption_available():
            raise ValueError(
                "Custom LLM API keys are not available right now — the server's "
                "PROCESSIQ_LLM_ENCRYPTION_KEY is not configured. Contact your administrator."
            )

        if primary_api_key is not None:
            row.primary_api_key = _encrypt_secret(primary_api_key) if primary_api_key else None

        if use_custom_key and not row.primary_api_key:
            raise ValueError("Primary API Key is required to use your own API key.")

        row.use_custom_key = use_custom_key
        if use_custom_key:
            row.provider = provider or row.provider or DEFAULT_LLM_PROVIDER
            row.model = model or row.model or DEFAULT_LLM_MODEL
        else:
            row.provider = DEFAULT_LLM_PROVIDER
            row.model = DEFAULT_LLM_MODEL
        db.commit()
    except Exception as e:
        logger.error(f"save_llm_settings({user_id}) failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def reset_llm_settings(user_id: int) -> dict:
    """Resets this user to the default OpenRouter key and configured model."""
    db = _session()
    if db is not None:
        try:
            row = db.query(UserLlmSettings).filter(UserLlmSettings.user_id == user_id).first()
            if row is None:
                row = UserLlmSettings(user_id=user_id)
                db.add(row)
            row.use_custom_key = False
            row.provider = DEFAULT_LLM_PROVIDER
            row.model = DEFAULT_LLM_MODEL
            row.primary_api_key = None
            db.commit()
        except Exception as e:
            logger.error(f"reset_llm_settings({user_id}) failed: {e}")
            db.rollback()
        finally:
            db.close()

    return {
        "use_custom_key": False,
        "provider": DEFAULT_LLM_PROVIDER,
        "model": DEFAULT_LLM_MODEL,
        "primary_api_key": "",
    }