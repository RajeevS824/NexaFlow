"""
run.py  —  place this next to backend/app/

Run with:
    python run.py

DO NOT use --reload in production.
For development, use --reload only if you accept that models
reload on first request after each file change.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    # The single shared .env file lives at the project root, one level
    # above this backend's own folder (next to nexaflow/ and
    # DP-backend/ / Document-Parser/) -- NOT inside nexaflow-backend/
    # itself. `load_dotenv()` with no arguments only looks in the
    # current working directory, so it silently found nothing whenever
    # this was launched from anywhere else. Walk up from this file
    # instead so it's found regardless of where `python run.py` is run
    # from.
    _env_path = None
    for _parent in Path(__file__).resolve().parents:
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
        port=8001,
        reload=False,
        workers=1,
    )