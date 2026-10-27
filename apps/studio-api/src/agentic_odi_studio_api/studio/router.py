"""FastAPI router exposing the Living Studio sidecar API under ``/api``."""

from __future__ import annotations

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
    AddEvidenceRequest,
    AddOutcomeRequest,
    AddStepRequest,
    ChatRequest,
    CreateJobRequest,
    LlmHealthRequest,
    McpHealthRequest,
    PromoteEvidenceRequest,
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



@router.post("/evidence")
async def post_evidence(body: AddEvidenceRequest, request: Request) -> dict:
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.ADD_EVIDENCE.value,
            {
                "source_name": body.source_name,
                "source_kind": body.source_kind,
                "name": body.name,
                "content": body.content,
                "url": body.url,
                "item_type": body.item_type,
                "job_id": body.job_id,
                "step_id": body.step_id,
                "outcome_id": body.outcome_id,
            },
        )
        return {"ok": True, "result": result}
    try:
        evidence = _service(request).add_evidence(
            source_name=body.source_name,
            source_kind=body.source_kind,
            name=body.name,
            content=body.content,
            url=body.url,
            item_type=body.item_type,
            job_id=body.job_id,
            step_id=body.step_id,
            outcome_id=body.outcome_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True, "result": evidence.model_dump(mode="json")}


@router.delete("/evidence/{evidence_id}")
async def delete_evidence(
    evidence_id: str, request: Request, mcp_url: str | None = Query(None)
) -> dict:
    if _uses_mcp(request):
        await call_mcp_tool(
            _require_mcp_url(mcp_url or ""),
            ToolName.DELETE_EVIDENCE.value,
            {"evidence_id": evidence_id},
        )
        return {"ok": True}
    try:
        _service(request).delete_evidence(evidence_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True}


@router.post("/evidence/{evidence_id}/promote")
async def promote_evidence(
    evidence_id: str, body: PromoteEvidenceRequest, request: Request
) -> dict:
    if _uses_mcp(request):
        args = {"evidence_id": evidence_id, "target": body.target}
        if body.job_id:
            args["job_id"] = body.job_id
        if body.statement:
            args["statement"] = body.statement
        if body.name:
            args["name"] = body.name
        if body.importance is not None:
            args["importance"] = body.importance
        if body.satisfaction is not None:
            args["satisfaction"] = body.satisfaction
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.PROMOTE_EVIDENCE.value,
            args,
        )
        return {"ok": True, "result": result}
    try:
        artifact = _service(request).promote_evidence(
            evidence_id=evidence_id,
            target=body.target,
            job_id=body.job_id,
            statement=body.statement,
            name=body.name,
            importance=body.importance,
            satisfaction=body.satisfaction,
        )
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True, "result": artifact.model_dump(mode="json")}
