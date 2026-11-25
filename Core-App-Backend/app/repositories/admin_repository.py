"""
app/repositories/admin_repository.py
-----------------------------------------------
Database access for admin CRUD operations:
roles, users, products, and role-product permissions.
"""
from typing import Optional

from app.core.security import hash_password
from app.database.connection import get_connection

# Map product codes to frontend slugs
PRODUCT_SLUGS = {
    "BPM": "business-process-mapper",
    "NXT": "nextflow",
    "DOC": "document-parser",
}


# ============================================================
# ROLES
# ============================================================

def list_roles(org_id: int) -> list[dict]:
    """List all roles for an org, with assigned user counts."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT r.RoleID, r.RoleName, COALESCE(r.Description, ''), r.Status,
                   (SELECT COUNT(DISTINCT ur.UserID) FROM UserRole ur WHERE ur.RoleID = r.RoleID)
            FROM Role r
            WHERE r.OrgID = %s
            ORDER BY r.RoleID
            """,
            (org_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": int(r[0]),
                "name": str(r[1]),
                "description": str(r[2]),
                "status": bool(r[3]),
                "assigned_count": int(r[4]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def create_role(org_id: int, created_by: int, name: str, description: str = "", status: bool = True) -> int:
    """Insert a new Role row. Returns RoleID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO Role (OrgID, RoleName, Description, Status, CreatedBy)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING RoleID
            """,
            (org_id, name, description, bool(status), created_by),
        )
        row = cursor.fetchone()
        conn.commit()
        return int(row[0])
    finally:
        conn.close()


def update_role(role_id: int, org_id: int, name: Optional[str] = None, description: Optional[str] = None, status: Optional[bool] = None) -> bool:
    """Update a Role row. Returns True if a row was updated."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        sets = []
        params = []
        if name is not None:
            sets.append("RoleName = %s")
            params.append(name)
        if description is not None:
            sets.append("Description = %s")
            params.append(description)
        if status is not None:
            sets.append("Status = %s")
            params.append(bool(status))
        if not sets:
            return False
        sets.append("UpdatedAt = NOW()")
        params.append(role_id)
        params.append(org_id)
        cursor.execute(
            f"UPDATE Role SET {', '.join(sets)} WHERE RoleID = %s AND OrgID = %s",
            params,
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_role(role_id: int, org_id: int) -> bool:
    """Delete a Role row (also removes UserRole and RoleProductAccess rows)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # FK constraints: delete related rows first.
        cursor.execute("DELETE FROM UserRole WHERE RoleID = %s", (role_id,))
        cursor.execute("DELETE FROM RoleProductAccess WHERE RoleID = %s", (role_id,))
        cursor.execute("DELETE FROM Role WHERE RoleID = %s AND OrgID = %s", (role_id, org_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_role_id_by_name(org_id: int, role_name: str) -> Optional[int]:
    """Find RoleID for a role name (case-insensitive) within an org."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT RoleID FROM Role WHERE OrgID = %s AND LOWER(RoleName) = LOWER(%s) LIMIT 1",
            (org_id, role_name),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else None
    finally:
        conn.close()


# ============================================================
# USERS (enterprise)
# ============================================================

def list_users(org_id: int) -> list[dict]:
    """List all enterprise Users in an org, with their role group names."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT u.UserID, u.FirstName, u.Email, u.Status,
                   (SELECT r.RoleName
                    FROM UserRole ur
                    JOIN Role r ON r.RoleID = ur.RoleID
                    WHERE ur.UserID = u.UserID
                    ORDER BY ur.UserRoleID DESC
                    LIMIT 1)
            FROM "user" u
            WHERE u.OrgID = %s
            ORDER BY u.UserID
            """,
            (org_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": int(r[0]),
                "full_name": str(r[1]),
                "email": str(r[2]),
                "status": bool(r[3]),
                "role_group": str(r[4]) if r[4] else None,
                "role": "user",
                "created_via_admin": True,
            }
            for r in rows
        ]
    finally:
        conn.close()


def create_user(org_id: int, full_name: str, email: str, password: str) -> int:
    """Insert a new enterprise User row. Raises ValueError on duplicate email."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT UserID FROM \"user\" WHERE LOWER(Email) = LOWER(%s) LIMIT 1", (email,))
        if cursor.fetchone():
            raise ValueError("A user with this email already exists.")

        password_hash = hash_password(password)
        # EmployeeCode: derive from email prefix + short random suffix
        import uuid
        employee_code = f"EMP-{uuid.uuid4().hex[:8].upper()}"
        cursor.execute(
            """
            INSERT INTO "user" (OrgID, EmployeeCode, FirstName, Email, PasswordHash)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING UserID
            """,
            (org_id, employee_code, full_name, email, password_hash),
        )
        row = cursor.fetchone()
        conn.commit()
        return int(row[0])
    finally:
        conn.close()


def update_user(user_id: int, org_id: int, full_name: Optional[str] = None, email: Optional[str] = None) -> bool:
    """Update a user's name/email."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        sets = []
        params = []
        if full_name is not None:
            sets.append("FirstName = %s")
            params.append(full_name)
        if email is not None:
            cursor.execute("SELECT UserID FROM \"user\" WHERE LOWER(Email) = LOWER(%s) AND UserID <> %s LIMIT 1", (email, user_id))
            if cursor.fetchone():
                raise ValueError("A user with this email already exists.")
            sets.append("Email = %s")
            params.append(email)
        if not sets:
            return False
        sets.append("UpdatedAt = NOW()")
        params.append(user_id)
        params.append(org_id)
        cursor.execute(
            f"UPDATE \"user\" SET {', '.join(sets)} WHERE UserID = %s AND OrgID = %s",
            params,
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_user(user_id: int, org_id: int) -> bool:
    """Delete a User row (also removes UserRole rows)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM UserRole WHERE UserID = %s", (user_id,))
        cursor.execute("DELETE FROM UserSession WHERE UserID = %s", (user_id,))
        cursor.execute("DELETE FROM \"user\" WHERE UserID = %s AND OrgID = %s", (user_id, org_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def assign_role_to_user(user_id: int, org_id: int, role_id: int, assigned_by: int) -> None:
    """Assign a role to a user.

    A user has exactly ONE role at a time in this app (the UI only ever
    shows/edits a single "Role Group" per user), so this first clears any
    other role assignment for the user before adding the new one. Without
    this, repeatedly changing a user's role via Edit would pile up extra
    UserRole rows instead of replacing the old one - which both made the
    "current" role unpredictable (list_users picks one nondeterministically)
    and inflated other roles' assigned-user counts with stale rows.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Check the user belongs to this org
        cursor.execute("SELECT UserID FROM \"user\" WHERE UserID = %s AND OrgID = %s LIMIT 1", (user_id, org_id))
        if not cursor.fetchone():
            return

        # Remove any other role assignment(s) this user has in this org first,
        # so a user only ever holds one role at a time.
        cursor.execute(
            """
            DELETE FROM UserRole
            WHERE UserID = %s
              AND RoleID <> %s
              AND RoleID IN (SELECT RoleID FROM Role WHERE OrgID = %s)
            """,
            (user_id, role_id, org_id),
        )

        # Upsert the target role assignment.
        cursor.execute("SELECT UserRoleID FROM UserRole WHERE UserID = %s AND RoleID = %s LIMIT 1", (user_id, role_id))
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                "UPDATE UserRole SET AssignedBy = %s WHERE UserRoleID = %s",
                (assigned_by, int(existing[0])),
            )
        else:
            cursor.execute(
                """
                INSERT INTO UserRole (UserID, RoleID, AssignedBy)
                VALUES (%s, %s, %s)
                """,
                (user_id, role_id, assigned_by),
            )
        conn.commit()
    finally:
        conn.close()


def unassign_role_from_user(user_id: int, org_id: int) -> None:
    """Remove all role assignments from a user."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM UserRole
            WHERE UserID = %s
              AND RoleID IN (SELECT RoleID FROM Role WHERE OrgID = %s)
            """,
            (user_id, org_id),
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# PRODUCTS
# ============================================================

def list_org_products(org_id: int) -> list[dict]:
    """List all products licensed to an organization."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.ProductID, p.ProductName, p.ProductCode, COALESCE(p.Description, ''),
                   l.Status
            FROM License l
            JOIN Product p ON p.ProductID = l.ProductID
            WHERE l.OrgID = %s
            ORDER BY p.ProductID
            """,
            (org_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": int(r[0]),
                "name": str(r[1]),
                "code": str(r[2]),
                "slug": PRODUCT_SLUGS.get(str(r[2]), str(r[2]).lower()),
                "description": str(r[3]),
                "enabled": bool(r[4]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def set_product_enabled(org_id: int, product_id: int, enabled: bool) -> bool:
    """Enable/disable a licensed product for one organization's users.

    Only touches License.Status (the per-organization access flag) - NOT
    Product.IsActive. Product.IsActive is a single global row shared by
    every organization in the system (there's no per-org column on
    Product), so flipping it here would deactivate the product for every
    other organization too, and would stop it from being auto-licensed to
    brand-new community sign-ups (see license_all_products_for_org, which
    filters on Product.IsActive). License.Status is what every access
    check in this app actually enforces per-org, so it's the correct and
    sufficient switch for this toggle.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE License SET Status = %s WHERE OrgID = %s AND ProductID = %s",
            (bool(enabled), org_id, product_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ============================================================
# ROLE PRODUCT ACCESS (permissions)
# ============================================================

def get_role_permissions(role_id: int, org_id: int) -> list[dict]:
    """Return RoleProductAccess rows for a role, for all org-licensed products."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # All licensed products for the org
        cursor.execute(
            """
            SELECT p.ProductID, p.ProductCode, p.ProductName
            FROM License l
            JOIN Product p ON p.ProductID = l.ProductID
            WHERE l.OrgID = %s
            ORDER BY p.ProductID
            """,
            (org_id,),
        )
        product_rows = cursor.fetchall()

        # Existing permissions for this role
        cursor.execute(
            """
            SELECT ProductID, CanView, CanEdit, CanExecute
            FROM RoleProductAccess
            WHERE RoleID = %s
            """,
            (role_id,),
        )
        perm_map = {}
        for row in cursor.fetchall():
            perm_map[int(row[0])] = {
                "can_view": bool(row[1]),
                "can_edit": bool(row[2]),
                "can_execute": bool(row[3]),
            }

        result = []
        for p in product_rows:
            product_id = int(p[0])
            perm = perm_map.get(product_id, {"can_view": False, "can_edit": False, "can_execute": False})
            result.append({
                "product_id": product_id,
                "code": str(p[1]),
                "name": str(p[2]),
                "can_view": perm["can_view"],
                "can_edit": perm["can_edit"],
                "can_execute": perm["can_execute"],
            })
        return result
    finally:
        conn.close()


def save_role_permissions(role_id: int, permissions: list[dict], assigned_by: int) -> None:
    """Replace RoleProductAccess rows for a role."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Delete existing permissions for this role
        cursor.execute("DELETE FROM RoleProductAccess WHERE RoleID = %s", (role_id,))
        # Insert new ones where can_view is True
        for perm in permissions:
            if not perm.get("can_view"):
                continue
            cursor.execute(
                """
                INSERT INTO RoleProductAccess
                    (RoleID, ProductID, CanView, CanEdit, CanExecute, AssignedBy)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    role_id,
                    perm["product_id"],
                    True,
                    bool(perm.get("can_edit")),
                    bool(perm.get("can_execute")),
                    assigned_by,
                ),
            )
        conn.commit()
    finally:
        conn.close()