"""A field added on one persistence link must exist on all of them.

The persistence checklist requires models, the in-memory repository and the
SQLite repository to round-trip the same fields. This module fails loudly when a
field is added to one and forgotten on another, instead of letting the two
backends diverge silently after a reload.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentic_odi_core.models import Outcome
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
