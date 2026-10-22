"""Tests for the shared MCP tool-result error parser."""

from __future__ import annotations

from types import SimpleNamespace

from agentic_odi_core.remote import (
    StudioErrorCode,
    parse_tool_result,
    tool_result_text,
)


def test_parse_not_found() -> None:
    problem = parse_tool_result("Error: Job with ID JOB-1 not found.")

    assert problem is not None
    assert problem.code is StudioErrorCode.NOT_FOUND
    assert problem.retryable is False
    assert "not found" in problem.message.lower()


def test_parse_out_of_range() -> None:
    problem = parse_tool_result("Error: importance and satisfaction must be between 1.0 and 10.0")

    assert problem is not None
    assert problem.code is StudioErrorCode.OUT_OF_RANGE
    assert problem.suggestion is not None


def test_parse_unreachable_is_retryable() -> None:
    problem = parse_tool_result("Error: MCP server unreachable at http://mcp")

    assert problem is not None
    assert problem.code is StudioErrorCode.MCP_UNREACHABLE
    assert problem.retryable is True


def test_parse_generic_tool_error() -> None:
    problem = parse_tool_result("Error: the tool exploded")

    assert problem is not None
    assert problem.code is StudioErrorCode.MCP_TOOL_FAILED
    assert problem.retryable is False


def test_success_text_is_not_an_error() -> None:
    assert parse_tool_result('Job created successfully: {"id": "JOB-1"}') is None
    assert parse_tool_result("[]") is None
    assert parse_tool_result("") is None


def test_tool_result_text_reads_the_first_content_block() -> None:
    result = SimpleNamespace(
        content=[SimpleNamespace(text="Error: Outcome with ID O-1 not found.")]
    )

    assert tool_result_text(result) == "Error: Outcome with ID O-1 not found."


def test_tool_result_text_accepts_a_plain_string() -> None:
    assert tool_result_text("[]") == "[]"
