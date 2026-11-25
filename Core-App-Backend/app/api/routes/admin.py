"""
app/api/routes/admin.py
-----------------------------------------------
Admin-only endpoints for managing roles, users, products,
and role-product permissions.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import require_admin
from app.repositories.admin_repository import (
    assign_role_to_user,
    create_role,
    create_user,
    delete_role,
    delete_user,
    get_role_id_by_name,
    get_role_permissions,
    list_org_products,
    list_roles,
    list_users,
    save_role_permissions,
    set_product_enabled,
    unassign_role_from_user,
    update_role,
    update_user,
)
from app.schemas.admin import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    AssignRoleRequest,
    PermissionSaveRequest,
    ProductToggleRequest,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)
from app.schemas.auth import UserResponse
from app.services.analytics_service import get_admin_dashboard_analytics

router = APIRouter(prefix="/admin", tags=["Admin"])


# ============================================================
# DASHBOARD ANALYTICS
# ============================================================

@router.get("/analytics/dashboard")
async def get_dashboard_analytics(current_user: dict = Depends(require_admin)):
    """Real-time usage analytics for the Admin Panel dashboard.

    Scoped to only the products this organization has licensed - a
    product with no license is omitted from `products` entirely. Every
    number is a live query against the relevant database; nothing here
    is mocked.
    """
    return get_admin_dashboard_analytics(current_user["org_id"])


# ============================================================
# ROLES
# ============================================================

@router.get("/roles", response_model=list[RoleResponse])
async def get_roles(current_user: dict = Depends(require_admin)):
    """List all roles in the current admin's organization."""
    return list_roles(current_user["org_id"])


@router.post("/roles", response_model=RoleResponse)
async def create_role_endpoint(payload: RoleCreate, current_user: dict = Depends(require_admin)):
    """Create a new role."""
    role_id = create_role(
        org_id=current_user["org_id"],
        created_by=current_user["id"],
        name=payload.name,
        description=payload.description,
        status=payload.status,
    )
    return RoleResponse(id=role_id, name=payload.name, description=payload.description, status=payload.status, assigned_count=0)


@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role_endpoint(role_id: int, payload: RoleUpdate, current_user: dict = Depends(require_admin)):
    """Update a role."""
    updated = update_role(
        role_id=role_id,
        org_id=current_user["org_id"],
        name=payload.name,
        description=payload.description,
        status=payload.status,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Role not found.")
    # Return updated role
    roles = list_roles(current_user["org_id"])
    role = next((r for r in roles if r["id"] == role_id), None)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")
    return role


@router.delete("/roles/{role_id}")
async def delete_role_endpoint(role_id: int, current_user: dict = Depends(require_admin)):
    """Delete a role."""
    deleted = delete_role(role_id, current_user["org_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Role not found.")
    return {"message": "Role deleted."}


# ============================================================
# USERS
# ============================================================

@router.get("/users", response_model=list[UserResponse])
async def get_users(current_user: dict = Depends(require_admin)):
    """List all enterprise users in the current admin's organization."""
    return list_users(current_user["org_id"])


@router.post("/users", response_model=UserResponse)
async def create_user_endpoint(payload: AdminCreateUserRequest, current_user: dict = Depends(require_admin)):
    """Create a new enterprise user."""
    try:
        user_id = create_user(
            org_id=current_user["org_id"],
            full_name=payload.full_name,
            email=payload.email,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return UserResponse(
        id=user_id,
        full_name=payload.full_name,
        email=payload.email,
        role="user",
        role_group=None,
        status=True,
        created_via_admin=True,
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user_endpoint(user_id: int, payload: AdminUpdateUserRequest, current_user: dict = Depends(require_admin)):
    """Update a user's name/email."""
    updated = update_user(
        user_id=user_id,
        org_id=current_user["org_id"],
        full_name=payload.full_name,
        email=payload.email,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="User not found.")
    users = list_users(current_user["org_id"])
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@router.delete("/users/{user_id}")
async def delete_user_endpoint(user_id: int, current_user: dict = Depends(require_admin)):
    """Delete a user."""
    deleted = delete_user(user_id, current_user["org_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"message": "User deleted."}


@router.post("/users/{user_id}/assign-role")
async def assign_role_endpoint(user_id: int, payload: AssignRoleRequest, current_user: dict = Depends(require_admin)):
    """Assign a role to a user."""
    role_id = get_role_id_by_name(current_user["org_id"], payload.role_name)
    if not role_id:
        raise HTTPException(status_code=404, detail="Role not found.")
    assign_role_to_user(user_id, current_user["org_id"], role_id, current_user["id"])
    return {"message": f"Role '{payload.role_name}' assigned to user {user_id}."}


@router.delete("/users/{user_id}/unassign-role")
async def unassign_role_endpoint(user_id: int, current_user: dict = Depends(require_admin)):
    """Remove all role assignments from a user."""
    unassign_role_from_user(user_id, current_user["org_id"])
    return {"message": f"All roles unassigned from user {user_id}."}


# ============================================================
# PRODUCTS
# ============================================================

@router.get("/products")
async def get_products(current_user: dict = Depends(require_admin)):
    """List all products licensed to the organization."""
    return list_org_products(current_user["org_id"])


@router.patch("/products/{product_id}/toggle")
async def toggle_product(product_id: int, payload: ProductToggleRequest, current_user: dict = Depends(require_admin)):
    """Enable/disable a licensed product for the organization's users."""
    updated = set_product_enabled(current_user["org_id"], product_id, payload.enabled)
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found in your licenses.")
    return {"message": f"Product {'enabled' if payload.enabled else 'disabled'}."}


# ============================================================
# ROLE PERMISSIONS
# ============================================================

@router.get("/roles/{role_id}/permissions")
async def get_role_permissions_endpoint(role_id: int, current_user: dict = Depends(require_admin)):
    """Get all product permissions for a role."""
    # Verify role belongs to this org
    role = next((r for r in list_roles(current_user["org_id"]) if r["id"] == role_id), None)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")
    return get_role_permissions(role_id, current_user["org_id"])


@router.post("/roles/{role_id}/permissions")
async def save_role_permissions_endpoint(role_id: int, payload: PermissionSaveRequest, current_user: dict = Depends(require_admin)):
    """Save product permissions for a role."""
    # Verify role belongs to this org
    role = next((r for r in list_roles(current_user["org_id"]) if r["id"] == role_id), None)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")
    save_role_permissions(role_id, [p.dict() for p in payload.permissions], current_user["id"])
    return {"message": "Permissions saved."}