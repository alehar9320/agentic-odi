"""FastAPI app for the Living Studio sidecar."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from agentic_odi_core import ODIService
from agentic_odi_core.errors import StoreCorrupt
from agentic_odi_core.funnel import count_launch, start_session
from agentic_odi_core.messages import CAPABILITIES
from agentic_odi_core.recovery import corrupt_store_message, latest_backup
from agentic_odi_core.remote import StudioError, StudioErrorCode
from agentic_odi_core.repository import InMemoryRepository, Repository
from agentic_odi_core.sqlite_repository import SQLiteRepository
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from agentic_odi_studio_api.studio.approvals import ApprovalRegistry
from agentic_odi_studio_api.studio.connectors import ConnectorService
from agentic_odi_studio_api.studio.errors import (
    RequestIdMiddleware,
    StudioHTTPError,
    register_error_handlers,
    request_id_for,
)
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

CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self' http://localhost:5173 http://127.0.0.1:5173 "
    "http://localhost:8100 http://127.0.0.1:8100 ws://localhost:5173; "
    "font-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


#: The one document that has to stay self-contained. `/offline.html` is served
#: from the service worker's cache when there is no network at all (#546), so its
#: theme script and styles cannot become separate files without a request that
#: would fail too. Those exact blocks are named by hash instead: a hash admits
#: that markup and nothing else, so the policy still refuses inline script and
#: inline style everywhere a reply could be injected.
OFFLINE_DOCUMENT = "offline.html"
_INLINE_BLOCK = re.compile(
    r"<(script|style)\b[^>]*>(?P<body>.*?)</\1>",
    re.DOTALL | re.IGNORECASE,
)


def offline_inline_hashes(spa_dist: Path) -> list[str]:
    """CSP source expressions for the offline document's inline blocks."""
    try:
        markup = (spa_dist / OFFLINE_DOCUMENT).read_text(encoding="utf-8")
    except OSError:
        return []
    hashes = []
    for match in _INLINE_BLOCK.finditer(markup):
        digest = hashlib.sha256(match.group("body").encode("utf-8")).digest()
        hashes.append("'sha256-" + base64.b64encode(digest).decode("ascii") + "'")
    return hashes


def content_security_policy(spa_dist: Path | None = None) -> str:
    """``CSP_POLICY``, plus the hashes the offline document needs.

    The hashes go into both ``script-src`` and ``style-src``: the browser checks
    the directive that matches the element, not the file the element came from,
    and the offline document has one block of each.
    """
    hashes = offline_inline_hashes(SPA_DIST if spa_dist is None else spa_dist)
    if not hashes:
        return CSP_POLICY
    allowance = " " + " ".join(hashes)
    return CSP_POLICY.replace("script-src 'self';", f"script-src 'self'{allowance};").replace(
        "style-src 'self';", f"style-src 'self'{allowance};"
    )


