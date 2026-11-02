"""FastAPI app for the Living Studio sidecar."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from agentic_odi_core import ODIService
from agentic_odi_core.messages import CAPABILITIES
from agentic_odi_core.remote import StudioError, StudioErrorCode
from agentic_odi_core.repository import Repository
from agentic_odi_core.sqlite_repository import SQLiteRepository
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agentic_odi_studio_api.studio.approvals import ApprovalRegistry
from agentic_odi_studio_api.studio.connectors import ConnectorService
from agentic_odi_studio_api.studio.errors import (
    RequestIdMiddleware,
    StudioHTTPError,
    register_error_handlers,
    request_id_for,
)
from agentic_odi_studio_api.studio.health import collect_health
from agentic_odi_studio_api.studio.marketplace import StudioMarketplace
from agentic_odi_studio_api.studio.memory import StudioMemory
from agentic_odi_studio_api.studio.router import router as studio_router

CORS_ORIGINS = [
    "tauri://localhost",
    "http://tauri.localhost",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8100",
    "http://127.0.0.1:8100",
]

DEFAULT_BACKEND = "local"


def default_spa_dist() -> Path:
    """Resolve the built SPA, preferring an explicit override."""
    configured = os.environ.get("AGENTIC_ODI_STUDIO_DIST")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[4] / "apps" / "studio" / "dist"


SPA_DIST = default_spa_dist()


def create_app(
    repo: Repository | None = None,
    backend: str | None = None,
    connectors: ConnectorService | None = None,
    memory: StudioMemory | None = None,
    marketplace: StudioMarketplace | None = None,
) -> FastAPI:
    if repo is None:
        repo = SQLiteRepository()
    service = ODIService(repo)
    # Pending write approvals live for the life of the process: a local sidecar
    # serves one person and has no durable run state to resume into.
    approvals = ApprovalRegistry()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        # Nothing may outlive the process waiting on a decision.
        approvals.cancel_all()

    app = FastAPI(
        title="Agentic ODI Studio API",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.service = service
    app.state.backend = backend or os.environ.get("AGENTIC_ODI_BACKEND") or DEFAULT_BACKEND
    resolved_marketplace = marketplace or StudioMarketplace()
    app.state.marketplace = resolved_marketplace
    app.state.connectors = connectors or ConnectorService(marketplace=resolved_marketplace)
    app.state.memory = memory or StudioMemory()
    app.state.approvals = approvals

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)

    @app.get("/health")
    async def health(request: Request) -> dict:
        # The same report the Studio API serves under /api/health: a liveness
        # stub beside a real health route would be two truths about one machine.
        report = await collect_health(service.repo, request_id=request_id_for(request))
        return report.model_dump(mode="json")

    @app.get("/capabilities")
    def capabilities() -> dict:
        return {"capabilities": CAPABILITIES}

    app.include_router(studio_router)

    if SPA_DIST.is_dir() and not os.getenv("AGENTIC_ODI_DISABLE_SPA"):
        assets_dir = SPA_DIST / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", response_model=None)
        def spa_fallback(request: Request, full_path: str) -> FileResponse | JSONResponse:
            if full_path == "api" or full_path.startswith("api/"):
                raise StudioHTTPError(
                    StudioError(code=StudioErrorCode.NOT_FOUND, message="Not Found")
                )
            candidate = (SPA_DIST / full_path).resolve()
            if full_path and candidate.is_file() and candidate.is_relative_to(SPA_DIST.resolve()):
                return FileResponse(candidate)
            index = SPA_DIST / "index.html"
            if index.is_file():
                return FileResponse(index)
            error = StudioError(
                code=StudioErrorCode.NOT_FOUND,
                message="Not Found",
                request_id=request_id_for(request),
            )
            return JSONResponse({"error": error.model_dump(mode="json")}, status_code=404)

    return app
