"""FastAPI router exposing the Living Studio sidecar API under ``/api``."""

from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

import httpx
from agentic_odi_connectors.catalog import UnknownPresetError
from agentic_odi_connectors.marketplace import DEFAULT_LIMIT, MAX_LIMIT
from agentic_odi_connectors.models import HealthStatus
from agentic_odi_connectors.registry import (
    ConnectorNotFoundError,
    DuplicateConnectorError,
)
from agentic_odi_core import (
    EvidenceNotFoundError,
    InvalidOutcomeStatementError,
    JobNotFoundError,
    NoStrategyEvidenceError,
    OdiError,
    ODIService,
    OutcomeNotFoundError,
    OutcomeProposal,
    OutcomeStatementError,
    ProposalStatus,
    SegmentNotFoundError,
    StepNotFoundError,
    ToolName,
    ValueOutOfRangeError,
    error_status,
    invalid_strategy_request,
    manual_claim_check,
)
from agentic_odi_core.remote import StudioError, StudioErrorCode
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from agentic_odi_studio_api.studio.approvals import (
    ApprovalDecision,
    ApprovalNotFoundError,
    ApprovalRegistry,
)
from agentic_odi_studio_api.studio.changelog import get_changelog
from agentic_odi_studio_api.studio.chat import stream_chat
from agentic_odi_studio_api.studio.connectors import ConnectorService
from agentic_odi_studio_api.studio.errors import (
    StudioHTTPError,
    code_for_status,
    request_id_for,
)
from agentic_odi_studio_api.studio.marketplace import StudioMarketplace
from agentic_odi_studio_api.studio.mcp_data import call_mcp_tool, fetch_canvas, fetch_local_canvas
from agentic_odi_studio_api.studio.memory import (
    ConversationNotFoundError,
    ObservationNotFoundError,
    StudioMemory,
)
from agentic_odi_studio_api.studio.probes import (
    check_llm_health,
    defaults,
    is_endpoint_reachable,
    list_models,
)
from agentic_odi_studio_api.studio.schemas import (
    AddConnectorRequest,
    AddCustomerOutcomeRequest,
    AddEvidenceRequest,
    AddOutcomeRequest,
    AddStepRequest,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApproveProposalRequest,
    CapabilitiesResponse,
    CapabilityItem,
    ChatRequest,
    ClaimOut,
    ConnectorListItem,
    ConnectorOperationResponse,
    ConversationListResponse,
    ConversationResponse,
    ConversationTreeResponse,
    CreateJobRequest,
    LatestConversationResponse,
    LlmHealthRequest,
    LlmProxyRequest,
    MarketplaceListingOut,
    MarketplaceSearchResponse,
    McpHealthRequest,
    ModelListRequest,
    ObservationCreateRequest,
    ObservationListResponse,
    ObservationResponse,
    ObservationUpdateRequest,
    PromoteEvidenceRequest,
    ProposalOut,
    ProposeOutcomeRequest,
    ProposeStrategyRequest,
    RejectProposalRequest,
    ScheduleWorkRequest,
    SignalActionRequest,
    TurnNode,
    UpdateConversationRequest,
    UpdateCustomerOutcomeRequest,
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
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.VALIDATION,
                message="mcp_url is required for the mcp backend",
                suggestion="Set the MCP server URL in Settings.",
            ),
            status_code=400,
        )
    return mcp_url


def _json_or_raw(value: str) -> Any:
    """MCP answers in text; a JSON payload is returned as the object it encodes."""
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _first_validation_error(exc: ValidationError) -> str:
    """One line naming the first field a model rejected."""
    errors = exc.errors()
    if not errors:
        return str(exc)
    first = errors[0]
    location = ".".join(str(part) for part in first.get("loc", ()))
    message = str(first.get("msg", exc))
    return f"{location}: {message}" if location else message


def _as_http_error(exc: Exception) -> StudioHTTPError:
    """Translate domain errors into typed HTTP responses without leaking 500s."""
    if isinstance(exc, ValidationError):
        return StudioHTTPError(
            StudioError(code=StudioErrorCode.VALIDATION, message=_first_validation_error(exc)),
            status_code=422,
        )
    if isinstance(exc, OutcomeStatementError):
        return StudioHTTPError(
            StudioError(code=StudioErrorCode.VALIDATION, message=str(exc)),
            status_code=422,
        )
    if isinstance(
        exc,
        (
            JobNotFoundError,
            StepNotFoundError,
            OutcomeNotFoundError,
            EvidenceNotFoundError,
            SegmentNotFoundError,
        ),
    ):
        return StudioHTTPError(StudioError(code=StudioErrorCode.NOT_FOUND, message=str(exc)))
    if isinstance(exc, NoStrategyEvidenceError):
        # Stage 6 refusing to invent a bet is a problem with the request, and the
        # MCP backend reports it with this same spelling, so both say it alike.
        return StudioHTTPError(
            StudioError(
                code=StudioErrorCode.VALIDATION,
                message=invalid_strategy_request(str(exc)),
            ),
            status_code=422,
        )
    if isinstance(exc, ValueOutOfRangeError):
        return StudioHTTPError(StudioError(code=StudioErrorCode.OUT_OF_RANGE, message=str(exc)))
    if isinstance(exc, OdiError):
        status = error_status(exc)
        return StudioHTTPError(
            StudioError(code=code_for_status(status), message=str(exc)),
            status_code=status,
        )
    return StudioHTTPError(StudioError(code=StudioErrorCode.INTERNAL, message=str(exc)))


