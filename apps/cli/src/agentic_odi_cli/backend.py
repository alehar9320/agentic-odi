"""Backend abstraction for the CLI.

Two backends implement the same :class:`Backend` seam:

* :class:`LocalBackend` runs the ODI logic directly against a local SQLite
  store (no server required).
* :class:`MCPBackend` delegates to a remote MCP server over HTTP, which may be
  a local ``python -m agentic_odi_mcp_server`` process or a hosted endpoint.

Commands resolve a backend once from the options stored on
:mod:`agentic_odi_cli.context`. Keeping the local and remote paths behind one interface
means the same command works against either, and a future hosted backend only
has to implement ``call``.
"""

from __future__ import annotations

import asyncio
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import typer

if TYPE_CHECKING:
    from agentic_odi_core import ODIService

# Kept as literals so importing the CLI does not pull in the core package
# (``agentic-odi --version`` must stay lightweight). ``tests/contract`` asserts
# these keys match ``agentic_odi_core.contract.TOOL_NAMES``.

DEFAULT_BACKEND = "local"
DEFAULT_MCP_URL = "http://localhost:8000/mcp"
DEFAULT_MCP_TIMEOUT = 30.0

_VALUE_RANGE_ERROR = "importance and satisfaction must be between 1.0 and 10.0"

_CUSTOMER_VALUE_FIELDS = (
    "direction",
    "unit_of_measure",
    "object_of_control",
    "contextual_clarifier",
    "statement",
    "importance",
    "satisfaction",
    "value_metrics",
)

_BUSINESS_VALUE_FIELDS = {
    "category": "category",
    "business_statement": "statement",
    "detail": "detail",
    "estimated_annual_value": "estimated_annual_value",
    "confidence": "confidence",
}


