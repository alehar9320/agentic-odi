"""FastAPI router exposing the Living Studio sidecar API under ``/api``."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
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
    DecisionNotFoundError,
    EvidenceNotFoundError,
    JobNotFoundError,
    OdiError,
    ODIService,
    OutcomeNotFoundError,
    OutcomeStatementError,
    Rejection,
    SegmentNotFoundError,
    StepNotFoundError,
    ToolName,
    ValueOutOfRangeError,
    error_status,
    outcome_delta,
)
from agentic_odi_core.remote import StudioError, StudioErrorCode
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

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
    AcceptSegmentCandidateRequest,
    AddConnectorRequest,
    AddCustomerOutcomeRequest,
    AddEvidenceRequest,
    AddOutcomeRequest,
    AddSegmentRequest,
    AddStepRequest,
    AdvanceBetRequest,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    CapabilitiesResponse,
    CapabilityItem,
    ChatRequest,
    ChooseStrategyRequest,
    ConnectorListItem,
    ConnectorOperationResponse,
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
    RecordBetRequest,
    RecordDecisionRequest,
    ReviewDecisionRequest,
    ScheduleWorkRequest,
    SetOutcomeValueRequest,
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


def _as_http_error(exc: Exception) -> StudioHTTPError:
    """Translate domain errors into typed HTTP responses without leaking 500s."""
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
            DecisionNotFoundError,
            EvidenceNotFoundError,
        ),
    ):
        return StudioHTTPError(StudioError(code=StudioErrorCode.NOT_FOUND, message=str(exc)))
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


@router.get("/compare")
async def get_compare(
    request: Request,
    outcome_ids: str = Query(""),
) -> dict:
    """Align two or three outcomes on shared axes, one row per metric.

    The ids are taken explicitly and in order, so the surface cannot compare a
    different set than the one the user saw. A missing metric renders the
    literal ``not measured``; a real recorded ``0`` stays ``0``.
    """
    ids = [item.strip() for item in outcome_ids.split(",") if item.strip()]
    try:
        comparison = _service(request).compare_outcomes(ids)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {
        "columns": list(comparison.columns),
        "statements": list(comparison.statements),
        "rows": [
            {"metric": row.metric, "label": row.label, "cells": list(row.cells)}
            for row in comparison.rows
        ],
    }


@router.post("/decisions")
async def post_decision(body: RecordDecisionRequest, request: Request) -> dict:
    """Record a decision, optionally superseding an earlier one.

    The transport is all this adds: the service validates the rationale, the
    chosen and rejected ids, and the supersession, so the CLI and this route
    cannot disagree about what a valid decision is.
    """
    decided_at = body.decided_at or datetime.now(timezone.utc).isoformat()
    rejected = [{"outcome_id": item.outcome_id, "reason": item.reason} for item in body.rejected]
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.RECORD_DECISION.value,
            {
                "job_id": body.job_id,
                "chosen_outcome_ids": body.chosen_outcome_ids,
                "rationale": body.rationale,
                "decided_by": body.decided_by,
                "decided_at": decided_at,
                "rejected": rejected,
                "confidence": body.confidence.value,
                "supersedes": body.supersedes,
            },
        )
        return _payload_from_text(result)
    try:
        decision = _service(request).record_decision(
            job_id=body.job_id,
            chosen_outcome_ids=body.chosen_outcome_ids,
            rationale=body.rationale,
            decided_by=body.decided_by,
            decided_at=decided_at,
            rejected=[Rejection(**item) for item in rejected],
            confidence=body.confidence,
            supersedes=body.supersedes,
        )
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return decision.model_dump(mode="json")


@router.get("/decisions")
async def get_decisions(request: Request, job_id: str = Query(...)) -> list[dict]:
    """The decision history for a job, oldest first, superseded entries kept."""
    try:
        decisions = _service(request).list_decisions(job_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return [decision.model_dump(mode="json") for decision in decisions]


@router.get("/roadmap")
async def get_roadmap(
    request: Request,
    job_id: str = Query(...),
    horizon: int = Query(4),
    today: str | None = Query(None),
) -> dict:
    """The derived outcome roadmap for a job, from its recorded decisions.

    A view over the decision log, not a store: entries are grouped by the
    quarter of the decision date in UTC. Undecided outcomes are excluded and
    counted, and a baseline nobody measured renders ``not measured`` — never
    ``0``. ``today`` pins the window so a caller's view is reproducible.
    """
    pinned: date | None = None
    if today:
        try:
            pinned = date.fromisoformat(today)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "validation_error",
                    "message": "today must be an ISO-8601 date",
                },
            ) from exc
    try:
        roadmap = _service(request).build_roadmap(job_id, horizon=horizon, today=pinned)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {
        "entries": [
            {
                "period": entry.period,
                "outcome_id": entry.outcome_id,
                "statement": entry.statement,
                "decision_id": entry.decision_id,
                "baseline": entry.baseline,
                "target": entry.target,
            }
            for entry in roadmap.entries
        ],
        "undecided_count": roadmap.undecided_count,
        "horizon_excluded_count": roadmap.horizon_excluded_count,
        "superseded_excluded_count": roadmap.superseded_excluded_count,
        "horizon": roadmap.horizon,
        "exclusion_note": roadmap.exclusion_note(),
    }


@router.post("/decisions/review")
async def post_decision_review(body: ReviewDecisionRequest, request: Request) -> dict:
    """Re-examine a past decision against today's numbers.

    A read-only projection: it writes nothing, not even a review record. Each
    chosen outcome is improved, degraded, no change, no evidence, or orphaned.
    ``today`` is supplied so the elapsed-days figure is reproducible.
    """
    if body.today:
        try:
            today = date.fromisoformat(body.today)
        except ValueError as exc:
            raise StudioHTTPError(
                StudioError(
                    code=StudioErrorCode.VALIDATION, message="today must be an ISO-8601 date"
                ),
                status_code=422,
            ) from exc
    else:
        today = datetime.now(timezone.utc).date()
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.REVIEW_DECISION.value,
            {"decision_id": body.decision_id, "today": today.isoformat()},
        )
        return _payload_from_text(result)
    try:
        review = _service(request).review_decision(body.decision_id, today=today)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {
        "decision_id": review.decision_id,
        "job_id": review.job_id,
        "decided_at": review.decided_at,
        "days_elapsed": review.days_elapsed,
        "stale": review.stale,
        "summary": review.summary(),
        "outcomes": [
            {
                "outcome_id": o.outcome_id,
                "statement": o.statement,
                "state": o.state,
                "satisfaction_change": o.satisfaction_change,
                "importance_change": o.importance_change,
                "opportunity_change": o.opportunity_change,
            }
            for o in review.outcomes
        ],
    }


@router.get("/outcomes/{outcome_id}/history")
async def get_outcome_history(outcome_id: str, request: Request) -> list[dict]:
    """Every recorded score snapshot for an outcome, oldest first."""
    try:
        snapshots = _service(request).list_score_snapshots(outcome_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return [s.model_dump(mode="json") for s in snapshots]


@router.get("/outcomes/{outcome_id}/delta")
async def get_outcome_delta(
    outcome_id: str, request: Request, since: str | None = Query(None)
) -> dict | None:
    """The signed change for an outcome, per metric. Missing is null, never 0."""
    try:
        service = _service(request)
        delta = outcome_delta(service.list_score_snapshots(), outcome_id, since=since)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    if delta is None:
        return None
    return {
        "importance": delta.importance,
        "satisfaction": delta.satisfaction,
        "opportunity": delta.opportunity,
        "direction": delta.direction,
    }


@router.post("/bets")
async def post_bet(body: RecordBetRequest, request: Request) -> dict:
    """Record a bet, capturing its baseline at creation."""
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.RECORD_BET.value,
            {
                "decision_id": body.decision_id,
                "outcome_id": body.outcome_id,
                "hypothesis": body.hypothesis,
                "target": body.target,
                "measure_by": body.measure_by,
                "baseline": body.baseline,
            },
        )
        return _payload_from_text(result)
    try:
        bet = _service(request).record_bet(
            decision_id=body.decision_id,
            outcome_id=body.outcome_id,
            hypothesis=body.hypothesis,
            target=body.target,
            measure_by=body.measure_by,
            baseline=body.baseline,
        )
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return bet.model_dump(mode="json")


@router.get("/bets")
async def get_bets(
    request: Request,
    job_id: str | None = Query(None),
    decision_id: str | None = Query(None),
) -> list[dict]:
    try:
        bets = _service(request).list_bets(job_id=job_id, decision_id=decision_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return [b.model_dump(mode="json") for b in bets]


@router.post("/bets/{bet_id}/advance")
async def post_bet_advance(bet_id: str, body: AdvanceBetRequest, request: Request) -> dict:
    """Move a bet to a new status, refusing an illegal transition."""
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.ADVANCE_BET.value,
            {"bet_id": bet_id, "status": body.status.value, "at": body.at},
        )
        return _payload_from_text(result)
    try:
        bet = _service(request).advance_bet(bet_id, body.status, at=body.at)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return bet.model_dump(mode="json")


@router.post("/segments")
async def post_segment(body: AddSegmentRequest, request: Request) -> dict:
    """Create a segment from its member outcomes."""
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.ADD_SEGMENT.value,
            {
                "job_id": body.job_id,
                "name": body.name,
                "criterion": body.criterion,
                "outcome_ids": body.outcome_ids,
                "notes": body.notes,
                "origin": body.origin.value,
            },
        )
        return _payload_from_text(result)
    try:
        segment = _service(request).add_segment(
            job_id=body.job_id,
            name=body.name,
            criterion=body.criterion,
            outcome_ids=body.outcome_ids,
            notes=body.notes,
            origin=body.origin,
        )
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return segment.model_dump(mode="json")


@router.get("/segments")
async def get_segments(
    request: Request,
    job_id: str | None = Query(None),
) -> list[dict]:
    try:
        segments = _service(request).list_segments(job_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return [s.model_dump(mode="json") for s in segments]


@router.get("/segments/{segment_id}")
async def get_segment(segment_id: str, request: Request) -> dict:
    try:
        segment = _service(request).get_segment(segment_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    if segment is None:
        raise _as_http_error(SegmentNotFoundError(segment_id))
    return segment.model_dump(mode="json")


@router.delete("/segments/{segment_id}")
async def delete_segment(segment_id: str, request: Request) -> dict:
    """Delete a segment. Outcomes are never touched."""
    try:
        _service(request).delete_segment(segment_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {"deleted": segment_id}


@router.get("/segments/{segment_id}/profile")
async def get_segment_profile(segment_id: str, request: Request) -> dict:
    """Read a segment's servability: underserved vs overserved, kept separate."""
    try:
        profile = _service(request).segment_profile(segment_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {
        "segment_id": profile.segment_id,
        "segment_name": profile.segment_name,
        "total_members": profile.total_members,
        "measured_count": profile.measured_count,
        "unscored_count": profile.unscored_count,
        "missing_count": profile.missing_count,
        "underserved_count": profile.underserved_count,
        "appropriate_count": profile.appropriate_count,
        "overserved_count": profile.overserved_count,
        "top_underserved": [
            {"outcome_id": e.outcome_id, "statement": e.statement, "score": e.score, "band": e.band}
            for e in profile.top_underserved
        ],
        "top_overserved": [
            {"outcome_id": e.outcome_id, "statement": e.statement, "score": e.score, "band": e.band}
            for e in profile.top_overserved
        ],
        "measured_ratio": profile.measured_ratio,
        "gaps": list(profile.gaps),
    }


@router.get("/jobs/{job_id}/segment-candidates")
async def get_segment_candidates(job_id: str, request: Request) -> dict:
    """Propose segment candidates from the scores. Writes nothing."""
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(request.query_params.get("mcp_url", "")),
            ToolName.SUGGEST_SEGMENTS.value,
            {"job_id": job_id},
        )
        return _payload_from_text(result)
    try:
        candidates = _service(request).suggest_segments(job_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return {
        "candidates": [
            {
                "name": c.name,
                "members": list(c.members),
                "rationale": c.rationale,
                "evidence_count": c.evidence_count,
                "segment": c.segment,
                "decile": c.decile,
                "fingerprint": c.fingerprint,
            }
            for c in candidates.candidates
        ],
        "reason": candidates.reason,
    }


@router.post("/segment-candidates/accept")
async def post_accept_segment_candidate(
    body: AcceptSegmentCandidateRequest, request: Request
) -> dict:
    """Accept a suggested candidate into a segment."""
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.ACCEPT_SEGMENT_CANDIDATE.value,
            {
                "job_id": body.job_id,
                "fingerprint": body.fingerprint,
                "name": body.name,
                "criterion": body.criterion,
            },
        )
        return _payload_from_text(result)
    try:
        segment = _service(request).accept_segment_candidate(
            job_id=body.job_id,
            fingerprint=body.fingerprint,
            name=body.name,
            criterion=body.criterion,
        )
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return segment.model_dump(mode="json")


