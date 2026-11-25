"""
app/main.py
-----------------------------------------------
FastAPI application entrypoint for the NexaFlow RBAC backend.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ALLOWED_ORIGINS, API_PREFIX
from app.database.init_db import init_db

logger = logging.getLogger("uvicorn")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize database and seed data."""
    try:
        init_db()
        logger.info("Database initialized and seeded.")
    except Exception as exc:
        logger.warning("Database initialization skipped: %s", exc)
    yield


app = FastAPI(
    title="NexaFlow RBAC API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


from app.api.routes.auth import router as auth_router
from app.api.routes.admin import router as admin_router
from app.api.routes.contact import router as contact_router

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(admin_router, prefix=API_PREFIX)
app.include_router(contact_router, prefix=API_PREFIX)