class CSPMiddleware:
    """Attach a strict Content-Security-Policy to every HTTP response.

    The policy refuses inline script, eval, and wildcard script sources so a
    prompt-injected reply cannot execute in the served shell or the Tauri
    window. Localhost origins are the development-only exception for the Vite
    dev server and the sidecar itself; production serves from 'self'.
    """

    def __init__(self, app: ASGIApp, policy: str) -> None:
        self.app = app
        self.policy = policy

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_csp(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if "content-security-policy" not in headers:
                    headers.append("content-security-policy", self.policy)
            await send(message)

        await self.app(scope, receive, send_with_csp)


#: Seconds of quiet between passive checkpoints. A passive checkpoint never
#: waits on a reader, so it is safe to run on a timer; it keeps the write-ahead
#: log from growing unbounded between clean shutdowns.
DEFAULT_CHECKPOINT_SECONDS = 60.0


def checkpoint_seconds() -> float:
    """The idle-checkpoint interval, from ``AGENTIC_ODI_CHECKPOINT_SECONDS``."""
    raw = os.environ.get("AGENTIC_ODI_CHECKPOINT_SECONDS")
    if not raw:
        return DEFAULT_CHECKPOINT_SECONDS
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_CHECKPOINT_SECONDS


def default_spa_dist() -> Path:
    """Resolve the built SPA, preferring an explicit override."""
    configured = os.environ.get("AGENTIC_ODI_STUDIO_DIST")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[4] / "apps" / "studio" / "dist"


SPA_DIST = default_spa_dist()


def _boot_failure_error(error: StoreCorrupt) -> StudioError:
    """The structured failure the SPA renders instead of a traceback."""
    backup = latest_backup(error.path)
    return StudioError(
        code=StudioErrorCode.STORE_CORRUPT,
        message=corrupt_store_message(error, backup=backup),
        detail="\n".join(error.problems) if error.problems else None,
        suggestion=(
            f"Restore {backup.name} over {Path(error.path).name}, then restart. "
            "The damaged file has not been changed."
            if backup is not None
            else "No backup exists yet. Move the damaged file aside to start a new one; "
            "the damaged file has not been changed."
        ),
    )


def create_app(
    repo: Repository | None = None,
    backend: str | None = None,
    connectors: ConnectorService | None = None,
    memory: StudioMemory | None = None,
    marketplace: StudioMarketplace | None = None,
) -> FastAPI:
    # A damaged file must not reach the person as a traceback. The store is
    # gated on open; when it fails, the app still starts and answers with the
    # failure page until the file is restored. The file itself is never touched.
    boot_error: StoreCorrupt | None = None
    if repo is None:
        try:
            repo = SQLiteRepository()
        except StoreCorrupt as exc:
            boot_error = exc
            repo = InMemoryRepository()
    service = ODIService(repo)
    # Pending write approvals live for the life of the process: a local sidecar
    # serves one person and has no durable run state to resume into.
    approvals = ApprovalRegistry()

    if memory is None:
        try:
            memory = StudioMemory()
        except StoreCorrupt as exc:
            # The conversation history is a second database. Damage there is
            # reported the same way; the process keeps running on an empty,
            # ephemeral store so the failure page can be served.
            boot_error = boot_error or exc
            memory = StudioMemory(":memory:")
    resolved_memory = memory

    checkpoint_interval = checkpoint_seconds()

    async def _idle_checkpoint() -> None:
        """Fold the log back on a timer while the sidecar sits idle."""
        while True:
            await asyncio.sleep(checkpoint_interval)
            try:
                await asyncio.to_thread(repo.checkpoint, "PASSIVE")
            except Exception:  # noqa: BLE001  # nosec B110 - a checkpoint is best-effort
                # A checkpoint is durability, not a write. A store that cannot
                # checkpoint right now (a reader holds the log) still closes
                # cleanly later; killing the timer would stop all checkpoints.
                pass

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # One app session is one sidecar launch, so the session id is drawn here
        # and nowhere else. The per-install device id is a different identity and
        # is never used as this one.
        count_launch(repo, start_session())
        idle_task: asyncio.Task[None] | None = None
        if checkpoint_interval > 0:
            idle_task = asyncio.create_task(_idle_checkpoint())
        try:
            yield
        finally:
            # Nothing may outlive the process waiting on a decision.
            approvals.cancel_all()
            if idle_task is not None:
                idle_task.cancel()
                with suppress(asyncio.CancelledError):
                    await idle_task
            # Close on the way out so a clean stop leaves no write-ahead log
            # for the next process to recover. The store checkpoints first.
            await asyncio.to_thread(repo.close)
            await asyncio.to_thread(resolved_memory.close)

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
    app.state.memory = resolved_memory
    app.state.approvals = approvals
    app.state.boot_error = _boot_failure_error(boot_error) if boot_error else None
    app.state.db_integrity = "corrupt" if boot_error else getattr(repo, "integrity", "unknown")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def _refuse_when_boot_failed(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Answer every data route with the boot failure while it stands."""
        boot_failure = app.state.boot_error
        path = request.url.path
        if boot_failure is not None and path.startswith("/api"):
            # Diagnostics and health stay reachable so a person can see what is
            # wrong and copy the message. This middleware sits outside the app's
            # exception handlers, so it returns the error body directly rather
            # than raising.
            if not (path.startswith("/api/diagnostics") or path.startswith("/api/health")):
                failure = boot_failure.model_copy(update={"request_id": request_id_for(request)})
                return JSONResponse({"error": failure.model_dump(mode="json")}, status_code=503)
        return await call_next(request)

    # Registration order is reversed: the last middleware added runs outermost,
    # so the request id is assigned before the boot check reads it.
    app.middleware("http")(_refuse_when_boot_failed)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(CSPMiddleware, policy=content_security_policy())
    register_error_handlers(app)

    @app.get("/health")
    def health() -> dict:
        if app.state.boot_error is not None:
            return {"status": "degraded", "reason": "store_corrupt"}
        return {"status": "ok"}

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