@router.post("/segments/{segment_id}/strategy")
async def post_strategy(segment_id: str, body: ChooseStrategyRequest, request: Request) -> dict:
    """Record a strategy for a segment, refusing one its data does not support."""
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.CHOOSE_STRATEGY.value,
            {
                "segment_id": segment_id,
                "kind": body.kind.value,
                "rationale": body.rationale,
                "expected_effect": body.expected_effect,
                "chosen_at": body.chosen_at,
            },
        )
        return _payload_from_text(result)
    try:
        strategy = _service(request).choose_strategy(
            segment_id=segment_id,
            kind=body.kind,
            rationale=body.rationale,
            expected_effect=body.expected_effect,
            chosen_at=body.chosen_at,
        )
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return strategy.model_dump(mode="json")


@router.get("/strategies")
async def get_strategies(request: Request, segment_id: str | None = Query(None)) -> list[dict]:
    try:
        strategies = _service(request).list_strategies(segment_id)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return [s.model_dump(mode="json") for s in strategies]


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
    if _uses_mcp(request):
        payload = {
            "job_id": body.job_id,
            "statement": body.statement,
            "importance": body.importance,
            "satisfaction": body.satisfaction,
        }
        for key in ("importance_n", "satisfaction_n"):
            if getattr(body, key) is not None:
                payload[key] = getattr(body, key)
        if body.score_method != "estimate":
            payload["score_method"] = body.score_method
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.ADD_OUTCOME.value,
            payload,
        )
        return _payload_from_text(result)
    try:
        outcome = _service(request).add_outcome(
            job_id=body.job_id,
            statement=body.statement,
            importance=body.importance,
            satisfaction=body.satisfaction,
            importance_n=body.importance_n,
            satisfaction_n=body.satisfaction_n,
            score_method=body.score_method,
        )
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return outcome.model_dump(mode="json")


