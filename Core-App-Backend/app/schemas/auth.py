"""
app/schemas/auth.py
-----------------------------------------------
Pydantic models for authentication and user management.
"""
from pydantic import BaseModel, EmailStr, Field


# ============================================================
# AUTH
# ============================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1)
    email: EmailStr
    company_name: str = Field(default="", max_length=200)
    password: str = Field(min_length=8)


class ProductAccess(BaseModel):
    id: int
    code: str
    name: str
    slug: str
    can_view: bool = True
    can_edit: bool = False
    can_execute: bool = False


class LoginResponse(BaseModel):
    token: str
    user_id: int
    full_name: str
    email: str
    role: str  # "admin" | "user"
    account_type: str = "user"  # "admin" | "enterprise" | "community"
    org_id: int
    org_name: str
    products: list[ProductAccess]


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    role: str = "user"
    role_group: str | None = None
    status: bool = True
    created_via_admin: bool = False


# ============================================================
# PASSWORD RESET
# ============================================================

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class ValidateResetTokenResponse(BaseModel):
    valid: bool