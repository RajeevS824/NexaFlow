"""
app/repositories/auth_repository.py
-----------------------------------------------
Database access for authentication: finding users across
Admin, User, and CommunityEditionUser tables, plus product
access resolution.
"""
from datetime import datetime
from typing import Optional

from app.core.security import hash_password, verify_password
from app.database.connection import get_connection

# Map product codes to frontend slugs
PRODUCT_SLUGS = {
    "BPM": "business-process-mapper",
    "NXT": "nextflow",
    "DOC": "document-parser",
}


# ============================================================
# Helpers
# ============================================================

def _row_to_product(row) -> dict:
    """Convert a product row from a query to a dict with slug."""
    return {
        "id": int(row[0]),
        "code": str(row[1]),
        "name": str(row[2]),
        "slug": PRODUCT_SLUGS.get(str(row[1]), str(row[1]).lower()),
    }


# ============================================================
# Lookup account by email
# ============================================================

def find_admin_by_email(email: str) -> Optional[dict]:
    """Look up an Admin row by email. Returns dict or None."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT a.AdminID, a.OrgID, a.FullName, a.Email, a.PasswordHash,
                   o.OrganizationName
            FROM Admin a
            JOIN Organization o ON o.OrgID = a.OrgID
            WHERE LOWER(a.Email) = LOWER(%s)
            """,
            (email,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "org_id": int(row[1]),
            "full_name": str(row[2]),
            "email": str(row[3]),
            "password_hash": str(row[4]),
            "org_name": str(row[5]),
            "role": "admin",
        }
    finally:
        conn.close()


def find_user_by_email(email: str) -> Optional[dict]:
    """Look up an enterprise User row by email. Returns dict or None."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT u.UserID, u.OrgID, u.FirstName, u.Email, u.PasswordHash,
                   u.Status, o.OrganizationName
            FROM "user" u
            JOIN Organization o ON o.OrgID = u.OrgID
            WHERE LOWER(u.Email) = LOWER(%s)
            """,
            (email,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "org_id": int(row[1]),
            "full_name": str(row[2]),
            "email": str(row[3]),
            "password_hash": str(row[4]),
            "status": bool(row[5]),
            "org_name": str(row[6]),
            "role": "user",
        }
    finally:
        conn.close()


def find_community_user_by_email(email: str) -> Optional[dict]:
    """Look up a CommunityEditionUser row by email. Returns dict or None."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT c.CommunityEditionUserID, c.OrgID, c.FullName, c.Email,
                   c.PasswordHash, c.Status, o.OrganizationName
            FROM CommunityEditionUser c
            JOIN Organization o ON o.OrgID = c.OrgID
            WHERE LOWER(c.Email) = LOWER(%s)
            """,
            (email,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "org_id": int(row[1]),
            "full_name": str(row[2]),
            "email": str(row[3]),
            "password_hash": str(row[4]),
            "status": bool(row[5]),
            "org_name": str(row[6]),
            "role": "user",
        }
    finally:
        conn.close()


# ============================================================
# Product access
# ============================================================

def get_org_licensed_products(org_id: int) -> list[dict]:
    """Return all products licensed to an organization."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.ProductID, p.ProductCode, p.ProductName
            FROM License l
            JOIN Product p ON p.ProductID = l.ProductID
            WHERE l.OrgID = %s AND l.Status = TRUE AND p.IsActive = TRUE
            ORDER BY p.ProductID
            """,
            (org_id,),
        )
        rows = cursor.fetchall()
        return [_row_to_product(r) for r in rows]
    finally:
        conn.close()


def get_user_role_product_access(user_id: int, org_id: int) -> list[dict]:
    """Return products a user can access via their role's RoleProductAccess.

    A user only sees a product when their assigned role has a
    RoleProductAccess row with CanView = 1 for that product, AND the
    organization holds a valid license for it.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.ProductID, p.ProductCode, p.ProductName,
                   rpa.CanView, rpa.CanEdit, rpa.CanExecute
            FROM UserRole ur
            JOIN Role r ON r.RoleID = ur.RoleID
            JOIN RoleProductAccess rpa ON rpa.RoleID = r.RoleID
            JOIN Product p ON p.ProductID = rpa.ProductID
            JOIN License l ON l.ProductID = p.ProductID AND l.OrgID = %s
            WHERE ur.UserID = %s
              AND r.Status = TRUE
              AND rpa.CanView = TRUE
              AND p.IsActive = TRUE
              AND l.Status = TRUE
            ORDER BY p.ProductID
            """,
            (org_id, user_id),
        )
        rows = cursor.fetchall()
        products = []
        for row in rows:
            product = _row_to_product(row[:3])
            product["can_view"] = bool(row[3])
            product["can_edit"] = bool(row[4])
            product["can_execute"] = bool(row[5])
            products.append(product)
        return products
    finally:
        conn.close()


# ============================================================
# Registration
# ============================================================

