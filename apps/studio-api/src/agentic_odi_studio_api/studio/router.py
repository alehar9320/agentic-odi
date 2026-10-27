"""FastAPI router exposing the Living Studio sidecar API under ``/api``."""

from __future__ import annotations

import json

from agentic_odi_core import (
    JobNotFoundError,
    ODIService,
    OutcomeNotFoundError,
    StepNotFoundError,
    ToolName,
    ValueOutOfRangeError,
)
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from agentic_odi_studio_api.studio.chat import stream_chat
from agentic_odi_studio_api.studio.mcp_data import call_mcp_tool, fetch_canvas, fetch_local_canvas
from agentic_odi_studio_api.studio.probes import check_llm_health, defaults, is_endpoint_reachable
from agentic_odi_studio_api.studio.schemas import (
    AddOutcomeRequest,
    AddStepRequest,
    ChatRequest,
    CreateJobRequest,
    LlmHealthRequest,
    McpHealthRequest,
    ScheduleWorkRequest,
    UpdateJobRequest,
    UpdateOutcomeRequest,
    UpdateStepRequest,
)

router = APIRouter(prefix="/api")


def _service(request: Request) -> ODIService:
    return request.app.state.service


def _uses_mcp(request: Request) -> bool:
    return request.app.state.backend == "mcp"


def _require_mcp_url(mcp_url: str) -> str:
    if not mcp_url:
        raise HTTPException(status_code=400, detail="mcp_url is required for the mcp backend")
    return mcp_url


def _as_http_error(exc: Exception) -> HTTPException:
    """Translate domain errors into HTTP responses without leaking 500s."""
    if isinstance(exc, (JobNotFoundError, StepNotFoundError, OutcomeNotFoundError)):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueOutOfRangeError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


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


@router.post("/jobs")
async def post_job(body: CreateJobRequest, request: Request) -> dict:
    """Create a Job — works with the model offline because it is manual."""
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.ADD_JOB.value,
            {"name": body.name, "description": body.description},
        )
        return {"ok": True, "result": result}
    job = _service(request).add_job(name=body.name, description=body.description)
    return {"ok": True, "result": job.model_dump(mode="json")}


@router.patch("/jobs/{job_id}")
async def patch_job(job_id: str, body: UpdateJobRequest, request: Request) -> dict:
    updates = body.model_dump(exclude_none=True, exclude={"mcp_url"})
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.UPDATE_JOB.value,
            {"job_id": job_id, **updates},
        )
        return {"ok": True, "result": result}
    try:
        job = _service(request).update_job(job_id, updates)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True, "result": job.model_dump(mode="json")}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, request: Request, mcp_url: str | None = Query(None)) -> dict:
    if _uses_mcp(request):
        await call_mcp_tool(
            _require_mcp_url(mcp_url or ""), ToolName.DELETE_JOB.value, {"job_id": job_id}
        )
        return {"ok": True}
    try:
        _service(request).delete_job(job_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True}


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


@router.patch("/steps/{step_id}")
async def patch_step(step_id: str, body: UpdateStepRequest, request: Request) -> dict:
    updates = body.model_dump(exclude_none=True, exclude={"mcp_url"})
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.UPDATE_STEP.value,
            {"step_id": step_id, **updates},
        )
        return {"ok": True, "result": result}
    try:
        step = _service(request).update_step(step_id, updates)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True, "result": step.model_dump(mode="json")}


@router.delete("/steps/{step_id}")
async def delete_step(step_id: str, request: Request, mcp_url: str | None = Query(None)) -> dict:
    if _uses_mcp(request):
        await call_mcp_tool(
            _require_mcp_url(mcp_url or ""), ToolName.DELETE_STEP.value, {"step_id": step_id}
        )
        return {"ok": True}
    try:
        _service(request).delete_step(step_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True}


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


@router.patch("/outcomes/{outcome_id}")
async def patch_outcome(outcome_id: str, body: UpdateOutcomeRequest, request: Request) -> dict:
    updates = body.model_dump(exclude_none=True, exclude={"mcp_url"})
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.UPDATE_OUTCOME.value,
            {"outcome_id": outcome_id, **updates},
        )
        return {"ok": True, "result": result}
    try:
        outcome = _service(request).update_outcome(outcome_id, updates)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True, "result": outcome.model_dump(mode="json")}


@router.delete("/outcomes/{outcome_id}")
async def delete_outcome(
    outcome_id: str, request: Request, mcp_url: str | None = Query(None)
) -> dict:
    if _uses_mcp(request):
        await call_mcp_tool(
            _require_mcp_url(mcp_url or ""),
            ToolName.DELETE_OUTCOME.value,
            {"outcome_id": outcome_id},
        )
        return {"ok": True}
    try:
        _service(request).delete_outcome(outcome_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True}


@router.post("/chat")
async def post_chat(body: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_chat(body),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/schedule")
async def get_scheduled_work(
    request: Request,
    job_id: str | None = Query(None),
    status: str | None = Query(None),
    mcp_url: str | None = Query(None),
) -> dict:
    if _uses_mcp(request):
        url = _require_mcp_url(mcp_url or "")
        args: dict = {}
        if job_id:
            args["job_id"] = job_id
        if status:
            args["status"] = status
        res = await call_mcp_tool(url, ToolName.LIST_SCHEDULED_WORK.value, args)
        return {"ok": True, "result": json.loads(res) if isinstance(res, str) else res}
    items = _service(request).list_scheduled_work(job_id=job_id, status=status)
    return {"ok": True, "result": [item.model_dump(mode="json") for item in items]}


@router.post("/schedule")
async def post_scheduled_work(body: ScheduleWorkRequest, request: Request) -> dict:
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.SCHEDULE_WORK.value,
            {
                "name": body.name,
                "schedule_expression": body.schedule_expression,
                "agent_id": body.agent_id,
                "trigger_type": body.trigger_type,
                "payload": body.payload,
                "job_id": body.job_id,
            },
        )
        return {"ok": True, "result": result}
    work = _service(request).schedule_work(
        name=body.name,
        schedule_expression=body.schedule_expression,
        agent_id=body.agent_id,
        trigger_type=body.trigger_type,
        payload=body.payload,
        job_id=body.job_id,
    )
    return {"ok": True, "result": work.model_dump(mode="json")}


@router.post("/schedule/{work_id}/trigger")
async def post_trigger_scheduled_work(
    work_id: str, request: Request, mcp_url: str | None = Query(None)
) -> dict:
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(mcp_url or ""),
            ToolName.TRIGGER_SCHEDULED_WORK.value,
            {"work_id": work_id},
        )
        return {"ok": True, "result": result}
    try:
        work = _service(request).trigger_scheduled_work(work_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True, "result": work.model_dump(mode="json")}


@router.post("/schedule/{work_id}/cancel")
async def post_cancel_scheduled_work(
    work_id: str, request: Request, mcp_url: str | None = Query(None)
) -> dict:
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(mcp_url or ""),
            ToolName.CANCEL_SCHEDULED_WORK.value,
            {"work_id": work_id},
        )
        return {"ok": True, "result": result}
    try:
        work = _service(request).cancel_scheduled_work(work_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True, "result": work.model_dump(mode="json")}
