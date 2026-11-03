"""ALH-196 (M2-03.1) — the bulk record an undo token rides.

A bulk operation is addressed later, possibly from another process, so the inverse must be
readable from the store rather than held in memory: the same persistence route the scheduled
work record already takes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from agentic_odi_core.models import BulkChange, BulkOperation
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.sqlite_repository import SQLiteRepository

APPLIED = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
UNDONE = datetime(2026, 11, 3, 12, 30, tzinfo=timezone.utc)


def _change(outcome_id: str) -> BulkChange:
    return BulkChange(
        outcome_id=outcome_id,
        before={"step_id": None, "theme_ids": [], "tags": []},
        after={"step_id": "s-2", "theme_ids": ["t-1"], "tags": ["churn"]},
    )


def _operation(token: str, applied_at: datetime = APPLIED) -> BulkOperation:
    return BulkOperation(
        id=token,
        applied_at=applied_at,
        requested=2,
        changes=[_change("o-1")],
        skipped=[{"id": "o-9", "reason": "outcome not found"}],
    )


@pytest.fixture(params=["memory", "sqlite"])
def repo(request: pytest.FixtureRequest, tmp_path: Path):
    if request.param == "memory":
        return InMemoryRepository()
    return SQLiteRepository(db_path=str(tmp_path / "odi.db"))


def test_a_bulk_operation_is_readable_by_its_token(repo) -> None:
    repo.add_bulk_operation(_operation("b-1"))
    read = repo.get_bulk_operation("b-1")
    assert read is not None
    assert read.changes[0].after["step_id"] == "s-2"
    assert read.undone_at is None


def test_an_unknown_token_reads_as_nothing(repo) -> None:
    assert repo.get_bulk_operation("b-nope") is None


def test_bulk_operations_are_listed_in_creation_order(repo) -> None:
    repo.add_bulk_operation(_operation("b-2", APPLIED))
    repo.add_bulk_operation(_operation("b-1", APPLIED))
    repo.add_bulk_operation(_operation("b-3", APPLIED))
    assert [op.id for op in repo.list_bulk_operations()] == ["b-2", "b-1", "b-3"]


def test_marking_a_bulk_operation_undone_persists(repo) -> None:
    repo.add_bulk_operation(_operation("b-1"))
    updated = repo.update_bulk_operation("b-1", {"undone_at": UNDONE})
    assert updated is not None and updated.undone_at == UNDONE
    assert repo.get_bulk_operation("b-1").undone_at == UNDONE


def test_a_bulk_operation_survives_a_reopen(tmp_path: Path) -> None:
    path = str(tmp_path / "odi.db")
    store = SQLiteRepository(db_path=path)
    store.add_bulk_operation(_operation("b-1"))
    reopened = SQLiteRepository(db_path=path)
    read = reopened.get_bulk_operation("b-1")
    assert read is not None
    assert read.changes[0].before["theme_ids"] == []
    assert read.skipped[0]["reason"] == "outcome not found"


# --- the bulk change itself --------------------------------------------------

from agentic_odi_core.bulk import image  # noqa: E402
from agentic_odi_core.errors import ValidationError  # noqa: E402
from agentic_odi_core.models import Outcome  # noqa: E402
from agentic_odi_core.query import OutcomeQuery  # noqa: E402
from agentic_odi_core.services import ODIService  # noqa: E402

STATEMENT_ONE = "Minimize the time to approve an invoice when it arrives"
STATEMENT_TWO = "Minimize the number of errors in the reconciliation when the supplier edits it"
STATEMENT_THREE = "Minimize the time to classify a chargeback when a customer disputes it"


@pytest.fixture
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _job_with_map(service: ODIService, name: str, stages: tuple[str, ...]) -> dict[str, str]:
    """One job with a step per named stage, and that stage's step id under each name."""
    job = service.add_job(name)
    #: The job map needs one outcome before it means anything (ALH-20), so the seed carries one
    #: the tests below never name.
    service.add_outcome(job.id, STATEMENT_THREE)
    steps = {}
    for order, stage in enumerate(stages, start=1):
        steps[stage] = service.add_step(job.id, f"Step for {stage}", order=order, stage=stage).id
    return {"job_id": job.id, **steps}


def _outcome(service: ODIService, job_id: str, statement: str) -> str:
    return service.add_outcome(job_id, statement).id


def test_a_preview_lists_the_rows_a_real_run_would_write_without_writing_them(
    service: ODIService,
) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("locate", "execute"))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)
    o_b = _outcome(service, one["job_id"], STATEMENT_TWO)
    theme = service.add_theme("Billing").id
    before = dict(service.repo.outcomes)

    preview = service.bulk_update_outcomes([o_a, o_b], add_theme_ids=[theme], dry_run=True)

    assert sorted(preview.changed) == sorted([o_a, o_b])
    assert preview.undo_token is None
    assert preview.changes[0]["field"] == "theme_ids"
    assert dict(service.repo.outcomes) == before
    assert service.repo.bulk_operations == {}