def create_community_organization(company_name: str, email: str) -> int:
    """Create a new Organization for a community sign-up. Returns OrgID.

    OrganizationSlug is UNIQUE at the database level, but the slug used
    to be derived only from the typed company name (e.g. "xyz") with no
    uniqueness guarantee - since company name is optional and defaults
    to "My Company" when blank, any second sign-up reusing the same or
    a common/blank company name hit a UNIQUE-constraint violation and
    registration failed with no useful error. A short random suffix
    (reusing the same uuid as CompanyCode) makes every slug unique
    regardless of what company name was typed.
    """
    import uuid

    conn = get_connection()
    try:
        cursor = conn.cursor()
        unique_suffix = uuid.uuid4().hex[:8]
        base_slug = company_name.lower().strip().replace(" ", "-")[:80] or "community"
        slug = f"{base_slug}-{unique_suffix}"
        code = f"COM-{unique_suffix.upper()}"
        cursor.execute(
            """
            INSERT INTO Organization
                (OrganizationName, OrganizationSlug, CompanyCode, Email, Address, Status)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            RETURNING OrgID
            """,
            (company_name, slug, code, email, ""),
        )
        row = cursor.fetchone()
        conn.commit()
        return int(row[0])
    finally:
        conn.close()


def create_community_user(org_id: int, full_name: str, email: str, password: str) -> int:
    """Insert a CommunityEditionUser row. Returns CommunityEditionUserID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        password_hash = hash_password(password)
        cursor.execute(
            """
            INSERT INTO CommunityEditionUser (OrgID, FullName, Email, PasswordHash)
            VALUES (%s, %s, %s, %s)
            RETURNING CommunityEditionUserID
            """,
            (org_id, full_name, email, password_hash),
        )
        row = cursor.fetchone()
        conn.commit()
        return int(row[0])
    finally:
        conn.close()


# ============================================================
# Password reset
# ============================================================

def find_account_by_email(email: str) -> Optional[dict]:
    """Look up an account (Admin, User, or CommunityEditionUser) by email.

    Returns a dict with keys: account_type ('admin'|'user'|'community'),
    id, full_name, email - or None if no account matches.
    """
    admin = find_admin_by_email(email)
    if admin:
        return {"account_type": "admin", "id": admin["id"], "full_name": admin["full_name"], "email": admin["email"]}

    user = find_user_by_email(email)
    if user:
        return {"account_type": "user", "id": user["id"], "full_name": user["full_name"], "email": user["email"]}

    community = find_community_user_by_email(email)
    if community:
        return {
            "account_type": "community",
            "id": community["id"],
            "full_name": community["full_name"],
            "email": community["email"],
        }

    return None


def create_password_reset_token(account_type: str, account_id: int, email: str, token: str, expires_at: datetime) -> None:
    """Insert a new PasswordResetToken row."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO PasswordResetToken (Token, AccountType, AccountID, Email, ExpiresAt)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (token, account_type, account_id, email, expires_at),
        )
        conn.commit()
    finally:
        conn.close()


def find_valid_reset_token(token: str) -> Optional[dict]:
    """Return the PasswordResetToken row if it exists, is unused, and unexpired."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT TokenID, AccountType, AccountID, Email, ExpiresAt, UsedAt
            FROM PasswordResetToken
            WHERE Token = %s
            LIMIT 1
            """,
            (token,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        if row[5] is not None:  # UsedAt already set
            return None
        if row[4] is not None and row[4] < datetime.utcnow():
            return None
        return {
            "token_id": int(row[0]),
            "account_type": str(row[1]),
            "account_id": int(row[2]),
            "email": str(row[3]),
        }
    finally:
        conn.close()


def mark_reset_token_used(token: str) -> None:
    """Mark a PasswordResetToken row as used (so it can't be replayed)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE PasswordResetToken SET UsedAt = NOW() WHERE Token = %s",
            (token,),
        )
        conn.commit()
    finally:
        conn.close()


def update_password_by_account(account_type: str, account_id: int, new_password: str) -> bool:
    """Set a new password hash on the given account. Returns True if a row was updated."""
    table_map = {
        "admin": ("Admin", "AdminID"),
        "user": ("\"user\"", "UserID"),
        "community": ("CommunityEditionUser", "CommunityEditionUserID"),
    }
    if account_type not in table_map:
        return False
    table, id_column = table_map[account_type]

    password_hash = hash_password(new_password)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE {table} SET PasswordHash = %s, UpdatedAt = NOW() WHERE {id_column} = %s",
            (password_hash, account_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def license_all_products_for_org(org_id: int) -> None:
    """License every product in the Product master to the given org."""
    from datetime import date

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT ProductID, ProductCode FROM Product WHERE IsActive = TRUE")
        rows = cursor.fetchall()
        for product_id, product_code in rows:
            cursor.execute(
                "SELECT LicenseID FROM License WHERE OrgID = %s AND ProductID = %s LIMIT 1",
                (org_id, int(product_id)),
            )
            if not cursor.fetchone():
                license_key = f"COM-{product_code}-{org_id}-{date.today().year}"
                cursor.execute(
                    """
                    INSERT INTO License (LicenseKey, OrgID, ProductID, PurchaseDate, Status)
                    VALUES (%s, %s, %s, %s, TRUE)
                    """,
                    (license_key, org_id, int(product_id), date.today()),
                )
        conn.commit()
    finally:
        conn.close()