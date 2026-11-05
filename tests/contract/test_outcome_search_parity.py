"""ALH-194 (M2-02.1) — one query, identical answers from the terminal and the sidecar.

The CLI and ``GET /api/outcomes/search`` are two spellings of the same
``search_outcomes`` contract, so a query that is right in one is right in the
other: same ids, same order, same pre-pagination total, same facet counts.

ALH-163 (M2-01.2) joins the theme rollup to that pair. A branch counted by
``get_theme_rollup`` has to be the branch the search returns for the same theme
with ``include_children``, or the board's chip and the terminal's tree are two
answers to one question.
"""

from __future__ import annotations

from typing import Any

import pytest
from agentic_odi_cli.backend import LocalBackend
from agentic_odi_core import JobStage, ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def _pair(db_path: str) -> tuple[LocalBackend, TestClient]:
    return (
        LocalBackend(db_path=db_path),
        TestClient(create_app(SQLiteRepository(db_path=db_path), backend="local")),
    )


def _seed(service: ODIService) -> dict[str, str]:
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
    exceptions = service.add_outcome(
        job.id, "Maximize the number of exceptions caught before close when reconciling"
    )
    other = service.add_job("Onboard a new supplier")
    service.add_outcome(other.id, "Minimize the time it takes to verify a supplier when onboarding")
    service.add_evidence(
        source_name="Interview",
        source_kind="transcript",
        name="Approver quote",
        content="the approval alone takes three days",
        outcome_id=timing.id,
    )
    theme = service.add_theme(name="Cash timing", job_id=job.id)
    service.assign_theme([accuracy.id, exceptions.id], theme.id)
    #: ALH-163: a child holds the one outcome the parent does not, so a branch is a wider answer
    #: than a theme, and both doors have to say so.
    child = service.add_theme(name="Payment windows", job_id=job.id, parent_id=theme.id, ordinal=1)
    service.assign_theme([timing.id], child.id)
    return {
        "job": job.id,
        "other": other.id,
        "timing": timing.id,
        "accuracy": accuracy.id,
        "exceptions": exceptions.id,
        "theme": theme.id,
        "child": child.id,
    }


QUERIES: list[dict[str, Any]] = [
    {},
    {"text": "three days"},
    {"text": "INVOICE"},
    {"stage": "execute"},
    {"confidence": "unscored"},
    {"min_score": 8, "max_score": 12},
    {"limit": 2},
    {"limit": 2, "offset": 2},
    {"text": "elephants"},
    {"stage": "locate", "confidence": "scored"},
]


@pytest.mark.parametrize("query", QUERIES, ids=lambda query: str(query) or "blank")
def test_every_query_answers_the_same_on_both_surfaces(tmp_path, query: dict[str, Any]) -> None:
    db_path = str(tmp_path / "odi.db")
    _, client = _pair(db_path)
    ids = _seed(client.app.state.service)
    backend, client = _pair(db_path)  # fresh readers over the file that was just written

    variants = [
        {**query, "job_id": ids["job"]},
        {**query, "job_id": ids["other"]},
        {**query, "job_id": ids["job"], "theme_ids": [ids["theme"]]},
        {**query, "job_id": ids["job"], "theme_ids": [ids["theme"]], "include_children": True},
    ]
    for variant in variants:
        assert backend.call("search_outcomes", variant) == _api_search(client, variant), variant


def test_a_branch_widens_the_same_way_on_both_doors(tmp_path) -> None:
    """Agreement alone would not catch a flag both doors ignored — so name the widening."""
    db_path = str(tmp_path / "odi.db")
    _, client = _pair(db_path)
    ids = _seed(client.app.state.service)
    backend, client = _pair(db_path)
    query = {"job_id": ids["job"], "theme_ids": [ids["theme"]]}

    narrow = backend.call("search_outcomes", query)
    branch = backend.call("search_outcomes", {**query, "include_children": True})

    assert narrow["total"] == 2
    assert branch["total"] == 3
    assert sorted(item["id"] for item in branch["items"]) == sorted(
        [ids["accuracy"], ids["exceptions"], ids["timing"]]
    )
    assert _api_search(client, {**query, "include_children": True}) == branch


def test_an_unshared_store_answers_the_same_on_both_surfaces(tmp_path) -> None:
    backend, client = _pair(str(tmp_path / "empty.db"))

    assert backend.call("search_outcomes", {}) == _api_search(client, {})


def test_the_branch_a_theme_counts_is_the_branch_both_doors_return(tmp_path) -> None:
    """ALH-163: the rollup and a branch-wide search are the same question asked twice.

    The drift this pins is a chip that reads *Billing 3* above two results, or a card that
    promises a top score the ranked list puts somewhere else. One store answers both, so a
    number that disagrees between them is a bug in a surface, not a difference of opinion.
    """
    db_path = str(tmp_path / "odi.db")
    _, client = _pair(db_path)
    ids = _seed(client.app.state.service)
    backend, client = _pair(db_path)

    for key in ("theme", "child"):
        theme_id = ids[key]
        rollup = backend.call("get_theme_rollup", {"theme_id": theme_id})
        branch = {"job_id": ids["job"], "theme_ids": [theme_id], "include_children": True}
        measured = backend.call("search_outcomes", {**branch, "confidence": "scored"})

        assert rollup["outcomes"] == _api_search(client, branch)["total"], theme_id
        assert rollup["outcomes"] == backend.call("search_outcomes", branch)["total"], theme_id
        assert rollup["measured"] == measured["total"], theme_id
        assert rollup["top_opportunity"] == measured["items"][0]["opportunity_score"], theme_id
        assert rollup["top_statement"] == measured["items"][0]["statement"], theme_id


def test_one_read_of_the_tree_is_the_same_rows_as_reading_them_one_by_one(tmp_path) -> None:
    """A whole-tree read is the cheap door onto the same numbers, not a second calculation.

    The terminal's `odi themes rollup` takes the list and the card is filled from either tool;
    if the two ever disagreed, the numbers a person sees would depend on which one the model
    happened to call.
    """
    db_path = str(tmp_path / "odi.db")
    _, client = _pair(db_path)
    ids = _seed(client.app.state.service)
    backend, _ = _pair(db_path)

    rows = backend.call("list_theme_rollups", {"job_id": ids["job"]})

    assert rows == [backend.call("get_theme_rollup", {"theme_id": row["theme_id"]}) for row in rows]


def _api_search(client: TestClient, query: dict[str, Any]) -> dict[str, Any]:
    response = client.get("/api/outcomes/search", params=query)
    assert response.status_code == 200, response.text
    return response.json()
