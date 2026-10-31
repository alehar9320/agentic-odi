"""Event-list helpers shared by the daemon and its tests."""

from __future__ import annotations

import re
from collections.abc import Iterable

from agentic_odi_openhands.models import (
    ActionEvent,
    Event,
    MessageEvent,
    ObservationEvent,
    UserRejectObservation,
)

_PR_URL = re.compile(r"https?://[^\s)\]\"']+/pull/\d+")


def pending_actions(events: Iterable[Event]) -> list[ActionEvent]:
    """Actions with no observation and no rejection, newest last.

    The SDK links a response to an action by ``tool_call_id`` and/or the
    action event id (``action_id``); a match on either clears the action.
    """
    ordered = list(events)
    answered: set[str] = set()
    for event in ordered:
        if isinstance(event, (ObservationEvent, UserRejectObservation)):
            for key in (event.tool_call_id, event.action_id):
                if key:
                    answered.add(key)

    pending: list[ActionEvent] = []
    seen: set[str] = set()
    for event in ordered:
        if not isinstance(event, ActionEvent):
            continue
        key = event.tool_call_id or event.id
        if key in answered or event.id in answered or key in seen:
            continue
        seen.add(key)
        pending.append(event)
    return pending


def final_message(events: Iterable[Event]) -> str | None:
    """The last non-empty agent message, which is where agents report results."""
    for event in reversed(list(events)):
        if isinstance(event, MessageEvent) and event.source == "agent":
            text = event.text
            if text:
                return text
    return None


def pr_urls(text: str | None) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for match in _PR_URL.findall(text):
        if match not in found:
            found.append(match)
    return found
