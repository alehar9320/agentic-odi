"""Tests for the sidecar capabilities manifest."""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def test_capabilities_manifest_describes_sidecar_features() -> None:
    app = create_app(repo=InMemoryRepository())
    client = TestClient(app)

    response = client.get("/api/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert "capabilities" in body
    ids = [item["id"] for item in body["capabilities"]]
    expected = [
        "local-data",
        "local-memory",
        "deterministic-assistant",
        "browser-model",
        "endpoint-model",
        "sidecar-llm",
        "sidecar-connectors",
        "sidecar-mcp",
        "sidecar-import",
    ]
    assert ids == expected

    by_id = {item["id"]: item for item in body["capabilities"]}
    assert by_id["sidecar-llm"]["available"] is True
    assert by_id["local-data"]["available"] is True
    assert by_id["browser-model"]["available"] is False


def test_capabilities_requires_known_shape() -> None:
    app = create_app(repo=InMemoryRepository())
    client = TestClient(app)

    response = client.get("/api/capabilities")

    assert response.status_code == 200
    for item in response.json()["capabilities"]:
        assert set(item) == {"id", "label", "description", "available", "reason"}
