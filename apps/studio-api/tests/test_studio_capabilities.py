"""Tests for the sidecar capabilities manifest."""

from __future__ import annotations

import re
from pathlib import Path

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


def test_capabilities_ids_are_a_subset_of_the_shared_catalog() -> None:
    """#801: the sidecar keeps its own answers, but its ids must match the catalog.

    The catalog is the contract both hosts share. The sidecar may decide
    availability for itself, but it must not invent an id the catalog does not
    know, or drop one the SPA expects.
    """
    catalog_path = (
        Path(__file__).resolve().parents[3]
        / "apps"
        / "studio"
        / "src"
        / "bff"
        / "capabilities"
        / "catalog.ts"
    )
    catalog_ids = set(re.findall(r'id: "([a-z-]+)"', catalog_path.read_text(encoding="utf-8")))

    app = create_app(repo=InMemoryRepository())
    client = TestClient(app)
    sidecar_ids = {item["id"] for item in client.get("/api/capabilities").json()["capabilities"]}

    assert sidecar_ids <= catalog_ids, (
        f"the sidecar advertises ids the catalog does not know: {sidecar_ids - catalog_ids}"
    )
