import logging
import os
from pathlib import Path

logger = logging.getLogger("document_pipeline")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "output"

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))
OUTPUT_ROOT = os.getenv("OUTPUT_ROOT", str(BASE_DIR / "Output"))

# ---- Security ----
# Document Parser does not have its own login page or user table: it is
# reached only from inside the NexaFlow workspace, so it trusts the SAME
# signed JWT that NexaFlow issued at login, verified with the SAME secret.
# This must be the identical value as NexaFlow's JWT_SECRET_KEY -- both
# read it from the one shared global .env, so in normal operation they
# always match.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_SECRET_CONFIGURED = bool(JWT_SECRET_KEY) and JWT_SECRET_KEY != "nexaflow-super-secret-change-me-in-production"
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

if not JWT_SECRET_CONFIGURED:
    logger.warning(
        "JWT_SECRET_KEY is not set (or is still the sample value) in the global "
        ".env. Falling back to an insecure development key -- tokens issued by "
        "NexaFlow will only verify correctly here if BOTH services share the "
        "real secret. Set a unique, random JWT_SECRET_KEY before deploying."
    )
    JWT_SECRET_KEY = JWT_SECRET_KEY or "dev-only-insecure-key-set-JWT_SECRET_KEY-in-env"
