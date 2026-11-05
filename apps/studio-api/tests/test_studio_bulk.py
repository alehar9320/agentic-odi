"""ALH-197 (M2-03.2) — the landscape's bulk run over HTTP.

Both routes are adapters: whatever ``ODIService.bulk_update_outcomes`` and ``undo_bulk``
report is the body, so the browser renders a calculation it did not make. The tests here
therefore check the shape the Studio gets, not the rules of a bulk change — those are
pinned in ``packages/core/tests/test_bulk.py``.
"""

from __future__ import annotations

from typing import Any

from agentic_odi_core import InMemoryRepository
from agentic_odi_core.models import Job, Outcome, Step
from agentic_odi_core.services import ODIService
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import router as router_module
from fastapi.testclient import TestClient

STATEMENT_ONE = "Minimize the time to approve an invoice when it arrives"
STATEMENT_TWO = "Minimize the number of errors in the reconciliation when the supplier edits it"
STATEMENT_THREE = "Minimize the time to classify a chargeback when a customer disputes it"


def _store() -> InMemoryRepository:
    repo = InMemoryRepository()
    repo.add_job(Job(id="j-1", name="Reconcile invoices"))
    repo.add_outcome(Outcome(id="o-1", job_id="j-1", statement=STATEMENT_ONE))
    repo.add_outcome(Outcome(id="o-2", job_id="j-1", statement=STATEMENT_TWO))
    #: A row the narrowing below never names, so a query's answer is countable.
    repo.add_outcome(Outcome(id="o-3", job_id="j-1", statement=STATEMENT_THREE))
    repo.add_step(Step(id="s-locate", job_id="j-1", name="Locate", order=1, stage="locate"))
    repo.add_step(Step(id="s-execute", job_id="j-1", name="Execute", order=2, stage="execute"))
    return repo


def _client(repo: InMemoryRepository, backend: str = "local") -> TestClient:
    return TestClient(create_app(repo, backend=backend))


def _theme(repo: InMemoryRepository, name: str = "Billing") -> str:
    return ODIService(repo).add_theme(name).id


def _bulk(client: TestClient, **body: Any) -> dict[str, Any]:
    response = client.post("/api/outcomes/bulk", json=body)
    assert response.status_code == 200, response.json()
    return response.json()


def _stored(repo: InMemoryRepository, outcome_id: str) -> Outcome:
    """Read one outcome back, as a whole object the assertions can walk into."""
    stored = repo.get_outcome(outcome_id)
    assert stored is not None
    return stored


# --- the preview --------------------------------------------------------------


def test_a_dry_run_answers_with_the_table_and_writes_nothing() -> None:
    repo = _store()
    client = _client(repo)

    report = _bulk(client, outcome_ids=["o-1"], stage="locate", dry_run=True)

    assert report["changed"] == ["o-1"]
    assert report["requested"] == 1
    assert report["undo_token"] is None
    assert report["changes"] == [
        {"outcome_id": "o-1", "field": "step_id", "from": None, "to": "s-locate"}
    ]
    assert _stored(repo, "o-1").step_id is None
    assert repo.bulk_operations == {}


def test_a_preview_and_the_write_it_describes_name_the_same_rows() -> None:
    repo = _store()
    client = _client(repo)
    theme = _theme(repo)
    body = {"outcome_ids": ["o-1", "o-2"], "add_theme_ids": [theme], "add_tags": ["churn"]}

    preview = _bulk(client, **body, dry_run=True)
    applied = _bulk(client, **body, dry_run=False)

    assert (applied["changes"], applied["skipped"]) == (preview["changes"], preview["skipped"])
    assert applied["undo_token"] is not None
    assert _stored(repo, "o-2").tags == ["churn"]


# --- the rows that do not move ------------------------------------------------


def test_one_bad_id_is_reported_while_the_good_row_changes() -> None:
    repo = _store()
    client = _client(repo)

    report = _bulk(client, outcome_ids=["o-1", "o-gone"], stage="locate")

    assert report["changed"] == ["o-1"]
    assert report["skipped"] == [{"id": "o-gone", "reason": "outcome not found"}]


