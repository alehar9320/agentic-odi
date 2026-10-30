"""Parse the schedule formats the CLI and Studio advertise.

Accepted:

* ISO-8601 timestamps — ``2026-11-01T09:00:00Z``
* relative delays — ``+1h``, ``+90m``, ``+2d``, ``+30s``, ``+1w``
* five- or six-field cron — ``0 9 * * 1-5``

Anything else is rejected at creation, with a message that lists the accepted
formats instead of storing a string nothing can interpret.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from agentic_odi_core.models import ScheduledWorkTriggerType

ACCEPTED_FORMATS = "ISO-8601 timestamp, relative delay (+1h, +90m, +2d), or cron"

_RELATIVE = re.compile(r"^\+\s*(\d+)\s*(s|m|h|d|w)$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


class ScheduleExpressionError(ValueError):
    """The expression is not one of the documented formats."""

    def __init__(self, expression: str, detail: str = "") -> None:
        message = f"Unrecognized schedule expression {expression!r}. Use {ACCEPTED_FORMATS}."
        if detail:
            message = f"{message} ({detail})"
        super().__init__(message)
        self.expression = expression


@dataclass(frozen=True)
class ParsedSchedule:
    expression: str
    trigger_type: ScheduledWorkTriggerType
    next_run_at: datetime
    recurring: bool


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_iso(expression: str) -> datetime | None:
    try:
        return _aware(datetime.fromisoformat(expression.replace("Z", "+00:00")))
    except ValueError:
        return None


def _parse_relative(expression: str, now: datetime) -> datetime | None:
    match = _RELATIVE.match(expression)
    if not match:
        return None
    amount = int(match.group(1))
    return now + timedelta(seconds=amount * _UNIT_SECONDS[match.group(2).lower()])


def _is_cron(expression: str) -> bool:
    return len(expression.split()) in (5, 6) and not _RELATIVE.match(expression)


def _croniter():
    from croniter import croniter

    return croniter


def parse_schedule(expression: str, now: datetime | None = None) -> ParsedSchedule:
    raw = expression.strip()
    if not raw:
        raise ScheduleExpressionError(expression, "empty")
    base = _aware(now or datetime.now(timezone.utc))

    iso = _parse_iso(raw)
    if iso is not None:
        return ParsedSchedule(raw, ScheduledWorkTriggerType.ONESHOT, iso, False)

    relative = _parse_relative(raw, base)
    if relative is not None:
        return ParsedSchedule(raw, ScheduledWorkTriggerType.ONESHOT, relative, False)

    if _is_cron(raw):
        croniter = _croniter()
        if not croniter.is_valid(raw):
            raise ScheduleExpressionError(expression, "invalid cron fields")
        try:
            next_run = croniter(raw, base).get_next(datetime)
        except (ValueError, KeyError) as exc:
            raise ScheduleExpressionError(expression, str(exc)) from exc
        return ParsedSchedule(
            raw, ScheduledWorkTriggerType.CRON, _aware(next_run), True
        )

    raise ScheduleExpressionError(expression)


def next_occurrence(expression: str, after: datetime) -> datetime | None:
    """Next firing strictly after ``after``, or ``None`` for a one-shot."""
    parsed = parse_schedule(expression, now=after)
    if not parsed.recurring:
        return None
    croniter = _croniter()
    return _aware(croniter(parsed.expression, _aware(after)).get_next(datetime))
