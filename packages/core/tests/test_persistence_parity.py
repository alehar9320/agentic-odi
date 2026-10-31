"""A field added on one persistence link must exist on all of them.

The persistence checklist requires models, the in-memory repository and the
SQLite repository to round-trip the same fields. This module fails loudly when a
field is added to one and forgotten on another, instead of letting the two
backends diverge silently after a reload.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentic_odi_core.models import Outcome, ScoreSnapshot
from agentic_odi_core.repository import InMemoryRepository, Repository
from agentic_odi_core.sqlite_repository import SQLiteRepository

_STATEMENT = "Minimize the time it takes to onboard a new engineer."


def _seed(repo: Repository) -> Outcome:
    return repo.add_outcome(
        Outcome(
            job_id="job-1",
            statement=_STATEMENT,
            importance=8.0,
            satisfaction=6.0,
            importance_n=40,
            satisfaction_n=40,
            score_method="survey",
        )
    )


@pytest.fixture(params=["memory", "sqlite"])
def repo(request: pytest.FixtureRequest, tmp_path: Path) -> Repository:
    if request.param == "memory":
        return InMemoryRepository()
    return SQLiteRepository(str(tmp_path / "odi.db"))


def _reopen(repo: Repository) -> Repository:
    """Refresh a repository's view of its store.

    SQLite re-reads the event log from disk; the in-memory store has no external
    store, so its live dicts are already the source of truth.
    """
    if isinstance(repo, SQLiteRepository):
        repo.reload()
    return repo


def test_sample_metadata_survives_every_repository(repo: Repository) -> None:
    outcome = _seed(repo)
    loaded = _reopen(repo).get_outcome(outcome.id)
    assert loaded is not None
    assert (loaded.importance_n, loaded.satisfaction_n, loaded.score_method) == (40, 40, "survey")


def test_unknown_counts_stay_unknown_after_reload(repo: Repository) -> None:
    outcome = repo.add_outcome(
        Outcome(job_id="job-1", statement=_STATEMENT, importance=8.0, satisfaction=6.0)
    )
    loaded = _reopen(repo).get_outcome(outcome.id)
    assert loaded is not None
    assert loaded.importance_n is None
    assert loaded.satisfaction_n is None
    assert loaded.score_method == "estimate"


def test_score_snapshots_survive_every_repository(repo: Repository) -> None:
    repo.add_score_snapshot(
        ScoreSnapshot(
            id="snap-1",
            outcome_id="outcome-1",
            importance=8.0,
            satisfaction=6.0,
            opportunity_score=10.0,
            importance_n=40,
            satisfaction_n=40,
            method="survey",
            note="from the Q3 survey",
        )
    )

    history = _reopen(repo).list_score_snapshots("outcome-1")

    assert len(history) == 1
    only = history[0]
    assert (only.importance, only.satisfaction, only.opportunity_score) == (8.0, 6.0, 10.0)
    assert (only.importance_n, only.satisfaction_n, only.method) == (40, 40, "survey")
    assert only.note == "from the Q3 survey"


def test_a_snapshot_note_stays_unknown_after_reload(repo: Repository) -> None:
    repo.add_score_snapshot(ScoreSnapshot(id="snap-1", outcome_id="outcome-1"))
    loaded = _reopen(repo).list_score_snapshots("outcome-1")
    assert loaded[0].note is None
    assert loaded[0].importance_n is None


def test_band_and_provenance_survive_every_repository(repo: Repository) -> None:
    outcome = repo.add_outcome(
        Outcome(
            job_id="job-1",
            statement=_STATEMENT,
            importance=8.0,
            satisfaction=6.0,
            importance_n=40,
            satisfaction_n=40,
            score_method="survey",
            opportunity_low=9.5,
            opportunity_high=11.5,
            interval_n=40,
            interval_seed=7,
            interval_confidence_level=0.95,
            interval_computed_at="2026-01-01T00:00:00Z",
        )
    )

    loaded = _reopen(repo).get_outcome(outcome.id)
    assert loaded is not None
    assert (loaded.opportunity_low, loaded.opportunity_high) == (9.5, 11.5)
    assert loaded.interval_n == 40
    assert loaded.interval_seed == 7
    assert loaded.interval_confidence_level == 0.95


def test_a_score_edit_clears_a_stale_band_on_every_repository(repo: Repository) -> None:
    from agentic_odi_core.services import ODIService

    service = ODIService(repo)
    outcome = repo.add_outcome(
        Outcome(
            job_id="job-1",
            statement="Minimize the time to onboard when a new engineer joins.",
            importance=8.0,
            satisfaction=6.0,
            importance_n=40,
            satisfaction_n=40,
            score_method="survey",
            opportunity_low=9.5,
            opportunity_high=11.5,
            interval_n=40,
        )
    )

    service.update_outcome(outcome.id, {"satisfaction": 5.0})

    loaded = _reopen(repo).get_outcome(outcome.id)
    assert loaded is not None
    assert loaded.opportunity_low is None
    assert loaded.opportunity_high is None
    assert loaded.interval_n is None
