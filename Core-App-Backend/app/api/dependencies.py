"""
app/api/dependencies.py
-----------------------------------------------
Shared FastAPI dependencies: current user from JWT token.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token
from app.repositories.auth_repository import (
    find_admin_by_email,
    find_user_by_email,
    find_community_user_by_email,
)

security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Return the current user dict from a Bearer JWT token.

    Raises 401 if the token is missing/invalid.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload.get("sub"))
    email = payload.get("email")
    role = payload.get("role")
    org_id = int(payload.get("org_id"))

    if role == "admin":
        user = find_admin_by_email(email)
        if not user:
            raise HTTPException(status_code=401, detail="Admin account not found.")
        return {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "role": "admin",
            "account_type": "admin",
            "org_id": user["org_id"],
            "org_name": user["org_name"],
        }

    if role == "user":
        enterprise_user = find_user_by_email(email)
        user = enterprise_user or find_community_user_by_email(email)
        if not user:
            raise HTTPException(status_code=401, detail="User account not found.")
        return {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "role": "user",
            "account_type": "enterprise" if enterprise_user else "community",
            "org_id": user["org_id"],
            "org_name": user["org_name"],
        }

    raise HTTPException(status_code=401, detail="Unknown user role.")


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency that only allows admin users."""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user