"""Stages 5 and 6 through the sidecar: the same records under both backends.

The routes never invent a segment or a bet. `GET /api/segments` is empty until
``segment_market`` has clustered the scored outcomes, and
``POST /api/strategy/propose`` answers 422 with what is missing when no path has
evidence — the refusal is the feature.
"""

from __future__ import annotations

import json

from agentic_odi_core import InMemoryRepository, invalid_strategy_request
from agentic_odi_core.remote import StudioError, StudioErrorCode
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import router as router_module
from agentic_odi_studio_api.studio.errors import StudioHTTPError
from fastapi.testclient import TestClient


def _client(backend: str = "local") -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend=backend))


def _service(client: TestClient):
    return client.app.state.service  # type: ignore[attr-defined]


def _seed_underserved_job(client: TestClient) -> str:
    service = _service(client)
    job = service.add_job("Rotate a leaked secret")
    step = service.add_step(job.id, "Gather the current values", order=1, allow_empty_job_map=True)
    service.add_outcome(
        job.id,
        statement="Minimize the time it takes to rotate the secret when it leaks",
        importance=9,
        satisfaction=2,
        step_id=step.id,
    )
    service.add_outcome(
        job.id,
        statement="Minimize the number of missed values after rotation",
        importance=8,
        satisfaction=3,
        step_id=step.id,
    )
    return job.id


def _seed_served_outcome(client: TestClient) -> None:
    """A second step the market already gets: what a bet differentiates from."""
    service = _service(client)
    jobs = service.get_jobs()
    verify = service.add_step(jobs[0].id, "Verify the new value", order=2, allow_empty_job_map=True)
    service.add_outcome(
        jobs[0].id,
        statement="Minimize the time it takes to verify the new value when deploying",
        importance=5,
        satisfaction=5,
        step_id=verify.id,
    )


def test_local_segments_are_empty_until_the_outcomes_are_clustered() -> None:
    client = _client()
    assert client.get("/api/segments").json() == []

    job_id = _seed_underserved_job(client)
    _service(client).segment_market()

    segments = client.get("/api/segments").json()
    assert len(segments) == 1
    segment = segments[0]
    assert segment["job_id"] == job_id
    assert segment["verdict"] == "underserved"
    assert segment["confidence"] > 0
    assert len(segment["outcome_ids"]) == 2
    assert segment["rationale"]


def test_local_segments_filter_by_job() -> None:
    client = _client()
    job_id = _seed_underserved_job(client)
    _service(client).segment_market()

    assert len(client.get(f"/api/segments?job_id={job_id}").json()) == 1
    assert client.get("/api/segments?job_id=nope").json() == []


def test_local_strategy_is_null_before_stage_six_runs() -> None:
    client = _client()
    assert client.get("/api/strategy").json() is None


def test_local_propose_records_one_path_and_the_paths_it_beat() -> None:
    client = _client()
    _seed_underserved_job(client)
    _seed_served_outcome(client)
    _service(client).segment_market()

    proposed = client.post("/api/strategy/propose", json={})
    assert proposed.status_code == 200
    strategy = proposed.json()
    assert strategy["kind"] in {"differentiated", "disruptive", "new_market"}
    assert {entry["kind"] for entry in strategy["rejected"]} == {
        "differentiated",
        "disruptive",
        "new_market",
    } - {strategy["kind"]}
    assert all(entry["why"] for entry in strategy["rejected"])

    recorded = client.get("/api/strategy").json()
    assert recorded["id"] == strategy["id"]

    again = client.post("/api/strategy/propose", json={}).json()
    assert again["id"] == strategy["id"]


def test_local_propose_refuses_and_says_what_is_missing() -> None:
    client = _client()
    _seed_underserved_job(client)

    response = client.post("/api/strategy/propose", json={})
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation"
    assert body["message"].startswith("Invalid strategy request:")


def test_mcp_backend_uses_the_contract_tools(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((tool, arguments))
        if tool == "get_segments":
            return json.dumps([{"id": "seg-1", "verdict": "underserved"}])
        if tool == "get_strategy":
            return "null"
        return json.dumps({"id": "st-1", "kind": "differentiated", "rejected": []})

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    client = _client(backend="mcp")

    assert client.get("/api/segments?job_id=j-1&mcp_url=http://mcp").json() == [
        {"id": "seg-1", "verdict": "underserved"}
    ]
    assert client.get("/api/strategy?mcp_url=http://mcp").json() is None
    proposed = client.post("/api/strategy/propose", json={"mcp_url": "http://mcp"})
    assert proposed.status_code == 200
    assert proposed.json()["kind"] == "differentiated"

    assert calls == [
        ("get_segments", {"job_id": "j-1"}),
        ("get_strategy", {}),
        ("propose_strategy", {}),
    ]


def test_mcp_backend_refusal_is_the_same_422_as_the_local_backend(monkeypatch) -> None:
    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.VALIDATION,
                message=invalid_strategy_request("No path is supported yet: score outcomes."),
            )
        )

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    client = _client(backend="mcp")

    response = client.post("/api/strategy/propose", json={"mcp_url": "http://mcp"})
    assert response.status_code == 422
    assert response.json()["error"]["message"].startswith("Invalid strategy request:")


def test_mcp_backend_requires_mcp_url_with_the_existing_400_shape() -> None:
    client = _client(backend="mcp")
    assert client.get("/api/segments").status_code == 400
    assert client.post("/api/strategy/propose", json={}).status_code == 400
