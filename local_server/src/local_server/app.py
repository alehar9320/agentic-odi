"""FastAPI app for local server."""

from __future__ import annotations

from core import ODIService
from core.repository import Repository
from core.sqlite_repository import SQLiteRepository
from fastapi import FastAPI


def create_app(repo: Repository | None = None) -> FastAPI:
    if repo is None:
        repo = SQLiteRepository()
    ODIService(repo)
    app = FastAPI(title="Agentic ODI Local Server")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/capabilities")
    def capabilities() -> dict:
        return {"capabilities": "local"}

    return app
