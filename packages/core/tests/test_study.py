"""A Study is one named pass over a Job, and running it again makes a wave.

ALH-69 (M2-05). The container and its rules are what this proves: a wave is
unique per (job, name); a study opens planned and closes once, and closing twice
keeps the first ``closed_at`` rather than quietly moving the date. Legacy rows
that carry no study are reported as belonging to no study — never assigned an
invented one. The whole chain is asserted against both repositories so a study
survives a close-and-reopen.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.contract import TOOL_SPECS, ToolName
from agentic_odi_core.models import Study, StudyStatus
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.schema import odi_schema
from agentic_odi_core.services import JobNotFoundError, ODIService, ValidationError
from agentic_odi_core.sqlite_repository import SQLiteRepository
from pydantic import ValidationError as PydanticValidationError


@pytest.fixture
def service() -> ODIService:
    svc = ODIService(InMemoryRepository())
    svc.add_job("Reconcile supplier invoices", "Match invoices to purchase orders")
    return svc


def _job_id(svc: ODIService) -> str:
    return svc.get_jobs()[0].id


def _outcome(
    svc: ODIService,
    job_id: str,
    statement: str = "Minimize the time it takes to match an invoice when it arrives",
) -> str:
    return svc.add_outcome(job_id, statement, 8.0, 3.0).id


def _study_id(svc: ODIService, outcome_id: str) -> str | None:
    outcome = svc.get_outcome(outcome_id)
    assert outcome is not None
    return outcome.study_id


# --- the model --------------------------------------------------------------


def test_wave_must_be_a_positive_pass_number() -> None:
    with pytest.raises(PydanticValidationError):
        Study(job_id="JOB-1", name="Q3 sweep", wave=0)


def test_a_study_opens_planned_with_no_close_date() -> None:
    study = Study(job_id="JOB-1", name="Q3 sweep", wave=1)
    assert study.status is StudyStatus.PLANNED
    assert study.closed_at is None
    assert study.opened_at is not None


def test_a_study_that_is_not_closed_cannot_carry_a_close_date() -> None:
    with pytest.raises(PydanticValidationError):
        Study(job_id="JOB-1", name="Q3 sweep", wave=1, status=StudyStatus.PLANNED, closed_at=_now())


def test_a_closed_study_must_carry_a_close_date() -> None:
    with pytest.raises(PydanticValidationError):
        Study(job_id="JOB-1", name="Q3 sweep", wave=1, status=StudyStatus.CLOSED)


def _now():  # noqa: ANN202 - test helper
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


# --- opening, listing, and wave uniqueness ----------------------------------


def test_open_study_records_the_pass_and_starts_it_planned(service: ODIService) -> None:
    job_id = _job_id(service)

    study = service.open_study(job_id, "Q3 reconciliation sweep", wave=1)

    assert study.status is StudyStatus.PLANNED
    assert study.wave == 1
    assert service.list_studies(job_id) == [study]


def test_open_study_refuses_a_duplicate_wave_for_the_same_job_and_name(service: ODIService) -> None:
    job_id = _job_id(service)
    service.open_study(job_id, "Q3 sweep", wave=1)

    with pytest.raises(ValidationError):
        service.open_study(job_id, "Q3 sweep", wave=1)


def test_the_same_wave_number_is_allowed_under_a_different_name(service: ODIService) -> None:
    job_id = _job_id(service)
    service.open_study(job_id, "Q3 sweep", wave=1)

    second = service.open_study(job_id, "Q4 sweep", wave=1)

    assert second.name == "Q4 sweep"
    assert len(service.list_studies(job_id)) == 2


def test_the_same_wave_number_is_allowed_under_a_different_job(service: ODIService) -> None:
    first_job = service.add_job("Onboard a customer", None)
    second_job = service.add_job("Offboard a customer", None)
    service.open_study(first_job.id, "Field study", wave=1)

    study = service.open_study(second_job.id, "Field study", wave=1)

    assert study.job_id == second_job.id


def test_open_study_needs_a_job_that_exists(service: ODIService) -> None:
    with pytest.raises(JobNotFoundError):
        service.open_study("nope", "Q3 sweep", wave=1)


def test_list_studies_is_empty_until_a_study_is_opened(service: ODIService) -> None:
    assert service.list_studies(_job_id(service)) == []


# --- closing ----------------------------------------------------------------


def test_closing_a_study_records_closed_at(service: ODIService) -> None:
    job_id = _job_id(service)
    study = service.open_study(job_id, "Q3 sweep", wave=1)

    closed = service.close_study(study.id)

    assert closed.status is StudyStatus.CLOSED
    assert closed.closed_at is not None


def test_closing_twice_keeps_the_first_close_date(service: ODIService) -> None:
    job_id = _job_id(service)
    study = service.open_study(job_id, "Q3 sweep", wave=1)
    first = service.close_study(study.id)

    second = service.close_study(study.id)

    assert second.closed_at == first.closed_at
    assert second.status is StudyStatus.CLOSED


# --- scoping an outcome to a study ------------------------------------------


def test_an_outcome_defaults_to_belonging_to_no_study(service: ODIService) -> None:
    job_id = _job_id(service)
    outcome_id = _outcome(service, job_id)

    assert _study_id(service, outcome_id) is None


def test_an_outcome_can_be_scoped_to_a_study_in_its_own_job(service: ODIService) -> None:
    job_id = _job_id(service)
    outcome_id = _outcome(service, job_id)
    study = service.open_study(job_id, "Q3 sweep", wave=1)

    scoped = service.update_outcome(outcome_id, {"study_id": study.id})

    assert scoped.study_id == study.id


def test_scoping_an_outcome_to_a_foreign_job_study_fails_without_mutation(
    service: ODIService,
) -> None:
    job_id = _job_id(service)
    outcome_id = _outcome(service, job_id)
    other_job = service.add_job("Offboard a customer", None)
    foreign = service.open_study(other_job.id, "Q3 sweep", wave=1)

    with pytest.raises(ValidationError):
        service.update_outcome(outcome_id, {"study_id": foreign.id})

    assert _study_id(service, outcome_id) is None


# --- persistence and replay -------------------------------------------------


def test_a_study_survives_a_reopen(tmp_path) -> None:
    db = str(tmp_path / "study.db")
    svc = ODIService(SQLiteRepository(db_path=db))
    svc.add_job("Reconcile supplier invoices", None)
    job_id = svc.get_jobs()[0].id
    study = svc.open_study(job_id, "Q3 sweep", wave=1)
    svc.close_study(study.id)

    reopened = ODIService(SQLiteRepository(db_path=db))
    restored = reopened.list_studies(job_id)

    assert len(restored) == 1
    assert restored[0].status is StudyStatus.CLOSED
    assert restored[0].closed_at is not None


def test_reopening_a_store_did_not_assign_invented_studies_to_legacy_rows(tmp_path) -> None:
    db = str(tmp_path / "legacy.db")
    first = ODIService(SQLiteRepository(db_path=db))
    first.add_job("Reconcile supplier invoices", None)
    job_id = first.get_jobs()[0].id
    outcome_id = _outcome(first, job_id)

    reopened = ODIService(SQLiteRepository(db_path=db))
    reopened.add_job("A second job", None)

    assert _study_id(reopened, outcome_id) is None
    assert reopened.list_studies(job_id) == []


def test_study_and_outcome_are_the_same_through_both_repositories(tmp_path) -> None:
    db = str(tmp_path / "parity.db")
    memory = ODIService(InMemoryRepository())
    sql = ODIService(SQLiteRepository(db_path=db))
    for svc in (memory, sql):
        svc.add_job("Reconcile supplier invoices", None)
    job_id = memory.get_jobs()[0].id
    sql_job_id = sql.get_jobs()[0].id
    study = memory.open_study(job_id, "Q3 sweep", wave=1)
    sql.open_study(sql_job_id, "Q3 sweep", wave=1)

    assert len(memory.list_studies(job_id)) == len(sql.list_studies(sql_job_id))
    assert study.wave == 1


# --- contract and schema surfaces -------------------------------------------


def test_study_is_a_published_entity_schema() -> None:
    schema = odi_schema()
    assert "Study" in schema
    assert "study_id" in schema["Outcome"]["properties"]


def test_the_study_tools_are_declared_in_the_contract() -> None:
    assert ToolName.OPEN_STUDY.value in TOOL_SPECS
    assert ToolName.LIST_STUDIES.value in TOOL_SPECS
    assert TOOL_SPECS[ToolName.OPEN_STUDY.value].required == ("job_id", "name", "wave")
    assert TOOL_SPECS[ToolName.LIST_STUDIES.value].effect.value == "read"
