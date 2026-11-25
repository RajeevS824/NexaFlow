"""
app/api/dependencies.py
-----------------------------------------------
Shared FastAPI dependency: require a valid NexaFlow-issued Bearer token
on every Document Parser request, and scope that request's DB reads/
writes to the authenticated user.

Applied at the router level in app/api/routes/document.py, so every
route in this service requires a signed-in NexaFlow user by default,
except the top-level /health liveness check.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.global_state import set_current_user_id
from app.core.security import decode_access_token

security = HTTPBearer()


async def require_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """Validate the Bearer token and scope this request to its user id.

    Raises 401 if the token is missing, expired, or invalid. On success,
    stores the user id in a request-scoped context variable (see
    app.core.global_state) so existing repository code -- which reads
    get_current_user_id() -- automatically stays scoped to the right
    user, including across the long-running OCR pipeline.
    """
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

    set_current_user_id(user_id)
    return user_id