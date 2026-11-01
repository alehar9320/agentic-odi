"""Authentication requirements for the Living Studio sidecar API (``/api/*``)."""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def _raw_client() -> TestClient:
    return TestClient(create_app(InMemoryRepository()))


def test_missing_token_gets_401() -> None:
    client = _raw_client()
    response = client.get("/api/config")
    assert response.status_code == 401


def test_wrong_token_gets_401() -> None:
    client = _raw_client()
    response = client.get("/api/config", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_health_stays_open_without_token() -> None:
    client = _raw_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_valid_token_passes() -> None:
    app = create_app(InMemoryRepository())
    token = app.state.studio_token
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    response = client.get("/api/config")
    assert response.status_code == 200
    assert "defaults" in response.json()
