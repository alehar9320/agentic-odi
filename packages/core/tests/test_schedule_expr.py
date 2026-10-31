from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from agentic_odi_core import ScheduledWorkTriggerType
from agentic_odi_core.schedule_expr import (
    ScheduleExpressionError,
    next_occurrence,
    parse_schedule,
)

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def test_iso_timestamp_is_a_one_shot() -> None:
    parsed = parse_schedule("2026-11-01T09:00:00Z", now=NOW)
    assert parsed.trigger_type == ScheduledWorkTriggerType.ONESHOT
    assert not parsed.recurring
    assert parsed.next_run_at == datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("+30s", NOW + timedelta(seconds=30)),
        ("+90m", NOW + timedelta(minutes=90)),
        ("+2h", NOW + timedelta(hours=2)),
        ("+2d", NOW + timedelta(days=2)),
        ("+1w", NOW + timedelta(weeks=1)),
        ("+ 5 m", NOW + timedelta(minutes=5)),
    ],
)
def test_relative_delays(expression: str, expected: datetime) -> None:
    parsed = parse_schedule(expression, now=NOW)
    assert parsed.trigger_type == ScheduledWorkTriggerType.ONESHOT
    assert parsed.next_run_at == expected


def test_cron_is_recurring_and_after_now() -> None:
    parsed = parse_schedule("0 9 * * 1-5", now=NOW)
    assert parsed.trigger_type == ScheduledWorkTriggerType.CRON
    assert parsed.recurring
    assert parsed.next_run_at > NOW
    assert parsed.next_run_at.hour == 9


def test_six_field_cron_is_accepted() -> None:
    parsed = parse_schedule("0 0 9 * * *", now=NOW)
    assert parsed.recurring


def test_next_occurrence_moves_forward() -> None:
    after = datetime(2026, 10, 29, 9, 0, tzinfo=timezone.utc)
    nxt = next_occurrence("0 9 * * *", after)
    assert nxt == datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)
    assert next_occurrence("+1h", after) is None


@pytest.mark.parametrize("expression", ["", "tomorrow", "+2y", "not a cron at all", "99 99 * * *"])
def test_invalid_expressions_lists_formats(expression: str) -> None:
    with pytest.raises(ScheduleExpressionError) as excinfo:
        parse_schedule(expression)
    if expression:
        assert "ISO-8601" in str(excinfo.value)


def test_service_rejects_unparseable_expression() -> None:
    from agentic_odi_core import InMemoryRepository, ODIService

    service = ODIService(InMemoryRepository())
    with pytest.raises(ScheduleExpressionError, match="ISO-8601"):
        service.schedule_work(name="bad", schedule_expression="tomorrow")
