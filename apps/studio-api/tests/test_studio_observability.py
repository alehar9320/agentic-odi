"""Tests for the per-turn structured log line and its redaction."""

from __future__ import annotations

import json
import logging

from agentic_odi_studio_api.studio.observability import log_turn, redact


def test_redact_hides_sensitive_values_and_keeps_the_rest() -> None:
    redacted = redact(
        {
            "token": "t",
            "api_key": "k",
            "quote": "customer words",
            "model": "m",
        }
    )

    assert redacted["token"] == "[redacted]"
    assert redacted["api_key"] == "[redacted]"
    assert redacted["quote"] == "[redacted]"
    assert redacted["model"] == "m"


def test_log_turn_writes_one_json_line(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="agentic_odi_studio_api.studio.observability"):
        log_turn(
            request_id="req-1",
            model="m",
            rounds=2,
            tool_calls=3,
            tool_errors=1,
            duration_ms=42,
            outcome="completed",
        )

    lines = [record.getMessage() for record in caplog.records]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["request_id"] == "req-1"
    assert payload["rounds"] == 2
    assert payload["tool_calls"] == 3
    assert payload["tool_errors"] == 1
    assert payload["duration_ms"] == 42
    assert payload["outcome"] == "completed"


def test_log_turn_never_writes_secrets_or_quotations(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="agentic_odi_studio_api.studio.observability"):
        log_turn(
            request_id="req-1",
            model="m",
            rounds=1,
            tool_calls=1,
            tool_errors=0,
            duration_ms=10,
            outcome="completed",
            api_key="sk-live-secret",
            quote="customer words",
        )

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "api_key" not in text
    assert "sk-live-secret" not in text
    assert "quote" not in text
    assert "customer words" not in text
    assert "request_id" in text


def test_log_turn_records_the_error_code_of_a_failed_turn(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="agentic_odi_studio_api.studio.observability"):
        log_turn(
            request_id="req-1",
            model="m",
            rounds=0,
            tool_calls=0,
            tool_errors=0,
            duration_ms=5,
            outcome="failed",
            error_code="mcp_unreachable",
        )

    payload = json.loads(caplog.records[0].getMessage())
    assert payload["error_code"] == "mcp_unreachable"


def test_log_turn_records_token_counts_and_model(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="agentic_odi_studio_api.studio.observability"):
        log_turn(
            request_id="req-1",
            model="m",
            rounds=1,
            tool_calls=0,
            tool_errors=0,
            duration_ms=10,
            outcome="completed",
            prompt_tokens=120,
            completion_tokens=40,
            total_tokens=160,
        )

    payload = json.loads(caplog.records[0].getMessage())
    assert payload["prompt_tokens"] == 120
    assert payload["completion_tokens"] == 40
    assert payload["total_tokens"] == 160
    assert payload["model"] == "m"


def test_log_turn_allows_a_null_token_count(caplog) -> None:
    """A backend that reports no usage leaves the counts null, never guessed."""
    with caplog.at_level(logging.INFO, logger="agentic_odi_studio_api.studio.observability"):
        log_turn(
            request_id="req-1",
            model="m",
            rounds=1,
            tool_calls=0,
            tool_errors=0,
            duration_ms=10,
            outcome="completed",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
        )

    payload = json.loads(caplog.records[0].getMessage())
    assert payload["prompt_tokens"] is None
    assert payload["completion_tokens"] is None
    assert payload["total_tokens"] is None


def test_log_turn_never_writes_a_bearer_token_with_token_counts(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="agentic_odi_studio_api.studio.observability"):
        log_turn(
            request_id="req-1",
            model="m",
            rounds=1,
            tool_calls=0,
            tool_errors=0,
            duration_ms=10,
            outcome="completed",
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
            authorization="Bearer sk-live-secret",
            api_key="sk-live-secret",
        )

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "sk-live-secret" not in text
    assert "authorization" not in text
    assert "api_key" not in text
    assert "total_tokens" in text


def test_log_turn_redacts_nested_values(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="agentic_odi_studio_api.studio.observability"):
        log_turn(
            request_id="req-1",
            model="m",
            rounds=0,
            tool_calls=0,
            tool_errors=0,
            duration_ms=1,
            outcome="completed",
            context={"api_key": "sk-live", "name": "studio"},
        )

    payload = json.loads(caplog.records[0].getMessage())
    assert payload["context"]["api_key"] == "[redacted]"
    assert payload["context"]["name"] == "studio"
