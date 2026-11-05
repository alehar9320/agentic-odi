"""Onboarding is measurable on this machine (ALH-147): five local counters.

The funnel is a handful of append-only records in the same event log the domain
uses. Nothing here reaches the network, nothing here can fail a user action, and
no counter may be invented at runtime — the vocabulary is fixed.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from agentic_odi_core import funnel
from agentic_odi_core.events import Event, resolve_device_id
from agentic_odi_core.funnel import (
    FUNNEL_EVENT,
    FUNNEL_NAMES,
    adjacent_conversions,
    count_launch,
    count_milestone,
    count_reset,
    read_counts,
    record_launch,
    record_milestone,
    reset,
    session_id,
    start_session,
    stats,
)
from agentic_odi_core.intent_store import IntentStore
from agentic_odi_core.models import Job
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository


@pytest.fixture
def store(tmp_path):
    opened = IntentStore(str(tmp_path / "funnel.db"))
    yield opened
    opened.close()


def _events(opened, workspace_id: str = "local") -> list[dict]:
    return [
        event
        for event in opened.get_stream(workspace_id=workspace_id)
        if event["type"] == FUNNEL_EVENT
    ]


def _names(opened, workspace_id: str = "local") -> list[str]:
    return [str(event["payload"]["name"]) for event in _events(opened, workspace_id)]


class _UnusableStore:
    """A log that refuses to be written. It is deliberately not a whole EventStore.

    The funnel is typed against the protocol, but the point of these tests is a
    store that fails, and which method fails is not the behaviour under test.
    """

    def append(self, *args: object, **kwargs: object) -> Event:
        raise RuntimeError("the disk is on fire")

    def get_stream(self, **kwargs: object) -> list[Event]:
        return []


def test_a_launch_appends_exactly_one_funnel_event(store) -> None:
    record_launch(store, session_id="sess-1")

    assert _names(store) == ["launch"]


def test_a_funnel_event_carries_the_agreed_payload(store) -> None:
    record_launch(store, session_id="sess-1")

    payload = _events(store)[0]["payload"]
    assert set(payload) == {"name", "at", "session_id"}
    assert payload["session_id"] == "sess-1"


def test_a_funnel_event_records_the_moment_it_happened(store) -> None:
    record_launch(store, session_id="sess-1")

    assert datetime.fromisoformat(_events(store)[0]["payload"]["at"])


def test_a_second_launch_records_exactly_one_return_session(store) -> None:
    record_launch(store, session_id="sess-1")
    record_launch(store, session_id="sess-2")

    assert sorted(_names(store)) == ["launch", "launch", "return_session"]


def test_a_return_session_event_belongs_to_the_session_that_came_back(store) -> None:
    record_launch(store, session_id="sess-1")
    record_launch(store, session_id="sess-2")

    returned = [event for event in _events(store) if event["payload"]["name"] == "return_session"]
    assert [event["payload"]["session_id"] for event in returned] == ["sess-2"]


def test_a_launch_uses_the_current_session_when_none_is_given(store) -> None:
    current = start_session()

    record_launch(store)

    assert _events(store)[0]["payload"]["session_id"] == current


def test_a_milestone_is_recorded_once_however_often_it_hits(store) -> None:
    for _ in range(3):
        record_milestone(store, "first_message", session_id="sess-1")

    assert _names(store) == ["first_message"]


def test_the_milestones_are_independent_counters(store) -> None:
    record_milestone(store, "first_message", session_id="sess-1")
    record_milestone(store, "first_outcome", session_id="sess-1")
    record_milestone(store, "first_message", session_id="sess-1")

    assert sorted(_names(store)) == ["first_message", "first_outcome"]


def test_a_milestone_is_idempotent_within_a_workspace(store) -> None:
    record_milestone(store, "first_score", session_id="sess-1", workspace_id="ws-a")
    record_milestone(store, "first_score", session_id="sess-2", workspace_id="ws-a")

    assert _names(store, "ws-a") == ["first_score"]


def test_a_fresh_workspace_records_its_own_first_milestone(store) -> None:
    record_milestone(store, "first_message", session_id="sess-1", workspace_id="ws-a")
    record_milestone(store, "first_message", session_id="sess-1", workspace_id="ws-b")

    assert _names(store, "ws-a") == ["first_message"]
    assert _names(store, "ws-b") == ["first_message"]


def test_a_name_outside_the_vocabulary_is_refused(store) -> None:
    with pytest.raises(ValueError, match="first_message"):
        record_milestone(store, "page_view", session_id="sess-1")


def test_the_funnel_vocabulary_is_exactly_the_five_agreed_names() -> None:
    assert FUNNEL_NAMES == (
        "launch",
        "first_message",
        "first_outcome",
        "first_score",
        "return_session",
    )


def test_stats_reports_a_count_and_a_window_for_each_event(store) -> None:
    record_launch(store, session_id="sess-1")
    record_milestone(store, "first_message", session_id="sess-1")

    counts = stats(store)
    assert counts["launch"]["counts"] == 1
    assert counts["first_message"]["counts"] == 1


def test_stats_windows_on_the_events_it_counted(store) -> None:
    record_launch(store, session_id="sess-1")
    record_launch(store, session_id="sess-2")
    events = _events(store)

    counts = stats(store)
    assert counts["launch"]["first_seen"] == events[0]["payload"]["at"]
    assert counts["launch"]["last_seen"] == events[-1]["payload"]["at"]


def test_stats_names_every_event_even_when_nothing_has_happened(store) -> None:
    assert sorted(stats(store)) == sorted(FUNNEL_NAMES)


def test_stats_says_nothing_yet_for_an_event_that_has_not_happened(store) -> None:
    record_launch(store, session_id="sess-1")

    assert stats(store)["first_score"] == {
        "counts": 0,
        "first_seen": None,
        "last_seen": None,
    }


def test_reset_brings_every_count_back_to_zero(store) -> None:
    record_launch(store, session_id="sess-1")
    record_milestone(store, "first_outcome", session_id="sess-1")

    reset(store, session_id="sess-1")

    assert all(view["counts"] == 0 for view in stats(store).values())


def test_reset_appends_a_marker_rather_than_deleting_the_history(store) -> None:
    record_launch(store, session_id="sess-1")

    reset(store, session_id="sess-1")

    assert _names(store) == ["launch"]


def test_the_funnel_measures_again_after_a_reset(store) -> None:
    record_milestone(store, "first_message", session_id="sess-1")
    reset(store, session_id="sess-1")

    record_milestone(store, "first_message", session_id="sess-2")

    assert stats(store)["first_message"]["counts"] == 1


def test_a_launch_after_a_reset_is_counted_as_the_first_launch(store) -> None:
    record_launch(store, session_id="sess-1")
    reset(store, session_id="sess-1")

    record_launch(store, session_id="sess-2")

    assert _names(store)[1:] == ["launch"]


def test_a_store_that_cannot_be_written_does_not_break_the_user_action() -> None:
    broken: Any = _UnusableStore()

    record_launch(broken, session_id="sess-1")
    record_milestone(broken, "first_message", session_id="sess-1")
    reset(broken, session_id="sess-1")


def test_a_write_failure_is_logged(caplog) -> None:
    broken: Any = _UnusableStore()

    with caplog.at_level("WARNING"):
        record_launch(broken, session_id="sess-1")

    assert any(record.levelname == "WARNING" for record in caplog.records)


def test_a_workspace_without_a_store_records_nothing() -> None:
    record_launch(None, session_id="sess-1")

    assert all(view["counts"] == 0 for view in stats(None).values())


def test_a_session_id_is_fresh_for_every_launch() -> None:
    first = start_session()
    second = start_session()

    assert first != second
    assert session_id() == second


def test_no_funnel_event_borrows_the_device_id_as_its_session_id(store, tmp_path) -> None:
    device = resolve_device_id(tmp_path / "device_id")
    session = start_session()

    record_launch(store, session_id=session, device_id=device)
    record_milestone(store, "first_message", session_id=session, device_id=device)

    assert {event["payload"]["session_id"] for event in _events(store)} == {session}
    assert session != device


def test_funnel_events_do_not_change_what_the_repository_replays(tmp_path) -> None:
    db_path = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path)
    repo.add_job(Job(id="job-1", name="Onboard customers"))

    record_launch(repo.store, session_id="sess-1")

    reloaded = SQLiteRepository(db_path)
    assert [job.id for job in reloaded.list_jobs()] == ["job-1"]
    reloaded.store.close()
    repo.store.close()


def test_conversion_between_adjacent_steps_compares_a_step_to_the_one_before_it(store) -> None:
    record_launch(store, session_id="sess-1")
    record_milestone(store, "first_message", session_id="sess-1")

    rows = adjacent_conversions(stats(store))

    assert [(row["from"], row["to"]) for row in rows] == [
        ("launch", "first_message"),
        ("first_message", "first_outcome"),
        ("first_outcome", "first_score"),
        ("first_score", "return_session"),
    ]
    launched = rows[0]
    assert launched["from_counts"] == 1
    assert launched["to_counts"] == 1
    assert launched["conversion"] == pytest.approx(1.0)


def test_an_unmeasurable_conversion_is_left_blank_rather_than_called_zero(store) -> None:
    rows = adjacent_conversions(stats(store))

    assert [row["conversion"] for row in rows] == [None, None, None, None]


def test_the_funnel_never_reaches_the_network() -> None:
    source = Path(funnel.__file__).read_text(encoding="utf-8")

    for library in ("httpx", "requests", "urllib"):
        assert library not in source


def test_a_counter_recorded_through_a_service_lands_in_that_service_log(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"), workspace_id="ws-7", device_id="dev-7")
    service = ODIService(repo)

    count_milestone(service, "first_message")

    event = _events(repo.store, "ws-7")[0]
    assert event["device_id"] == "dev-7"
    repo.store.close()


def test_an_in_memory_workspace_counts_nothing_and_fails_nothing() -> None:
    service = ODIService(InMemoryRepository())

    count_launch(service)
    count_milestone(service, "first_message")
    count_reset(service)

    assert all(view["counts"] == 0 for view in read_counts(service).values())
