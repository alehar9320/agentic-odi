"""Backend abstraction for the CLI.

Two backends implement the same :class:`Backend` seam:

* :class:`LocalBackend` runs the ODI logic directly against a local SQLite
  store (no server required).
* :class:`MCPBackend` delegates to a remote MCP server over HTTP, which may be
  a local ``python -m mcp_server`` process or a hosted endpoint.

Commands resolve a backend once from a :class:`BackendConfig` stored on the
Typer context. Keeping the local and remote paths behind one interface means
the same command works against either, and a future hosted backend only has to
implement ``call``.
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
    from core import ODIService

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
)

_BUSINESS_VALUE_FIELDS = {
    "category": "category",
    "business_statement": "statement",
    "detail": "detail",
    "estimated_annual_value": "estimated_annual_value",
    "confidence": "confidence",
}


class BackendError(Exception):
    """A user-facing failure: not found, invalid input, or unreachable server."""


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
            from core import ODIService
            from core.sqlite_repository import SQLiteRepository

            self._service = ODIService(SQLiteRepository(db_path=self._db_path))
        return self._service

    def call(self, tool_name: str, args: dict[str, Any]) -> Any:
        handler = _LOCAL_HANDLERS.get(tool_name)
        if handler is None:
            raise NotImplementedError(f"Unknown tool: {tool_name}")
        return handler(self, args)

    def _add_customer_outcome(self, args: dict[str, Any]) -> dict[str, Any]:
        from core import ValueOutOfRangeError
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
        from core import CustomerOutcomeNotFoundError, customer_outcome_not_found

        outcome_id = args["outcome_id"]
        try:
            outcome = self.service.get_customer_outcome(outcome_id)
        except CustomerOutcomeNotFoundError:
            raise BackendError(customer_outcome_not_found(outcome_id)) from None
        return outcome.model_dump()

    def _list_customer_outcomes(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        outcomes = self.service.list_customer_outcomes(args.get("job_id"))
        return [outcome.model_dump() for outcome in outcomes]

    def _update_customer_outcome(self, args: dict[str, Any]) -> dict[str, Any]:
        from core import CustomerOutcome, CustomerOutcomeNotFoundError, customer_outcome_not_found
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
        from core import CustomerOutcomeNotFoundError, customer_outcome_not_found

        outcome_id = args["outcome_id"]
        try:
            self.service.delete_customer_outcome(outcome_id)
        except CustomerOutcomeNotFoundError:
            raise BackendError(customer_outcome_not_found(outcome_id)) from None
        return outcome_id

    def _compute_opportunity(self, args: dict[str, Any]) -> float:
        from core import compute_opportunity_score

        importance = args["importance"]
        satisfaction = args["satisfaction"]
        if not (1.0 <= importance <= 10.0) or not (1.0 <= satisfaction <= 10.0):
            raise BackendError(_VALUE_RANGE_ERROR)
        return compute_opportunity_score(importance, satisfaction)


_LOCAL_HANDLERS = {
    "add_customer_outcome": LocalBackend._add_customer_outcome,
    "get_customer_outcome": LocalBackend._get_customer_outcome,
    "list_customer_outcomes": LocalBackend._list_customer_outcomes,
    "update_customer_outcome": LocalBackend._update_customer_outcome,
    "delete_customer_outcome": LocalBackend._delete_customer_outcome,
    "compute_opportunity": LocalBackend._compute_opportunity,
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

    async def _run() -> str:
        async with Client(mcp_url) as client:
            result = await client.call_tool(tool, args)
            return result.content[0].text  # type: ignore[index]

    async def _guarded() -> str:
        return await asyncio.wait_for(_run(), timeout=timeout)

    try:
        return asyncio.run(_guarded())
    except asyncio.TimeoutError as exc:
        raise BackendError(f"timed out after {timeout:.0f}s contacting {mcp_url}") from exc
    except Exception as exc:  # noqa: BLE001
        raise BackendError(f"could not reach MCP server at {mcp_url}: {exc}") from exc


def _parse_remote(tool_name: str, text: str) -> Any:
    """Parse a tool result, raising ``BackendError`` on the server's error text."""
    stripped = text.strip()
    if stripped.startswith("Error:") or " not found:" in stripped:
        raise BackendError(stripped)

    if tool_name == "compute_opportunity":
        return _extract_float(stripped)
    if tool_name == "delete_customer_outcome":
        return stripped.rsplit(": ", 1)[-1]

    payload = _extract_json(stripped)
    if tool_name == "list_customer_outcomes":
        return payload if isinstance(payload, list) else [payload]
    return payload


def _extract_json(text: str) -> Any:
    start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
    if start == -1:
        return text
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError:
        return text


def _extract_float(text: str) -> float:
    try:
        return float(text.rsplit(":", 1)[-1].strip())
    except ValueError as exc:
        raise BackendError(text) from exc


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
    raise BackendError(f"unknown backend: {resolved}")


def resolve_backend(config: BackendConfig) -> Backend:
    if config.backend in {"mcp", "remote"} and config.db_path:
        typer.echo("Warning: --db is ignored when the backend is 'mcp'", err=True)
    return get_backend(backend=config.backend, db_path=config.db_path, mcp_url=config.mcp_url)


def require_backend(ctx: typer.Context) -> Backend:
    """Resolve the backend stored on the Typer context (lazily, once)."""
    obj = ctx.obj
    if isinstance(obj, Backend):
        return obj
    if isinstance(obj, BackendConfig):
        resolved = resolve_backend(obj)
        ctx.obj = resolved
        return resolved
    typer.echo("Error: no backend configured", err=True)
    raise typer.Exit(code=1)


def run_tool(ctx: typer.Context, tool_name: str, args: dict[str, Any]) -> Any:
    """Call ``tool_name`` on the resolved backend, reporting failures cleanly."""
    try:
        return require_backend(ctx).call(tool_name, args)
    except BackendError as exc:
        message = str(exc)
        if message.startswith("Error: "):
            message = message[len("Error: ") :]
        typer.secho(f"Error: {message}", fg="red", err=True)
        raise typer.Exit(code=1) from exc
