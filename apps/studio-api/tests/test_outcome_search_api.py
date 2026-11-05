"""ALH-194 (M2-02.1) — the same narrowing through the sidecar as through the terminal.

`GET /api/outcomes/search` is a read: it returns the parent's
``{items, total, facets}`` envelope and writes nothing, whichever backend answers.
"""

from __future__ import annotations

import json
from typing import Any

from agentic_odi_core import InMemoryRepository, JobStage
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import router as router_module
from fastapi.testclient import TestClient


def _client(backend: str = "local") -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend=backend))


def _service(client: TestClient):
    return client.app.state.service  # type: ignore[attr-defined]


def _seed(client: TestClient) -> dict[str, str]:
    """One job, two scored outcomes on a stage, one unscored, one quote, one theme."""
    service = _service(client)
    job = service.add_job("Reconcile supplier invoices")
    step = service.add_step(
        job.id, "Execute the match", 3, JobStage.EXECUTE, allow_empty_job_map=True
    )
    timing = service.add_outcome(
        job.id,
        "Minimize the time it takes to approve an invoice when reconciling",
        importance=8,
        satisfaction=2,
        step_id=step.id,
    )
    accuracy = service.add_outcome(
        job.id,
        "Minimize the number of mismatches found after close when reconciling",
        importance=6,
        satisfaction=4,
        step_id=step.id,
    )
    unscored = service.add_outcome(
        job.id, "Maximize the number of exceptions caught before close when reconciling"
    )
    other = service.add_job("Onboard a new supplier")
    foreign = service.add_outcome(
        other.id, "Minimize the time it takes to verify a supplier when onboarding"
    )
    service.add_evidence(
        source_name="Interview",
        source_kind="transcript",
        name="Approver quote",
        content="the approval alone takes three days",
        outcome_id=timing.id,
    )
    service.add_evidence(
        source_name="Support ticket",
        source_kind="ticket",
        name="Second quote",
        content="three days again, every invoice",
        outcome_id=timing.id,
    )
    theme = service.add_theme(name="Cash timing", job_id=job.id)
    service.assign_theme([accuracy.id, unscored.id], theme.id)
    return {
        "job": job.id,
        "other": other.id,
        "timing": timing.id,
        "accuracy": accuracy.id,
        "unscored": unscored.id,
        "foreign": foreign.id,
        "theme": theme.id,
    }


def _get(client: TestClient, query: str) -> dict[str, Any]:
    response = client.get(f"/api/outcomes/search?{query}")
    assert response.status_code == 200, response.text
    return response.json()


def test_an_empty_store_answers_the_envelope_rather_than_an_error() -> None:
    result = _get(_client(), "")
    assert result["items"] == []
    assert result["total"] == 0
    assert result["facets"]["stage"] == {stage.value: 0 for stage in JobStage}
    assert result["facets"]["theme"] == {}
    assert result["facets"]["confidence"] == {"scored": 0, "unscored": 0}


def test_a_quote_only_match_returns_the_outcome_it_supports_once() -> None:
    """Two evidence rows say "three days"; the outcome appears once, not twice."""
    client = _client()
    ids = _seed(client)

    result = _get(client, "text=three+days")
    assert [item["id"] for item in result["items"]] == [ids["timing"]]
    assert result["total"] == 1


def test_the_filters_narrow_without_leaking_and_the_facets_follow_the_query() -> None:
    client = _client()
    ids = _seed(client)

    themed = _get(client, f"job_id={ids['job']}&theme_ids={ids['theme']}")
    assert {item["id"] for item in themed["items"]} == {ids["accuracy"], ids["unscored"]}
    assert themed["total"] == 2
    # Dimension-removed: the theme row keeps its own filter off, so it counts the
    # job's themed outcomes either way, while the stage row still applies it.
    assert themed["facets"]["theme"] == {ids["theme"]: 2}
    assert themed["facets"]["stage"]["execute"] == 1
    assert themed["facets"]["confidence"] == {"scored": 1, "unscored": 1}

    staged = _get(client, f"job_id={ids['job']}&stage=execute")
    assert {item["id"] for item in staged["items"]} == {ids["timing"], ids["accuracy"]}
    assert staged["facets"]["stage"]["locate"] == 0

    banded = _get(client, f"job_id={ids['job']}&min_score=8&max_score=12")
    assert [item["id"] for item in banded["items"]] == [ids["accuracy"]]
    assert banded["total"] == 1

    scored = _get(client, f"job_id={ids['job']}&confidence=unscored")
    assert [item["id"] for item in scored["items"]] == [ids["unscored"]]

    unscoped = [item["id"] for item in _get(client, "")["items"]]
    assert ids["foreign"] in unscoped
    assert len(unscoped) == 4


def test_pages_of_one_query_split_the_same_total_without_duplicates() -> None:
    client = _client()
    ids = _seed(client)

    first = _get(client, f"job_id={ids['job']}&limit=1&offset=0")
    second = _get(client, f"job_id={ids['job']}&limit=1&offset=1")
    third = _get(client, f"job_id={ids['job']}&limit=1&offset=2")
    beyond = _get(client, f"job_id={ids['job']}&limit=1&offset=9")

    assert [first["total"], second["total"], third["total"]] == [3, 3, 3]
    assert [first["items"][0]["id"], second["items"][0]["id"], third["items"][0]["id"]] == [
        ids["timing"],
        ids["accuracy"],
        ids["unscored"],
    ]
    assert beyond["items"] == []
    assert first["facets"] == second["facets"]


