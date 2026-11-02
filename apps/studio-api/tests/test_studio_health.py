"""The one health answer: sidecar, store, MCP, and model.

Promise 6 of Pillar 0: a person can read one line that says, accurately, which
of the model, the store, and the MCP server are working. These tests pin the
report, its status rule, and that it never 500s even when everything is down.
"""

from __future__ import annotations

import socket

import pytest
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def _client(repo=None) -> TestClient:
    return TestClient(create_app(repo or InMemoryRepository()))


def _closed_port() -> int:
    """A port nothing is listening on, so a probe reports it unreachable."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_health_returns_the_four_checks_and_a_request_id() -> None:
    response = _client().get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert set(body["checks"]) == {"sidecar", "store", "mcp", "llm"}
    for check in body["checks"].values():
        assert set(check) == {"ok", "detail", "latency_ms"}
        assert isinstance(check["ok"], bool)
        assert isinstance(check["detail"], str) and check["detail"]
    assert body["request_id"]


def test_health_is_ok_when_the_store_and_sidecar_are_healthy() -> None:
    """With no MCP server and no model, the report still answers — degraded."""
    response = _client().get(
        "/api/health",
        params={
            "mcp_url": f"http://127.0.0.1:{_closed_port()}/mcp",
            "base_url": "http://127.0.0.1:1/v1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["checks"]["sidecar"]["ok"] is True
    assert body["checks"]["store"]["ok"] is True
    assert body["checks"]["mcp"]["ok"] is False
    assert body["status"] == "degraded"


def test_health_names_the_closed_mcp_url_in_the_detail() -> None:
    port = _closed_port()
    url = f"http://127.0.0.1:{port}/mcp"

    body = _client().get("/api/health", params={"mcp_url": url}).json()

    assert body["checks"]["mcp"]["ok"] is False
    assert url in body["checks"]["mcp"]["detail"]


def test_health_is_down_when_the_store_is_not_healthy() -> None:
    class BrokenStore(InMemoryRepository):
        def health(self) -> bool:  # noqa: D102 - deliberately unhealthy
            return False

    response = _client(BrokenStore()).get("/api/health")

    # A health endpoint that 500s is not a health endpoint.
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "down"
    assert body["checks"]["store"]["ok"] is False


def test_app_health_serves_the_same_report_as_the_api_route() -> None:
    """One truth about one machine: /health and /api/health cannot disagree."""
    client = _client()

    app_health = client.get("/health").json()
    api_health = client.get("/api/health").json()

    assert app_health["status"] == api_health["status"]
    assert set(app_health["checks"]) == set(api_health["checks"])


def test_health_echoes_the_request_id_header() -> None:
    response = _client().get("/health", headers={"X-Request-ID": "first-light"})

    assert response.status_code == 200
    assert response.json()["request_id"] == "first-light"


def test_health_never_writes_to_the_store() -> None:
    repo = InMemoryRepository()
    client = _client(repo)
    before = repo.list_jobs()

    client.get("/api/health")
    client.get("/health")

    assert repo.list_jobs() == before


def test_health_answers_within_its_budget_when_everything_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even with every probe failing, the report arrives well inside 3 seconds."""
    import time

    monkeypatch.setenv("AGENTIC_ODI_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("AGENTIC_ODI_MCP_URL", "http://127.0.0.1:1/mcp")

    started = time.perf_counter()
    response = _client().get("/api/health")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert elapsed < 3.0
