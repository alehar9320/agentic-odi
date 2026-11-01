"""Tests for the Studio's metadata-only diagnostics endpoint."""

from __future__ import annotations

from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.sqlite_repository import SQLiteRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio.memory import StudioMemory
from fastapi.testclient import TestClient


def test_diagnostics_returns_only_metadata_and_database_basename(monkeypatch, tmp_path) -> None:
    private_path = tmp_path / "private-user-directory" / "odi.db"
    private_path.parent.mkdir(parents=True)
    client = TestClient(create_app(SQLiteRepository(str(private_path)), backend="local"))
    user_text = "PRIVATE-DIAGNOSTIC-CANARY customer conversation"

    created = client.post("/api/jobs", json={"name": user_text, "description": user_text})
    assert created.status_code == 200

    response = client.get("/api/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["version"]
    assert body["python"]
    assert "config" not in body
    assert body["db"] == {
        "name": "odi.db",
        "size_bytes": private_path.stat().st_size,
        "integrity": "ok",
        "counts": {"jobs": 1, "outcomes": 0, "evidence": 0, "observations": 0},
    }
    assert body["migrations"] == {"events": "current"}
    assert isinstance(body["capabilities"], list)
    assert user_text not in response.text
    assert str(private_path.parent) not in response.text
    assert "configured-secret" not in response.text


def test_diagnostics_reports_the_boot_integrity_result() -> None:
    memory = StudioMemory(":memory:")
    try:
        app = create_app(InMemoryRepository(), backend="local", memory=memory)
        app.state.db_integrity = "ok"

        response = TestClient(app).get("/api/diagnostics")

        assert response.status_code == 200
        assert response.json()["db"]["integrity"] == "ok"
    finally:
        memory.close()
