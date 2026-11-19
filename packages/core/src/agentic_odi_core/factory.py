"""Repository factory selecting a persistent or in-memory store."""

from __future__ import annotations

import os

from agentic_odi_core.paths import default_odi_db_path
from agentic_odi_core.repository import InMemoryRepository, Repository
from agentic_odi_core.sqlite_repository import SQLiteRepository


def build_repository(db_path: str | None = None) -> Repository:
    resolved: str | None
    if db_path is not None:
        resolved = db_path
    else:
        resolved = str(default_odi_db_path())
    if resolved == ":memory:":
        return InMemoryRepository()
    parent = os.path.dirname(resolved)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return SQLiteRepository(db_path=resolved)
