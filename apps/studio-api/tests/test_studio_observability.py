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