def _payload_from_text(text: str) -> dict[str, Any]:
    """Return the JSON payload in an MCP tool result, or the text itself."""
    start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
    if start == -1:
        return {"result": text}
    try:
        payload = json.loads(text[start:])
    except json.JSONDecodeError:
        return {"result": text}
    if isinstance(payload, dict):
        return payload
    return {"result": text}


def _connectors(request: Request) -> ConnectorService:
    return request.app.state.connectors


def _memory(request: Request) -> StudioMemory:
    return request.app.state.memory


def _approvals(request: Request) -> ApprovalRegistry:
    return request.app.state.approvals


@router.get("/config")
def get_config() -> dict:
    return {"defaults": defaults()}


@router.get("/diagnostics")
def get_diagnostics(request: Request) -> dict[str, Any]:
    """Return diagnostic metadata only; never return database paths or records."""
    service = _service(request)
    repository = service.repo
    connection = getattr(getattr(repository, "store", None), "conn", None)
    db_name = "odi.db"
    size_bytes = 0
    if connection is not None:
        try:
            database = next(
                (row for row in connection.execute("PRAGMA database_list") if row[1] == "main"),
                None,
            )
            filename = str(database[2]) if database else ""
            if filename:
                db_name = Path(filename).name
                try:
                    size_bytes = Path(filename).stat().st_size
                except OSError:
                    size_bytes = 0
            else:
                db_name = ":memory:"
        except Exception:  # noqa: BLE001
            # A missing/closed local store must not make diagnostics unavailable.
            db_name = "odi.db"

    try:
        studio_version = package_version("agentic-odi-studio-api")
    except PackageNotFoundError:
        studio_version = "unknown"

    counts = {
        "jobs": len(getattr(repository, "jobs", {})),
        "outcomes": len(getattr(repository, "outcomes", {})),
        "evidence": len(getattr(repository, "evidence", {})),
        "observations": len(_memory(request).list_observations(include_dismissed=True)),
    }
    capabilities = get_capabilities(request).capabilities
    return {
        "version": studio_version,
        "python": sys.version.split()[0],
        "db": {
            "name": db_name,
            "size_bytes": size_bytes,
            "integrity": getattr(request.app.state, "db_integrity", "unknown"),
            "counts": counts,
        },
        "migrations": {"events": "current"},
        "capabilities": [capability.model_dump(mode="json") for capability in capabilities],
    }


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


@router.post("/models")
async def post_models(body: ModelListRequest) -> dict:
    """The model ids this backend serves, for the composer's model picker."""
    models, error = await list_models(body.base_url, body.api_key)
    return {"models": models, "error": error}


@router.get("/connectors/catalog")
def get_connectors_catalog(request: Request) -> list[dict[str, Any]]:
    return _connectors(request).catalog()


#: Connection types the Customize page offers. A2A is listed but not
#: implemented: the UI shows it disabled so the roadmap is visible.
CONNECTION_TYPES: list[dict[str, object]] = [
    {"id": "mcp", "label": "MCP servers", "available": True},
    {"id": "a2a", "label": "A2A agents", "available": False, "note": "Coming soon"},
]


def _marketplace(request: Request) -> StudioMarketplace:
    return request.app.state.marketplace


@router.get("/marketplace/servers", response_model=MarketplaceSearchResponse)
def search_marketplace(
    request: Request,
    q: str = Query("", description="Substring to match against name, title, or summary."),
    area: str | None = Query(None, description="Capability area filter."),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> MarketplaceSearchResponse:
    listings, cached = _marketplace(request).search(q, area, limit)
    return MarketplaceSearchResponse(
        listings=[MarketplaceListingOut.from_listing(item) for item in listings],
        areas=_marketplace(request).catalog_areas(),
        cached=cached,
        types=CONNECTION_TYPES,
    )


@router.get("/marketplace/featured", response_model=MarketplaceSearchResponse)
def featured_marketplace(
    request: Request,
    limit: int = Query(6, ge=1, le=MAX_LIMIT),
) -> MarketplaceSearchResponse:
    listings = _marketplace(request).featured(limit)
    return MarketplaceSearchResponse(
        listings=[MarketplaceListingOut.from_listing(item) for item in listings],
        areas=_marketplace(request).catalog_areas(),
        cached=False,
        types=CONNECTION_TYPES,
    )


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
        config = _connectors(request).add(
            name=body.name,
            preset_id=body.preset,
            url=body.url,
            marketplace_id=body.marketplace_id,
        )
    except DuplicateConnectorError as exc:
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.CONFLICT,
                message=str(exc),
                suggestion="Pick a different name, or remove the existing connector first.",
            )
        ) from exc
    except (ValueError, UnknownPresetError) as exc:
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.VALIDATION,
                message=str(exc),
                suggestion="Choose a preset, or supply a name and a URL.",
            ),
            status_code=400,
        ) from exc
    return ConnectorOperationResponse(ok=True, name=config.name)


