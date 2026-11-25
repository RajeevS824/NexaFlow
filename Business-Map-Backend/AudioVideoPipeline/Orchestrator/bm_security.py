"""
bm_security.py  —  JWT verification for the Business Map orchestrator.

The Business Map orchestrator has no login page and no user table of its
own — it is only ever reached from inside the NexaFlow workspace after a
user has already logged in there. Rather than re-implementing auth, this
verifies the token NexaFlow already issued, using the SAME signing secret
shared through the one global root .env. No network call to NexaFlow is
needed; the signature alone proves the token is genuine and unexpired.

This mirrors Document-Parser-Backend/app/core/security.py exactly, so both
product backends trust the same token the same way.
"""
from pathlib import Path
from typing import Optional

# Ensure the shared root .env is loaded so JWT_SECRET_KEY reaches us even
# when this service is started directly (rather than via run_backend.py,
# which already loads the root .env and passes env vars to subprocesses).
# Walk up from this file's own location until we find a .env file.
try:
    from dotenv import load_dotenv

    # Load the shared secrets from the one global root .env. Walk up from this
    # file's own location and load EVERY .env we pass, so a nearer per-service
    # .env (e.g. Business-Map-Backend/.env, which has no JWT_SECRET_KEY) cannot
    # shadow the root .env that holds the shared signing key. The highest/root
    # .env is reloaded last with override=True so its shared values always win.
    _env_files = [
        _parent / ".env"
        for _parent in Path(__file__).resolve().parents
        if (_parent / ".env").is_file()
    ]

    if _env_files:
        # nearest -> root: load base values first...
        for _env_path in _env_files:
            load_dotenv(_env_path)
        # ...then reload the root last with override so shared secrets win.
        load_dotenv(_env_files[-1], override=True)
    else:
        load_dotenv()  # fall back to default discovery
except ImportError:
    pass

import os

import jwt

# Same shared secret/algorithm as nexaflow-backend (which issues the token)
# and Document-Parser-Backend (which verifies it). All three read the same
# values from the one root .env, so by construction they always match.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is not set in the shared .env. Business Map cannot "
        "verify tokens issued by NexaFlow."
    )


def decode_access_token(token: str) -> Optional[dict]:
    """Decode/validate a JWT issued by the NexaFlow backend.

    Returns the payload dict (containing at least "sub" = user id) or None
    if the token is missing, expired, or has an invalid signature.
    """
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
