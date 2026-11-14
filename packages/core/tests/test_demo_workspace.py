"""The demo workspace is a labeled fixture, loaded on purpose and repeatable.

``odi demo load`` exists so a stranger can see a filled canvas before they have
any research of their own, which only works if the sample can never be mistaken
for their data and never damages it. These tests hold the loader to that: exact
counts, ``origin="demo"`` on every row, deterministic ids, a second load that
changes nothing, and a first load that leaves real rows alone.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.demo import (
    DEMO_JOB_ID,
    FIXTURE_COUNTS,
    fixture_rows,
    load_demo_workspace,
)
from agentic_odi_core.evaluation import require_outcome_statement
from agentic_odi_core.models import JOB_STAGE_ORDER, Outcome
from agentic_odi_core.repository import InMemoryRepository, Repository
from agentic_odi_core.services import JobNotFoundError, ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository

STORE_ENTITIES = set(Repository.__annotations__)


@pytest.fixture(params=["sqlite", "in-memory"])
def service(request, tmp_path) -> ODIService:
    if request.param == "sqlite":
        return ODIService(SQLiteRepository(db_path=str(tmp_path / "demo.db")))
    return ODIService(InMemoryRepository())


# -- the fixture itself -------------------------------------------------------


def test_the_fixture_is_the_size_the_loader_promises() -> None:
    rows = fixture_rows()
    assert {name: len(items) for name, items in rows.items()} == FIXTURE_COUNTS


def test_every_fixture_row_says_it_is_a_demo() -> None:
    for name, rows in fixture_rows().items():
        for row in rows:
            assert row.origin == "demo", f"{name} row {row.id} is unlabelled"


def test_the_fixture_reuses_the_same_ids_every_time() -> None:
    first = {name: [row.id for row in rows] for name, rows in fixture_rows().items()}
    second = {name: [row.id for row in rows] for name, rows in fixture_rows().items()}
    assert first == second


def test_the_fixture_attaches_to_the_job_it_was_asked_for() -> None:
    rows = fixture_rows("JOB-777")
    assert [job.id for job in rows["jobs"]] == ["JOB-777"]
    for name, items in rows.items():
        if name == "jobs":
            continue
        for row in items:
            assert row.job_id == "JOB-777", f"{name} row {row.id} points elsewhere"


def test_the_job_map_covers_each_stage_exactly_once() -> None:
    steps = fixture_rows()["steps"]
    assert [step.order for step in steps] == list(range(1, 9))
    assert [step.stage for step in steps] == JOB_STAGE_ORDER
    assert [step.stage_index for step in steps] == list(range(1, 9))


def test_every_fixture_statement_is_a_valid_outcome_statement() -> None:
    for outcome in fixture_rows()["outcomes"]:
        require_outcome_statement(outcome.statement)


def test_outcomes_are_scored_and_the_landscape_spans_the_ranges() -> None:
    outcomes = fixture_rows()["outcomes"]
    assert all(outcome.importance is not None for outcome in outcomes)
    assert all(outcome.satisfaction is not None for outcome in outcomes)
    underserved = [o for o in outcomes if o.opportunity_score > 10.0]
    overserved = [o for o in outcomes if o.opportunity_score < 10.0]
    assert underserved and overserved, "the landscape needs underserved and overserved outcomes"
    assert max(o.opportunity_score for o in outcomes) > 12.0


def test_rows_only_reference_rows_that_are_in_the_fixture() -> None:
    rows = fixture_rows()
    step_ids = {step.id for step in rows["steps"]}
    outcome_ids = {outcome.id for outcome in rows["outcomes"]}
    assert all(outcome.step_id in step_ids for outcome in rows["outcomes"])
    assert all(item.step_id in step_ids for item in rows["evidence"])
    assert all(item.outcome_id in outcome_ids for item in rows["evidence"])


def test_the_fixture_claims_no_entity_the_loader_cannot_write() -> None:
    """Segments, decisions and bets arrive with M1; the fixture must not invent them."""
    rows = fixture_rows()
    assert set(rows) <= STORE_ENTITIES
    assert set(rows) == {"jobs", "steps", "outcomes", "evidence"}


# -- loading ------------------------------------------------------------------


def test_loading_fills_an_empty_store_with_exactly_the_fixture_counts(service) -> None:
    load_demo_workspace(service)
    repo = service.repo
    assert len(repo.jobs) == FIXTURE_COUNTS["jobs"]
    assert len(repo.steps) == FIXTURE_COUNTS["steps"]
    assert len(repo.outcomes) == FIXTURE_COUNTS["outcomes"]
    assert len(repo.evidence) == FIXTURE_COUNTS["evidence"]
    assert not repo.segments and not repo.strategies and not repo.customer_outcomes


def test_loading_reports_the_counts_it_written(service) -> None:
    result = load_demo_workspace(service)
    assert result.job_id == DEMO_JOB_ID
    assert result.counts == FIXTURE_COUNTS


def test_loading_twice_changes_no_counts(service) -> None:
    load_demo_workspace(service)
    load_demo_workspace(service)
    repo = service.repo
    counts = (len(repo.jobs), len(repo.steps), len(repo.outcomes), len(repo.evidence))
    assert counts == (1, 8, 40, 12)


def test_loading_twice_appends_nothing_to_the_event_log(tmp_path) -> None:
    repo = SQLiteRepository(db_path=str(tmp_path / "demo.db"), workspace_id="demo-log")
    service = ODIService(repo)
    load_demo_workspace(service)
    events = len(repo.store.get_stream(workspace_id="demo-log"))
    load_demo_workspace(service)
    assert len(repo.store.get_stream(workspace_id="demo-log")) == events


def test_the_fixture_survives_a_reload_from_the_store(tmp_path) -> None:
    path = str(tmp_path / "demo.db")
    load_demo_workspace(ODIService(SQLiteRepository(db_path=path)))

    reader = SQLiteRepository(db_path=path)
    try:
        assert len(reader.outcomes) == FIXTURE_COUNTS["outcomes"]
        assert all(outcome.origin == "demo" for outcome in reader.outcomes.values())
        assert all(step.stage is not None for step in reader.steps.values())
    finally:
        reader.close()


def test_loading_leaves_real_rows_intact(service) -> None:
    service.add_job("My own research", id="job-real")
    service.add_outcome(
        "job-real",
        "Minimize the time it takes to brief a contractor when starting work",
        importance=7.0,
        satisfaction=6.0,
    )
    real_job = service.get_job("job-real")
    real_outcome = service.get_outcomes("job-real")[0]

    load_demo_workspace(service)

    assert service.get_job("job-real") == real_job
    after = service.get_outcomes("job-real")
    assert after == [real_outcome]
    assert all(outcome.origin == "user" for outcome in after)
    assert len(service.get_jobs()) == 2


def test_loading_onto_an_existing_job_attaches_the_fixture_without_creating_one(service) -> None:
    service.add_job("My own research", id="job-real")

    result = load_demo_workspace(service, job_id="job-real")

    assert result.job_id == "job-real"
    assert len(service.repo.jobs) == 1
    assert service.get_job("job-real").name == "My own research"
    assert service.get_job(DEMO_JOB_ID) is None
    assert all(outcome.job_id == "job-real" for outcome in service.repo.outcomes.values())
    assert all(outcome.origin == "demo" for outcome in service.repo.outcomes.values())


def test_loading_onto_a_job_that_does_not_exist_is_refused(service) -> None:
    with pytest.raises(JobNotFoundError):
        load_demo_workspace(service, job_id="nope")


def test_an_existing_demo_can_be_re_targeted_at_a_job(service) -> None:
    """A second load with --job moves the fixture rows, it does not copy them."""
    load_demo_workspace(service)
    service.add_job("My own research", id="job-real")

    load_demo_workspace(service, job_id="job-real")

    assert len(service.repo.jobs) == 2
    assert len(service.repo.outcomes) == FIXTURE_COUNTS["outcomes"]
    assert all(outcome.job_id == "job-real" for outcome in service.repo.outcomes.values())


def test_the_loader_writes_through_the_same_service_as_everyone_else(service) -> None:
    """Nothing bypasses validation: the statements are the ODI shape on read too."""
    load_demo_workspace(service)
    for outcome in service.repo.outcomes.values():
        assert isinstance(outcome, Outcome)
        require_outcome_statement(outcome.statement)
