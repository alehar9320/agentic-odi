"""Per-turn observability: one structured log line, with redaction.

The turn log is what makes a failure diagnosable after the fact, so it must
carry the request id, the shape of the turn, and how it ended — and nothing
that could leak a token, an API key, or a customer's words.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

log = logging.getLogger(__name__)

REDACTED = "[redacted]"

#: Keys whose values must never reach a log line.
SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "quote",
        "quotes",
        "transcript",
        "customer_words",
    }
)


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    if lowered in SENSITIVE_KEYS:
        return True
    return any(marker in lowered for marker in ("token", "secret", "password", "api_key"))


def redact(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``mapping`` with sensitive values replaced."""
    return {key: REDACTED if _is_sensitive(str(key)) else value for key, value in mapping.items()}


def log_turn(**fields: Any) -> None:
    """Write one JSON log line describing a chat turn.

    Sensitive fields are dropped outright: the line says what happened in the
    turn, and it must not name a secret any more than it carries its value.
    Nested mappings are redacted rather than dropped, so a context that is
    worth keeping can still be logged.
    """
    payload: dict[str, Any] = {}
    for key, value in fields.items():
        if _is_sensitive(str(key)):
            continue
        payload[key] = redact(value) if isinstance(value, Mapping) else value
    log.info(json.dumps(payload, default=str, sort_keys=True))
