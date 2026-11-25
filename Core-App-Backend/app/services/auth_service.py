"""
app/services/auth_service.py
-----------------------------------------------
Business logic for authentication: multi-table login,
registration, access-token generation, and password reset.
"""
import logging
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException

from app.core.config import FRONTEND_BASE_URL, RESET_TOKEN_EXPIRE_MINUTES
from app.core.email_service import EmailSendError, send_password_reset_email
from app.core.security import create_access_token, verify_password
from app.repositories.auth_repository import (
    create_community_organization,
    create_community_user,
    create_password_reset_token,
    find_account_by_email,
    find_admin_by_email,
    find_community_user_by_email,
    find_user_by_email,
    find_valid_reset_token,
    get_org_licensed_products,
    get_user_role_product_access,
    license_all_products_for_org,
    mark_reset_token_used,
    update_password_by_account,
)

logger = logging.getLogger("uvicorn")

# Generic response used regardless of whether the email matched an
# account - avoids leaking which addresses have an account.
GENERIC_FORGOT_PASSWORD_MESSAGE = "If an account with that email exists, a reset link has been sent."


# ============================================================
# Login
# ============================================================

def login(email: str, password: str) -> dict:
    """Authenticate a user against Admin, User, then CommunityEditionUser.

    Returns a LoginResponse-compatible dict or raises HTTPException.
    """
    # 1) Admin
    admin = find_admin_by_email(email)
    if admin and verify_password(password, admin["password_hash"]):
        products = get_org_licensed_products(admin["org_id"])
        token = create_access_token(
            subject=str(admin["id"]),
            role="admin",
            org_id=admin["org_id"],
            extra={"email": admin["email"]},
        )
        return {
            "token": token,
            "user_id": admin["id"],
            "full_name": admin["full_name"],
            "email": admin["email"],
            "role": "admin",
            "account_type": "admin",
            "org_id": admin["org_id"],
            "org_name": admin["org_name"],
            "products": products,
        }

    # 2) Enterprise User (created by admin)
    user = find_user_by_email(email)
    if user and verify_password(password, user["password_hash"]):
        if not user["status"]:
            raise HTTPException(status_code=403, detail="Your account has been deactivated.")
        products = get_user_role_product_access(user["id"], user["org_id"])
        token = create_access_token(
            subject=str(user["id"]),
            role="user",
            org_id=user["org_id"],
            extra={"email": user["email"]},
        )
        return {
            "token": token,
            "user_id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "role": "user",
            "account_type": "enterprise",
            "org_id": user["org_id"],
            "org_name": user["org_name"],
            "products": products,
        }

    # 3) Community Edition User (frontend sign-up)
    community = find_community_user_by_email(email)
    if community and verify_password(password, community["password_hash"]):
        if not community["status"]:
            raise HTTPException(status_code=403, detail="Your account has been deactivated.")
        products = get_org_licensed_products(community["org_id"])
        token = create_access_token(
            subject=str(community["id"]),
            role="user",
            org_id=community["org_id"],
            extra={"email": community["email"]},
        )
        return {
            "token": token,
            "user_id": community["id"],
            "full_name": community["full_name"],
            "email": community["email"],
            "role": "user",
            "account_type": "community",
            "org_id": community["org_id"],
            "org_name": community["org_name"],
            "products": products,
        }

    raise HTTPException(status_code=401, detail="Invalid email or password.")


# ============================================================
# Registration (community edition)
# ============================================================

def register(full_name: str, email: str, company_name: str, password: str) -> dict:
    """Create a new community user + org + licenses, then return auth payload."""
    # Reject if email already exists in any of the three tables
    if find_admin_by_email(email) or find_user_by_email(email) or find_community_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    org_name = company_name.strip() or "My Company"
    org_id = create_community_organization(org_name, email)
    license_all_products_for_org(org_id)
    user_id = create_community_user(org_id, full_name, email, password)

    products = get_org_licensed_products(org_id)
    token = create_access_token(
        subject=str(user_id),
        role="user",
        org_id=org_id,
        extra={"email": email},
    )
    return {
        "token": token,
        "user_id": user_id,
        "full_name": full_name,
        "email": email,
        "role": "user",
        "account_type": "community",
        "org_id": org_id,
        "org_name": org_name,
        "products": products,
    }


# ============================================================
# Password reset
# ============================================================

def forgot_password(email: str) -> dict:
    """Create a reset token and email it, if the address matches an account.

    Always returns the same generic message so we don't reveal whether an
    account exists for that email - but if the email itself fails to send
    for a *known* account (bad SMTP config, network issue, etc.) we surface
    a real error, since that's a genuine bug the admin needs to know about.
    """
    account = find_account_by_email(email)
    if not account:
        # Don't reveal account existence; nothing else to do.
        return {"message": GENERIC_FORGOT_PASSWORD_MESSAGE}

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    create_password_reset_token(account["account_type"], account["id"], account["email"], token, expires_at)

    reset_link = f"{FRONTEND_BASE_URL}/reset-password/{token}"

    try:
        send_password_reset_email(account["email"], account["full_name"], reset_link, RESET_TOKEN_EXPIRE_MINUTES)
    except EmailSendError as exc:
        logger.error("forgot_password: could not send reset email to %s: %s", account["email"], exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"message": GENERIC_FORGOT_PASSWORD_MESSAGE}


def validate_reset_token(token: str) -> bool:
    """Return True if the token exists, is unused, and hasn't expired."""
    return find_valid_reset_token(token) is not None


def reset_password(token: str, new_password: str) -> dict:
    """Consume a valid reset token and set a new password on the account."""
    record = find_valid_reset_token(token)
    if not record:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")

    updated = update_password_by_account(record["account_type"], record["account_id"], new_password)
    if not updated:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")

    mark_reset_token_used(token)
    return {"message": "Your password has been updated. You can now sign in."}