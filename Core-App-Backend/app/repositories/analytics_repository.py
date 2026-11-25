"""
app/repositories/analytics_repository.py
-----------------------------------------------
Read-only queries that power the Admin Panel dashboard's real-time
analytics. Pulls live counts straight from the database - nothing here
is mocked or hardcoded.

NexaFlow's own numbers (active users) come from this service's own
PostgreSQL database. Document Parser and Business Map numbers come from
THEIR databases (see app/core/config.py):
  * Business Map    -> PostgreSQL (BUSINESSMAP_DB_NAME / DB_SCHEMA).
  * Document Parser -> still SQL Server, read through a small pyodbc
    connection used ONLY for this one read (PRODUCT_DB_NAME + the DB_*
    settings).
Both are scoped down to this organization by first collecting this org's
user IDs from NexaFlow's own User / CommunityEditionUser tables, then
filtering the other product's rows by that ID list. A separate connection
per database is used (rather than a single cross-database query), which
keeps each product's schema fully decoupled from NexaFlow's.

If a product's database is unreachable (e.g. that service isn't
running / not deployed), the corresponding function returns None so
the dashboard can show "unavailable" instead of silently displaying
zeroes as if that were real, verified data.
"""
import logging
from datetime import datetime, timedelta

import psycopg2

from app.core.config import PRODUCT_DB_NAME, BUSINESSMAP_DB_NAME, BUSINESSMAP_DB_SCHEMA
from app.database.connection import SQLSERVER_ERRORS, get_connection, get_sqlserver_connection

logger = logging.getLogger("uvicorn")


def get_active_user_count(org_id: int) -> int:
    """Real count of active (Status=1) enterprise + community users in the org."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM "user" WHERE OrgID = %s AND Status = TRUE) +
                (SELECT COUNT(*) FROM CommunityEditionUser WHERE OrgID = %s AND Status = TRUE)
            """,
            (org_id, org_id),
        )
        row = cursor.fetchone()
        return int(row[0] or 0)
    finally:
        conn.close()


def _get_org_user_ids(org_id: int) -> list[int]:
    """All UserID / CommunityEditionUserID values belonging to this org.

    These are the same numeric identity space used as the
    `uploaded_by` / `ProcessedUserID` / `user_id` foreign keys in the
    Document Parser and Business Map databases (CommunityEditionUser
    IDs deliberately start at 90000 to avoid colliding with enterprise
    UserIDs), so this list is what scopes those otherwise org-unaware
    tables down to just this organization.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT UserID FROM "user" WHERE OrgID = %s
            UNION
            SELECT CommunityEditionUserID FROM CommunityEditionUser WHERE OrgID = %s
            """,
            (org_id, org_id),
        )
        return [int(r[0]) for r in cursor.fetchall()]
    finally:
        conn.close()


def _last_7_day_labels() -> list[str]:
    """['MM-DD', ...] for today and the 6 days before it, oldest first."""
    today = datetime.utcnow().date()
    return [(today - timedelta(days=i)).strftime("%m-%d") for i in range(6, -1, -1)]


def _last_7_day_keys() -> list[str]:
    """['YYYY-MM-DD', ...] for today and the 6 days before it, oldest first."""
    today = datetime.utcnow().date()
    return [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]


def _build_trend(by_day: dict) -> list[dict]:
    labels = _last_7_day_labels()
    keys = _last_7_day_keys()
    return [{"label": labels[i], "value": int(by_day.get(keys[i], 0))} for i in range(7)]


def get_document_parser_stats(org_id: int) -> dict | None:
    """Real Document Parser usage for this org: totals, status breakdown,
    and a 7-day processing trend, queried live from the Document Parser
    database. Returns None if that database can't be reached right now.
    """
    user_ids = _get_org_user_ids(org_id)
    if not user_ids:
        return {"documents_total": 0, "jobs_total": 0, "status_breakdown": [], "trend": _build_trend({})}

    placeholders = ",".join("?" for _ in user_ids)
    try:
        conn = get_sqlserver_connection(PRODUCT_DB_NAME)
    except SQLSERVER_ERRORS:
        logger.warning("analytics: could not reach Document Parser database %s", PRODUCT_DB_NAME)
        return None

    try:
        cursor = conn.cursor()

        cursor.execute(
            f"SELECT COUNT(*) FROM dbo.documents WHERE uploaded_by IN ({placeholders})",
            user_ids,
        )
        documents_total = int(cursor.fetchone()[0] or 0)

        cursor.execute(
            f"""
            SELECT status, COUNT(*) FROM dbo.processing_jobs
            WHERE ProcessedUserID IN ({placeholders})
            GROUP BY status
            """,
            user_ids,
        )
        status_rows = cursor.fetchall()
        status_breakdown = [{"status": str(r[0]), "count": int(r[1])} for r in status_rows]
        jobs_total = sum(s["count"] for s in status_breakdown)

        cursor.execute(
            f"""
            SELECT CAST(queued_at AS DATE), COUNT(*)
            FROM dbo.processing_jobs
            WHERE ProcessedUserID IN ({placeholders})
              AND queued_at >= DATEADD(day, -6, CAST(SYSUTCDATETIME() AS DATE))
            GROUP BY CAST(queued_at AS DATE)
            """,
            user_ids,
        )
        by_day = {str(r[0]): int(r[1]) for r in cursor.fetchall()}

        return {
            "documents_total": documents_total,
            "jobs_total": jobs_total,
            "status_breakdown": status_breakdown,
            "trend": _build_trend(by_day),
        }
    except SQLSERVER_ERRORS:
        logger.exception("analytics: query against Document Parser database failed")
        return None
    finally:
        conn.close()


def get_business_map_stats(org_id: int) -> dict | None:
    """Real Business Map usage for this org: totals, status breakdown,
    and a 7-day processing trend, queried live from the Business Map
    database. Returns None if that database can't be reached right now.
    """
    user_ids = _get_org_user_ids(org_id)
    if not user_ids:
        return {"jobs_total": 0, "status_breakdown": [], "trend": _build_trend({})}

    placeholders = ",".join("%s" for _ in user_ids)
    # Business Map's tables live in the schema named by DB_SCHEMA (default "public").
    schema = '"' + BUSINESSMAP_DB_SCHEMA.replace('"', '""') + '"'
    try:
        conn = get_connection(BUSINESSMAP_DB_NAME)
    except psycopg2.Error:
        logger.warning("analytics: could not reach Business Map database %s", BUSINESSMAP_DB_NAME)
        return None

    try:
        cursor = conn.cursor()

        cursor.execute(
            f"""
            SELECT status, COUNT(*) FROM {schema}.jobs
            WHERE user_id IN ({placeholders})
            GROUP BY status
            """,
            user_ids,
        )
        status_rows = cursor.fetchall()
        status_breakdown = [{"status": str(r[0]), "count": int(r[1])} for r in status_rows]
        jobs_total = sum(s["count"] for s in status_breakdown)

        cursor.execute(
            f"""
            SELECT CAST(created_at AS DATE), COUNT(*)
            FROM {schema}.jobs
            WHERE user_id IN ({placeholders})
              AND created_at >= (CAST(NOW() AT TIME ZONE 'UTC' AS DATE) - 6)
            GROUP BY CAST(created_at AS DATE)
            """,
            user_ids,
        )
        by_day = {str(r[0]): int(r[1]) for r in cursor.fetchall()}

        return {
            "jobs_total": jobs_total,
            "status_breakdown": status_breakdown,
            "trend": _build_trend(by_day),
        }
    except psycopg2.Error:
        logger.exception("analytics: query against Business Map database failed")
        return None
    finally:
        conn.close()
