"""HTTP error shape, status mapping, and request-id handling for the sidecar.

Every failure the Studio API reports travels as one body::

    {"error": {"code": ..., "message": ..., "detail": ..., "suggestion": ...,
               "retryable": ..., "request_id": ...}}

The model itself lives in :mod:`agentic_odi_core.remote` so the CLI and the
sidecar agree on what a failure is; this module owns the HTTP mapping.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import uuid4

from agentic_odi_core.remote import StudioError, StudioErrorCode
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

#: A request id is echoed in responses and written to logs, so it must be a
#: short, boring token. Anything else is replaced with a fresh one.
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

STATUS_FOR_CODE: dict[StudioErrorCode, int] = {
    StudioErrorCode.NOT_FOUND: 404,
    StudioErrorCode.VALIDATION: 422,
    StudioErrorCode.OUT_OF_RANGE: 422,
    StudioErrorCode.CONFLICT: 409,
    StudioErrorCode.MCP_UNREACHABLE: 502,
    StudioErrorCode.LLM_UNREACHABLE: 502,
    StudioErrorCode.MCP_TOOL_FAILED: 500,
    StudioErrorCode.LLM_TOOL_ROUNDS_EXHAUSTED: 500,
    StudioErrorCode.INTERNAL: 500,
}

CODE_FOR_STATUS: dict[int, StudioErrorCode] = {
    400: StudioErrorCode.VALIDATION,
    404: StudioErrorCode.NOT_FOUND,
    409: StudioErrorCode.CONFLICT,
    422: StudioErrorCode.VALIDATION,
    500: StudioErrorCode.INTERNAL,
    502: StudioErrorCode.MCP_UNREACHABLE,
}


class StudioHTTPError(Exception):
    """A failure that already knows its HTTP status and its error model."""

    def __init__(self, error: StudioError, status_code: int | None = None) -> None:
        self.error = error
        self.status_code = status_code if status_code is not None else status_for_code(error.code)
        super().__init__(error.message)


def status_for_code(code: StudioErrorCode) -> int:
    """Return the HTTP status that belongs to an error code."""
    return STATUS_FOR_CODE.get(code, 500)


def code_for_status(status_code: int) -> StudioErrorCode:
    """Return the error code that belongs to an HTTP status."""
    return CODE_FOR_STATUS.get(status_code, StudioErrorCode.INTERNAL)


def request_id_for(request: Request) -> str:
    """Return the request id assigned to this request, or an empty string."""
    return str(getattr(request.state, "request_id", "") or "")


def _error_body(request: Request, error: StudioError) -> dict[str, Any]:
    request_id = request_id_for(request)
    if not error.request_id:
        error = error.model_copy(update={"request_id": request_id})
    return {"error": error.model_dump(mode="json")}


def _error_response(request: Request, error: StudioError, status_code: int) -> JSONResponse:
    request_id = request_id_for(request)
    headers = {REQUEST_ID_HEADER: request_id} if request_id else None
    return JSONResponse(_error_body(request, error), status_code=status_code, headers=headers)


def studio_error_handler(request: Request, exc: StudioHTTPError) -> JSONResponse:
    """Render a :class:`StudioHTTPError` as the one error body."""
    return _error_response(request, exc.error, exc.status_code)


def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Render a request-body validation failure as a ``validation`` error."""
    detail = _compact_validation_text(exc)
    error = StudioError(
        code=StudioErrorCode.VALIDATION,
        message="Request validation failed.",
        detail=detail,
        suggestion="Check the request body and try again.",
    )
    return _error_response(request, error, 422)


def _compact_validation_text(exc: RequestValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        parts.append(f"{location}: {error.get('msg', 'invalid')}")
    return "; ".join(parts)


def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Render a Starlette/FastAPI ``HTTPException`` as the one error body."""
    error = StudioError(
        code=code_for_status(exc.status_code),
        message=str(exc.detail),
    )
    return _error_response(request, error, exc.status_code)


def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log an unexpected failure and return it without internals."""
    request_id = request_id_for(request)
    logger.exception("unhandled studio-api error (request_id=%s)", request_id, exc_info=exc)
    error = StudioError(
        code=StudioErrorCode.INTERNAL,
        message=f"Something went wrong (request {request_id}). No report was sent.",
        suggestion="Try again — or open Settings → About → Diagnostics to review and export a local, redacted report.",
    )
    return _error_response(request, error, 500)


def _safe_request_id(candidate: str | None) -> str:
    """Return the client's request id when it is safe to echo, else a fresh one."""
    if candidate and REQUEST_ID_PATTERN.match(candidate):
        return candidate
    return uuid4().hex


class RequestIdMiddleware:
    """Accept or mint an ``X-Request-ID`` and echo it on the response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _safe_request_id(Headers(scope=scope).get(REQUEST_ID_HEADER))
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        await self.app(scope, receive, send_with_request_id)


def register_error_handlers(app: FastAPI) -> None:
    """Install the one-error-body handlers on an app."""
    handler: Any = studio_error_handler
    app.add_exception_handler(StudioHTTPError, handler)
    handler = validation_error_handler
    app.add_exception_handler(RequestValidationError, handler)
    handler = http_error_handler
    app.add_exception_handler(StarletteHTTPException, handler)
    handler = unhandled_error_handler
    app.add_exception_handler(Exception, handler)
