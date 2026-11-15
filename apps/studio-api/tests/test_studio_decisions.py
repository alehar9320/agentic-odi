"""C6.2 (ALH-158): recording a decision from the API and the CLI.

Readiness choices pinned here:

* The route is transport only; ``ODIService.record_decision`` owns validation
  and supersession, so the two surfaces cannot disagree.
* A rejection is ``{outcome_id, reason}``; ``--reject OUTCOME_ID=REASON`` is the
  CLI spelling and the API takes the two fields separately.
* ``decided_at`` defaults to the request time in UTC when the caller omits it,
  and is echoed unchanged when supplied.
* Superseding names the predecessor in the response and keeps it readable.
* Errors are the shared typed body: no traceback, and a missing job is not a
  success.
"""

from __future__ import annotations

import json

from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def _client() -> tuple[TestClient, InMemoryRepository]:
    repo = InMemoryRepository()
    return TestClient(create_app(repo, backend="local")), repo


def _seed(repo: InMemoryRepository) -> tuple[str, list[str]]:
    service = ODIService(repo)
    job = service.add_job("Publish a plugin")
    ids = [
        service.add_outcome(
            job.id,
            "Minimize the time it takes to publish a plugin when a release is ready",
            8.0,
            3.0,
        ).id,
        service.add_outcome(
            job.id, "Minimize the cost of supporting a plugin when it ships", 5.0, 7.0
        ).id,
    ]
    return job.id, ids


def _body(job_id: str, chosen: list[str], rejected: list[str] | None = None, **overrides) -> dict:
    payload: dict = {
        "job_id": job_id,
        "chosen_outcome_ids": chosen,
        "rationale": "The publishing path blocks every release.",
        "decided_by": "dana",
        "rejected": [
            {"outcome_id": outcome_id, "reason": "Already served by the support team."}
            for outcome_id in (rejected or [])
        ],
    }
    payload.update(overrides)
    return payload


def test_record_decision_persists_and_lists() -> None:
    client, repo = _client()
    job_id, ids = _seed(repo)

    created = client.post("/api/decisions", json=_body(job_id, [ids[0]], rejected=[ids[1]]))

    assert created.status_code == 200, created.text
    decision = created.json()
    assert decision["job_id"] == job_id
    assert decision["chosen_outcome_ids"] == [ids[0]]
    assert decision["rejected"] == [
        {"outcome_id": ids[1], "reason": "Already served by the support team."}
    ]
    assert decision["decided_by"] == "dana"
    assert decision["decided_at"]

    history = client.get("/api/decisions", params={"job_id": job_id})
    assert [item["id"] for item in history.json()] == [decision["id"]]


def test_record_decision_echoes_a_supplied_timestamp() -> None:
    client, repo = _client()
    job_id, ids = _seed(repo)

    response = client.post(
        "/api/decisions", json=_body(job_id, [ids[0]], decided_at="2026-10-29T00:00:00Z")
    )

    assert response.json()["decided_at"] == "2026-10-29T00:00:00Z"


def test_record_decision_supersedes_and_names_the_predecessor() -> None:
    client, repo = _client()
    job_id, ids = _seed(repo)
    first = client.post("/api/decisions", json=_body(job_id, [ids[0]], rejected=[ids[1]])).json()

    second = client.post(
        "/api/decisions",
        json=_body(job_id, [ids[1]], rejected=[ids[0]], supersedes=first["id"]),
    )

    assert second.status_code == 200, second.text
    assert second.json()["superseded_by"] is None

    history = client.get("/api/decisions", params={"job_id": job_id}).json()
    assert [item["id"] for item in history] == [first["id"], second.json()["id"]]
    predecessor = history[0]
    assert predecessor["superseded_by"] == second.json()["id"]
    assert predecessor["superseded_at"] == second.json()["decided_at"]


def test_record_decision_refuses_an_empty_rationale() -> None:
    client, repo = _client()
    job_id, ids = _seed(repo)

    response = client.post("/api/decisions", json=_body(job_id, [ids[0]], rationale=""))

    assert response.status_code == 422
    assert "rationale" in response.text


def test_record_decision_unknown_job_is_not_a_success() -> None:
    client, repo = _client()
    _, ids = _seed(repo)

    response = client.post("/api/decisions", json=_body("JOB-NOPE", [ids[0]]))

    assert response.status_code == 404
    body = response.json()
    assert "Traceback" not in response.text
    assert body.get("error", body).get("code")


def test_record_decision_unknown_outcome_is_not_a_success() -> None:
    client, repo = _client()
    job_id, _ = _seed(repo)

    response = client.post("/api/decisions", json=_body(job_id, ["OUT-NOPE"]))

    assert response.status_code == 404
    assert "Traceback" not in response.text


def test_record_decision_unknown_predecessor_is_not_a_success() -> None:
    client, repo = _client()
    job_id, ids = _seed(repo)

    response = client.post("/api/decisions", json=_body(job_id, [ids[0]], supersedes="DEC-NOPE"))

    assert response.status_code == 404
    assert "Traceback" not in response.text


def test_cli_and_api_record_equal_fields(tmp_path) -> None:
    """The same decision through both surfaces persists the same fields."""
    from agentic_odi_cli.cli import app
    from typer.testing import CliRunner

    client, repo = _client()
    job_id, ids = _seed(repo)

    api_decision = client.post(
        "/api/decisions",
        json=_body(job_id, [ids[0]], rejected=[ids[1]], decided_at="2026-10-29T00:00:00Z"),
    ).json()

    runner = CliRunner()
    db = str(tmp_path / "cli.db")
    job = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Publish a plugin", "--json"])
    cli_job_id = json.loads(job.output)["id"]
    cli_ids = []
    for statement, importance, satisfaction in (
        ("Minimize the time it takes to publish a plugin when a release is ready", 8, 3),
        ("Minimize the cost of supporting a plugin when it ships", 5, 7),
    ):
        outcome = runner.invoke(
            app,
            [
                "--db",
                db,
                "desired-outcomes",
                "add",
                "--job-id",
                cli_job_id,
                "--statement",
                statement,
                "--importance",
                str(importance),
                "--satisfaction",
                str(satisfaction),
                "--json",
            ],
        )
        cli_ids.append(json.loads(outcome.output)["id"])

    cli_result = runner.invoke(
        app,
        [
            "--db",
            db,
            "decide",
            "record",
            "--job-id",
            cli_job_id,
            "--choose",
            cli_ids[0],
            "--rationale",
            "The publishing path blocks every release.",
            "--decided-by",
            "dana",
            "--reject",
            f"{cli_ids[1]}=Already served by the support team.",
            "--decided-at",
            "2026-10-29T00:00:00Z",
            "--json",
        ],
    )

    assert cli_result.exit_code == 0, cli_result.output
    cli_decision = json.loads(cli_result.output)
    for field in ("rationale", "decided_by", "decided_at", "confidence"):
        assert cli_decision[field] == api_decision[field], field
    assert [r["reason"] for r in cli_decision["rejected"]] == [
        r["reason"] for r in api_decision["rejected"]
    ]
