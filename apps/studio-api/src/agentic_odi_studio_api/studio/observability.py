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

#: Keys that contain a sensitive-looking substring ("token") but are not
#: secrets: they are counts. Checked before the substring heuristic, so the
#: turn line can carry what a turn cost without the redactor eating it.
NON_SENSITIVE_KEYS = frozenset(
    {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    }
)


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    if lowered in NON_SENSITIVE_KEYS:
        return False
    if lowered in SENSITIVE_KEYS:
        return True
    return any(marker in lowered for marker in ("token", "secret", "password", "api_key"))


#: Recurse no deeper than this. A cycle cannot enter through JSON, but a caller
#: may pass one, and the turn must still finish rather than hang the request.
_MAX_DEPTH = 8


def _redact_value(value: Any, depth: int = 0) -> Any:
    if depth > _MAX_DEPTH:
        return REDACTED
    if isinstance(value, Mapping):
        return {
            key: REDACTED if _is_sensitive(str(key)) else _redact_value(nested, depth + 1)
            for key, nested in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_value(item, depth + 1) for item in value]
    return value


def redact(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``mapping`` with sensitive values replaced.

    Redaction applies at every depth, so a nested token, a list of mappings, or
    a quote inside a context reaches the log as ``[redacted]`` rather than
    verbatim.
    """
    return _redact_value(dict(mapping))


def log_turn(**fields: Any) -> None:
    """Write one JSON log line describing a chat turn.

    Sensitive fields are dropped outright: the line says what happened in the
    turn, and it must not name a secret any more than it carries its value.
    Nested mappings and sequences are redacted rather than dropped, so a
    context that is worth keeping can still be logged.
    """
    payload: dict[str, Any] = {}
    for key, value in fields.items():
        if _is_sensitive(str(key)):
            continue
        payload[key] = _redact_value(value)
    log.info(json.dumps(payload, default=str, sort_keys=True))
