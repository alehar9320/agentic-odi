"""FastAPI app for local server."""

from __future__ import annotations

import os
from pathlib import Path

from core import ODIService
from core.repository import Repository
from core.sqlite_repository import SQLiteRepository
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from local_server.studio.router import router as studio_router

CORS_ORIGINS = [
    "tauri://localhost",
    "http://tauri.localhost",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8100",
    "http://127.0.0.1:8100",
]

REPO_ROOT = Path(__file__).resolve().parents[3]
SPA_DIST = REPO_ROOT / "studio" / "dist"


def create_app(repo: Repository | None = None) -> FastAPI:
    if repo is None:
        repo = SQLiteRepository()
    service = ODIService(repo)
    app = FastAPI(title="Agentic ODI Local Server")
    app.state.service = service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/capabilities")
    def capabilities() -> dict:
        return {"capabilities": "local"}

    app.include_router(studio_router)

    if SPA_DIST.is_dir() and not os.getenv("AGENTIC_ODI_DISABLE_SPA"):
        assets_dir = SPA_DIST / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", response_model=None)
        def spa_fallback(full_path: str) -> FileResponse | JSONResponse:
            candidate = (SPA_DIST / full_path).resolve()
            if full_path and candidate.is_file() and candidate.is_relative_to(SPA_DIST.resolve()):
                return FileResponse(candidate)
            index = SPA_DIST / "index.html"
            if index.is_file():
                return FileResponse(index)
            return JSONResponse({"detail": "Not Found"}, status_code=404)

    return app