def test_a_preview_and_a_real_run_on_unchanged_input_agree(service: ODIService) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("locate", "execute"))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)
    o_b = _outcome(service, one["job_id"], STATEMENT_TWO)
    theme = service.add_theme("Billing").id

    preview = service.bulk_update_outcomes([o_a, o_b], add_theme_ids=[theme], dry_run=True)
    real = service.bulk_update_outcomes([o_a, o_b], add_theme_ids=[theme])

    assert (real.changed, real.skipped) == (preview.changed, preview.skipped)
    assert real.undo_token is not None


def test_one_bad_row_does_not_abort_the_others(service: ODIService) -> None:
    mine = _job_with_map(service, "Reconcile invoices", ("execute",))
    theirs = _job_with_map(service, "Onboard vendors", ("execute",))
    good = _outcome(service, mine["job_id"], STATEMENT_ONE)
    foreign = _outcome(service, theirs["job_id"], STATEMENT_TWO)
    scoped_theme = service.add_theme("Billing", job_id=mine["job_id"]).id

    report = service.bulk_update_outcomes(
        [good, "o-missing", foreign], add_theme_ids=[scoped_theme]
    )

    assert report.changed == [good]
    reasons = {row["id"]: row["reason"] for row in report.skipped}
    assert reasons["o-missing"] == "outcome not found"
    assert "organizes job" in reasons[foreign]


def test_a_repeated_id_cannot_write_twice(service: ODIService) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("execute",))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)
    theme = service.add_theme("Billing").id

    report = service.bulk_update_outcomes([o_a, o_a], add_theme_ids=[theme])

    assert report.requested == 1
    assert report.changed == [o_a]
    assert service.repo.get_outcome(o_a).theme_ids == [theme]


def test_an_empty_selection_is_refused(service: ODIService) -> None:
    with pytest.raises(ValidationError, match="No outcomes selected"):
        service.bulk_update_outcomes([], add_tags=["churn"])


def test_a_theme_both_added_and_removed_is_refused_before_any_write(
    service: ODIService,
) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("execute",))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)
    theme = service.add_theme("Billing").id

    with pytest.raises(ValidationError, match="both added and removed"):
        service.bulk_update_outcomes([o_a], add_theme_ids=[theme], remove_theme_ids=[theme])
    assert service.repo.get_outcome(o_a).theme_ids == []


def test_a_stage_moves_each_outcome_onto_its_own_jobs_step(service: ODIService) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("locate", "execute"))
    two = _job_with_map(service, "Onboard vendors", ("locate",))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)
    o_b = _outcome(service, two["job_id"], STATEMENT_TWO)

    report = service.bulk_update_outcomes([o_a, o_b], stage="locate")

    assert sorted(report.changed) == sorted([o_a, o_b])
    assert service.repo.get_outcome(o_a).step_id == one["locate"]
    assert service.repo.get_outcome(o_b).step_id == two["locate"]


def test_a_job_without_that_stage_is_skipped_rather_than_guessed(
    service: ODIService,
) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("execute",))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)

    report = service.bulk_update_outcomes([o_a], stage="locate")

    assert report.changed == []
    assert report.skipped[0]["reason"] == "job has no stage 'locate'"


def test_an_unknown_stage_is_refused_with_the_shared_contract_message(
    service: ODIService,
) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("execute",))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)

    with pytest.raises(ValidationError, match="Unknown stage: migrate"):
        service.bulk_update_outcomes([o_a], stage="migrate")


def test_added_tags_land_once_and_a_row_that_already_matches_changes_nothing(
    service: ODIService,
) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("execute",))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)
    o_b = _outcome(service, one["job_id"], STATEMENT_TWO)
    service.update_outcome(o_b, {"tags": ["churn"]})

    report = service.bulk_update_outcomes([o_a, o_b], add_tags=["churn"])

    assert report.changed == [o_a]
    assert service.repo.get_outcome(o_a).tags == ["churn"]
    assert report.skipped[0]["reason"] == "no change"
    assert len(service.repo.bulk_operations) == 1


def test_a_run_that_changes_nothing_records_nothing_to_undo(
    service: ODIService,
) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("execute",))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)
    service.bulk_update_outcomes([o_a], stage="execute")

    again = service.bulk_update_outcomes([o_a], stage="execute")

    assert again.changed == []
    assert again.undo_token is None
    assert again.skipped[0]["reason"] == "no change"
    assert len(service.repo.bulk_operations) == 1