@router.delete("/connectors/{name}")
def delete_connector(name: str, request: Request) -> ConnectorOperationResponse:
    try:
        _connectors(request).delete(name)
    except ConnectorNotFoundError as exc:
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.NOT_FOUND,
                message=str(exc),
                suggestion="Check the connector name in Settings.",
            )
        ) from exc
    return ConnectorOperationResponse(ok=True, name=name)


@router.post("/connectors/{name}/health")
def health_connector(name: str, request: Request) -> HealthStatus:
    try:
        return _connectors(request).health(name)
    except ConnectorNotFoundError as exc:
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.NOT_FOUND,
                message=str(exc),
                suggestion="Check the connector name in Settings.",
            )
        ) from exc


@router.get("/canvas")
async def get_canvas(request: Request, mcp_url: str | None = Query(None)) -> dict:
    if _uses_mcp(request):
        if not mcp_url:
            raise StudioHTTPError(
                StudioError(
                    code=StudioErrorCode.VALIDATION,
                    message="mcp_url is required for the mcp backend",
                    suggestion="Set the MCP server URL in Settings.",
                ),
                status_code=400,
            )
        return await fetch_canvas(mcp_url)
    return fetch_local_canvas(_service(request))


@router.get("/jobs")
async def get_jobs(request: Request, mcp_url: str | None = Query(None)) -> dict:
    if _uses_mcp(request):
        result = await call_mcp_tool(_require_mcp_url(mcp_url or ""), ToolName.GET_JOBS.value, {})
        return {"ok": True, "result": _json_or_raw(result)}
    return {
        "ok": True,
        "result": [job.model_dump(mode="json") for job in _service(request).get_jobs()],
    }


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request, mcp_url: str | None = Query(None)) -> dict:
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(mcp_url or ""), ToolName.GET_JOB.value, {"job_id": job_id}
        )
        return {"ok": True, "result": _json_or_raw(result)}
    job = _service(request).get_job(job_id)
    if job is None:
        raise _as_http_error(JobNotFoundError(job_id))
    return {"ok": True, "result": job.model_dump(mode="json")}


@router.get("/steps")
async def get_steps(
    request: Request,
    job_id: str | None = Query(None),
    mcp_url: str | None = Query(None),
) -> dict:
    service = _service(request)
    if _uses_mcp(request):
        target = _require_mcp_url(mcp_url or "")
        if job_id:
            result = await call_mcp_tool(target, ToolName.GET_JOB_MAP.value, {"job_id": job_id})
            return {"ok": True, "result": _json_or_raw(result)}
        jobs = _json_or_raw(await call_mcp_tool(target, ToolName.GET_JOBS.value, {}))
        steps: list[Any] = []
        for job in jobs if isinstance(jobs, list) else []:
            job_steps = _json_or_raw(
                await call_mcp_tool(target, ToolName.GET_JOB_MAP.value, {"job_id": job["id"]})
            )
            if isinstance(job_steps, list):
                steps.extend(job_steps)
        return {"ok": True, "result": steps}
    if job_id:
        return {
            "ok": True,
            "result": [step.model_dump(mode="json") for step in service.get_job_map(job_id)],
        }
    return {
        "ok": True,
        "result": [
            step.model_dump(mode="json")
            for job in service.get_jobs()
            for step in service.get_job_map(job.id)
        ],
    }


@router.get("/outcomes")
async def get_outcomes(
    request: Request,
    job_id: str | None = Query(None),
    step_id: str | None = Query(None),
    mcp_url: str | None = Query(None),
) -> dict:
    if _uses_mcp(request):
        target = _require_mcp_url(mcp_url or "")
        if not job_id:
            raise StudioHTTPError(
                StudioError(
                    code=StudioErrorCode.VALIDATION,
                    message="job_id is required for the mcp backend",
                    suggestion="Pass job_id, or use the local backend to list every outcome.",
                ),
                status_code=400,
            )
        arguments: dict[str, Any] = {"job_id": job_id}
        if step_id:
            arguments["step_id"] = step_id
        result = await call_mcp_tool(target, ToolName.GET_OUTCOMES.value, arguments)
        return {"ok": True, "result": _json_or_raw(result)}
    service = _service(request)
    if job_id:
        outcomes = service.get_outcomes(job_id, step_id)
    else:
        outcomes = [
            outcome
            for job in service.get_jobs()
            for outcome in service.get_outcomes(job.id, step_id)
        ]
    return {"ok": True, "result": [item.model_dump(mode="json") for item in outcomes]}


