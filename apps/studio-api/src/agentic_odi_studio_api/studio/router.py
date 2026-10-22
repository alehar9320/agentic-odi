"""FastAPI router exposing the Living Studio sidecar API under ``/api``."""

from __future__ import annotations

from typing import Any

from agentic_odi_connectors.catalog import UnknownPresetError
from agentic_odi_connectors.models import HealthStatus
from agentic_odi_connectors.registry import (
    ConnectorNotFoundError,
    DuplicateConnectorError,
)
from agentic_odi_core import (
    JobNotFoundError,
    OdiError,
    ODIService,
    OutcomeNotFoundError,
    StepNotFoundError,
    ToolName,
    ValueOutOfRangeError,
    error_status,
)
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from agentic_odi_studio_api.studio.changelog import get_changelog
from agentic_odi_studio_api.studio.chat import stream_chat
from agentic_odi_studio_api.studio.connectors import ConnectorService
from agentic_odi_studio_api.studio.mcp_data import call_mcp_tool, fetch_canvas, fetch_local_canvas
from agentic_odi_studio_api.studio.memory import ObservationNotFoundError, StudioMemory
from agentic_odi_studio_api.studio.probes import check_llm_health, defaults, is_endpoint_reachable
from agentic_odi_studio_api.studio.schemas import (
    AddConnectorRequest,
    AddOutcomeRequest,
    AddStepRequest,
    ChatRequest,
    ConnectorListItem,
    ConnectorOperationResponse,
    ConversationResponse,
    CreateJobRequest,
    LatestConversationResponse,
    LlmHealthRequest,
    McpHealthRequest,
    ObservationCreateRequest,
    ObservationListResponse,
    ObservationResponse,
    ObservationUpdateRequest,
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
    if isinstance(exc, OdiError):
        return HTTPException(status_code=error_status(exc), detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


def _connectors(request: Request) -> ConnectorService:
    return request.app.state.connectors


def _memory(request: Request) -> StudioMemory:
    return request.app.state.memory


@router.get("/config")
def get_config() -> dict:
    return {"defaults": defaults()}


@router.get("/changelog")
def get_changelog_route() -> dict:
    return get_changelog()


@router.post("/health/mcp")
def post_mcp_health(body: McpHealthRequest) -> dict:
    return {"reachable": is_endpoint_reachable(body.mcp_url)}


@router.post("/health/llm")
async def post_llm_health(body: LlmHealthRequest) -> dict:
    healthy, message = await check_llm_health(body.base_url, body.api_key, body.model)
    return {"healthy": healthy, "message": message}


@router.get("/connectors/catalog")
def get_connectors_catalog(request: Request) -> list[dict[str, Any]]:
    return _connectors(request).catalog()


@router.get("/connectors")
def list_connectors(request: Request) -> list[ConnectorListItem]:
    service = _connectors(request)
    return [
        ConnectorListItem(name=config.name, kind=config.kind, enabled=config.enabled)
        for config in service.list()
    ]


@router.post("/connectors")
def add_connector(body: AddConnectorRequest, request: Request) -> ConnectorOperationResponse:
    try:
        config = _connectors(request).add(name=body.name, preset_id=body.preset, url=body.url)
    except DuplicateConnectorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, UnknownPresetError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ConnectorOperationResponse(ok=True, name=config.name)


@router.delete("/connectors/{name}")
def delete_connector(name: str, request: Request) -> ConnectorOperationResponse:
    try:
        _connectors(request).delete(name)
    except ConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ConnectorOperationResponse(ok=True, name=name)


@router.post("/connectors/{name}/health")
def health_connector(name: str, request: Request) -> HealthStatus:
    try:
        return _connectors(request).health(name)
    except ConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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


@router.get("/memory/observations", response_model=ObservationListResponse)
def list_observations(request: Request) -> ObservationListResponse:
    observations = _memory(request).list_observations()
    return ObservationListResponse(
        observations=[observation.to_dict() for observation in observations]
    )


@router.post("/memory/observations", response_model=ObservationResponse)
def create_observation(body: ObservationCreateRequest, request: Request) -> ObservationResponse:
    try:
        observation = _memory(request).add_observation(
            kind=body.kind,
            text=body.text,
            data=body.data,
            status="confirmed" if body.confirmed else "suggested",
            confidence=body.confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ObservationResponse(observation=observation.to_dict())


@router.patch("/memory/observations/{observation_id}", response_model=ObservationResponse)
def update_observation(
    observation_id: str, body: ObservationUpdateRequest, request: Request
) -> ObservationResponse:
    try:
        observation = _memory(request).update_observation(
            observation_id,
            text=body.text,
            status=body.status,
            data=body.data,
            confidence=body.confidence,
        )
    except ObservationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ObservationResponse(observation=observation.to_dict())


@router.delete("/memory/observations/{observation_id}")
def delete_observation(observation_id: str, request: Request) -> dict:
    try:
        _memory(request).delete_observation(observation_id)
    except ObservationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@router.delete("/memory")
def clear_memory(request: Request) -> dict:
    _memory(request).clear_memory()
    return {"ok": True}


@router.get("/conversations/latest", response_model=LatestConversationResponse)
def latest_conversation(request: Request) -> LatestConversationResponse:
    memory = _memory(request)
    conversation = memory.latest_conversation()
    if conversation is None:
        return LatestConversationResponse(conversation=None, turns=[])
    return LatestConversationResponse(
        conversation=conversation.to_dict(),
        turns=[turn.to_dict() for turn in memory.list_turns(conversation.id)],
    )


@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(request: Request) -> ConversationResponse:
    return ConversationResponse(conversation=_memory(request).create_conversation().to_dict())


@router.post("/chat")
async def post_chat(request: Request, body: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_chat(body, service=request.app.state.connectors, memory=request.app.state.memory),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
