"""Coverage: what the research does not cover (A8 / ALH-21).

A job with outcomes in only Define and Locate must report six named gaps. Every
stage appears in canonical order, an outcome with no stage is counted in an
explicit ``unassigned`` bucket, and ``quotes`` counts evidence rows linked to a
stage's outcomes — never a global quote count, and never the same row twice.
The report is a read: running it writes nothing.
"""

from __future__ import annotations

import pytest
from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_core.models import JOB_STAGE_ORDER, JobStage
from agentic_odi_core.sqlite_repository import SQLiteRepository

VALID = "Minimize the time it takes to onboard a customer when they sign up"


@pytest.fixture
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _stage_step(service: ODIService, job_id: str, stage: JobStage):
    # A coverage fixture stages the map deliberately, then measures what lands
    # on it; ``allow_empty_job_map`` is the audited path for that.
    return service.add_step(
        job_id,
        stage.value,
        order=JOB_STAGE_ORDER.index(stage) + 1,
        stage=stage,
        allow_empty_job_map=True,
    )


def _measured_outcome(service: ODIService, job_id: str, step_id: str | None) -> str:
    outcome = service.add_outcome(job_id, VALID, importance=8.0, satisfaction=4.0, step_id=step_id)
    return outcome.id


def test_all_eight_stages_in_canonical_order(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    report = service.coverage_report(job.id)

    assert [row.stage for row in report.per_stage] == JOB_STAGE_ORDER


def test_define_and_locate_only_reports_six_named_gaps(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    define = _stage_step(service, job.id, JobStage.DEFINE)
    locate = _stage_step(service, job.id, JobStage.LOCATE)
    _measured_outcome(service, job.id, define.id)
    _measured_outcome(service, job.id, locate.id)

    report = service.coverage_report(job.id)

    assert [row.stage for row in report.per_stage if row.outcomes == 0] == [
        JobStage.PREPARE,
        JobStage.CONFIRM,
        JobStage.EXECUTE,
        JobStage.MONITOR,
        JobStage.MODIFY,
        JobStage.CONCLUDE,
    ]
    assert report.gaps == [row.stage for row in report.per_stage if row.outcomes == 0]


def test_empty_job_returns_a_zeroed_report(service: ODIService) -> None:
    job = service.add_job("Onboard customers")

    report = service.coverage_report(job.id)

    assert report.totals.outcomes == 0
    assert report.totals.measured == 0
    assert report.totals.quotes == 0
    assert report.totals.unassigned_outcomes == 0
    assert all(row.outcomes == 0 for row in report.per_stage)
    assert report.gaps == JOB_STAGE_ORDER


def test_unknown_job_is_a_not_found_error(service: ODIService) -> None:
    from agentic_odi_core import JobNotFoundError

    with pytest.raises(JobNotFoundError):
        service.coverage_report("does-not-exist")


def test_measured_requires_both_scores(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    define = _stage_step(service, job.id, JobStage.DEFINE)
    _measured_outcome(service, job.id, define.id)
    # A step-less outcome with only one score set is not measured.
    unmeasured = service.add_outcome(job.id, VALID, importance=7.0, satisfaction=3.0)
    service.update_outcome(unmeasured.id, {"satisfaction": None})

    report = service.coverage_report(job.id)
    define_row = next(row for row in report.per_stage if row.stage is JobStage.DEFINE)

    assert define_row.outcomes == 1
    assert define_row.measured == 1
    assert report.totals.outcomes == 2
    assert report.totals.measured == 1


def test_unassigned_is_explicit_and_never_hidden(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    _measured_outcome(service, job.id, None)

    report = service.coverage_report(job.id)

    assert report.totals.outcomes == 1
    assert report.totals.unassigned_outcomes == 1
    assert report.totals.unassigned_measured == 1
    assert all(row.outcomes == 0 for row in report.per_stage)


def test_quotes_count_evidence_rows_not_global_quotes(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    other = service.add_job("A second job")
    define = _stage_step(service, job.id, JobStage.DEFINE)
    outcome_id = _measured_outcome(service, job.id, define.id)
    other_outcome = _measured_outcome(service, other.id, None)
    service.add_evidence("call", "manual", "q", "text", outcome_id=outcome_id)
    service.add_evidence("call", "manual", "q2", "text", outcome_id=outcome_id)
    service.add_evidence("call", "manual", "q3", "text", outcome_id=other_outcome)

    report = service.coverage_report(job.id)
    define_row = next(row for row in report.per_stage if row.stage is JobStage.DEFINE)

    assert define_row.quotes == 2
    assert report.totals.quotes == 2


def test_each_evidence_row_counts_once_even_from_the_same_quote(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    define = _stage_step(service, job.id, JobStage.DEFINE)
    first = _measured_outcome(service, job.id, define.id)
    second = _measured_outcome(service, job.id, define.id)
    # Two rows standing behind the same customer quote. The count is rows, not
    # distinct quotes, so this is two — and each row counts once.
    service.add_evidence("call", "manual", "q", "text", outcome_id=first, raw={"quote_id": "Q1"})
    service.add_evidence("call", "manual", "q", "text", outcome_id=second, raw={"quote_id": "Q1"})

    report = service.coverage_report(job.id)
    define_row = next(row for row in report.per_stage if row.stage is JobStage.DEFINE)

    assert define_row.quotes == 2


def test_report_writes_no_events(tmp_path) -> None:
    repo = SQLiteRepository(db_path=str(tmp_path / "odi.db"))
    service = ODIService(repo)
    job = service.add_job("Onboard customers")
    define = _stage_step(service, job.id, JobStage.DEFINE)
    _measured_outcome(service, job.id, define.id)
    before = len(repo.store.get_stream())

    service.coverage_report(job.id)
    service.coverage_report(job.id)

    assert len(repo.store.get_stream()) == before


def test_no_cross_job_leakage(service: ODIService) -> None:
    first = service.add_job("First")
    second = service.add_job("Second")
    define = _stage_step(service, first.id, JobStage.DEFINE)
    _measured_outcome(service, first.id, define.id)

    report = service.coverage_report(second.id)

    assert report.totals.outcomes == 0
    assert report.gaps == JOB_STAGE_ORDER


def test_sqlite_report_matches_in_memory(service: ODIService, tmp_path) -> None:
    job = service.add_job("Onboard customers")
    define = _stage_step(service, job.id, JobStage.DEFINE)
    _measured_outcome(service, job.id, define.id)
    in_memory = service.coverage_report(job.id)

    sqlite_service = ODIService(SQLiteRepository(db_path=str(tmp_path / "odi.db")))
    sqlite_job = sqlite_service.add_job("Onboard customers")
    sqlite_define = _stage_step(sqlite_service, sqlite_job.id, JobStage.DEFINE)
    _measured_outcome(sqlite_service, sqlite_job.id, sqlite_define.id)
    on_disk = sqlite_service.coverage_report(sqlite_job.id)

    assert in_memory.per_stage == on_disk.per_stage
    assert in_memory.gaps == on_disk.gaps
    assert in_memory.totals.outcomes == on_disk.totals.outcomes


def test_json_shape_is_stable_across_runs(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    define = _stage_step(service, job.id, JobStage.DEFINE)
    _measured_outcome(service, job.id, define.id)

    first = service.coverage_report(job.id).model_dump(mode="json")
    second = service.coverage_report(job.id).model_dump(mode="json")

    assert first == second
    assert list(first) == ["job_id", "per_stage", "totals", "gaps"]