def test_an_impossible_filter_says_so_and_still_answers_with_the_envelope() -> None:
    client = _client()
    ids = _seed(client)

    result = _get(client, f"job_id={ids['job']}&text=elephants")
    assert result["items"] == []
    assert result["total"] == 0
    assert result["facets"]["confidence"] == {"scored": 0, "unscored": 0}


def test_searching_writes_nothing() -> None:
    client = _client()
    ids = _seed(client)
    before = _get(client, f"job_id={ids['job']}")

    _get(client, "text=invoice&stage=execute")
    _get(client, f"theme_ids={ids['theme']}&min_score=9")

    assert _get(client, f"job_id={ids['job']}") == before


def test_a_malformed_query_parameter_is_refused_with_the_established_shape() -> None:
    client = _client()
    response = client.get("/api/outcomes/search?stage=sidestep")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation"
    assert "sidestep" in error["message"]


def test_a_negative_page_is_a_refused_request_rather_than_a_crash() -> None:
    """An out-of-range number is the same failure here as everywhere else: 422."""
    client = _client()
    response = client.get("/api/outcomes/search?offset=-1")
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "out_of_range"
    assert "offset" in error["message"]


def test_mcp_backend_uses_the_contract_tool(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((tool, arguments))
        return json.dumps({"items": [{"id": "o-1"}], "total": 1, "facets": {}})

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    client = _client(backend="mcp")

    result = client.get(
        "/api/outcomes/search?mcp_url=http://mcp&job_id=j-1&text=cash"
        "&theme_ids=t-1&theme_ids=t-2&min_score=5&confidence=scored&limit=10&offset=2"
    ).json()

    assert result == {"items": [{"id": "o-1"}], "total": 1, "facets": {}}
    assert calls == [
        (
            "search_outcomes",
            {
                "job_id": "j-1",
                "text": "cash",
                "theme_ids": ["t-1", "t-2"],
                "confidence": "scored",
                "min_score": 5.0,
                "limit": 10,
                "offset": 2,
            },
        )
    ]


def test_mcp_backend_requires_mcp_url_with_the_existing_400_shape() -> None:
    client = _client(backend="mcp")
    assert client.get("/api/outcomes/search").status_code == 400


# --- a theme that stands for its branch (ALH-163) --------------------------


def _branch(client: TestClient) -> dict[str, str]:
    """The seeded store plus a child theme holding the one outcome the parent does not."""
    ids = _seed(client)
    service = _service(client)
    child = service.add_theme(
        name="Payment windows", job_id=ids["job"], parent_id=ids["theme"], ordinal=1
    )
    service.assign_theme([ids["timing"]], child.id)
    return {**ids, "child": child.id}


def test_a_theme_filter_can_answer_for_a_whole_branch() -> None:
    client = _client()
    ids = _branch(client)

    own = _get(client, f"job_id={ids['job']}&theme_ids={ids['theme']}")
    assert {item["id"] for item in own["items"]} == {ids["accuracy"], ids["unscored"]}

    subtree = _get(client, f"job_id={ids['job']}&theme_ids={ids['theme']}&include_children=true")
    assert {item["id"] for item in subtree["items"]} == {
        ids["accuracy"],
        ids["unscored"],
        ids["timing"],
    }
    assert subtree["total"] == 3
    # The facet keeps each theme's own count while the list is the branch, so the tree a person
    # clicks through is the same tree `themes rollup` counts beside.
    assert subtree["facets"]["theme"] == {ids["theme"]: 2, ids["child"]: 1}


def test_a_branch_filter_with_no_theme_named_has_nothing_to_widen() -> None:
    """The flag widens a theme filter; on its own it changes nothing and refuses nothing."""
    client = _client()
    ids = _branch(client)

    plain = _get(client, f"job_id={ids['job']}")
    widened = _get(client, f"job_id={ids['job']}&include_children=true")

    assert widened == plain


def test_a_branch_filter_refuses_an_unknown_theme_as_a_bad_request() -> None:
    """The refusal is the same 400 the plain theme filter gives — never a widened empty page."""
    client = _client()
    _branch(client)

    response = client.get("/api/outcomes/search?theme_ids=t-ghost&include_children=true")

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation"
    assert error["message"] == "Unknown theme: t-ghost"


def test_mcp_backend_forwards_the_branch_flag_and_nothing_else(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((tool, arguments))
        return json.dumps({"items": [], "total": 0, "facets": {}})

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    client = _client(backend="mcp")

    client.get("/api/outcomes/search?mcp_url=http://mcp&theme_ids=t-1")
    client.get("/api/outcomes/search?mcp_url=http://mcp&theme_ids=t-1&include_children=true")

    assert [arguments for _tool, arguments in calls] == [
        {"theme_ids": ["t-1"]},
        {"theme_ids": ["t-1"], "include_children": True},
    ]