def test_a_filter_selects_every_match_of_the_narrowing_not_one_page(
    service: ODIService,
) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("locate", "execute"))
    when = (
        "it arrives at night",
        "the amount is small",
        "a delegate signs for it",
        "the vendor is new",
        "it is already paid",
    )
    ids = [
        _outcome(service, one["job_id"], STATEMENT_ONE.replace("when it arrives", f"when {w}"))
        for w in when
    ]
    theme = service.add_theme("Billing").id

    report = service.bulk_update_outcomes(
        None, query=OutcomeQuery(text="invoice"), add_theme_ids=[theme]
    )

    assert sorted(report.changed) == sorted(ids)


# --- taking it back -----------------------------------------------------------


def test_undo_restores_themes_stage_and_tags_exactly(service: ODIService) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("locate", "execute"))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)
    theme = service.add_theme("Billing").id
    service.update_outcome(o_a, {"tags": ["keep-me"]})
    original = image(service.repo.get_outcome(o_a))

    report = service.bulk_update_outcomes(
        [o_a], add_theme_ids=[theme], stage="locate", add_tags=["churn"]
    )
    undone = service.undo_bulk(report.undo_token)

    assert sorted(undone.changed) == sorted(report.changed)
    assert image(service.repo.get_outcome(o_a)) == original


def test_undo_restores_a_step_that_was_never_set(service: ODIService) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("locate", "execute"))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)
    assert service.repo.get_outcome(o_a).step_id is None

    report = service.bulk_update_outcomes([o_a], stage="locate")
    service.undo_bulk(report.undo_token)

    assert service.repo.get_outcome(o_a).step_id is None


def test_a_newer_bulk_run_expires_the_older_token(service: ODIService) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("locate", "execute"))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)
    first = service.bulk_update_outcomes([o_a], add_tags=["churn"])
    second = service.bulk_update_outcomes([o_a], add_tags=["pricing"])

    with pytest.raises(ValidationError, match=f"{second.undo_token} wrote after it"):
        service.undo_bulk(first.undo_token)


def test_one_token_cannot_undo_twice(service: ODIService) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("locate", "execute"))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)
    report = service.bulk_update_outcomes([o_a], add_tags=["churn"])
    service.undo_bulk(report.undo_token)

    with pytest.raises(ValidationError, match="already undone"):
        service.undo_bulk(report.undo_token)


def test_an_unknown_token_is_refused(service: ODIService) -> None:
    with pytest.raises(ValidationError, match="Unknown bulk token"):
        service.undo_bulk("b-does-not-exist")


def test_undo_leaves_a_row_someone_answered_after_the_bulk_run(
    service: ODIService,
) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("locate", "execute"))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)
    o_b = _outcome(service, one["job_id"], STATEMENT_TWO)
    theme = service.add_theme("Billing").id

    report = service.bulk_update_outcomes([o_a, o_b], add_theme_ids=[theme])
    service.update_outcome(o_b, {"tags": ["hand-edited"]})
    undone = service.undo_bulk(report.undo_token)

    assert undone.changed == [o_a]
    assert undone.skipped[0]["reason"] == "changed since the bulk update"
    assert service.repo.get_outcome(o_a).theme_ids == []
    assert service.repo.get_outcome(o_b).theme_ids == [theme]
    assert service.repo.get_outcome(o_b).tags == ["hand-edited"]


def test_a_reordered_membership_is_not_a_conflict(service: ODIService) -> None:
    one = _job_with_map(service, "Reconcile invoices", ("locate", "execute"))
    o_a = _outcome(service, one["job_id"], STATEMENT_ONE)
    first = service.add_theme("Billing").id
    second = service.add_theme("Collections").id
    service.assign_theme([o_a], first)
    report = service.bulk_update_outcomes([o_a], add_theme_ids=[second])
    service.update_outcome(o_a, {"theme_ids": [second, first]})

    service.undo_bulk(report.undo_token)

    assert service.repo.get_outcome(o_a).theme_ids == [first]


def test_a_token_still_works_after_a_reload(tmp_path: Path) -> None:
    from agentic_odi_core.models import Job, Step

    path = str(tmp_path / "odi.db")
    store = SQLiteRepository(db_path=path)
    store.add_job(Job(id="j-1", name="Reconcile invoices"))
    store.add_outcome(
        Outcome(
            id="o-1",
            job_id="j-1",
            statement="Minimize the time to approve an invoice when it arrives",
        )
    )
    store.add_step(Step(id="s-1", job_id="j-1", name="Locate", order=2, stage="locate"))
    service = ODIService(store)
    theme = service.add_theme("Billing").id
    report = service.bulk_update_outcomes(["o-1"], add_theme_ids=[theme], stage="locate")

    reopened = ODIService(SQLiteRepository(db_path=path))
    undone = reopened.undo_bulk(report.undo_token)

    assert undone.changed == ["o-1"]
    assert reopened.repo.get_outcome("o-1").theme_ids == []
    assert reopened.repo.get_outcome("o-1").step_id is None
