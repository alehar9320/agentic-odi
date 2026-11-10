"""B3.1: retained paired survey inputs survive a reload and reproduce a band.

The retention slice must make a stored band reproducible from the *real* paired
responses after a reload, not only for the process that imported it. These tests
drive the real import path over a SQLite reopen so "persisted and replayed" is
not an in-memory dict, and pin the refusals: a rejected or dry-run import retains
nothing, a legacy aggregate-only outcome reports no input set rather than an
empty one, and no respondent identifier leaks into the read shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import Outcome
from agentic_odi_core.repository import InMemoryRepository, Repository
from agentic_odi_core.services import ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository
from agentic_odi_core.stats import opportunity_interval as bootstrap_interval
from agentic_odi_core.trust import build_survey_input_set

_STATEMENT = "Minimize the time it takes to onboard a new engineer when they join."


@pytest.fixture(params=["memory", "sqlite"])
def repo(request: pytest.FixtureRequest, tmp_path: Path) -> Repository:
    if request.param == "memory":
        return InMemoryRepository()
    return SQLiteRepository(str(tmp_path / "odi.db"))


def _reopen(repo: Repository) -> Repository:
    if isinstance(repo, SQLiteRepository):
        repo.reload()
    return repo


def _seed_outcome(service: ODIService, statement: str = _STATEMENT) -> str:
    job = service.add_job("Engineer onboarding")
    outcome = service.add_outcome(job.id, statement, 5.0, 5.0)
    service.add_step(job.id, name="Evaluate", order=1)
    return outcome.id


def _survey_rows(outcome_id: str, pairs: list[tuple[float, float]]) -> list[dict[str, object]]:
    return [
        {
            "outcome_id": outcome_id,
            "importance": importance,
            "satisfaction": satisfaction,
            "respondent_id": f"r-{index}",
        }
        for index, (importance, satisfaction) in enumerate(pairs)
    ]


def test_retained_inputs_survive_a_reload_in_canonical_order(repo: Repository) -> None:
    service = ODIService(repo)
    outcome_id = _seed_outcome(service)
    pairs = [(8.0, 6.0), (3.0, 9.0), (7.5, 7.5), (9.0, 4.0)]

    service.import_survey(_survey_rows(outcome_id, pairs))
    inputs = ODIService(_reopen(repo)).get_outcome_inputs(outcome_id)

    assert inputs is not None
    assert [(i.importance, i.satisfaction) for i in inputs] == pairs
    assert [i.respondent_id for i in inputs] == ["r-0", "r-1", "r-2", "r-3"]


def test_a_reloaded_input_set_reproduces_the_stored_band(repo: Repository) -> None:
    service = ODIService(repo)
    outcome_id = _seed_outcome(service)
    pairs = [(8.0, 6.0), (3.0, 9.0), (7.5, 7.5), (9.0, 4.0), (5.0, 5.0)]
    service.import_survey(_survey_rows(outcome_id, pairs))

    reopened = ODIService(_reopen(repo))
    outcome = reopened.get_outcome(outcome_id)
    assert outcome is not None
    inputs = reopened.get_outcome_inputs(outcome_id)
    assert inputs is not None

    # Bootstrapping from the *retained* pairs reproduces the stored band exactly.
    recomputed = bootstrap_interval(
        [i.importance for i in inputs], [i.satisfaction for i in inputs]
    )
    assert recomputed.low == outcome.opportunity_low
    assert recomputed.high == outcome.opportunity_high
    assert recomputed.n == outcome.interval_n


def test_a_rejected_import_retains_nothing(repo: Repository) -> None:
    service = ODIService(repo)
    outcome_id = _seed_outcome(service)
    rows = _survey_rows(outcome_id, [(8.0, 6.0), (3.0, 9.0)])
    rows.append({"outcome_id": "does-not-exist", "importance": 5.0, "satisfaction": 5.0})

    with pytest.raises(ValidationError):
        service.import_survey(rows)

    assert service.get_outcome_inputs(outcome_id) is None
    assert _reopen(repo).get_survey_input_set(outcome_id) is None


def test_a_dry_run_plan_retains_nothing(repo: Repository) -> None:
    service = ODIService(repo)
    outcome_id = _seed_outcome(service)

    plan = service.get_survey_import_plan(_survey_rows(outcome_id, [(8.0, 6.0), (3.0, 9.0)]))

    assert plan.writable
    assert service.get_outcome_inputs(outcome_id) is None
    assert _reopen(repo).get_survey_input_set(outcome_id) is None


def test_a_legacy_aggregate_only_outcome_reports_no_input_set(repo: Repository) -> None:
    service = ODIService(repo)
    outcome_id = _seed_outcome(service)
    # A survey-labelled score written without retained pairs, as a legacy row
    # would be: the read side must say "no input set", never an empty list.
    service.update_outcome(
        outcome_id,
        {
            "importance": 8.0,
            "satisfaction": 6.0,
            "importance_n": 30,
            "satisfaction_n": 30,
            "score_method": "survey",
        },
    )

    assert service.get_outcome_inputs(outcome_id) is None


def test_a_score_edit_invalidates_and_drops_the_retained_inputs(repo: Repository) -> None:
    service = ODIService(repo)
    outcome_id = _seed_outcome(service)
    service.import_survey(_survey_rows(outcome_id, [(8.0, 6.0), (3.0, 9.0), (7.0, 7.0)]))
    assert service.get_outcome_inputs(outcome_id) is not None

    service.update_outcome(outcome_id, {"importance": 4.0})

    assert service.get_outcome_inputs(outcome_id) is None
    assert _reopen(repo).get_survey_input_set(outcome_id) is None


def test_deleting_the_outcome_drops_the_retained_inputs(repo: Repository) -> None:
    service = ODIService(repo)
    outcome_id = _seed_outcome(service)
    service.import_survey(_survey_rows(outcome_id, [(8.0, 6.0), (3.0, 9.0)]))

    service.delete_outcome(outcome_id)

    assert _reopen(repo).get_survey_input_set(outcome_id) is None


def test_the_read_shape_carries_no_personal_identifier(repo: Repository) -> None:
    service = ODIService(repo)
    outcome_id = _seed_outcome(service)
    service.import_survey(_survey_rows(outcome_id, [(8.0, 6.0), (3.0, 9.0)]))

    inputs = service.get_outcome_inputs(outcome_id)
    assert inputs is not None
    # Only the opaque per-pair token and the numbers; nothing else is exposed.
    for item in inputs:
        assert set(vars(item)) == {"outcome_id", "respondent_id", "importance", "satisfaction"}


def test_a_cross_job_input_set_is_rejected(repo: Repository) -> None:
    service = ODIService(repo)
    outcome_id = _seed_outcome(service)
    outcome = service.get_outcome(outcome_id)
    assert outcome is not None
    input_set = build_survey_input_set(outcome, [(8.0, 6.0)])
    # Re-point the set at a job that is not the outcome's own job.
    forged = input_set.model_copy(update={"job_id": "some-other-job"})

    with pytest.raises(ValidationError):
        repo.add_survey_input_set(forged)
    assert repo.get_survey_input_set(outcome_id) is None


def test_an_input_set_for_an_unknown_outcome_is_rejected(repo: Repository) -> None:
    outcome = Outcome(job_id="job-x", statement=_STATEMENT, importance=8.0, satisfaction=6.0)
    input_set = build_survey_input_set(outcome, [(8.0, 6.0)])

    with pytest.raises(ValidationError):
        repo.add_survey_input_set(input_set)
