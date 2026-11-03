"""Shared error model and parser for MCP tool results."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel

from agentic_odi_core.errors import (
    ConflictError,
    ConsentRequired,
    NotFoundError,
    RateLimitError,
    SerializationError,
    StoreError,
    ValidationError,
)
from agentic_odi_core.services import ValueOutOfRangeError


class StudioErrorCode(str, Enum):
    MCP_UNREACHABLE = "mcp_unreachable"
    MCP_TOOL_FAILED = "mcp_tool_failed"
    LLM_UNREACHABLE = "llm_unreachable"
    LLM_TOOL_ROUNDS_EXHAUSTED = "llm_tool_rounds_exhausted"
    NOT_FOUND = "not_found"
    VALIDATION = "validation"
    OUT_OF_RANGE = "out_of_range"
    CONFLICT = "conflict"
    RATE_LIMITED = "rate_limited"
    CONSENT_REQUIRED = "consent_required"
    STORE_CORRUPT = "store_corrupt"
    INTERNAL = "internal"


class StudioError(BaseModel):
    code: StudioErrorCode
    message: str
    detail: str | None = None
    suggestion: str | None = None
    retryable: bool = False
    request_id: str | None = None


STATUS_FOR_CODE: dict[StudioErrorCode, int] = {
    StudioErrorCode.NOT_FOUND: 404,
    StudioErrorCode.VALIDATION: 422,
    StudioErrorCode.OUT_OF_RANGE: 422,
    StudioErrorCode.CONFLICT: 409,
    StudioErrorCode.RATE_LIMITED: 429,
    StudioErrorCode.CONSENT_REQUIRED: 403,
    StudioErrorCode.STORE_CORRUPT: 500,
    StudioErrorCode.MCP_UNREACHABLE: 502,
    StudioErrorCode.LLM_UNREACHABLE: 502,
    StudioErrorCode.MCP_TOOL_FAILED: 500,
    StudioErrorCode.LLM_TOOL_ROUNDS_EXHAUSTED: 500,
    StudioErrorCode.INTERNAL: 500,
}


#: Default human-friendly text for each error code, so every layer speaks
#: the same language instead of inventing messages at call sites.
_MESSAGE_FOR_CODE: dict[StudioErrorCode, str] = {
    StudioErrorCode.MCP_UNREACHABLE: "Can't reach the MCP server.",
    StudioErrorCode.LLM_UNREACHABLE: "Can't reach the model.",
    StudioErrorCode.NOT_FOUND: "Not found.",
    StudioErrorCode.VALIDATION: "Invalid input.",
    StudioErrorCode.OUT_OF_RANGE: "Value out of range.",
    StudioErrorCode.CONFLICT: "That conflicts with the current state.",
    StudioErrorCode.RATE_LIMITED: "Too many requests.",
    StudioErrorCode.CONSENT_REQUIRED: "That action needs the PM's approval first.",
    StudioErrorCode.STORE_CORRUPT: "The database failed its integrity check.",
    StudioErrorCode.MCP_TOOL_FAILED: "The operation did not complete.",
    StudioErrorCode.LLM_TOOL_ROUNDS_EXHAUSTED: "The assistant reached its tool limit for this turn.",
    StudioErrorCode.INTERNAL: "Something went wrong.",
}

#: A short, actionable hint per code. ``None`` means "retry is the only move."
_SUGGESTION_FOR_CODE: dict[StudioErrorCode, str | None] = {
    StudioErrorCode.MCP_UNREACHABLE: (
        "Start the MCP server (`python -m agentic_odi_mcp_server`), then try again."
    ),
    StudioErrorCode.LLM_UNREACHABLE: "Check your model settings, or keep working by hand.",
    StudioErrorCode.NOT_FOUND: "Check the identifier and try again.",
    StudioErrorCode.VALIDATION: "Fix the input and try again.",
    StudioErrorCode.OUT_OF_RANGE: "Use a value inside the documented range.",
    StudioErrorCode.CONFLICT: "Reload and try again.",
    StudioErrorCode.RATE_LIMITED: "Wait, then try again.",
    StudioErrorCode.CONSENT_REQUIRED: "Get the PM's approval for this workspace, then try again.",
    StudioErrorCode.STORE_CORRUPT: (
        "Restore a backup, then restart. The damaged file was left untouched."
    ),
    StudioErrorCode.MCP_TOOL_FAILED: "Try again.",
    StudioErrorCode.LLM_TOOL_ROUNDS_EXHAUSTED: "Ask me to continue from here.",
    StudioErrorCode.INTERNAL: "Try again.",
}

#: Transient failures a caller can realistically recover from by retrying. A
#: tool failure stays retryable=false on purpose: the model recovers within
#: the turn, so the user is never offered a redundant Retry. A rate limit is
#: the one 4xx worth retrying — waiting is the recovery — while needing
#: consent is not: retrying without agreement fails the same way again.
_RETRYABLE_FOR_CODE: frozenset[StudioErrorCode] = frozenset(
    {
        StudioErrorCode.MCP_UNREACHABLE,
        StudioErrorCode.LLM_UNREACHABLE,
        StudioErrorCode.LLM_TOOL_ROUNDS_EXHAUSTED,
        StudioErrorCode.RATE_LIMITED,
    }
)

#: Domain failure kind → the code that crosses the wire, most specific first:
#: ``ValueOutOfRangeError`` is a ``ValidationError``, and the pair is the
#: difference between "fix the input" and "pick a smaller number". Anything
#: not listed here is a tool failure, which is the one bucket that never needs
#: a new code. Kept beside the code tables it reads so the two cannot drift
#: into different vocabularies.
_CODE_BY_ERROR: tuple[tuple[type[BaseException], StudioErrorCode], ...] = (
    (ValueOutOfRangeError, StudioErrorCode.OUT_OF_RANGE),
    (ValidationError, StudioErrorCode.VALIDATION),
    (NotFoundError, StudioErrorCode.NOT_FOUND),
    (ConflictError, StudioErrorCode.CONFLICT),
    (RateLimitError, StudioErrorCode.RATE_LIMITED),
    (ConsentRequired, StudioErrorCode.CONSENT_REQUIRED),
    (StoreError, StudioErrorCode.INTERNAL),
    (SerializationError, StudioErrorCode.INTERNAL),
    # Last, because every domain validation error above is also a ValueError
    # and deserves its own rung first. A peer's ``ValueError`` — pydantic's
    # ``ValidationError`` included — is a bad argument, not a broken server.
    (ValueError, StudioErrorCode.VALIDATION),
)

_OUT_OF_RANGE_MARKERS = (
    "must be between",
    "out of range",
    "must be greater than",
    "must be less than",
)
_VALIDATION_MARKERS = (
    "is required",
    "must not be empty",
    "invalid ",
)


def message_for_code(code: StudioErrorCode) -> str:
    """Return a human-friendly default message for an error code."""
    return _MESSAGE_FOR_CODE.get(code, "Something went wrong.")


def suggestion_for_code(code: StudioErrorCode) -> str | None:
    """Return an actionable hint for an error code, or ``None``."""
    return _SUGGESTION_FOR_CODE.get(code, "Try again.")


def retryable_for_code(code: StudioErrorCode) -> bool:
    """Return whether an error of this code is worth retrying."""
    return code in _RETRYABLE_FOR_CODE


def code_for_error(exc: BaseException) -> StudioErrorCode:
    """Return the wire code that names what kind of failure ``exc`` is."""
    for error_type, code in _CODE_BY_ERROR:
        if isinstance(exc, error_type):
            return code
    return StudioErrorCode.MCP_TOOL_FAILED


def error_envelope(exc: BaseException) -> dict[str, Any]:
    """Serialize a failure into the four fields a client can branch on.

    This is the only place a Python exception becomes a wire value, so a
    handler never has to choose a code and a caller never has to read English
    to get one back. ``message`` is the exception's own sentence — it is the
    human half of the pair and carries no meaning a client should depend on.
    """
    code = code_for_error(exc)
    return {
        "code": code.value,
        "message": str(exc),
        "suggestion": suggestion_for_code(code),
        "retryable": retryable_for_code(code),
    }


def _envelope_error(stripped: str) -> StudioError | None:
    """Return the error an envelope describes, or ``None`` if this is not one.

    A payload counts as an envelope only when it is a JSON object holding an
    ``error`` object with a ``code`` — anything else is prose to be read the
    slow way. A code this build does not know (a newer server, a renamed
    member) becomes ``mcp_tool_failed`` rather than inventing a fifth bucket:
    the caller still learns the call failed and still gets the sentence.
    """
    if not stripped.startswith("{"):
        return None
    try:
        payload = json.loads(stripped)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    fields = payload.get("error")
    if not isinstance(fields, dict):
        return None
    raw_code = fields.get("code")
    if not isinstance(raw_code, str):
        return None
    try:
        code = StudioErrorCode(raw_code)
    except ValueError:
        code = StudioErrorCode.MCP_TOOL_FAILED

    message = fields.get("message")
    if not isinstance(message, str) or not message:
        sentence = payload.get("message")
        message = sentence[len("Error:") :].strip() if isinstance(sentence, str) else stripped

    suggestion = fields.get("suggestion")
    retryable = fields.get("retryable")
    return StudioError(
        code=code,
        message=message,
        suggestion=suggestion if isinstance(suggestion, str) else suggestion_for_code(code),
        retryable=retryable if isinstance(retryable, bool) else retryable_for_code(code),
    )


def parse_tool_result(text: str) -> StudioError | None:
    """Return a classified error for an MCP tool result, or ``None`` on success.

    The envelope written by :func:`error_envelope` is read first, so a
    classification keys on ``code`` and cannot be moved by a reworded message.

    The substring matching below is the prose fallback for a peer that predates
    the envelope — an older MCP server, or a client that only ever reads text.
    It is dated, not permanent: delete it once the CLI and the MCP server ship
    the envelope in the same release, since both call this function and no
    in-tree peer can then produce bare prose. Until then, the guardrail
    "never break a text client" keeps the sentence in the payload rather than
    replacing it.
    """
    if not text:
        return None

    stripped = text.strip()
    envelope = _envelope_error(stripped)
    if envelope is not None:
        return envelope

    lowered = stripped.lower()
    is_error = lowered.startswith("error:") or " not found:" in lowered
    if not is_error:
        return None

    message = stripped
    if lowered.startswith("error:"):
        message = stripped[len("error:") :].strip()

    lowered_message = message.lower()
    if "not found" in lowered_message:
        code = StudioErrorCode.NOT_FOUND
    elif "unreachable" in lowered_message or "connection refused" in lowered_message:
        code = StudioErrorCode.MCP_UNREACHABLE
    elif any(marker in lowered_message for marker in _OUT_OF_RANGE_MARKERS):
        code = StudioErrorCode.OUT_OF_RANGE
    elif any(marker in lowered_message for marker in _VALIDATION_MARKERS):
        code = StudioErrorCode.VALIDATION
    else:
        code = StudioErrorCode.MCP_TOOL_FAILED

    return StudioError(
        code=code,
        message=message,
        suggestion=suggestion_for_code(code),
        retryable=retryable_for_code(code),
    )


def tool_result_text(result: Any) -> str:
    """Extract readable text from a FastMCP ``CallToolResult`` or a plain value."""
    if isinstance(result, str):
        return result

    content = getattr(result, "content", None)
    if content:
        first = content[0]
        text = getattr(first, "text", None)
        if text is not None:
            return str(text)

    return str(result)
