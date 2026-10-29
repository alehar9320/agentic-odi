"""Tests for the shared MCP tool-result error parser."""

from __future__ import annotations

from types import SimpleNamespace

from agentic_odi_core.remote import (
    StudioErrorCode,
    message_for_code,
    parse_tool_result,
    retryable_for_code,
    suggestion_for_code,
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


def test_message_for_code_is_human_friendly() -> None:
    assert message_for_code(StudioErrorCode.MCP_UNREACHABLE) == "Can't reach the MCP server."
    assert message_for_code(StudioErrorCode.LLM_UNREACHABLE) == "Can't reach the model."
    assert message_for_code(StudioErrorCode.NOT_FOUND) == "Not found."
    assert message_for_code(StudioErrorCode.VALIDATION) == "Invalid input."
    assert message_for_code(StudioErrorCode.OUT_OF_RANGE) == "Value out of range."
    assert message_for_code(StudioErrorCode.CONFLICT) == "That conflicts with the current state."
    assert message_for_code(StudioErrorCode.MCP_TOOL_FAILED) == "The operation did not complete."
    assert message_for_code(StudioErrorCode.LLM_TOOL_ROUNDS_EXHAUSTED) == (
        "The assistant reached its tool limit for this turn."
    )
    assert message_for_code(StudioErrorCode.INTERNAL) == "Something went wrong."


def test_suggestion_for_code_names_a_fix_when_one_exists() -> None:
    mcp_suggestion = suggestion_for_code(StudioErrorCode.MCP_UNREACHABLE)
    assert mcp_suggestion is not None
    assert "python -m agentic_odi_mcp_server" in mcp_suggestion
    assert suggestion_for_code(StudioErrorCode.NOT_FOUND) is not None
    assert suggestion_for_code(StudioErrorCode.VALIDATION) is not None
    # An internal failure offers only a retry, not a root-cause fix.
    assert suggestion_for_code(StudioErrorCode.INTERNAL) is not None


def test_retryable_for_code_flags_transient_failures() -> None:
    assert retryable_for_code(StudioErrorCode.MCP_UNREACHABLE) is True
    assert retryable_for_code(StudioErrorCode.LLM_UNREACHABLE) is True
    assert retryable_for_code(StudioErrorCode.LLM_TOOL_ROUNDS_EXHAUSTED) is True
    assert retryable_for_code(StudioErrorCode.NOT_FOUND) is False
    assert retryable_for_code(StudioErrorCode.VALIDATION) is False
    assert retryable_for_code(StudioErrorCode.INTERNAL) is False


def test_parse_not_found_carries_the_default_suggestion() -> None:
    problem = parse_tool_result("Error: Job with ID JOB-1 not found.")
    assert problem is not None
    assert problem.suggestion == suggestion_for_code(StudioErrorCode.NOT_FOUND)


def test_parse_unreachable_carries_mcp_suggestion_and_retryable() -> None:
    problem = parse_tool_result("Error: MCP server unreachable at http://mcp")
    assert problem is not None
    assert problem.suggestion == suggestion_for_code(StudioErrorCode.MCP_UNREACHABLE)
    assert problem.retryable == retryable_for_code(StudioErrorCode.MCP_UNREACHABLE)
