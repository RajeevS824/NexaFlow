"""
app/core/security.py
-----------------------------------------------
JWT verification for the Document Parser backend.

Document Parser has no login page and no user table of its own -- it is
only ever reached from inside the NexaFlow workspace after a user has
already logged in there. Rather than re-implement auth, this simply
verifies the token NexaFlow already issued, using the same signing
secret (shared via the global .env). No network call to NexaFlow is
needed; the signature alone proves the token is genuine and unexpired.
"""
from typing import Optional

import jwt

from app.core.config import JWT_ALGORITHM, JWT_SECRET_KEY


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT issued by the NexaFlow backend.

    Returns the payload dict (containing at least "sub" = user id) or
    None if the token is missing, expired, or has an invalid signature.
    """
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