def test_a_row_whose_job_lacks_that_stage_is_skipped_rather_than_guessed() -> None:
    repo = _store()
    repo.add_job(Job(id="j-2", name="Onboard vendors"))
    repo.add_outcome(Outcome(id="o-4", job_id="j-2", statement=STATEMENT_THREE))
    client = _client(repo)

    report = _bulk(client, outcome_ids=["o-1", "o-4"], stage="locate")

    assert report["changed"] == ["o-1"]
    assert report["skipped"] == [{"id": "o-4", "reason": "job has no stage 'locate'"}]


# --- refusals that arrive as an envelope --------------------------------------


def test_an_empty_selection_is_refused_before_anything_runs() -> None:
    client = _client(_store())

    response = client.post("/api/outcomes/bulk", json={"outcome_ids": [], "stage": "locate"})

    assert response.status_code == 400
    assert "No outcomes selected" in response.json()["error"]["message"]


def test_an_unknown_stage_is_refused_with_the_service_sentence() -> None:
    client = _client(_store())

    response = client.post("/api/outcomes/bulk", json={"outcome_ids": ["o-1"], "stage": "migrate"})

    assert response.status_code == 400
    assert "Unknown stage: migrate" in response.json()["error"]["message"]


def test_a_theme_both_added_and_removed_is_refused_and_writes_nothing() -> None:
    repo = _store()
    client = _client(repo)
    theme = _theme(repo)

    response = client.post(
        "/api/outcomes/bulk",
        json={"outcome_ids": ["o-1"], "add_theme_ids": [theme], "remove_theme_ids": [theme]},
    )

    assert response.status_code == 400
    assert "both added and removed" in response.json()["error"]["message"]
    assert _stored(repo, "o-1").theme_ids == []


def test_a_change_that_names_nothing_to_change_is_refused() -> None:
    client = _client(_store())

    response = client.post("/api/outcomes/bulk", json={"outcome_ids": ["o-1"]})

    assert response.status_code == 400
    assert "Nothing to change" in response.json()["error"]["message"]


# --- the wider run ------------------------------------------------------------


def test_a_narrowing_widens_the_run_to_every_match_it_named() -> None:
    repo = _store()
    client = _client(repo)
    theme = _theme(repo)

    report = _bulk(
        client,
        outcome_ids=["o-1"],
        query={"text": "supplier"},
        add_theme_ids=[theme],
        dry_run=False,
    )

    #: ``o-1`` was named and the narrowing answered ``o-2``; ``o-3`` matches neither, so it
    #: stays out of the run rather than being swept in by the widening.
    assert report["requested"] == 2
    assert sorted(report["changed"]) == ["o-1", "o-2"]
    assert _stored(repo, "o-3").theme_ids == []


def test_a_narrowing_that_stands_for_a_theme_branch_widens_the_run_to_it() -> None:
    """The preview has to sweep the same rows the visible search counted.

    The board shows one number above the dialog and sends one ``query``; if the widening
    stopped at the theme the person clicked, a preview of two would write one.
    """
    repo = _store()
    client = _client(repo)
    service = ODIService(repo)
    parent = service.add_theme("Billing", job_id="j-1").id
    child = service.add_theme("Card networks", job_id="j-1", parent_id=parent).id
    service.assign_theme(["o-1"], parent)
    service.assign_theme(["o-2"], child)

    narrowed = _bulk(client, query={"theme_ids": [parent]}, add_tags=["review"], dry_run=True)
    branch = _bulk(
        client,
        query={"theme_ids": [parent], "include_children": True},
        add_tags=["review"],
        dry_run=True,
    )

    assert narrowed["changed"] == ["o-1"]
    assert sorted(branch["changed"]) == ["o-1", "o-2"]
    assert [narrowed["requested"], branch["requested"]] == [1, 2]
    assert [_stored(repo, "o-1").tags, _stored(repo, "o-2").tags] == [[], []]


# --- the mcp backend takes the same arguments ---------------------------------


