"""FastAPI router exposing the Living Studio sidecar API under ``/api``."""

from __future__ import annotations

from agentic_odi_core import ODIService, ToolName
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from agentic_odi_studio_api.studio.chat import stream_chat
from agentic_odi_studio_api.studio.mcp_data import call_mcp_tool, fetch_canvas, fetch_local_canvas
from agentic_odi_studio_api.studio.probes import check_llm_health, defaults, is_endpoint_reachable
from agentic_odi_studio_api.studio.schemas import (
    AddOutcomeRequest,
    AddStepRequest,
    ChatRequest,
    LlmHealthRequest,
    McpHealthRequest,
)

router = APIRouter(prefix="/api")


def _service(request: Request) -> ODIService:
    return request.app.state.service


def _uses_mcp(request: Request) -> bool:
    return request.app.state.backend == "mcp"


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
async def get_canvas(request: Request, mcp_url: str | None = Query(None)) -> dict:
    if _uses_mcp(request):
        if not mcp_url:
            raise HTTPException(status_code=400, detail="mcp_url is required for the mcp backend")
        return await fetch_canvas(mcp_url)
    return fetch_local_canvas(_service(request))


@router.post("/steps")
async def post_step(body: AddStepRequest, request: Request) -> dict:
    if _uses_mcp(request):
        result = await call_mcp_tool(
            body.mcp_url,
            ToolName.ADD_STEP.value,
            {"job_id": body.job_id, "name": body.name, "order": body.order},
        )
    else:
        result = (
            _service(request)
            .add_step(job_id=body.job_id, name=body.name, order=body.order)
            .model_dump_json()
        )
    return {"ok": True, "result": result}


@router.post("/outcomes")
async def post_outcome(body: AddOutcomeRequest, request: Request) -> dict:
    if _uses_mcp(request):
        result = await call_mcp_tool(
            body.mcp_url,
            ToolName.ADD_OUTCOME.value,
            {
                "job_id": body.job_id,
                "statement": body.statement,
                "importance": body.importance,
                "satisfaction": body.satisfaction,
            },
        )
    else:
        result = (
            _service(request)
            .add_outcome(
                job_id=body.job_id,
                statement=body.statement,
                importance=body.importance,
                satisfaction=body.satisfaction,
            )
            .model_dump_json()
        )
    return {"ok": True, "result": result}


@router.post("/chat")
async def post_chat(body: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_chat(body),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
