"""
run.py  —  place this next to backend/app/

Run with:
    python run.py

DO NOT use --reload in production.
For development, use --reload only if you accept that models
reload on first request after each file change.
"""

# Load environment variables from the shared project-root .env (if
# present) BEFORE importing anything under app/, since modules like
# app.database.connection read os.getenv(...) at import time. Requires
# `pip install python-dotenv`; safe to skip if not installed (falls
# back to real OS env vars / defaults).
#
# The shared .env lives one level above this backend's own folder
# (next to nexaflow/ and nexaflow-backend/), not inside it -- so we
# walk up from this file to find it instead of relying on
# `load_dotenv()`'s default (current-working-directory-only) lookup,
# which silently found nothing unless you happened to launch this
# from the project root.
try:
    from pathlib import Path as _Path
    from dotenv import load_dotenv

    _env_path = None
    for _parent in _Path(__file__).resolve().parents:
        _candidate = _parent / ".env"
        if _candidate.is_file():
            _env_path = _candidate
            break

    if _env_path:
        load_dotenv(_env_path)
    else:
        load_dotenv()  # fall back to default discovery
except ImportError:
    pass

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,       # models load at startup, stay in memory
        workers=1,          # single worker = single model instance
    )