@router.post("/jobs")
async def post_job(body: CreateJobRequest, request: Request) -> dict:
    """Create a Job — works with the model offline because it is manual."""
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.ADD_JOB.value,
            {"name": body.name, "description": body.description},
        )
        return _payload_from_text(result)
    try:
        job = _service(request).add_job(name=body.name, description=body.description)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return job.model_dump(mode="json")


@router.patch("/jobs/{job_id}")
async def patch_job(job_id: str, body: UpdateJobRequest, request: Request) -> dict:
    updates = body.model_dump(exclude_none=True, exclude={"mcp_url"})
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.UPDATE_JOB.value,
            {"job_id": job_id, **updates},
        )
        return _payload_from_text(result)
    try:
        job = _service(request).update_job(job_id, updates)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return job.model_dump(mode="json")


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, request: Request, mcp_url: str | None = Query(None)) -> dict:
    if _uses_mcp(request):
        await call_mcp_tool(
            _require_mcp_url(mcp_url or ""), ToolName.DELETE_JOB.value, {"job_id": job_id}
        )
        return {"deleted": job_id}
    try:
        _service(request).delete_job(job_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"deleted": job_id}


@router.post("/steps")
async def post_step(body: AddStepRequest, request: Request) -> dict:
    if _uses_mcp(request):
        args = {"job_id": body.job_id, "name": body.name, "order": body.order}
        if body.stage is not None:
            args["stage"] = body.stage.value
        if body.allow_empty_job_map:
            args["allow_empty_job_map"] = True
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.ADD_STEP.value,
            args,
        )
        return _payload_from_text(result)
    try:
        step = _service(request).add_step(
            job_id=body.job_id,
            name=body.name,
            order=body.order,
            stage=body.stage,
            allow_empty_job_map=body.allow_empty_job_map,
        )
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return step.model_dump(mode="json")


@router.patch("/steps/{step_id}")
async def patch_step(step_id: str, body: UpdateStepRequest, request: Request) -> dict:
    updates = body.model_dump(exclude_none=True, exclude={"mcp_url"})
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.UPDATE_STEP.value,
            {"step_id": step_id, **updates},
        )
        return _payload_from_text(result)
    try:
        step = _service(request).update_step(step_id, updates)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return step.model_dump(mode="json")


@router.delete("/steps/{step_id}")
async def delete_step(step_id: str, request: Request, mcp_url: str | None = Query(None)) -> dict:
    if _uses_mcp(request):
        await call_mcp_tool(
            _require_mcp_url(mcp_url or ""), ToolName.DELETE_STEP.value, {"step_id": step_id}
        )
        return {"deleted": step_id}
    try:
        _service(request).delete_step(step_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"deleted": step_id}


@router.post("/outcomes")
async def post_outcome(body: AddOutcomeRequest, request: Request) -> dict:
    #: This endpoint is the by-hand capture path. A person typing two numbers is
    #: not an interview, so a score with no supplied check is recorded as an
    #: unverified one that says so — never as an interrogated score. The agent's
    #: own writes go through the MCP tool directly and are gated there.
    claim_check = body.claim_check
    if claim_check is None and (body.importance is not None or body.satisfaction is not None):
        claim_check = manual_claim_check()
    arguments: dict[str, Any] = {
        "job_id": body.job_id,
        "statement": body.statement,
    }
    if body.importance is not None:
        arguments["importance"] = body.importance
    if body.satisfaction is not None:
        arguments["satisfaction"] = body.satisfaction
    if claim_check is not None:
        arguments["claim_check"] = claim_check.model_dump(mode="json")
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.ADD_OUTCOME.value,
            arguments,
        )
        return _payload_from_text(result)
    try:
        outcome = _service(request).add_outcome(
            job_id=body.job_id,
            statement=body.statement,
            importance=body.importance,
            satisfaction=body.satisfaction,
            claim_check=claim_check,
        )
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return outcome.model_dump(mode="json")


@router.patch("/outcomes/{outcome_id}")
async def patch_outcome(outcome_id: str, body: UpdateOutcomeRequest, request: Request) -> dict:
    updates = body.model_dump(exclude_none=True, exclude={"mcp_url"})
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.UPDATE_OUTCOME.value,
            {"outcome_id": outcome_id, **updates},
        )
        return _payload_from_text(result)
    try:
        outcome = _service(request).update_outcome(outcome_id, updates)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return outcome.model_dump(mode="json")


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
        return {"deleted": outcome_id}
    try:
        _service(request).delete_outcome(outcome_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"deleted": outcome_id}


@router.get("/signals", response_model=list[dict[str, Any]])
async def get_signals(
    request: Request,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=1000),
    mcp_url: str | None = Query(None),
) -> list[dict[str, Any]]:
    """The signal feed, newest first. Same facts under both backends."""
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(mcp_url or ""),
            ToolName.LIST_SIGNALS.value,
            {"unread_only": unread_only, "limit": limit},
        )
        parsed = _json_or_raw(result)
        return parsed if isinstance(parsed, list) else []
    return [
        signal.model_dump(mode="json")
        for signal in _service(request).list_signals(unread_only=unread_only, limit=limit)
    ]


