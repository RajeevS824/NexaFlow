"""
bm_auth.py  —  shared FastAPI dependency: require a valid NexaFlow-issued
Bearer token on every Business Map orchestrator request, and scope that
request's job/history/settings reads to the authenticated user.

Mirrors Document-Parser-Backend/app/api/dependencies.py. The current user
id is stored in a request-scoped context variable (see get_current_user_id)
so route handlers can filter jobs/stats per user without re-parsing the
token in every handler.
"""
from contextvars import ContextVar
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from bm_security import decode_access_token

security = HTTPBearer(auto_error=False)

# Holds the authenticated user id for the lifetime of the current request.
_current_user_id: ContextVar[Optional[int]] = ContextVar(
    "bm_current_user_id", default=None
)


def get_current_user_id() -> Optional[int]:
    """Return the authenticated NexaFlow user id for the current request."""
    return _current_user_id.get()


def require_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> int:
    """Validate the Bearer token and scope this request to its user id.

    Raises 401 if the token is missing, expired, or invalid. On success,
    stores the user id in a request-scoped context variable (see
    get_current_user_id) so route handlers can scope jobs/settings to the
    right user.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token subject.")

    _current_user_id.set(user_id)
    return user_id