class BackendError(Exception):
    """A user-facing failure: not found, invalid input, or unreachable server.

    ``suggestion`` (when given) is rendered as a trailing hint so the user has a
    next action instead of just a red line.
    """

    def __init__(self, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.suggestion = suggestion

    @property
    def message(self) -> str:
        return self.args[0] if self.args else ""


def mcp_timeout() -> float:
    """Resolve the MCP call timeout in seconds (``AGENTIC_ODI_MCP_TIMEOUT``)."""
    raw = os.environ.get("AGENTIC_ODI_MCP_TIMEOUT")
    if not raw:
        return DEFAULT_MCP_TIMEOUT
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_MCP_TIMEOUT


def _validation_message(exc: Exception) -> str:
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            first = errors()[0]
        except (IndexError, TypeError):
            return str(exc)
        return f"Invalid customer outcome: {first.get('msg', exc)}"
    return f"Invalid customer outcome: {exc}"


class Backend(ABC):
    @abstractmethod
    def call(self, tool_name: str, args: dict[str, Any]) -> Any:
        """Run ``tool_name`` and return parsed data (dict, list, str, or float)."""


class LocalBackend(Backend):
    """Run ODI logic in-process against a local SQLite store."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path
        self._service: ODIService | None = None

    @property
    def service(self) -> ODIService:
        if self._service is None:
            from agentic_odi_core import ODIService
            from agentic_odi_core.sqlite_repository import SQLiteRepository

            self._service = ODIService(SQLiteRepository(db_path=self._db_path))
        return self._service

    def call(self, tool_name: str, args: dict[str, Any]) -> Any:
        from agentic_odi_core import OdiError

        handler = _LOCAL_HANDLERS.get(tool_name)
        if handler is None:
            raise NotImplementedError(f"Unknown tool: {tool_name}")
        try:
            return handler(self, args)
        except OdiError as exc:
            raise BackendError(str(exc)) from exc

    def _add_job(self, args: dict[str, Any]) -> dict[str, Any]:
        job = self.service.add_job(name=args["name"], description=args.get("description"))
        return job.model_dump()

    def _get_jobs(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {}
        if "limit" in args:
            kwargs["limit"] = args["limit"]
        if "offset" in args:
            kwargs["offset"] = args["offset"]
        return [job.model_dump() for job in self.service.get_jobs(**kwargs)]

    def _get_job(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import job_not_found

        job_id = args["job_id"]
        job = self.service.get_job(job_id)
        if job is None:
            raise BackendError(job_not_found(job_id))
        return job.model_dump()

    def _update_job(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import JobNotFoundError, job_not_found

        updates: dict[str, Any] = {key: args[key] for key in ("name", "description") if key in args}
        try:
            job = self.service.update_job(args["job_id"], updates)
        except JobNotFoundError:
            raise BackendError(job_not_found(args["job_id"])) from None
        return job.model_dump()

    def _delete_job(self, args: dict[str, Any]) -> str:
        from agentic_odi_core import JobNotFoundError, job_not_found

        job_id = args["job_id"]
        try:
            self.service.delete_job(job_id)
        except JobNotFoundError:
            raise BackendError(job_not_found(job_id)) from None
        return job_id

    def _add_step(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import JobNotFoundError, job_not_found

        try:
            step = self.service.add_step(
                job_id=args["job_id"],
                name=args["name"],
                order=args["order"],
                stage=args.get("stage"),
                allow_empty_job_map=args.get("allow_empty_job_map", False),
            )
        except JobNotFoundError:
            raise BackendError(job_not_found(args["job_id"])) from None
        return step.model_dump()

    def _get_job_map(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        from agentic_odi_core import job_not_found

        job_id = args["job_id"]
        if self.service.get_job(job_id) is None:
            raise BackendError(job_not_found(job_id))
        kwargs: dict[str, Any] = {"job_id": job_id}
        if "limit" in args:
            kwargs["limit"] = args["limit"]
        if "offset" in args:
            kwargs["offset"] = args["offset"]
        return [step.model_dump() for step in self.service.get_job_map(**kwargs)]

    def _get_step(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import step_not_found

        step_id = args["step_id"]
        step = self.service.get_step(step_id)
        if step is None:
            raise BackendError(step_not_found(step_id))
        return step.model_dump()

    def _update_step(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import StepNotFoundError, step_not_found

        updates: dict[str, Any] = {key: args[key] for key in ("name", "order") if key in args}
        try:
            step = self.service.update_step(args["step_id"], updates)
        except StepNotFoundError:
            raise BackendError(step_not_found(args["step_id"])) from None
        return step.model_dump()

    def _delete_step(self, args: dict[str, Any]) -> str:
        from agentic_odi_core import StepNotFoundError, step_not_found

        step_id = args["step_id"]
        try:
            self.service.delete_step(step_id)
        except StepNotFoundError:
            raise BackendError(step_not_found(step_id)) from None
        return step_id

    def _add_outcome(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import (
            JobNotFoundError,
            StepNotFoundError,
            ValueOutOfRangeError,
            job_not_found,
            step_not_found,
        )

        step_id = args.get("step_id")
        try:
            outcome = self.service.add_outcome(
                job_id=args["job_id"],
                statement=args["statement"],
                importance=float(args["importance"]),
                satisfaction=float(args["satisfaction"]),
                step_id=step_id,
            )
        except JobNotFoundError:
            raise BackendError(job_not_found(args["job_id"])) from None
        except StepNotFoundError:
            raise BackendError(step_not_found(step_id)) from None
        except ValueOutOfRangeError as exc:
            raise BackendError(_VALUE_RANGE_ERROR) from exc
        return outcome.model_dump()

    def _get_outcomes(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        from agentic_odi_core import job_not_found

        job_id = args["job_id"]
        if self.service.get_job(job_id) is None:
            raise BackendError(job_not_found(job_id))
        kwargs: dict[str, Any] = {"job_id": job_id, "step_id": args.get("step_id")}
        if "limit" in args:
            kwargs["limit"] = args["limit"]
        if "offset" in args:
            kwargs["offset"] = args["offset"]
        outcomes = self.service.get_outcomes(**kwargs)
        return [outcome.model_dump() for outcome in outcomes]

    def _get_outcome(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import outcome_not_found

        outcome_id = args["outcome_id"]
        outcome = self.service.get_outcome(outcome_id)
        if outcome is None:
            raise BackendError(outcome_not_found(outcome_id))
        return outcome.model_dump()

    def _update_outcome(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import OutcomeNotFoundError, ValueOutOfRangeError, outcome_not_found

        updates: dict[str, Any] = {
            key: args[key]
            for key in ("statement", "importance", "satisfaction", "step_id")
            if key in args
        }
        try:
            outcome = self.service.update_outcome(args["outcome_id"], updates)
        except OutcomeNotFoundError:
            raise BackendError(outcome_not_found(args["outcome_id"])) from None
        except ValueOutOfRangeError as exc:
            raise BackendError(_VALUE_RANGE_ERROR) from exc
        return outcome.model_dump()

    def _delete_outcome(self, args: dict[str, Any]) -> str:
        from agentic_odi_core import OutcomeNotFoundError, outcome_not_found

        outcome_id = args["outcome_id"]
        try:
            self.service.delete_outcome(outcome_id)
        except OutcomeNotFoundError:
            raise BackendError(outcome_not_found(outcome_id)) from None
        return outcome_id

    def _add_customer_outcome(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import ValueOutOfRangeError
        from pydantic import ValidationError

        try:
            outcome = self.service.add_customer_outcome(
                job_id=args["job_id"],
                customer_value=args["customer_value"],
                business_value=args["business_value"],
                step_id=args.get("step_id"),
            )
        except ValidationError as exc:
            raise BackendError(_validation_message(exc)) from None
        except ValueOutOfRangeError as exc:
            raise BackendError(_VALUE_RANGE_ERROR) from exc
        return outcome.model_dump()

    def _get_customer_outcome(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import CustomerOutcomeNotFoundError, customer_outcome_not_found

        outcome_id = args["outcome_id"]
        try:
            outcome = self.service.get_customer_outcome(outcome_id)
        except CustomerOutcomeNotFoundError:
            raise BackendError(customer_outcome_not_found(outcome_id)) from None
        return outcome.model_dump()

    def _list_customer_outcomes(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {"job_id": args.get("job_id")}
        if "limit" in args:
            kwargs["limit"] = args["limit"]
        if "offset" in args:
            kwargs["offset"] = args["offset"]
        outcomes = self.service.list_customer_outcomes(**kwargs)
        return [outcome.model_dump() for outcome in outcomes]

    def _update_customer_outcome(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import (
            CustomerOutcome,
            CustomerOutcomeNotFoundError,
            customer_outcome_not_found,
        )
        from pydantic import ValidationError

        outcome_id = args["outcome_id"]
        try:
            existing = self.service.get_customer_outcome(outcome_id)
        except CustomerOutcomeNotFoundError:
            raise BackendError(customer_outcome_not_found(outcome_id)) from None

        customer_value = existing.customer_value.model_dump()
        for field in _CUSTOMER_VALUE_FIELDS:
            if field in args:
                customer_value[field] = args[field]
        business_value = existing.business_value.model_dump()
        for arg_key, field in _BUSINESS_VALUE_FIELDS.items():
            if arg_key in args:
                business_value[field] = args[arg_key]
        updates: dict[str, Any] = {
            "customer_value": customer_value,
            "business_value": business_value,
        }
        if "step_id" in args:
            updates["step_id"] = args["step_id"]

        candidate = existing.model_dump()
        candidate.update(updates)
        try:
            CustomerOutcome.model_validate(candidate)
        except ValidationError as exc:
            raise BackendError(_validation_message(exc)) from None

        outcome = self.service.update_customer_outcome(outcome_id, updates)
        return outcome.model_dump()

    def _delete_customer_outcome(self, args: dict[str, Any]) -> str:
        from agentic_odi_core import CustomerOutcomeNotFoundError, customer_outcome_not_found

        outcome_id = args["outcome_id"]
        try:
            self.service.delete_customer_outcome(outcome_id)
        except CustomerOutcomeNotFoundError:
            raise BackendError(customer_outcome_not_found(outcome_id)) from None
        return outcome_id

    def _add_evidence(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import (
            JobNotFoundError,
            OutcomeNotFoundError,
            StepNotFoundError,
            job_not_found,
            outcome_not_found,
            step_not_found,
        )

        try:
            evidence = self.service.add_evidence(
                source_name=args["source_name"],
                source_kind=args["source_kind"],
                name=args["name"],
                content=args["content"],
                item_type=args.get("item_type", "manual"),
                url=args.get("url"),
                raw=args.get("raw"),
                job_id=args.get("job_id"),
                step_id=args.get("step_id"),
                outcome_id=args.get("outcome_id"),
            )
        except JobNotFoundError:
            raise BackendError(job_not_found(args.get("job_id") or "")) from None
        except StepNotFoundError:
            raise BackendError(step_not_found(args.get("step_id"))) from None
        except OutcomeNotFoundError:
            raise BackendError(outcome_not_found(args.get("outcome_id"))) from None
        except ValueError as exc:
            raise BackendError(str(exc)) from None
        return evidence.model_dump()

    def _get_evidence(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import evidence_not_found

        evidence_id = args["evidence_id"]
        evidence = self.service.get_evidence(evidence_id)
        if evidence is None:
            raise BackendError(
                evidence_not_found(
                    evidence_id,
                    "List the stored records with list_evidence() to find a valid id.",
                )
            )
        return evidence.model_dump()

    def _list_evidence(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "job_id": args.get("job_id"),
            "step_id": args.get("step_id"),
            "outcome_id": args.get("outcome_id"),
        }
        if "limit" in args:
            kwargs["limit"] = args["limit"]
        if "offset" in args:
            kwargs["offset"] = args["offset"]
        items = self.service.list_evidence(**kwargs)
        return [item.model_dump() for item in items]

    def _delete_evidence(self, args: dict[str, Any]) -> str:
        from agentic_odi_core import EvidenceNotFoundError, evidence_not_found

        evidence_id = args["evidence_id"]
        try:
            self.service.delete_evidence(evidence_id)
        except EvidenceNotFoundError as exc:
            raise BackendError(evidence_not_found(evidence_id, exc.hint)) from None
        return evidence_id

    def _promote_evidence(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import (
            EvidenceNotFoundError,
            JobNotFoundError,
            OutcomeNotFoundError,
            StepNotFoundError,
            ValueOutOfRangeError,
            evidence_not_found,
            job_not_found,
            outcome_not_found,
            step_not_found,
        )

        evidence_id = args["evidence_id"]
        try:
            artifact = self.service.promote_evidence(
                evidence_id,
                args["target"],
                job_id=args.get("job_id"),
                statement=args.get("statement"),
                name=args.get("name"),
                importance=args.get("importance"),
                satisfaction=args.get("satisfaction"),
            )
        except EvidenceNotFoundError as exc:
            raise BackendError(evidence_not_found(evidence_id, exc.hint)) from None
        except JobNotFoundError:
            raise BackendError(job_not_found(args.get("job_id") or "")) from None
        except StepNotFoundError:
            raise BackendError(step_not_found(args.get("step_id"))) from None
        except OutcomeNotFoundError:
            raise BackendError(outcome_not_found(args.get("outcome_id"))) from None
        except ValueOutOfRangeError as exc:
            raise BackendError(_VALUE_RANGE_ERROR) from exc
        except ValueError as exc:
            raise BackendError(str(exc)) from None
        return artifact.model_dump()

    def _schedule_work(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import JobNotFoundError, job_not_found

        try:
            work = self.service.schedule_work(
                name=args["name"],
                schedule_expression=args["schedule_expression"],
                agent_id=args.get("agent_id", "default-agent"),
                trigger_type=args.get("trigger_type", "oneshot"),
                payload=args.get("payload"),
                job_id=args.get("job_id"),
            )
        except JobNotFoundError:
            raise BackendError(job_not_found(args.get("job_id") or "")) from None
        except ValueError as exc:
            raise BackendError(str(exc)) from None
        return work.model_dump()

    def _get_scheduled_work(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import ScheduledWorkNotFoundError, scheduled_work_not_found

        work_id = args["work_id"]
        try:
            work = self.service.get_scheduled_work(work_id)
        except ScheduledWorkNotFoundError:
            raise BackendError(scheduled_work_not_found(work_id)) from None
        return work.model_dump()

    def _list_scheduled_work(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        items = self.service.list_scheduled_work(
            job_id=args.get("job_id"),
            status=args.get("status"),
        )
        return [item.model_dump() for item in items]

    def _cancel_scheduled_work(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import ScheduledWorkNotFoundError, scheduled_work_not_found

        work_id = args["work_id"]
        try:
            work = self.service.cancel_scheduled_work(work_id)
        except ScheduledWorkNotFoundError:
            raise BackendError(scheduled_work_not_found(work_id)) from None
        return work.model_dump()

    def _trigger_scheduled_work(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import ScheduledWorkNotFoundError, scheduled_work_not_found

        work_id = args["work_id"]
        try:
            work = self.service.trigger_scheduled_work(work_id)
        except ScheduledWorkNotFoundError:
            raise BackendError(scheduled_work_not_found(work_id)) from None
        return work.model_dump()

    def _get_odi_schema(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import odi_schema

        return odi_schema()

    def _evaluate_outcome(self, args: dict[str, Any]) -> str:
        from agentic_odi_core import job_not_found
        from agentic_odi_core.evaluation import (
            evaluate_outcome_statement,
            statement_to_dict,
        )

        result = statement_to_dict(evaluate_outcome_statement(args["statement"]))
        job_id = args.get("job_id")
        if job_id is not None:
            if self.service.get_job(job_id) is None:
                return json.dumps({**result, "job_id": job_id, "error": job_not_found(job_id)})
            result["job_id"] = job_id
            result["existing_outcomes"] = [
                {
                    "id": outcome.id,
                    "statement": outcome.statement,
                    "opportunity_score": outcome.opportunity_score,
                }
                for outcome in self.service.get_outcomes(job_id)
            ]
        return json.dumps(result)

    def _get_odi_framework_guidelines(self, args: dict[str, Any]) -> str:
        from agentic_odi_core import ODI_FRAMEWORK_GUIDELINES

        return ODI_FRAMEWORK_GUIDELINES

    def _get_capabilities(self, args: dict[str, Any]) -> str:
        from agentic_odi_core import capability_summary

        return capability_summary()

    def _get_capabilities_manifest(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import capability_manifest

        return capability_manifest()

    def _compute_opportunity(self, args: dict[str, Any]) -> float:
        from agentic_odi_core import compute_opportunity_score

        importance = args["importance"]
        satisfaction = args["satisfaction"]
        if not (1.0 <= importance <= 10.0) or not (1.0 <= satisfaction <= 10.0):
            raise BackendError(_VALUE_RANGE_ERROR)
        return compute_opportunity_score(importance, satisfaction)

    def _list_signals(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        signals = self.service.list_signals(
            unread_only=bool(args.get("unread_only", False)),
            limit=int(args.get("limit", 50)),
        )
        return [signal.model_dump(mode="json") for signal in signals]

    def _mark_signal_read(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import SignalNotFoundError

        signal_id = args["signal_id"]
        try:
            signal = self.service.mark_signal_read(signal_id)
        except SignalNotFoundError:
            raise BackendError(f"signal not found: {signal_id}") from None
        return signal.model_dump(mode="json")

    def _dismiss_signal(self, args: dict[str, Any]) -> dict[str, Any]:
        from agentic_odi_core import SignalNotFoundError

        signal_id = args["signal_id"]
        try:
            signal = self.service.dismiss_signal(signal_id)
        except SignalNotFoundError:
            raise BackendError(f"signal not found: {signal_id}") from None
        return signal.model_dump(mode="json")


_LOCAL_HANDLERS = {
    "add_job": LocalBackend._add_job,
    "get_jobs": LocalBackend._get_jobs,
    "get_job": LocalBackend._get_job,
    "update_job": LocalBackend._update_job,
    "delete_job": LocalBackend._delete_job,
    "add_step": LocalBackend._add_step,
    "get_job_map": LocalBackend._get_job_map,
    "get_step": LocalBackend._get_step,
    "update_step": LocalBackend._update_step,
    "delete_step": LocalBackend._delete_step,
    "add_outcome": LocalBackend._add_outcome,
    "get_outcomes": LocalBackend._get_outcomes,
    "get_outcome": LocalBackend._get_outcome,
    "update_outcome": LocalBackend._update_outcome,
    "delete_outcome": LocalBackend._delete_outcome,
    "add_customer_outcome": LocalBackend._add_customer_outcome,
    "get_customer_outcome": LocalBackend._get_customer_outcome,
    "list_customer_outcomes": LocalBackend._list_customer_outcomes,
    "update_customer_outcome": LocalBackend._update_customer_outcome,
    "delete_customer_outcome": LocalBackend._delete_customer_outcome,
    "add_evidence": LocalBackend._add_evidence,
    "get_evidence": LocalBackend._get_evidence,
    "list_evidence": LocalBackend._list_evidence,
    "delete_evidence": LocalBackend._delete_evidence,
    "promote_evidence": LocalBackend._promote_evidence,
    "schedule_work": LocalBackend._schedule_work,
    "get_scheduled_work": LocalBackend._get_scheduled_work,
    "list_scheduled_work": LocalBackend._list_scheduled_work,
    "cancel_scheduled_work": LocalBackend._cancel_scheduled_work,
    "trigger_scheduled_work": LocalBackend._trigger_scheduled_work,
    "get_odi_schema": LocalBackend._get_odi_schema,
    "compute_opportunity": LocalBackend._compute_opportunity,
    "evaluate_outcome": LocalBackend._evaluate_outcome,
    "get_odi_framework_guidelines": LocalBackend._get_odi_framework_guidelines,
    "get_capabilities": LocalBackend._get_capabilities,
    "get_capabilities_manifest": LocalBackend._get_capabilities_manifest,
    "list_signals": LocalBackend._list_signals,
    "mark_signal_read": LocalBackend._mark_signal_read,
    "dismiss_signal": LocalBackend._dismiss_signal,
}


class MCPBackend(Backend):
    """Delegate to a remote MCP server over HTTP."""

    def __init__(self, mcp_url: str | None = None, timeout: float | None = None) -> None:
        self.mcp_url = mcp_url or os.environ.get("AGENTIC_ODI_MCP_URL") or DEFAULT_MCP_URL
        self.timeout = timeout if timeout is not None else mcp_timeout()

    def call(self, tool_name: str, args: dict[str, Any]) -> Any:
        text = _call_mcp(tool_name, args, self.mcp_url, self.timeout)
        return _parse_remote(tool_name, text)


def _call_mcp(tool: str, args: dict[str, Any], mcp_url: str, timeout: float) -> str:
    from fastmcp import Client

    from agentic_odi_cli import flags

    if flags.is_enabled("developer_mode"):
        typer.echo(f"[debug] MCP call: {tool} args={args}", err=True)

    async def _run() -> str:
        async with Client(mcp_url) as client:
            result = await client.call_tool(tool, args)
            return result.content[0].text  # type: ignore[index]

    async def _guarded() -> str:
        return await asyncio.wait_for(_run(), timeout=timeout)

    try:
        return asyncio.run(_guarded())
    except asyncio.TimeoutError as exc:
        raise BackendError(
            f"timed out after {timeout:.0f}s contacting {mcp_url}",
            "Check the MCP server and network, then retry or raise AGENTIC_ODI_MCP_TIMEOUT.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise BackendError(
            f"could not reach MCP server at {mcp_url}: {exc}",
            "Start the MCP server (python -m agentic_odi_mcp_server) and check AGENTIC_ODI_MCP_URL.",
        ) from exc


_FLOAT_TOOLS = frozenset({"compute_opportunity"})

_ID_TOOLS = frozenset(
    {
        "delete_job",
        "delete_step",
        "delete_outcome",
        "delete_customer_outcome",
        "delete_evidence",
    }
)

_LIST_TOOLS = frozenset(
    {
        "get_jobs",
        "get_job_map",
        "get_outcomes",
        "list_customer_outcomes",
        "list_evidence",
        "list_signals",
        "list_scheduled_work",
    }
)


def _parse_remote(tool_name: str, text: str) -> Any:
    """Parse a tool result, raising ``BackendError`` on the server's error text."""
    from agentic_odi_core.remote import parse_tool_result

    stripped = text.strip()
    problem = parse_tool_result(stripped)
    if problem is not None:
        raise BackendError(problem.message, problem.suggestion)

    if tool_name in _FLOAT_TOOLS:
        return _extract_float(stripped)
    if tool_name in _ID_TOOLS:
        return stripped.rsplit(": ", 1)[-1]

    payload = _extract_json(stripped)
    if tool_name in _LIST_TOOLS and not isinstance(payload, list):
        return [payload]
    return payload


def _extract_json(text: str) -> Any:
    """Parse the first complete JSON value in ``text``, prose and all.

    MCP replies often wrap a payload in a sentence, and that sentence can
    itself contain braces (``created {JOB-1}: [...]``). Each brace is tried as
    a start position with ``raw_decode``, so a stray one is skipped instead of
    swallowing the real payload, and the outermost value wins when payloads
    nest. Text with no parseable value is returned unchanged.
    """
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            payload, _end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            continue
        return payload
    return text


def _extract_float(text: str) -> float:
    try:
        return float(text.rsplit(":", 1)[-1].strip())
    except ValueError as exc:
        raise BackendError(text) from exc


@dataclass
class AutoBackend(Backend):
    """Prefer the local store, and reach for the MCP server if it fails.

    A locked or unreachable local store used to make every command fail even
    when an MCP server was running. Auto keeps the local-first path but does
    not let a local failure end the command.
    """

    def __init__(self, db_path: str | None = None, mcp_url: str | None = None) -> None:
        self._local = LocalBackend(db_path=db_path)
        self._mcp = MCPBackend(mcp_url=mcp_url)
        self._announced = False

    def call(self, tool_name: str, args: dict[str, Any]) -> Any:
        try:
            return self._local.call(tool_name, args)
        except (BackendError, NotImplementedError) as local_error:
            try:
                result = self._mcp.call(tool_name, args)
            except BackendError as mcp_error:
                raise local_error from mcp_error
            if not self._announced:
                typer.echo("Local store unavailable; using the MCP server.", err=True)
                self._announced = True
            return result


@dataclass
class BackendConfig:
    backend: str | None = None
    db_path: str | None = None
    mcp_url: str | None = None


def get_backend(
    backend: str | None = None, db_path: str | None = None, mcp_url: str | None = None
) -> Backend:
    resolved = backend or os.environ.get("AGENTIC_ODI_BACKEND") or DEFAULT_BACKEND
    if resolved == "local":
        return LocalBackend(db_path=db_path)
    if resolved in {"mcp", "remote"}:
        return MCPBackend(mcp_url=mcp_url)
    if resolved == "auto":
        return AutoBackend(db_path=db_path, mcp_url=mcp_url)
    raise BackendError(f"unknown backend: {resolved}")


def resolve_backend(config: BackendConfig) -> Backend:
    if config.backend in {"mcp", "remote"} and config.db_path:
        typer.echo("Warning: --db is ignored when the backend is 'mcp'", err=True)
    return get_backend(backend=config.backend, db_path=config.db_path, mcp_url=config.mcp_url)


def require_backend() -> Backend:
    """Resolve the backend selected by the global CLI options."""
    from agentic_odi_cli import context

    return resolve_backend(context.config())


def run_tool(tool_name: str, args: dict[str, Any]) -> Any:
    """Call ``tool_name`` on the resolved backend, reporting failures cleanly."""
    try:
        return require_backend().call(tool_name, args)
    except BackendError as exc:
        message = str(exc)
        if message.startswith("Error: "):
            message = message[len("Error: ") :]
        typer.secho(f"Error: {message}", fg="red", err=True)
        if exc.suggestion:
            typer.secho(f"Hint: {exc.suggestion}", fg="yellow", err=True)
        raise typer.Exit(code=1) from exc
