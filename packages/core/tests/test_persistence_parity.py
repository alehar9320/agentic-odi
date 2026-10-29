"""Cross-repository parity harness (the epic's Persistence checklist).

Every entity in the ODI store must behave identically through
:class:`~agentic_odi_core.repository.InMemoryRepository` and
:class:`~agentic_odi_core.sqlite_repository.SQLiteRepository`, and the SQLite
store must reproduce the same state when its event log is replayed.

The harness is table-driven and **fails on a missed link**: a new entity that
is written by the service but has no ``_apply_event`` branch shows up as a
divergence after reload rather than passing silently.
"""

from __future__ import annotations

from typing import Any

import pytest
from agentic_odi_core.models import (
    BusinessImpactCategory,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Direction,
    Evidence,
    Interview,
    InterviewQuote,
    Job,
    Outcome,
    Step,
)
from agentic_odi_core.repository import InMemoryRepository, Repository
from agentic_odi_core.sqlite_repository import SQLiteRepository

Snapshot = dict[str, Any]


def _snapshot(repo: Repository) -> Snapshot:
    """A comparable read of every entity surface the Repository exposes."""
    return {
        "jobs": [j.model_dump() for j in repo.list_jobs()],
        "steps": sorted(
            (s.model_dump() for s in repo.get_steps_for_job("job-1")),
            key=lambda d: d["id"],
        ),
        "outcomes": sorted(
            (o.model_dump() for o in repo.get_outcomes("job-1", sort="insertion")),
            key=lambda d: d["id"],
        ),
        "customer_outcomes": sorted(
            (c.model_dump() for c in repo.list_customer_outcomes("job-1")),
            key=lambda d: d["id"],
        ),
        "evidence": sorted(
            (e.model_dump() for e in repo.list_evidence("job-1")),
            key=lambda d: d["id"],
        ),
        "interviews": sorted(
            (i.model_dump() for i in repo.list_interviews("job-1")),
            key=lambda d: d["id"],
        ),
        "quotes": sorted(
            (q.model_dump() for i in repo.list_interviews("job-1") for q in repo.list_quotes(i.id)),
            key=lambda d: d["id"],
        ),
    }


def _seed(repo: Repository) -> None:
    """Write one of every entity and one cascade, through the repository API."""
    repo.add_job(Job(id="job-1", name="Onboard customers"))
    repo.add_step(Step(id="step-1", job_id="job-1", name="Prepare", order=3))
    repo.add_outcome(
        Outcome(
            id="outcome-1",
            job_id="job-1",
            step_id="step-1",
            statement="Minimize the time it takes to onboard",
            importance=8.0,
            satisfaction=4.0,
            opportunity_score=12.0,
        )
    )
    repo.add_customer_outcome(
        CustomerOutcome(
            id="co-1",
            job_id="job-1",
            customer_value=CustomerValue(
                direction=Direction.MINIMIZE,
                unit_of_measure="minutes",
                object_of_control="time to onboard",
                statement="Minimize the time it takes to onboard",
                importance=8.0,
                satisfaction=4.0,
            ),
            business_value=BusinessValue(
                category=BusinessImpactCategory.REVENUE_GROWTH,
                statement="Increase expansion revenue",
            ),
        )
    )
    repo.add_evidence(
        Evidence(
            id="ev-1",
            source_name="Interview 1",
            source_kind="interview",
            name="quote",
            content="It takes forever to get set up.",
            job_id="job-1",
            outcome_id="outcome-1",
            raw={"interview_id": "interview-1", "quote_id": "quote-1"},
        )
    )
    repo.add_interview(
        Interview(
            id="interview-1",
            job_id="job-1",
            title="Ana — onboarding",
            participant_label="Ana",
        )
    )
    repo.add_quote(
        InterviewQuote(
            id="quote-1",
            interview_id="interview-1",
            text="It takes forever to get set up.",
            ordinal=0,
        )
    )


def test_in_memory_and_sqlite_agree_on_a_full_seed(tmp_path) -> None:
    memory = InMemoryRepository()
    _seed(memory)

    sqlite = SQLiteRepository(str(tmp_path / "odi.db"))
    _seed(sqlite)

    assert _snapshot(sqlite) == _snapshot(memory)


def test_sqlite_reload_reproduces_the_same_state(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    _seed(repo)
    live = _snapshot(repo)

    repo.reload()
    assert _snapshot(repo) == live

    reopened = SQLiteRepository(db)
    assert _snapshot(reopened) == live


def test_interview_delete_cascade_survives_replay(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    _seed(repo)
    repo.add_quote(
        InterviewQuote(id="quote-2", interview_id="interview-1", text="Second", ordinal=1)
    )
    repo.add_interview(Interview(id="interview-2", title="Other", participant_label="Bo"))
    repo.add_quote(
        InterviewQuote(id="quote-3", interview_id="interview-2", text="Keep me", ordinal=0)
    )

    removed = repo.delete_interview("interview-1")
    assert sorted(removed) == ["quote-1", "quote-2"]

    after_delete = _snapshot(repo)
    repo.reload()
    assert _snapshot(repo) == after_delete
    # The other interview and its quote are untouched.
    assert repo.get_quote("quote-3") is not None
    assert repo.get_interview("interview-2") is not None


def test_job_delete_cascades_interviews_and_quotes(tmp_path) -> None:
    for repo in (InMemoryRepository(), SQLiteRepository(str(tmp_path / "odi.db"))):
        _seed(repo)
        assert repo.delete_job("job-1") is True
        assert repo.get_interview("interview-1") is None
        assert repo.get_quote("quote-1") is None
        assert repo.list_interviews() == []


@pytest.mark.parametrize(
    "entity",
    [
        "jobs",
        "steps",
        "outcomes",
        "customer_outcomes",
        "evidence",
        "interviews",
        "quotes",
    ],
)
def test_every_entity_round_trips(tmp_path, entity: str) -> None:
    """A new entity with no SQLite link fails here, not silently on replay."""
    sqlite = SQLiteRepository(str(tmp_path / "odi.db"))
    _seed(sqlite)
    assert _snapshot(sqlite)[entity], f"{entity} did not persist"


def _legacy_store(path: str) -> None:
    """A store written before interviews existed: jobs/outcomes only."""
    repo = SQLiteRepository(path)
    repo.add_job(Job(id="job-1", name="Legacy"))
    repo.add_outcome(
        Outcome(
            id="outcome-1",
            job_id="job-1",
            statement="Minimize the time it takes to onboard",
            importance=5.0,
            satisfaction=5.0,
        )
    )


def test_legacy_store_without_interviews_opens_cleanly(tmp_path) -> None:
    db = str(tmp_path / "legacy.db")
    _legacy_store(db)
    reopened = SQLiteRepository(db)
    assert reopened.list_interviews() == []
    assert reopened.list_quotes("anything") == []
    assert reopened.get_job("job-1") is not None
