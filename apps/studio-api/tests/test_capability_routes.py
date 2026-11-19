"""The MCP health route and the capability probe must agree on one method.

`registry.ts` used to probe `/api/health/mcp` with a GET, but the route only
accepts POST, so a healthy sidecar answered 405 and the capability list told the
person MCP was missing (#515). This test pins the route's method so the two
sides cannot drift apart again.
"""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(create_app(repo=InMemoryRepository()))


def test_mcp_health_route_is_post_only() -> None:
    client = _client()

    assert client.get("/api/health/mcp").status_code == 405

    response = client.post("/api/health/mcp", json={"mcp_url": "http://127.0.0.1:1/mcp"})

    assert response.status_code == 200
    assert set(response.json()) == {"reachable"}
    assert response.json()["reachable"] is False


def test_capabilities_manifest_still_names_the_mcp_capability() -> None:
    body = _client().get("/api/capabilities").json()

    ids = {item["id"] for item in body["capabilities"]}

    assert "sidecar-mcp" in ids
