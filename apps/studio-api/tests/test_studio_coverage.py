"""Router tests for coverage (A8 / ALH-21).

``GET /api/jobs/{id}/coverage`` is a read: it returns every stage in canonical
order, the explicit unassigned bucket, and the empty stages as ``gaps``. An
unknown job is a not-found error, distinct from an existing job with no
outcomes, which returns a zeroed report.
"""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_core.models import JOB_STAGE_ORDER, JobStage
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient

VALID = "Minimize the time it takes to onboard when a new hire starts"

STAGES = [
    "define",
    "locate",
    "prepare",
    "confirm",
    "execute",
    "monitor",
    "modify",
    "conclude",
]


def _client() -> tuple[TestClient, ODIService]:
    repo = InMemoryRepository()
    return TestClient(create_app(repo, backend="local")), ODIService(repo)


def test_coverage_returns_all_eight_stages_in_order() -> None:
    client, service = _client()
    job = service.add_job("Onboard")

    response = client.get(f"/api/jobs/{job.id}/coverage")

    assert response.status_code == 200, response.text
    report = response.json()["result"]
    assert [row["stage"] for row in report["per_stage"]] == STAGES
    assert report["gaps"] == STAGES


def test_coverage_define_and_locate_only_reports_six_gaps() -> None:
    client, service = _client()
    job = service.add_job("Onboard")
    steps = [
        service.add_step(job.id, stage.value, order=index, stage=stage, allow_empty_job_map=True)
        for index, stage in enumerate(JOB_STAGE_ORDER[:2], start=1)
    ]
    service.add_outcome(job.id, VALID, importance=8.0, satisfaction=4.0, step_id=steps[0].id)
    service.add_outcome(job.id, VALID, importance=7.0, satisfaction=3.0, step_id=steps[1].id)

    report = client.get(f"/api/jobs/{job.id}/coverage").json()["result"]

    assert report["gaps"] == ["prepare", "confirm", "execute", "monitor", "modify", "conclude"]
    assert report["totals"]["outcomes"] == 2


def test_coverage_empty_job_is_a_zeroed_report_not_an_error() -> None:
    client, service = _client()
    job = service.add_job("Empty")

    response = client.get(f"/api/jobs/{job.id}/coverage")

    assert response.status_code == 200
    report = response.json()["result"]
    assert report["totals"]["outcomes"] == 0
    assert report["totals"]["unassigned_outcomes"] == 0


def test_coverage_unknown_job_is_not_found() -> None:
    client, _ = _client()

    response = client.get("/api/jobs/does-not-exist/coverage")

    assert response.status_code == 404


def test_coverage_counts_only_this_jobs_evidence() -> None:
    client, service = _client()
    job = service.add_job("Onboard")
    other = service.add_job("Other")
    step = service.add_step(
        job.id, "define", order=1, stage=JobStage.DEFINE, allow_empty_job_map=True
    )
    outcome = service.add_outcome(job.id, VALID, importance=8.0, satisfaction=4.0, step_id=step.id)
    other_outcome = service.add_outcome(other.id, VALID, importance=8.0, satisfaction=4.0)
    service.add_evidence("call", "manual", "q", "text", outcome_id=outcome.id)
    service.add_evidence("call", "manual", "q2", "text", outcome_id=other_outcome.id)
    report = client.get(f"/api/jobs/{job.id}/coverage").json()["result"]

    assert report["totals"]["quotes"] == 1
    define_row = next(row for row in report["per_stage"] if row["stage"] == "define")
    assert define_row["quotes"] == 1
