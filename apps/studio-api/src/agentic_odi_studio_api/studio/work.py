"""Studio API routes for orchestrator work, runs, targets, and daemon status."""

from __future__ import annotations

from typing import Any

from agentic_odi_core.remote import StudioError, StudioErrorCode
from agentic_odi_integrations_openhands.service import (
    InvalidTransition,
    OrchestratorError,
    OrchestratorService,
    TargetNotConfigured,
    WorkItemNotFound,
)
from fastapi import APIRouter, Query, Request

from agentic_odi_studio_api.studio.errors import StudioHTTPError
from agentic_odi_studio_api.studio.schemas import AddWorkItemRequest

router = APIRouter(prefix="/api")


def _orchestrator(request: Request) -> OrchestratorService:
    service = getattr(request.app.state, "orchestrator", None)
    if service is None:
        service = OrchestratorService()
        request.app.state.orchestrator = service
    return service


def _http_error(exc: Exception) -> StudioHTTPError:
    if isinstance(exc, WorkItemNotFound):
        return StudioHTTPError(StudioError(code=StudioErrorCode.NOT_FOUND, message=str(exc)))
    if isinstance(exc, InvalidTransition):
        return StudioHTTPError(StudioError(code=StudioErrorCode.CONFLICT, message=str(exc)))
    if isinstance(exc, (TargetNotConfigured, ValueError)):
        return StudioHTTPError(StudioError(code=StudioErrorCode.VALIDATION, message=str(exc)))
    if isinstance(exc, OrchestratorError):
        return StudioHTTPError(StudioError(code=StudioErrorCode.INTERNAL, message=str(exc)))
    return StudioHTTPError(StudioError(code=StudioErrorCode.INTERNAL, message=str(exc)))


def _work_view(service: OrchestratorService, work: Any) -> dict[str, Any]:
    run = service.latest_run(work.id)
    return {
        "work_item": work.model_dump(mode="json"),
        "latest_run": run.public_view() if run is not None else None,
    }


@router.get("/work-items")
def list_work_items(
    request: Request,
    status: str | None = Query(None),
    source: str | None = Query(None),
) -> dict[str, Any]:
    try:
        service = _orchestrator(request)
        items = service.list_work_items(status=status, source_kind=source)
        views = [service.latest_run(item.id) for item in items]
    except Exception as exc:  # noqa: BLE001 - rendered as a typed Studio error
        raise _http_error(exc) from exc
    return {
        "work_items": [
            {
                "work_item": item.model_dump(mode="json"),
                "latest_run": run.public_view() if run is not None else None,
            }
            for item, run in zip(items, views, strict=True)
        ]
    }


@router.post("/work-items")
def add_work_item(body: AddWorkItemRequest, request: Request) -> dict[str, Any]:
    try:
        work, created = _orchestrator(request).add_work_item(
            body.title,
            body.prompt,
            target_alias=body.target,
            repository=body.repository,
            branch=body.branch,
            priority=body.priority,
            work_key=body.work_key,
            job_id=body.job_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
    return {"created": created, "work_item": work.model_dump(mode="json")}


@router.get("/work-items/{work_id}")
def get_work_item(work_id: str, request: Request) -> dict[str, Any]:
    try:
        service = _orchestrator(request)
        return _work_view(service, service.get_work_item(work_id))
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.post("/work-items/{work_id}/cancel")
def cancel_work_item(work_id: str, request: Request) -> dict[str, Any]:
    try:
        work = _orchestrator(request).cancel_work_item(work_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
    return {"work_item": work.model_dump(mode="json")}


@router.post("/work-items/{work_id}/retry")
def retry_work_item(work_id: str, request: Request) -> dict[str, Any]:
    try:
        work = _orchestrator(request).retry_work_item(work_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
    return {"work_item": work.model_dump(mode="json")}


@router.get("/agent-targets")
def list_agent_targets(request: Request) -> dict[str, Any]:
    try:
        targets = _orchestrator(request).targets()
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
    return {"targets": [target.public_view() for target in targets]}


@router.get("/agent-runs")
def list_agent_runs(
    request: Request, work_id: str | None = Query(None)
) -> dict[str, Any]:
    try:
        runs = _orchestrator(request).list_runs(work_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
    return {"runs": [run.public_view() for run in runs]}


@router.get("/orchestrator/status")
def orchestrator_status(request: Request) -> dict[str, Any]:
    try:
        status = _orchestrator(request).status()
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
    return {"status": status.model_dump(mode="json")}
