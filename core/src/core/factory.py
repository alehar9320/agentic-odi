"""Repository factory selecting a persistent or in-memory store."""

from __future__ import annotations

import os

from core.repository import InMemoryRepository, Repository
from core.sqlite_repository import SQLiteRepository


def build_repository(db_path: str | None = None) -> Repository:
    resolved: str | None
    if db_path is not None:
        resolved = db_path
    else:
        resolved = os.environ.get("AGENTIC_ODI_DB")
    if resolved is None:
        resolved = os.path.expanduser("~/.agentic-odi/odi.db")
    if resolved == ":memory:":
        return InMemoryRepository()
    parent = os.path.dirname(resolved)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return SQLiteRepository(db_path=resolved)
