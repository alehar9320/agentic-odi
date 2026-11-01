"""Shared error model and parser for MCP tool results."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class StudioErrorCode(str, Enum):
    MCP_UNREACHABLE = "mcp_unreachable"
    MCP_TOOL_FAILED = "mcp_tool_failed"
    LLM_UNREACHABLE = "llm_unreachable"
    LLM_TOOL_ROUNDS_EXHAUSTED = "llm_tool_rounds_exhausted"
    NOT_FOUND = "not_found"
    VALIDATION = "validation"
    OUT_OF_RANGE = "out_of_range"
    CONFLICT = "conflict"
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
    StudioErrorCode.STORE_CORRUPT: (
        "Restore a backup, then restart. The damaged file was left untouched."
    ),
    StudioErrorCode.MCP_TOOL_FAILED: "Try again.",
    StudioErrorCode.LLM_TOOL_ROUNDS_EXHAUSTED: "Ask me to continue from here.",
    StudioErrorCode.INTERNAL: "Try again.",
}

#: Transient failures a caller can realistically recover from by retrying. A
#: tool failure stays retryable=false on purpose: the model recovers within
#: the turn, so the user is never offered a redundant Retry.
_RETRYABLE_FOR_CODE: frozenset[StudioErrorCode] = frozenset(
    {
        StudioErrorCode.MCP_UNREACHABLE,
        StudioErrorCode.LLM_UNREACHABLE,
        StudioErrorCode.LLM_TOOL_ROUNDS_EXHAUSTED,
    }
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


def parse_tool_result(text: str) -> StudioError | None:
    """Return a classified error for an MCP error string, or ``None`` on success."""
    if not text:
        return None

    stripped = text.strip()
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
