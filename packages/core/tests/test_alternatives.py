"""What a customer uses today, recorded and asked about honestly (M2-07).

An empty inventory is unknown, never evidence that no solution exists; a
"nothing" row is real evidence for a new-market bet.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import Alternative, AlternativeLink
from agentic_odi_core.repository import InMemoryRepository, Repository
from agentic_odi_core.services import (
    AlternativeNotFoundError,
    JobNotFoundError,
    ODIService,
    OutcomeNotFoundError,
)
from agentic_odi_core.sqlite_repository import SQLiteRepository
from pydantic import ValidationError as PydanticValidationError

_STATEMENT = "Minimize the time it takes to onboard a new engineer when they join."


@pytest.fixture(params=["memory", "sqlite"])
def service(request: pytest.FixtureRequest, tmp_path: Path) -> ODIService:
    if request.param == "memory":
        repo: Repository = InMemoryRepository()
    else:
        repo = SQLiteRepository(str(tmp_path / "odi.db"))
    return ODIService(repo)


def _job_and_outcome(service: ODIService) -> tuple[str, str]:
    job = service.add_job("Onboard engineers")
    outcome = service.add_outcome(job.id, _STATEMENT, importance=8.0, satisfaction=6.0)
    return job.id, outcome.id


def test_a_linked_spreadsheet_reports_yes(service: ODIService) -> None:
    job_id, outcome_id = _job_and_outcome(service)
    spreadsheet = service.add_alternative(job_id, "Shared spreadsheet", kind="workaround")
    service.link_alternative(outcome_id, spreadsheet.id, adequacy=7.0)

    assert service.has_existing_solution(outcome_id) == "yes"


def test_only_nothing_reports_no_linked_nothing(service: ODIService) -> None:
    job_id, outcome_id = _job_and_outcome(service)
    nothing = service.add_alternative(job_id, "Nothing today", kind="nothing")
    service.link_alternative(outcome_id, nothing.id, adequacy=1.0)

    assert service.has_existing_solution(outcome_id) == "no_linked_nothing"


def test_no_links_reports_no_link_at_all(service: ODIService) -> None:
    _, outcome_id = _job_and_outcome(service)

    assert service.has_existing_solution(outcome_id) == "no_link_at_all"


def test_deleting_an_alternative_leaves_its_outcome_intact(service: ODIService) -> None:
    job_id, outcome_id = _job_and_outcome(service)
    alternative = service.add_alternative(job_id, "Vendor X", kind="product")
    service.link_alternative(outcome_id, alternative.id, adequacy=4.0)

    service.delete_alternative(alternative.id)

    assert service.get_outcome(outcome_id) is not None
    assert service.outcome_alternatives(outcome_id) == []
    assert service.has_existing_solution(outcome_id) == "no_link_at_all"


def test_deleting_the_outcome_leaves_no_orphan_link(service: ODIService) -> None:
    job_id, outcome_id = _job_and_outcome(service)
    alternative = service.add_alternative(job_id, "Vendor X", kind="product")
    service.link_alternative(outcome_id, alternative.id, adequacy=4.0)

    service.delete_outcome(outcome_id)

    assert service.list_alternatives(job_id) == [alternative]
    assert service.repo.list_alternative_links(outcome_id=outcome_id) == []


def test_alternative_round_trips_through_the_store(service: ODIService) -> None:
    job_id, outcome_id = _job_and_outcome(service)
    alternative = service.add_alternative(
        job_id, "Internal tool", kind="manual", notes="built in-house", source_kind="interview"
    )
    service.link_alternative(outcome_id, alternative.id, adequacy=6.0, usage_n=12, note="ok")

    if isinstance(service.repo, SQLiteRepository):
        service.repo.reload()

    loaded = service.get_alternative(alternative.id)
    assert (loaded.name, loaded.kind, loaded.notes, loaded.source_kind) == (
        "Internal tool",
        "manual",
        "built in-house",
        "interview",
    )
    pairs = service.outcome_alternatives(outcome_id)
    assert len(pairs) == 1
    assert pairs[0][1].adequacy == 6.0
    assert pairs[0][1].usage_n == 12


def test_a_cross_job_link_is_refused(service: ODIService) -> None:
    job_a, outcome_a = _job_and_outcome(service)
    job_b = service.add_job("Another job")
    alternative_b = service.add_alternative(job_b.id, "Vendor Y", kind="product")

    with pytest.raises(ValidationError):
        service.link_alternative(outcome_a, alternative_b.id, adequacy=5.0)

    assert service.repo.list_alternative_links(outcome_id=outcome_a) == []
    assert job_a != job_b.id


def test_missing_references_are_refused_without_events(service: ODIService) -> None:
    job_id, outcome_id = _job_and_outcome(service)
    alternative = service.add_alternative(job_id, "Vendor X", kind="product")

    with pytest.raises(OutcomeNotFoundError):
        service.link_alternative("missing-outcome", alternative.id, adequacy=5.0)
    with pytest.raises(AlternativeNotFoundError):
        service.link_alternative(outcome_id, "missing-alternative", adequacy=5.0)
    with pytest.raises(JobNotFoundError):
        service.add_alternative("missing-job", "X", kind="product")

    assert service.repo.list_alternative_links() == []


def test_adequacy_must_be_a_customer_rating_in_range() -> None:
    with pytest.raises(PydanticValidationError):
        AlternativeLink(outcome_id="o", alternative_id="a", adequacy=0.5)
    with pytest.raises(PydanticValidationError):
        AlternativeLink(outcome_id="o", alternative_id="a", adequacy=11.0)
    with pytest.raises(PydanticValidationError):
        AlternativeLink(outcome_id="o", alternative_id="a", adequacy=float("inf"))


def test_usage_n_must_be_a_positive_integer_when_given() -> None:
    with pytest.raises(PydanticValidationError):
        AlternativeLink(outcome_id="o", alternative_id="a", adequacy=5.0, usage_n=0)
    link = AlternativeLink(outcome_id="o", alternative_id="a", adequacy=5.0)
    assert link.usage_n is None


def test_unapproved_source_kind_is_refused(service: ODIService) -> None:
    job_id, _ = _job_and_outcome(service)

    with pytest.raises(ValidationError):
        service.add_alternative(job_id, "X", kind="product", source_kind="guessed")


def test_nothing_alongside_a_solution_still_reports_yes(service: ODIService) -> None:
    job_id, outcome_id = _job_and_outcome(service)
    nothing = service.add_alternative(job_id, "Nothing for this need", kind="nothing")
    vendor = service.add_alternative(job_id, "Vendor X", kind="product")
    service.link_alternative(outcome_id, nothing.id, adequacy=1.0)
    service.link_alternative(outcome_id, vendor.id, adequacy=4.0)

    assert service.has_existing_solution(outcome_id) == "yes"
    assert len(service.outcome_alternatives(outcome_id)) == 2


def test_unlink_removes_only_the_link(service: ODIService) -> None:
    job_id, outcome_id = _job_and_outcome(service)
    alternative = service.add_alternative(job_id, "Vendor X", kind="product")
    service.link_alternative(outcome_id, alternative.id, adequacy=4.0)

    service.unlink_alternative(outcome_id, alternative.id)

    assert service.get_alternative(alternative.id) is not None
    assert service.outcome_alternatives(outcome_id) == []
    with pytest.raises(ValidationError):
        service.unlink_alternative(outcome_id, alternative.id)


def test_a_kind_is_not_inferred_from_a_score(service: ODIService) -> None:
    job_id, _ = _job_and_outcome(service)
    with pytest.raises(PydanticValidationError):
        Alternative(job_id=job_id, name="X", kind="competitor")
