"""The one read route for the latest briefing: 204 when none, else the record.

``test_studio_brief.py`` already covers the onboarding ``StudioBrief`` that
reaches the model; this file covers the overnight *briefing* — a different
thing with a different name — so the two never share a module.
"""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository, RunChange
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio.schemas import BriefingResponse
from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend="local"))


def test_no_finished_run_returns_204() -> None:
    response = _client().get("/api/briefings/latest")

    assert response.status_code == 204
    assert response.content == b""


def test_a_stored_briefing_validates_against_the_schema() -> None:
    app = create_app(InMemoryRepository(), backend="local")
    client = TestClient(app)
    service = app.state.service
    work = service.schedule_work(name="Nightly run", schedule_expression="0 0 * * *")
    service.complete_scheduled_work(
        work.id,
        changes=[
            RunChange("added", "A new quote mentions onboarding.", "ev-1", "evidence"),
            RunChange("changed", "O-12 rose to 14.2.", "o-12", "outcome"),
        ],
    )

    response = client.get("/api/briefings/latest")

    assert response.status_code == 200
    parsed = BriefingResponse.model_validate(response.json())
    assert parsed.run_id == work.id
    assert [item.record_id for item in parsed.items] == ["ev-1", "o-12"]
    assert parsed.items[0].kind == "added"
    assert parsed.items[0].record_kind == "evidence"


def test_an_empty_briefing_is_200_with_no_items_not_204() -> None:
    app = create_app(InMemoryRepository(), backend="local")
    client = TestClient(app)
    work = app.state.service.schedule_work(name="Quiet night", schedule_expression="0 0 * * *")
    app.state.service.complete_scheduled_work(work.id)

    response = client.get("/api/briefings/latest")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_the_route_never_500s_when_a_stored_briefing_is_present() -> None:
    app = create_app(InMemoryRepository(), backend="local")
    client = TestClient(app)
    work = app.state.service.schedule_work(name="Nightly run", schedule_expression="0 0 * * *")
    app.state.service.complete_scheduled_work(work.id)

    for _ in range(3):
        assert client.get("/api/briefings/latest").status_code == 200