@router.patch("/outcomes/{outcome_id}")
async def patch_outcome(outcome_id: str, body: UpdateOutcomeRequest, request: Request) -> dict:
    updates = body.model_dump(exclude_none=True, exclude={"mcp_url", "at", "note"})
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.UPDATE_OUTCOME.value,
            {"outcome_id": outcome_id, "at": body.at, "note": body.note, **updates},
        )
        return _payload_from_text(result)
    try:
        outcome = _service(request).update_outcome(outcome_id, updates, at=body.at, note=body.note)
    except Exception as exc:  # noqa: BLE001
        raise _as_http_error(exc) from exc
    return outcome.model_dump(mode="json")


@router.patch("/outcomes/{outcome_id}/value")
async def set_outcome_value(
    outcome_id: str, body: SetOutcomeValueRequest, request: Request
) -> dict:
    """Record what an opportunity is worth, with its unit and its basis (W1).

    A separate route, not a patch field, because setting a value is a distinct
    act from editing a statement and the basis rules differ. A market or pilot
    basis without a source is refused by the service, so the API and CLI agree.
    """
    payload = body.model_dump(exclude={"mcp_url"})
    if _uses_mcp(request):
        result = await call_mcp_tool(
            _require_mcp_url(body.mcp_url),
            ToolName.SET_OUTCOME_VALUE.value,
            {"outcome_id": outcome_id, **payload},
        )
        return _payload_from_text(result)
    try:
        outcome = _service(request).set_outcome_value(outcome_id, **payload)
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
    return LatestConversationResponse(
        conversation=conversation.to_dict(),
        turns=[turn.to_dict() for turn in memory.list_turns(conversation.id)],
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
