"""FastAPI router exposing the Living Studio sidecar API under ``/api``."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from local_server.studio.chat import stream_chat
from local_server.studio.mcp_data import call_mcp_tool, fetch_canvas
from local_server.studio.probes import check_llm_health, defaults, is_endpoint_reachable
from local_server.studio.schemas import (
    AddOutcomeRequest,
    AddStepRequest,
    ChatRequest,
    LlmHealthRequest,
    McpHealthRequest,
)

router = APIRouter(prefix="/api")


@router.get("/config")
def get_config() -> dict:
    return {"defaults": defaults()}


@router.post("/health/mcp")
def post_mcp_health(body: McpHealthRequest) -> dict:
    return {"reachable": is_endpoint_reachable(body.mcp_url)}


@router.post("/health/llm")
async def post_llm_health(body: LlmHealthRequest) -> dict:
    healthy, message = await check_llm_health(body.base_url, body.api_key, body.model)
    return {"healthy": healthy, "message": message}


@router.get("/canvas")
async def get_canvas(mcp_url: str = Query(...)) -> dict:
    return await fetch_canvas(mcp_url)


@router.post("/steps")
async def post_step(body: AddStepRequest) -> dict:
    result = await call_mcp_tool(
        body.mcp_url,
        "add_step",
        {"job_id": body.job_id, "name": body.name, "order": body.order},
    )
    return {"ok": True, "result": result}


@router.post("/outcomes")
async def post_outcome(body: AddOutcomeRequest) -> dict:
    result = await call_mcp_tool(
        body.mcp_url,
        "add_outcome",
        {
            "job_id": body.job_id,
            "statement": body.statement,
            "importance": body.importance,
            "satisfaction": body.satisfaction,
        },
    )
    return {"ok": True, "result": result}


@router.post("/chat")
async def post_chat(body: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_chat(body),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
