"""
app/api/routes/auth.py
-----------------------------------------------
Authentication endpoints: login, register, me.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    ResetPasswordRequest,
    ValidateResetTokenResponse,
)
from app.repositories.auth_repository import get_org_licensed_products, get_user_role_product_access
from app.services.auth_service import (
    forgot_password,
    login,
    register,
    reset_password,
    validate_reset_token,
)

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger("uvicorn")


@router.post("/login", response_model=LoginResponse)
async def login_endpoint(payload: LoginRequest):
    """Authenticate and return a JWT token plus user/product context."""
    try:
        return login(payload.email, payload.password)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Login failed for %s", payload.email)
        raise HTTPException(status_code=500, detail="Login failed.")


@router.post("/register", response_model=LoginResponse)
async def register_endpoint(payload: RegisterRequest):
    """Create a new community-edition account and return a JWT token."""
    try:
        return register(payload.full_name, payload.email, payload.company_name, payload.password)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Registration failed for %s", payload.email)
        raise HTTPException(status_code=500, detail="Registration failed.")


@router.get("/me")
async def me_endpoint(current_user: dict = Depends(get_current_user)):
    """Return the current user's profile and product access.

    ``products`` reflects what's actually purchased/licensed for this
    account right now (not a static catalog) so pages like the profile
    menu's "Purchases" list always match reality:
      - admin / community: every product the organization holds a
        valid license for.
      - enterprise user: only the products their assigned role has
        been granted view access to (and the org still licenses).
    """
    account_type = current_user.get("account_type", "enterprise")
    if account_type == "enterprise":
        products = get_user_role_product_access(current_user["id"], current_user["org_id"])
    else:
        products = get_org_licensed_products(current_user["org_id"])

    return {
        "user_id": current_user["id"],
        "full_name": current_user["full_name"],
        "email": current_user["email"],
        "role": current_user["role"],
        "account_type": account_type,
        "org_id": current_user["org_id"],
        "org_name": current_user["org_name"],
        "products": products,
    }


@router.post("/forgot-password")
async def forgot_password_endpoint(payload: ForgotPasswordRequest):
    """Email a password-reset link if the address matches an account."""
    try:
        return forgot_password(payload.email)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Forgot-password request failed for %s", payload.email)
        raise HTTPException(status_code=500, detail="Failed to process password reset request.")


@router.get("/reset-password/{token}/validate", response_model=ValidateResetTokenResponse)
async def validate_reset_token_endpoint(token: str):
    """Check whether a reset token is still valid (unused and unexpired)."""
    return {"valid": validate_reset_token(token)}


@router.post("/reset-password")
async def reset_password_endpoint(payload: ResetPasswordRequest):
    """Set a new password using a valid reset token."""
    try:
        return reset_password(payload.token, payload.new_password)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Password reset failed")
        raise HTTPException(status_code=500, detail="Failed to reset password.")