@router.get("/signals/unread-count")
async def get_signal_unread_count(
    request: Request, mcp_url: str | None = Query(None)
) -> dict[str, int]:
    """What the bell badge shows. Suppressed and dismissed signals never count."""
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(mcp_url or ""),
            ToolName.LIST_SIGNALS.value,
            {"unread_only": True, "limit": 1000},
        )
        parsed = _json_or_raw(result)
        return {"count": len(parsed) if isinstance(parsed, list) else 0}
    return {"count": _service(request).count_unread_signals()}


@router.post("/signals/{signal_id}/read")
async def post_signal_read(
    signal_id: str, body: SignalActionRequest, request: Request
) -> dict[str, Any]:
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.MARK_SIGNAL_READ.value,
            {"signal_id": signal_id},
        )
        return _payload_from_text(result)
    try:
        signal = _service(request).mark_signal_read(signal_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return signal.model_dump(mode="json")


@router.post("/signals/{signal_id}/dismiss")
async def post_signal_dismiss(
    signal_id: str, body: SignalActionRequest, request: Request
) -> dict[str, Any]:
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.DISMISS_SIGNAL.value,
            {"signal_id": signal_id},
        )
        return _payload_from_text(result)
    try:
        signal = _service(request).dismiss_signal(signal_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return signal.model_dump(mode="json")


@router.get("/segments", response_model=list[dict[str, Any]])
async def get_segments(
    request: Request,
    job_id: str | None = Query(None),
    mcp_url: str | None = Query(None),
) -> list[dict[str, Any]]:
    """Stage 5's segments, same records under both backends.

    Empty until the agent has run ``segment_market``: a segment is derived from
    scored outcomes, never typed in.
    """
    if _uses_mcp(request):
        arguments: dict[str, Any] = {}
        if job_id:
            arguments["job_id"] = job_id
        result = await call_mcp_tool(
            _require_mcp_url(mcp_url or ""), ToolName.GET_SEGMENTS.value, arguments
        )
        parsed = _json_or_raw(result)
        return parsed if isinstance(parsed, list) else []
    return [
        segment.model_dump(mode="json")
        for segment in _service(request).list_segments(job_id=job_id)
    ]


@router.get("/strategy", response_model=dict[str, Any] | None)
async def get_strategy(
    request: Request,
    mcp_url: str | None = Query(None),
) -> dict[str, Any] | None:
    """The recorded strategy and the paths it beat, or ``null`` before Stage 6."""
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(mcp_url or ""), ToolName.GET_STRATEGY.value, {}
        )
        parsed = _json_or_raw(result)
        return parsed if isinstance(parsed, dict) else None
    strategy = _service(request).get_strategy()
    return None if strategy is None else strategy.model_dump(mode="json")


@router.post("/strategy/propose", response_model=dict[str, Any])
async def post_strategy_propose(
    body: ProposeStrategyRequest,
    request: Request,
) -> dict[str, Any]:
    """Ask which innovation path the evidence supports.

    A 422 with the missing evidence spelled out is the honest answer when no
    path has support: the tool refuses rather than inventing a bet.
    """
    if _uses_mcp(request):
        arguments: dict[str, Any] = {}
        if body.job_id:
            arguments["job_id"] = body.job_id
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url), ToolName.PROPOSE_STRATEGY.value, arguments
        )
        return _payload_from_text(result)
    try:
        strategy = _service(request).propose_strategy(job_id=body.job_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return strategy.model_dump(mode="json")


def _customer_outcome_args(body: AddCustomerOutcomeRequest) -> dict[str, Any]:
    return {
        "job_id": body.job_id,
        "customer_value": body.customer_value.model_dump(mode="json"),
        "business_value": body.business_value.model_dump(mode="json"),
        "step_id": body.step_id,
    }


@router.get("/customer-outcomes")
async def get_customer_outcomes(
    request: Request,
    job_id: str | None = Query(None),
    mcp_url: str | None = Query(None),
) -> dict:
    if _uses_mcp(request):
        arguments: dict[str, Any] = {}
        if job_id:
            arguments["job_id"] = job_id
        result = await call_mcp_tool(
            _require_mcp_url(mcp_url or ""), ToolName.LIST_CUSTOMER_OUTCOMES.value, arguments
        )
        return {"ok": True, "result": _json_or_raw(result)}
    outcomes = _service(request).list_customer_outcomes(job_id)
    return {"ok": True, "result": [item.model_dump(mode="json") for item in outcomes]}


@router.get("/customer-outcomes/{outcome_id}")
async def get_customer_outcome(
    outcome_id: str, request: Request, mcp_url: str | None = Query(None)
) -> dict:
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(mcp_url or ""),
            ToolName.GET_CUSTOMER_OUTCOME.value,
            {"outcome_id": outcome_id},
        )
        return {"ok": True, "result": _json_or_raw(result)}
    try:
        outcome = _service(request).get_customer_outcome(outcome_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True, "result": outcome.model_dump(mode="json")}


