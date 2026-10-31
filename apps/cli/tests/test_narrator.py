"""Tests for the CLI narrator adapter (M3-04 / ALH-169).

The adapter is the only place a model is reached. These tests use a stub client,
so no network is involved, and pin the honest-degradation contract:

* a well-formed reply parses into a :class:`NarrativeDraft`;
* a fenced reply is unwrapped;
* malformed JSON, a wrong shape, or an unusable response raises ``NarratorError``
  so the caller records a drop instead of printing an unchecked sentence;
* a transport failure raises ``NarratorError`` rather than escaping.
"""

from __future__ import annotations

import pytest
from agentic_odi_cli.narrator import OpenAINarrator, parse_draft
from agentic_odi_core import BriefInput, NarratorError


def test_parse_draft_reads_a_well_formed_reply() -> None:
    draft = parse_draft(
        '{"supported": [{"claim": "out-1 leads.", "outcome_ids": ["out-1"]}],'
        ' "recommendation": [], "risks": []}'
    )
    assert draft.supported[0].claim == "out-1 leads."
    assert draft.supported[0].outcome_ids == ("out-1",)


def test_parse_draft_unwraps_a_fenced_block() -> None:
    draft = parse_draft(
        '```json\n{"supported": [{"claim": "a", "outcome_ids": ["out-1"]}],'
        ' "recommendation": [], "risks": []}\n```'
    )
    assert draft.supported[0].claim == "a"


@pytest.mark.parametrize(
    "text",
    [
        "not json at all",
        '{"supported": "a string, not a list"}',
        '{"supported": [{"no_claim": true}]}',
        '{"supported": [{"claim": "x", "outcome_ids": "out-1"}]}',
    ],
)
def test_parse_draft_refuses_a_malformed_reply(text: str) -> None:
    with pytest.raises(NarratorError):
        parse_draft(text)


class _StubCompletions:
    def __init__(self, content: object = None, error: Exception | None = None) -> None:
        self._content = content
        self._error = error

    def create(self, **kwargs: object) -> object:
        if self._error is not None:
            raise self._error
        message = type("M", (), {"content": self._content})()
        choice = type("C", (), {"message": message})()
        return type("R", (), {"choices": [choice]})()


class _StubClient:
    def __init__(self, content: object = None, error: Exception | None = None) -> None:
        self.chat = type("Chat", (), {"completions": _StubCompletions(content, error)})()


_BRIEF = BriefInput(
    job_id="job-1", job_name="Publish a plugin", generated_at="2026-10-29T00:00:00Z"
)


def test_draft_parses_a_successful_response() -> None:
    client = _StubClient(
        '{"supported": [{"claim": "out-1 leads.", "outcome_ids": ["out-1"]}],'
        ' "recommendation": [], "risks": []}'
    )
    draft = OpenAINarrator(client, "model").draft(_BRIEF)
    assert draft.supported[0].claim == "out-1 leads."


def test_a_transport_failure_raises_narrator_error() -> None:
    client = _StubClient(error=RuntimeError("connection refused"))
    with pytest.raises(NarratorError, match="unavailable"):
        OpenAINarrator(client, "model").draft(_BRIEF)


def test_an_empty_response_raises_narrator_error() -> None:
    client = _StubClient(content="   ")
    with pytest.raises(NarratorError, match="empty"):
        OpenAINarrator(client, "model").draft(_BRIEF)
