"""The sidecar is the thing that launches, so the sidecar is the thing that counts.

ALH-147: `launch` and `return_session` at startup, `first_message` on a turn that
actually ended, and a stats endpoint that can say "nothing yet".

A launch owns its repository and closes it on the way out, exactly as the real
sidecar does — so "the app was launched twice" is two repositories over one file.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from agentic_odi_core.events import Event
from agentic_odi_core.funnel import FUNNEL_EVENT, FUNNEL_NAMES
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import chat
from fastapi.testclient import TestClient
from test_studio_chat_stream import _chunk, _FakeStream, _install, _request


@pytest.fixture
def db(tmp_path) -> str:
    return str(tmp_path / "odi.db")


def _events(db_path: str) -> list[Event]:
    repository = SQLiteRepository(db_path)
    try:
        return [event for event in repository.store.get_stream() if event["type"] == FUNNEL_EVENT]
    finally:
        repository.close()


def _names(db_path: str) -> list[str]:
    return [str(event["payload"]["name"]) for event in _events(db_path)]


@contextmanager
def _launched(db_path: str) -> Iterator[TestClient]:
    """One sidecar launch, with the lifespan that opens it and closes it again."""
    repository = SQLiteRepository(db_path)
    try:
        with TestClient(create_app(repository, backend="local")) as client:
            yield client
    finally:
        repository.close()


def _turn(request: Any, service: ODIService) -> list[str]:
    async def _run() -> list[str]:
        return [frame async for frame in chat.stream_chat(request, local_service=service)]

    return asyncio.run(_run())


def test_starting_the_sidecar_records_one_launch(db) -> None:
    with _launched(db):
        pass

    assert _names(db) == ["launch"]


def test_starting_the_sidecar_twice_records_exactly_one_return_session(db) -> None:
    with _launched(db):
        pass
    with _launched(db):
        pass

    assert sorted(_names(db)) == ["launch", "launch", "return_session"]


def test_every_sidecar_launch_draws_its_own_session_id(db) -> None:
    with _launched(db):
        pass
    with _launched(db):
        pass

    launches = [event for event in _events(db) if event["payload"]["name"] == "launch"]
    assert len({event["payload"]["session_id"] for event in launches}) == 2


def test_no_funnel_event_borrows_the_device_stamp_as_its_session_id(db) -> None:
    with _launched(db):
        pass
    with _launched(db):
        pass

    events = _events(db)
    sessions = {str(event["payload"]["session_id"]) for event in events}
    devices = {str(event["device_id"]) for event in events}
    assert sessions
    assert sessions.isdisjoint(devices)


def test_a_completed_turn_records_the_first_message(db, monkeypatch) -> None:
    _install(monkeypatch, [_FakeStream([_chunk(content="Three jobs so far.")])])

    repository = SQLiteRepository(db)
    try:
        _turn(_request(), ODIService(repository))
    finally:
        repository.close()

    assert _names(db) == ["first_message"]


def test_a_second_turn_does_not_record_a_second_first_message(db, monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(content="Three jobs so far.")]),
            _FakeStream([_chunk(content="Still three.")]),
        ],
    )

    repository = SQLiteRepository(db)
    try:
        service = ODIService(repository)
        _turn(_request(), service)
        _turn(_request(), service)
    finally:
        repository.close()

    assert _names(db) == ["first_message"]


def test_a_turn_that_ends_in_an_error_records_no_first_message(db, monkeypatch) -> None:
    _install(monkeypatch, [_FakeStream([_chunk(content="never sent")])])
    monkeypatch.setattr(chat, "is_endpoint_reachable", lambda url, timeout: False)

    repository = SQLiteRepository(db)
    try:
        frames = _turn(_request(), ODIService(repository))
    finally:
        repository.close()

    assert any("event: error" in frame for frame in frames)
    assert _names(db) == []


def test_the_stats_endpoint_reports_each_counter_with_its_window(db) -> None:
    with _launched(db) as client:
        body = client.get("/api/stats").json()

    assert set(body) == set(FUNNEL_NAMES)
    assert body["launch"]["counts"] == 1
    assert body["launch"]["first_seen"] == body["launch"]["last_seen"]


def test_the_stats_endpoint_can_say_nothing_yet(db) -> None:
    with _launched(db) as client:
        body = client.get("/api/stats").json()

    assert body["first_score"] == {"counts": 0, "first_seen": None, "last_seen": None}


def test_the_stats_endpoint_resets_the_measurement_and_returns_the_new_zeros(db) -> None:
    with _launched(db) as client:
        after_reset = client.post("/api/stats/reset").json()
        body = client.get("/api/stats").json()

    assert all(view["counts"] == 0 for view in after_reset.values())
    assert all(view["counts"] == 0 for view in body.values())


def test_the_reset_leaves_the_events_it_superseded_in_the_log(db) -> None:
    with _launched(db) as client:
        client.post("/api/stats/reset")

    assert _names(db) == ["launch"]


def test_a_sidecar_without_an_event_log_still_answers_the_stats_endpoint() -> None:
    app = create_app(InMemoryRepository(), backend="local")

    with TestClient(app) as client:
        response = client.get("/api/stats")
        reset_response = client.post("/api/stats/reset")

    assert response.status_code == 200
    assert reset_response.status_code == 200
    assert all(view["counts"] == 0 for view in response.json().values())