@router.post("/customer-outcomes")
async def post_customer_outcome(body: AddCustomerOutcomeRequest, request: Request) -> dict:
    if _uses_mcp(request):
        result = await call_mcp_tool(
            body.mcp_url, ToolName.ADD_CUSTOMER_OUTCOME.value, _customer_outcome_args(body)
        )
        return {"ok": True, "result": _json_or_raw(result)}
    try:
        outcome = _service(request).add_customer_outcome(
            job_id=body.job_id,
            customer_value=body.customer_value,
            business_value=body.business_value,
            step_id=body.step_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True, "result": outcome.model_dump(mode="json")}


@router.patch("/customer-outcomes/{outcome_id}")
async def patch_customer_outcome(
    outcome_id: str, body: UpdateCustomerOutcomeRequest, request: Request
) -> dict:
    updates = body.model_dump(exclude_none=True, exclude={"mcp_url"})
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.UPDATE_CUSTOMER_OUTCOME.value,
            {"outcome_id": outcome_id, **updates},
        )
        return {"ok": True, "result": _json_or_raw(result)}
    try:
        outcome = _service(request).update_customer_outcome(outcome_id, updates)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True, "result": outcome.model_dump(mode="json")}


@router.delete("/customer-outcomes/{outcome_id}")
async def delete_customer_outcome(
    outcome_id: str, request: Request, mcp_url: str | None = Query(None)
) -> dict:
    if _uses_mcp(request):
        await call_mcp_tool(
            _require_mcp_url(mcp_url or ""),
            ToolName.DELETE_CUSTOMER_OUTCOME.value,
            {"outcome_id": outcome_id},
        )
        return {"ok": True}
    try:
        _service(request).delete_customer_outcome(outcome_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True}


@router.get("/evidence")
async def get_evidence_records(
    request: Request,
    job_id: str | None = Query(None),
    step_id: str | None = Query(None),
    outcome_id: str | None = Query(None),
    mcp_url: str | None = Query(None),
) -> dict:
    if _uses_mcp(request):
        arguments = {
            key: value
            for key, value in {
                "job_id": job_id,
                "step_id": step_id,
                "outcome_id": outcome_id,
            }.items()
            if value
        }
        result = await call_mcp_tool(
            _require_mcp_url(mcp_url or ""), ToolName.LIST_EVIDENCE.value, arguments
        )
        return {"ok": True, "result": _json_or_raw(result)}
    records = _service(request).list_evidence(job_id=job_id, step_id=step_id, outcome_id=outcome_id)
    return {"ok": True, "result": [record.model_dump(mode="json") for record in records]}


@router.get("/evidence/{evidence_id}")
async def get_evidence(
    evidence_id: str, request: Request, mcp_url: str | None = Query(None)
) -> dict:
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(mcp_url or ""),
            ToolName.GET_EVIDENCE.value,
            {"evidence_id": evidence_id},
        )
        return {"ok": True, "result": _json_or_raw(result)}
    record = _service(request).get_evidence(evidence_id)
    if record is None:
        raise _as_http_error(EvidenceNotFoundError(evidence_id))
    return {"ok": True, "result": record.model_dump(mode="json")}


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
        raise StudioHTTPError(
            StudioError(code=StudioErrorCode.VALIDATION, message=str(exc))
        ) from exc
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
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.NOT_FOUND,
                message=str(exc),
                suggestion="Check the identifier and try again.",
            )
        ) from exc
    except ValueError as exc:
        raise StudioHTTPError(
            StudioError(code=StudioErrorCode.VALIDATION, message=str(exc))
        ) from exc
    return ObservationResponse(observation=observation.to_dict())


@router.delete("/memory/observations/{observation_id}")
def delete_observation(observation_id: str, request: Request) -> dict:
    try:
        _memory(request).delete_observation(observation_id)
    except ObservationNotFoundError as exc:
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.NOT_FOUND,
                message=str(exc),
                suggestion="Check the identifier and try again.",
            )
        ) from exc
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
    turns = memory.list_turns(conversation.id)
    for turn in turns:
        turn.claims = memory.claims_for_turn(turn)
    return LatestConversationResponse(
        conversation=conversation.to_dict(),
        turns=[turn.to_dict() for turn in turns],
    )


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(request: Request) -> ConversationListResponse:
    """The history a switcher lists: every thread, most recent touch first."""
    conversations = _memory(request).list_conversations()
    return ConversationListResponse(
        conversations=[conversation.to_dict() for conversation in conversations]
    )


@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(request: Request) -> ConversationResponse:
    return ConversationResponse(conversation=_memory(request).create_conversation().to_dict())


