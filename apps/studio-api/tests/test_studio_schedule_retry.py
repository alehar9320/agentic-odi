"""The schedule route tells the truth about a failed run, not just its status."""

from __future__ import annotations

from datetime import datetime, timezone

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend="local"))


def _fixed_now() -> datetime:
    return datetime(2026, 5, 1, 2, 0, 0, tzinfo=timezone.utc)


def test_schedule_response_carries_the_failure_and_its_retry() -> None:
    client = _client()
    created = client.post(
        "/api/schedule",
        json={"name": "Morning brief", "schedule_expression": "0 2 * * *"},
    )
    assert created.status_code == 200
    work_id = created.json()["result"]["id"]

    def failing(_work):
        raise RuntimeError("model unreachable")

    client.app.state.service.run_scheduled_work(work_id, failing, now=_fixed_now())

    listed = client.get("/api/schedule").json()["result"]
    item = next(row for row in listed if row["id"] == work_id)

    assert item["last_status"] == "failed"
    assert item["status"] != "completed"
    assert item["attempts"] == 1
    assert item["last_error"] == "RuntimeError: model unreachable"
    assert item["next_run_at"] == "2026-05-01T02:02:00+00:00"


def test_healthy_item_has_no_error_in_the_response() -> None:
    client = _client()
    created = client.post(
        "/api/schedule",
        json={"name": "Weekly sweep", "schedule_expression": "0 2 * * *"},
    )
    work_id = created.json()["result"]["id"]

    client.app.state.service.run_scheduled_work(work_id, lambda _w: "ok", now=_fixed_now())

    listed = client.get("/api/schedule").json()["result"]
    item = next(row for row in listed if row["id"] == work_id)

    assert item["last_status"] == "ok"
    assert item["attempts"] == 0
    assert item["last_error"] is None
    assert item["next_run_at"] is None