def test_the_bulk_route_hands_the_mcp_tool_the_same_arguments(monkeypatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((mcp_url, tool, arguments))
        return (
            '{"requested": 1, "changed": ["o-1"], "skipped": [], "changes": [], "undo_token": null}'
        )

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    client = _client(_store(), backend="mcp")

    report = _bulk(
        client,
        mcp_url="http://mcp",
        outcome_ids=["o-1"],
        stage="locate",
        add_tags=["churn"],
        dry_run=True,
    )

    assert report["changed"] == ["o-1"]
    assert calls == [
        (
            "http://mcp",
            "bulk_update_outcomes",
            {
                "outcome_ids": ["o-1"],
                "stage": "locate",
                "add_tags": ["churn"],
                "dry_run": True,
            },
        )
    ]


def test_a_wider_run_over_mcp_sends_the_ids_the_search_answered(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((tool, arguments))
        if tool == "search_outcomes":
            return '{"items": [{"id": "o-1"}, {"id": "o-2"}], "total": 2, "facets": {}}'
        return '{"requested": 2, "changed": ["o-1", "o-2"], "skipped": [], "changes": [], "undo_token": "b-1"}'

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    client = _client(_store(), backend="mcp")

    report = _bulk(
        client,
        mcp_url="http://mcp",
        outcome_ids=["o-1"],
        query={"text": "invoice"},
        stage="locate",
        dry_run=False,
    )

    assert report["changed"] == ["o-1", "o-2"]
    assert [tool for tool, _ in calls] == ["search_outcomes", "bulk_update_outcomes"]
    #: Named first, then the rest of the answer — the order the preview table showed.
    assert calls[1][1]["outcome_ids"] == ["o-1", "o-2"]


# --- taking it back ------------------------------------------------------------


def _undo(client: TestClient, token: str) -> dict[str, Any]:
    response = client.post("/api/outcomes/bulk/undo", json={"token": token})
    assert response.status_code == 200, response.json()
    return response.json()


def _applied_theme_run(client: TestClient, repo: InMemoryRepository) -> str:
    theme = _theme(repo)
    report = _bulk(client, outcome_ids=["o-1", "o-2"], add_theme_ids=[theme])
    assert report["undo_token"] is not None
    assert sorted(report["changed"]) == ["o-1", "o-2"]
    return str(report["undo_token"])


def test_undo_restores_what_the_run_wrote() -> None:
    repo = _store()
    client = _client(repo)
    token = _applied_theme_run(client, repo)

    undone = _undo(client, token)

    assert sorted(undone["changed"]) == ["o-1", "o-2"]
    assert _stored(repo, "o-1").theme_ids == []
    assert _stored(repo, "o-2").theme_ids == []


def test_undoing_the_same_token_twice_is_refused() -> None:
    repo = _store()
    client = _client(repo)
    token = _applied_theme_run(client, repo)
    _undo(client, token)

    response = client.post("/api/outcomes/bulk/undo", json={"token": token})

    assert response.status_code == 400
    assert "already undone" in response.json()["error"]["message"]


def test_a_newer_run_expires_the_older_token_without_touching_either_answer() -> None:
    repo = _store()
    client = _client(repo)
    first = _applied_theme_run(client, repo)
    second = _bulk(client, outcome_ids=["o-1"], add_tags=["pricing"])["undo_token"]

    response = client.post("/api/outcomes/bulk/undo", json={"token": first})

    assert response.status_code == 400
    assert f"{second} wrote after it" in response.json()["error"]["message"]
    #: The refusal is not a partial restore: the second run's tag is still on the row.
    assert _stored(repo, "o-1").tags == ["pricing"]


def test_a_row_someone_answered_after_the_run_is_left_alone_and_named() -> None:
    repo = _store()
    client = _client(repo)
    token = _applied_theme_run(client, repo)
    ODIService(repo).update_outcome("o-2", {"tags": ["hand-edited"]})

    undone = _undo(client, token)

    assert undone["changed"] == ["o-1"]
    assert undone["skipped"] == [{"id": "o-2", "reason": "changed since the bulk update"}]
    assert _stored(repo, "o-2").tags == ["hand-edited"]


def test_an_unknown_token_is_refused_with_the_service_sentence() -> None:
    client = _client(_store())

    response = client.post("/api/outcomes/bulk/undo", json={"token": "b-does-not-exist"})

    assert response.status_code == 400
    assert "Unknown bulk token" in response.json()["error"]["message"]


def test_the_undo_route_hands_the_mcp_tool_its_token(monkeypatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((mcp_url, tool, arguments))
        return (
            '{"requested": 1, "changed": ["o-1"], "skipped": [], "changes": [], "undo_token": null}'
        )

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    client = _client(_store(), backend="mcp")

    response = client.post(
        "/api/outcomes/bulk/undo", json={"mcp_url": "http://mcp", "token": "b-1"}
    )
    assert response.status_code == 200
    report = response.json()

    assert report["changed"] == ["o-1"]
    assert calls == [("http://mcp", "undo_bulk", {"token": "b-1"})]