@router.get("/conversations/{conversation_id}/tree", response_model=ConversationTreeResponse)
def conversation_tree(conversation_id: str, request: Request) -> ConversationTreeResponse:
    """The whole branch tree, so a reload reopens the branch that was on screen."""
    memory = _memory(request)
    conversation = memory.get_conversation(conversation_id)
    if conversation is None:
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.NOT_FOUND,
                message=f"Conversation {conversation_id} not found",
            )
        )
    turns = memory.conversation_tree(conversation_id)
    return ConversationTreeResponse(
        conversation=conversation.to_dict(),
        messages=[
            TurnNode(
                id=turn.message_id or f"turn-{turn.id}",
                parent_id=turn.parent_id,
                role=turn.role,
                content=turn.content,
                created_at=turn.created_at,
                claims=[ClaimOut(**claim.to_dict()) for claim in turn.claims],
            )
            for turn in turns
            if turn.role in {"user", "assistant"}
        ],
        head_id=conversation.head_id or (turns[-1].message_id if turns else None),
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
def patch_conversation(
    conversation_id: str, body: UpdateConversationRequest, request: Request
) -> ConversationResponse:
    """Record the visible branch, or rename the thread."""
    memory = _memory(request)
    try:
        if body.title is not None:
            memory.update_title(conversation_id, body.title)
        # A rename must not clear the selected branch; only touch the head when
        # the caller actually sent one.
        if "head_id" in body.model_fields_set:
            conversation = memory.set_head(conversation_id, body.head_id)
        else:
            found = memory.get_conversation(conversation_id)
            if found is None:
                raise ConversationNotFoundError(conversation_id)
            conversation = found
    except ConversationNotFoundError as exc:
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.NOT_FOUND,
                message=f"Conversation {conversation_id} not found",
            )
        ) from exc
    return ConversationResponse(conversation=conversation.to_dict())


@router.post("/approvals/{approval_id}", response_model=ApprovalDecisionResponse)
async def resolve_approval(
    approval_id: str, body: ApprovalDecisionRequest, request: Request
) -> ApprovalDecisionResponse:
    """Answer a paused write. The paused turn resumes on its own stream."""
    try:
        _approvals(request).resolve(
            approval_id, ApprovalDecision(approved=body.approved, reason=body.reason)
        )
    except ApprovalNotFoundError as exc:
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.NOT_FOUND,
                message="That approval request is no longer waiting.",
                suggestion="The turn may have ended or timed out. Send the request again.",
            )
        ) from exc
    return ApprovalDecisionResponse(ok=True, id=approval_id)


