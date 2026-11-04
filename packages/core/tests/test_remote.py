"""Tests for the shared MCP tool-result error parser."""

from __future__ import annotations

import json
from types import SimpleNamespace

from agentic_odi_core.errors import (
    ConflictError,
    ConsentRequired,
    NotFoundError,
    OdiError,
    RateLimitError,
    ValidationError,
)
from agentic_odi_core.remote import (
    StudioErrorCode,
    error_envelope,
    message_for_code,
    parse_tool_result,
    retryable_for_code,
    suggestion_for_code,
    tool_result_text,
)
from agentic_odi_core.services import ValueOutOfRangeError


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


def test_error_envelope_maps_each_failure_kind_to_a_code() -> None:
    cases: list[tuple[BaseException, dict[str, object]]] = [
        (
            NotFoundError("O-1", "Outcome"),
            {
                "code": "not_found",
                "message": "Outcome not found: O-1",
                "suggestion": "Check the identifier and try again.",
                "retryable": False,
            },
        ),
        (
            ValidationError("title is required"),
            {
                "code": "validation",
                "message": "title is required",
                "suggestion": "Fix the input and try again.",
                "retryable": False,
            },
        ),
        (
            ValueOutOfRangeError("importance must be between 1.0 and 10.0"),
            {
                "code": "out_of_range",
                "message": "importance must be between 1.0 and 10.0",
                "suggestion": "Use a value inside the documented range.",
                "retryable": False,
            },
        ),
        (
            ConflictError("that outcome is already recorded"),
            {
                "code": "conflict",
                "message": "that outcome is already recorded",
                "suggestion": "Reload and try again.",
                "retryable": False,
            },
        ),
        (
            ConsentRequired("the PM has not approved work on this workspace"),
            {
                "code": "consent_required",
                "message": "the PM has not approved work on this workspace",
                "suggestion": "Get the PM's approval for this workspace, then try again.",
                "retryable": False,
            },
        ),
        (
            RateLimitError("too many writes in a minute", retry_after=30),
            {
                "code": "rate_limited",
                "message": "too many writes in a minute",
                "suggestion": "Wait, then try again.",
                "retryable": True,
            },
        ),
        (
            RuntimeError("boom"),
            {
                "code": "mcp_tool_failed",
                "message": "boom",
                "suggestion": "Try again.",
                "retryable": False,
            },
        ),
    ]

    for exc, expected in cases:
        assert error_envelope(exc) == expected, type(exc).__name__


def test_error_envelope_never_invents_a_code_for_an_unfamiliar_error() -> None:
    class SomewhereNewError(OdiError):
        """An error type added after the table was written."""

    envelope = error_envelope(SomewhereNewError("nobody has seen this fail before"))

    assert envelope["code"] == StudioErrorCode.MCP_TOOL_FAILED.value
    assert envelope["retryable"] is retryable_for_code(StudioErrorCode.MCP_TOOL_FAILED)


def test_error_envelope_reads_a_plain_value_error_as_invalid_input() -> None:
    """A handler catches ``ValueError`` from a peer — pydantic's own included —
    and that is a problem with the request, not a server failure."""
    envelope = error_envelope(ValueError("importance must be a number"))

    assert envelope["code"] == StudioErrorCode.VALIDATION.value
    assert envelope["message"] == "importance must be a number"


def test_error_envelope_gives_the_same_code_whatever_the_sentence_says() -> None:
    plain = error_envelope(NotFoundError("O-1", "Outcome"))
    wordy = error_envelope(
        NotFoundError("O-1", "Customer outcome", hint="check the id in the board")
    )

    assert plain["code"] == wordy["code"] == StudioErrorCode.NOT_FOUND.value
    assert plain["suggestion"] == wordy["suggestion"]
    assert plain["retryable"] == wordy["retryable"]
    assert wordy["message"] == "Customer outcome not found: O-1. check the id in the board"


