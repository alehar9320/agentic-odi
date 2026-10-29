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
    INTERNAL = "internal"


class StudioError(BaseModel):
    code: StudioErrorCode
    message: str
    detail: str | None = None
    suggestion: str | None = None
    retryable: bool = False
    request_id: str | None = None


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
        return StudioError(
            code=StudioErrorCode.NOT_FOUND,
            message=message,
            suggestion="Check the identifier and try again.",
        )
    if "unreachable" in lowered_message or "connection refused" in lowered_message:
        return StudioError(
            code=StudioErrorCode.MCP_UNREACHABLE,
            message=message,
            suggestion="Check that the MCP server is running, then retry.",
            retryable=True,
        )
    if any(marker in lowered_message for marker in _OUT_OF_RANGE_MARKERS):
        return StudioError(
            code=StudioErrorCode.OUT_OF_RANGE,
            message=message,
            suggestion="Use a value inside the documented range.",
        )
    if any(marker in lowered_message for marker in _VALIDATION_MARKERS):
        return StudioError(code=StudioErrorCode.VALIDATION, message=message)

    return StudioError(code=StudioErrorCode.MCP_TOOL_FAILED, message=message)


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
