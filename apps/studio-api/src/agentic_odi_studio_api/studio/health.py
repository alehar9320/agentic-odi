"""One health answer for the whole stack.

A person, the SPA, the Worker, and a monitor all need the same sentence about
what is working: the sidecar, the store, the MCP server, and the model. This
module is the only place that knows that vocabulary, so every surface asks it
instead of re-deriving health from a port.

It reuses the two probes the first-run wizard already trusts
(:mod:`agentic_odi_studio_api.studio.probes`) and the repository's own
``health()``; it adds no third probe, never writes to the store, and always
answers inside its latency budget.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from agentic_odi_core.repository import Repository

from agentic_odi_studio_api.studio.probes import (
    check_llm_health,
    defaults,
    is_endpoint_reachable,
)
from agentic_odi_studio_api.studio.schemas import HealthCheck, HealthReport

#: A health endpoint that can hang is not a health endpoint. Each probe is
#: bounded well below this, and the whole report is bounded again.
HEALTH_BUDGET_S = 3.0


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _store_detail(repository: Repository) -> str:
    """Name the file the store reads, so a locked store is diagnosable."""
    connection = getattr(getattr(repository, "store", None), "conn", None)
    if connection is None:
        return "the store answers"
    try:
        database = next(
            (row for row in connection.execute("PRAGMA database_list") if row[1] == "main"),
            None,
        )
    except Exception:  # noqa: BLE001 - a closed store must not fail the report
        return "the store answers"
    filename = str(database[2]) if database else ""
    return f"the store answers ({filename or ':memory:'})"


def _check_store(repository: Repository) -> HealthCheck:
    started = time.perf_counter()
    try:
        ok = bool(repository.health())
    except Exception:  # noqa: BLE001
        ok = False
    if not ok:
        return HealthCheck(
            ok=False, detail="the store is locked or missing", latency_ms=_elapsed_ms(started)
        )
    return HealthCheck(ok=True, detail=_store_detail(repository), latency_ms=_elapsed_ms(started))


def _check_mcp(mcp_url: str) -> HealthCheck:
    started = time.perf_counter()
    try:
        reachable = is_endpoint_reachable(mcp_url, timeout=0.3)
    except Exception:  # noqa: BLE001
        reachable = False
    detail = mcp_url if reachable else f"{mcp_url} — not reachable"
    return HealthCheck(ok=reachable, detail=detail, latency_ms=_elapsed_ms(started))


async def _check_llm(base_url: str, api_key: str, model: str) -> HealthCheck:
    started = time.perf_counter()
    try:
        healthy, message = await check_llm_health(base_url, api_key, model)
    except Exception:  # noqa: BLE001
        healthy, message = False, "the model did not answer"
    return HealthCheck(ok=healthy, detail=message, latency_ms=_elapsed_ms(started))


def _status_for(checks: dict[str, HealthCheck]) -> str:
    """``down`` when the store or sidecar is unhealthy, else ``degraded`` when
    MCP or the model is not, else ``ok``. This is the only rule."""
    if not checks["sidecar"].ok or not checks["store"].ok:
        return "down"
    if not checks["mcp"].ok or not checks["llm"].ok:
        return "degraded"
    return "ok"


async def collect_health(
    repository: Repository,
    *,
    mcp_url: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    request_id: str = "",
) -> HealthReport:
    """The one health answer: sidecar, store, MCP, and model in one report."""
    configured = defaults()
    resolved_mcp = mcp_url or configured["mcp_url"]
    resolved_base = base_url or configured["base_url"]
    resolved_key = api_key if api_key is not None else configured["api_key"]
    resolved_model = model or configured["model_name"]

    sidecar = HealthCheck(ok=True, detail="the sidecar is serving requests", latency_ms=0)

    async def guarded(coro: Any) -> HealthCheck:
        return await asyncio.wait_for(coro, timeout=HEALTH_BUDGET_S)

    try:
        store, mcp, llm = await asyncio.wait_for(
            asyncio.gather(
                asyncio.to_thread(_check_store, repository),
                asyncio.to_thread(_check_mcp, resolved_mcp),
                guarded(_check_llm(resolved_base, resolved_key, resolved_model)),
            ),
            timeout=HEALTH_BUDGET_S + 0.5,
        )
    except asyncio.TimeoutError:
        store = _check_store(repository)
        mcp = HealthCheck(
            ok=False, detail=f"{resolved_mcp} — timed out", latency_ms=int(HEALTH_BUDGET_S * 1000)
        )
        llm = HealthCheck(
            ok=False, detail="the model did not answer", latency_ms=int(HEALTH_BUDGET_S * 1000)
        )

    checks = {"sidecar": sidecar, "store": store, "mcp": mcp, "llm": llm}
    return HealthReport(status=_status_for(checks), checks=checks, request_id=request_id)


__all__ = ["HEALTH_BUDGET_S", "collect_health"]