@router.post("/chat")
async def post_chat(request: Request, body: ChatRequest) -> StreamingResponse:
    # The request id is the server's: the header the client sent (or one the
    # server minted), never one the body claims, so the id in the frames, the
    # header, and the log line are always the same one.
    request_id = request_id_for(request)
    return StreamingResponse(
        stream_chat(
            body,
            service=request.app.state.connectors,
            memory=request.app.state.memory,
            request_id=request_id,
            approvals=request.app.state.approvals,
            local_service=request.app.state.service,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/capabilities", response_model=CapabilitiesResponse)
def get_capabilities(request: Request) -> CapabilitiesResponse:
    """Manifest of what this sidecar can provide to a browser BFF."""
    connectors_available = True
    try:
        _connectors(request).list()
    except Exception:  # noqa: BLE001
        connectors_available = False

    return CapabilitiesResponse(
        capabilities=[
            CapabilityItem(
                id="local-data",
                label="Local canvas data",
                description="Jobs, steps, and outcomes stored in the browser.",
                available=True,
            ),
            CapabilityItem(
                id="local-memory",
                label="Local memory and conversations",
                description="Observations and conversation history stored locally.",
                available=True,
            ),
            CapabilityItem(
                id="deterministic-assistant",
                label="Deterministic assistant",
                description="Answers about the canvas without a model.",
                available=True,
            ),
            CapabilityItem(
                id="browser-model",
                label="Browser built-in model",
                description="Uses the browser's built-in model when present.",
                available=False,
            ),
            CapabilityItem(
                id="endpoint-model",
                label="Configured model endpoint",
                description="Calls the model endpoint configured in Settings.",
                available=False,
            ),
            CapabilityItem(
                id="sidecar-llm",
                label="Sidecar model proxy",
                description="Streams model responses through this sidecar.",
                available=True,
            ),
            CapabilityItem(
                id="sidecar-connectors",
                label="Sidecar connectors",
                description="Third-party data sources through the sidecar.",
                available=connectors_available,
            ),
            CapabilityItem(
                id="sidecar-mcp",
                label="Sidecar MCP",
                description="Runs MCP servers through the sidecar.",
                available=_uses_mcp(request),
            ),
            CapabilityItem(
                id="sidecar-import",
                label="Sidecar import",
                description="Imports canvas data and memory from this sidecar.",
                available=True,
            ),
        ]
    )


@router.post("/llm/chat")
async def proxy_llm_chat(body: LlmProxyRequest) -> StreamingResponse:
    """Proxy a streaming model call so provider keys stay server-side."""
    url = f"{body.base_url.rstrip('/')}/chat/completions"

    async def event_stream():
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if body.api_key:
            headers["Authorization"] = f"Bearer {body.api_key}"
        payload: dict[str, Any] = {
            "model": body.model,
            "messages": [message.model_dump() for message in body.messages],
            "stream": body.stream,
        }
        if body.tools:
            payload["tools"] = body.tools

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code >= 400:
                        text = (await response.aread()).decode("utf-8", "replace")
                        yield (
                            "event: error\n"
                            + f"data: {json.dumps({'error': {'code': 'provider_error', 'message': text or f'HTTP {response.status_code}'}})}\n\n"
                        )
                        return
                    async for chunk in response.aiter_bytes():
                        yield chunk.decode("utf-8", "replace")
            except Exception as exc:  # noqa: BLE001
                yield (
                    "event: error\n"
                    + f"data: {json.dumps({'error': {'code': 'provider_error', 'message': str(exc)}})}\n\n"
                )

    return StreamingResponse(
        event_stream(),
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


@router.post("/evidence")
async def post_evidence(body: AddEvidenceRequest, request: Request) -> dict:
    """Capture a research record, keeping the knowledge where it already lives."""
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
    """Promote a record into a Job or a Desired Outcome."""
    if _uses_mcp(request):
        args: dict[str, Any] = {"evidence_id": evidence_id, "target": body.target}
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


def _proposal_out(proposal: OutcomeProposal) -> ProposalOut:
    """Serialize one proposal for the Studio."""
    return ProposalOut(
        id=proposal.id,
        evidence_id=proposal.evidence_id,
        job_id=proposal.job_id,
        step_id=proposal.step_id,
        statement=proposal.statement,
        direction=proposal.direction.value,
        unit_of_measure=proposal.unit_of_measure,
        object_of_control=proposal.object_of_control,
        contextual_clarifier=proposal.contextual_clarifier,
        importance=proposal.importance,
        satisfaction=proposal.satisfaction,
        confidence=proposal.confidence,
        rationale=proposal.rationale,
        quote=proposal.quote,
        source_name=proposal.source_name,
        status=proposal.status.value,
        created_at=proposal.created_at.isoformat(),
    )


@router.post("/proposals")
async def propose_outcome_api(body: ProposeOutcomeRequest, request: Request) -> dict:
    """Mine one evidence record into a scored, approvable outcome proposal."""
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.PROPOSE_OUTCOME.value,
            {"evidence_id": body.evidence_id},
        )
        return {"ok": True, "result": result}
    try:
        proposal = _service(request).propose_outcome_from_evidence(body.evidence_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True, "result": _proposal_out(proposal).model_dump(mode="json")}


@router.get("/proposals")
async def list_proposals_api(request: Request, status: str | None = Query(None)) -> dict:
    """List outcome proposals, optionally filtered by status."""
    try:
        proposal_status = ProposalStatus(status) if status is not None else None
    except ValueError as exc:
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.VALIDATION,
                message=f"invalid status '{status}'. Use proposed, approved, rejected, or edited.",
            ),
            status_code=422,
        ) from exc
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(request.query_params.get("mcp_url", "")),
            ToolName.LIST_PROPOSALS.value,
            {"status": status} if status else {},
        )
        return {"ok": True, "result": result}
    try:
        proposals = _service(request).list_proposals(status=proposal_status)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {
        "ok": True,
        "result": [_proposal_out(p) for p in proposals],
    }


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal_api(
    proposal_id: str, body: ApproveProposalRequest, request: Request
) -> dict:
    """Approve a proposal and write it as an Outcome."""
    if _uses_mcp(request):
        args: dict[str, Any] = {"proposal_id": proposal_id}
        if body.statement is not None:
            args["statement"] = body.statement
        if body.importance is not None:
            args["importance"] = body.importance
        if body.satisfaction is not None:
            args["satisfaction"] = body.satisfaction
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.APPROVE_PROPOSAL.value,
            args,
        )
        return {"ok": True, "result": result}
    try:
        outcome = _service(request).approve_proposal(
            proposal_id,
            statement=body.statement,
            importance=body.importance,
            satisfaction=body.satisfaction,
        )
    except InvalidOutcomeStatementError as exc:
        raise StudioHTTPError(
            StudioError(code=StudioErrorCode.VALIDATION, message=str(exc)),
            status_code=422,
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"ok": True, "result": outcome.model_dump(mode="json")}


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal_api(
    proposal_id: str, body: RejectProposalRequest, request: Request
) -> dict:
    """Reject a proposal. Nothing is written to the ODI store."""
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.REJECT_PROPOSAL.value,
            {"proposal_id": proposal_id},
        )
        return {"ok": True, "result": result}
    try:
        proposal = _service(request).reject_proposal(proposal_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {
        "ok": True,
        "result": _proposal_out(proposal).model_dump(mode="json"),
    }
