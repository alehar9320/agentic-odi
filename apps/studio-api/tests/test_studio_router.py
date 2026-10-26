"""Tests for successful passthrough responses from the Studio router."""

from __future__ import annotations

import json

from agentic_odi_core import InMemoryRepository
from agentic_odi_core.remote import StudioError, StudioErrorCode
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import router as router_module
from agentic_odi_studio_api.studio.errors import StudioHTTPError
from fastapi.testclient import TestClient


def _client(backend: str = "mcp") -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend=backend))


def test_post_step_returns_the_normalized_result(monkeypatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((mcp_url, tool, arguments))
        return 'Step created successfully: {"id": "step-1", "name": "Execute"}'

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)

    response = _client().post(
        "/api/steps",
        json={"mcp_url": "http://mcp", "job_id": "job-1", "name": "Execute", "order": 5},
    )

    assert response.status_code == 200
    assert response.json() == {"id": "step-1", "name": "Execute"}
    assert calls == [("http://mcp", "add_step", {"job_id": "job-1", "name": "Execute", "order": 5})]


def test_post_outcome_returns_the_normalized_result(monkeypatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((mcp_url, tool, arguments))
        return 'Outcome created successfully: {"id": "O-1"}'

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)

    response = _client().post(
        "/api/outcomes",
        json={
            "mcp_url": "http://mcp",
            "job_id": "job-1",
            "statement": "Minimize the time to ship a release when the build is green",
            "importance": 8.5,
            "satisfaction": 3.5,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"id": "O-1"}
    assert calls == [
        (
            "http://mcp",
            "add_outcome",
            {
                "job_id": "job-1",
                "statement": "Minimize the time to ship a release when the build is green",
                "importance": 8.5,
                "satisfaction": 3.5,
            },
        )
    ]


def test_post_step_without_an_mcp_url_is_a_validation_error() -> None:
    response = _client().post(
        "/api/steps",
        json={"mcp_url": "", "job_id": "job-1", "name": "Execute", "order": 5},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation"


def test_post_outcome_without_an_mcp_url_is_a_validation_error() -> None:
    response = _client().post(
        "/api/outcomes",
        json={
            "mcp_url": "",
            "job_id": "job-1",
            "statement": "Minimize the time to ship a release when the build is green",
            "importance": 8.5,
            "satisfaction": 3.5,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation"


def test_local_post_outcome_returns_the_outcome_object() -> None:
    client = _client("local")
    job = client.post("/api/jobs", json={"name": "Ship a service"}).json()

    response = client.post(
        "/api/outcomes",
        json={
            "mcp_url": "",
            "job_id": job["id"],
            "statement": "Minimize the time to ship a release when the build is green",
            "importance": 8.0,
            "satisfaction": 4.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"]
    assert body["statement"] == "Minimize the time to ship a release when the build is green"
    assert body["opportunity_score"] == 12.0


def test_local_delete_returns_the_deleted_id() -> None:
    client = _client("local")
    job = client.post("/api/jobs", json={"name": "Ship a service"}).json()

    response = client.delete(f"/api/jobs/{job['id']}")

    assert response.status_code == 200
    assert response.json() == {"deleted": job["id"]}


def test_mcp_delete_returns_the_deleted_id(monkeypatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((mcp_url, tool, arguments))
        return "Job deleted successfully: job-1"

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)

    response = _client().delete("/api/jobs/job-1?mcp_url=http://mcp")

    assert response.status_code == 200
    assert response.json() == {"deleted": "job-1"}
    assert calls == [("http://mcp", "delete_job", {"job_id": "job-1"})]


def test_mcp_job_create_returns_the_normalized_object(monkeypatch) -> None:
    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        return 'Job created successfully: {"id": "JOB-9", "name": "Ship a service"}'

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)

    response = _client().post("/api/jobs", json={"name": "Ship a service", "mcp_url": "http://mcp"})

    assert response.status_code == 200
    assert response.json() == {"id": "JOB-9", "name": "Ship a service"}


def test_local_job_create_returns_the_job_object() -> None:
    response = _client("local").post("/api/jobs", json={"name": "Ship a service"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Ship a service"
    assert body["id"]
    assert "ok" not in body


def test_local_step_create_returns_the_step_object() -> None:
    client = _client("local")
    job = client.post("/api/jobs", json={"name": "Ship a service"}).json()

    response = client.post(
        "/api/steps",
        json={"mcp_url": "", "job_id": job["id"], "name": "Prepare", "order": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Prepare"
    assert body["id"]
    assert isinstance(body, dict)
    assert not isinstance(body, str)


def test_mcp_failure_is_reported_as_an_error_not_a_success(monkeypatch) -> None:
    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        raise StudioHTTPError(
            StudioError(code=StudioErrorCode.NOT_FOUND, message="Job with ID X not found.")
        )

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)

    response = _client().post(
        "/api/steps",
        json={"mcp_url": "http://mcp", "job_id": "X", "name": "Execute", "order": 5},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_json_payload_text_is_parsed_into_an_object() -> None:
    from agentic_odi_studio_api.studio.router import _payload_from_text

    assert _payload_from_text('Outcome created successfully: {"id": "O-1"}') == {"id": "O-1"}
    assert _payload_from_text("Deleted job: job-1") == {"result": "Deleted job: job-1"}
    assert json.loads('{"id": "O-1"}') == {"id": "O-1"}


def test_local_create_routes_map_domain_errors() -> None:
    client = _client("local")
    job = client.post("/api/jobs", json={"name": "Ship a service"}).json()

    out_of_range = client.post(
        "/api/outcomes",
        json={
            "mcp_url": "",
            "job_id": job["id"],
            "statement": "Minimize the time to ship a release when the build is green",
            "importance": 42,
            "satisfaction": 3,
        },
    )
    assert out_of_range.status_code == 422
    assert out_of_range.json()["error"]["code"] == "out_of_range"

    missing_job = client.post(
        "/api/steps",
        json={"mcp_url": "", "job_id": "JOB-NOPE", "name": "Ship it", "order": 1},
    )
    assert missing_job.status_code == 404
    assert missing_job.json()["error"]["code"] == "not_found"

    missing_job_outcome = client.post(
        "/api/outcomes",
        json={
            "mcp_url": "",
            "job_id": "JOB-NOPE",
            "statement": "Minimize the time to ship a release when the build is green",
            "importance": 8,
            "satisfaction": 3,
        },
    )
    assert missing_job_outcome.status_code == 404
    assert missing_job_outcome.json()["error"]["code"] == "not_found"
