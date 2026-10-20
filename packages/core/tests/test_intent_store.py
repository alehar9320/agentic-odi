"""Tests for the append-only Intent Store."""

from __future__ import annotations

from agentic_odi_core.intent_store import IntentStore


def test_append_and_get_stream_return_events_in_order(tmp_path) -> None:
    store = IntentStore(str(tmp_path / "events.db"))
    try:
        store.append("JOB_CREATED", {"id": "job-1"})
        store.append("STEP_CREATED", {"id": "step-1", "job_id": "job-1"})

        stream = store.get_stream()
    finally:
        store.close()

    assert [event["type"] for event in stream] == ["JOB_CREATED", "STEP_CREATED"]
    assert [event["payload"] for event in stream] == [
        {"id": "job-1"},
        {"id": "step-1", "job_id": "job-1"},
    ]
    assert [event["id"] for event in stream] == [1, 2]
    assert all(event["timestamp"] for event in stream)


def test_clear_removes_every_event(tmp_path) -> None:
    store = IntentStore(str(tmp_path / "events.db"))
    try:
        store.append("JOB_CREATED", {"id": "job-1"})
        store.clear()
        assert store.get_stream() == []
    finally:
        store.close()


def test_get_stream_treats_blank_payload_as_empty_dict(tmp_path) -> None:
    store = IntentStore(str(tmp_path / "events.db"))
    try:
        store.conn.execute(
            "INSERT INTO events (timestamp, event_type, payload) VALUES (?, ?, ?)",
            ("2026-01-01T00:00:00", "LEGACY", ""),
        )
        store.conn.commit()

        assert store.get_stream()[0]["payload"] == {}
    finally:
        store.close()
