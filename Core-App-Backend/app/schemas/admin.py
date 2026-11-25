"""
app/schemas/admin.py
-----------------------------------------------
Pydantic models for admin CRUD (roles, products, users, permissions).
"""
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ============================================================
# ROLES
# ============================================================

class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=500)
    status: bool = True


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, max_length=500)
    status: Optional[bool] = None


class RoleResponse(BaseModel):
    id: int
    name: str
    description: str = ""
    status: bool = True
    assigned_count: int = 0


# ============================================================
# PRODUCTS
# ============================================================

class ProductResponse(BaseModel):
    id: int
    name: str
    code: str
    slug: str
    description: str = ""
    enabled: bool = True


class ProductToggleRequest(BaseModel):
    enabled: bool


# ============================================================
# PERMISSIONS (RoleProductAccess)
# ============================================================

class PermissionRow(BaseModel):
    product_id: int
    can_view: bool = True
    can_edit: bool = False
    can_execute: bool = False


class PermissionSaveRequest(BaseModel):
    permissions: list[PermissionRow]


# ============================================================
# USERS (enterprise, created by admin)
# ============================================================

class AdminCreateUserRequest(BaseModel):
    full_name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)


class AdminUpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role_group: Optional[str] = None


class AssignRoleRequest(BaseModel):
    role_name: str = Field(min_length=1)