def test_error_envelope_survives_json_serialisation() -> None:
    """The MCP hop puts this inside ``json.dumps``, so nothing in it may be exotic."""
    envelope = error_envelope(NotFoundError("O-1", "Outcome"))

    assert json.loads(json.dumps(envelope)) == envelope
    assert isinstance(envelope["code"], str)


def _envelope_text(envelope: dict[str, object], sentence: str) -> str:
    return json.dumps({"error": envelope, "message": sentence})


def test_parse_reads_an_envelopes_code_instead_of_its_sentence() -> None:
    text = _envelope_text(
        error_envelope(NotFoundError("O-1", "Outcome")),
        "Error: Outcome not found: O-1",
    )

    problem = parse_tool_result(text)

    assert problem is not None
    assert problem.code is StudioErrorCode.NOT_FOUND
    assert problem.message == "Outcome not found: O-1"
    assert problem.suggestion == "Check the identifier and try again."
    assert problem.retryable is False


def test_parse_gives_two_envelopes_the_same_verdict_whatever_they_say() -> None:
    """The anti-wording test: copy changes, classification cannot."""
    terse = parse_tool_result(
        _envelope_text(
            {
                "code": "consent_required",
                "message": "no consent",
                "suggestion": "Get the PM's approval for this workspace, then try again.",
                "retryable": False,
            },
            "Error: no consent",
        )
    )
    wordy = parse_tool_result(
        _envelope_text(
            {
                "code": "consent_required",
                "message": "the PM has not approved working on this workspace yet, so nothing "
                "was written and the run stopped before the first tool call",
                "suggestion": "Get the PM's approval for this workspace, then try again.",
                "retryable": False,
            },
            "Error: the PM has not approved working on this workspace yet",
        )
    )

    assert terse is not None and wordy is not None
    assert terse.code is wordy.code is StudioErrorCode.CONSENT_REQUIRED
    assert terse.retryable is wordy.retryable is False
    assert terse.suggestion == wordy.suggestion


def test_parse_trusts_the_envelope_over_a_marker_in_the_prose() -> None:
    """``must be between`` is an out-of-range marker in the legacy path; the code wins."""
    problem = parse_tool_result(
        _envelope_text(
            {
                "code": "validation",
                "message": "title must be between 3 and 80 characters, and it was empty",
                "suggestion": "Fix the input and try again.",
                "retryable": False,
            },
            "Error: title must be between 3 and 80 characters",
        )
    )

    assert problem is not None
    assert problem.code is StudioErrorCode.VALIDATION


def test_parse_carries_a_rate_limited_envelope_as_retryable() -> None:
    problem = parse_tool_result(
        _envelope_text(
            error_envelope(RateLimitError("too many writes in a minute")),
            "Error: too many writes in a minute",
        )
    )

    assert problem is not None
    assert problem.code is StudioErrorCode.RATE_LIMITED
    assert problem.retryable is True


def test_parse_falls_back_to_prose_for_a_peer_that_predates_the_envelope() -> None:
    problem = parse_tool_result("Error: Job with ID JOB-9 not found.")

    assert problem is not None
    assert problem.code is StudioErrorCode.NOT_FOUND
    assert problem.message == "Job with ID JOB-9 not found."


def test_parse_accepts_an_envelope_missing_its_advice_fields() -> None:
    """A peer that shipped only code and message still classifies."""
    problem = parse_tool_result(
        _envelope_text(
            {"code": "conflict", "message": "already recorded"}, "Error: already recorded"
        )
    )

    assert problem is not None
    assert problem.code is StudioErrorCode.CONFLICT
    assert problem.suggestion == suggestion_for_code(StudioErrorCode.CONFLICT)
    assert problem.retryable is retryable_for_code(StudioErrorCode.CONFLICT)


def test_parse_ignores_json_that_is_not_an_error() -> None:
    assert parse_tool_result(json.dumps({"id": "JOB-1", "note": "not found is a word too"})) is None
    assert parse_tool_result(json.dumps([{"code": "not_found"}])) is None
