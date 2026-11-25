"""
services/database.py — Thin service shim for database initialisation.

Business logic (model CRUD, history CRUD) has been moved to:
  - app.repositories.model_repository.ModelRepository
  - app.repositories.history_repository.HistoryRepository

This module exists solely so that main.py can call initialize_database()
without knowing about the underlying bootstrap details.
"""
from app.database.database import init_db


def initialize_database() -> None:
    """Bootstrap the SQL Server database (create if missing, apply schema, seed)."""
    init_db()
