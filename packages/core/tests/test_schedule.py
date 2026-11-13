from datetime import datetime, timezone

import pytest
from agentic_odi_core.schedule import (
    compute_next_run,
    is_due,
    validate_schedule_expression,
)


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "expression,now,expected",
    [
        ("@daily", _utc(2026, 11, 13, 10, 0), _utc(2026, 11, 14, 0, 0)),
        (
            "*/15 * * * *",
            _utc(2026, 11, 13, 10, 0),
            _utc(2026, 11, 13, 10, 15),
        ),
        (
            "0 9 * * 1",
            _utc(2026, 11, 13, 10, 0),
            _utc(2026, 11, 16, 9, 0),
        ),
    ],
)
def test_compute_next_run(expression, now, expected):
    result = compute_next_run(expression, now=now)
    assert result == expected
    assert result.tzinfo is not None


def test_compute_next_run_utc():
    now = _utc(2026, 11, 13, 10, 0)
    result = compute_next_run("@daily", now=now)
    assert result.tzinfo == timezone.utc
    assert result == _utc(2026, 11, 14, 0, 0)


def test_validate_schedule_expression_accepts_valid():
    validate_schedule_expression("@daily")
    validate_schedule_expression("*/15 * * * *")
    validate_schedule_expression("0 0 1 1 *")


def test_validate_schedule_expression_rejects_invalid():
    with pytest.raises(ValueError):
        validate_schedule_expression("not a cron expression")
    with pytest.raises(ValueError):
        validate_schedule_expression("* * *")
    with pytest.raises(ValueError):
        validate_schedule_expression("25 25 * * *")


def test_is_due_when_next_run_has_passed():
    now = _utc(2026, 11, 13, 10, 0)
    assert is_due("@daily", last_run=_utc(2026, 11, 12, 0, 0), now=now)


def test_is_not_due_when_next_run_is_future():
    now = _utc(2026, 11, 13, 10, 0)
    assert not is_due("@daily", last_run=_utc(2026, 11, 13, 0, 0), now=now)
