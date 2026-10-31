"""The Pillar-2 (ALH-7) integration contract, end to end over one store.

Every increment has its own focused tests. This module pins the *pillar-level*
acceptance sentence instead: one explicit fixture is imported with per-outcome
counts, persisted and replayed, ranked without mixing absent scores into zeroes,
explained with recorded arithmetic/method, and shown with caveats -- while an
invalid import leaves the prior state unchanged and a score edit invalidates a
stale band. If two increments ever disagree across the seam, this fails.

The store is SQLite so "persisted and replayed" is a real reopen, not a dict.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.repository import Repository
from agentic_odi_core.services import ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository

_STATEMENT = "Minimize the time to publish when a plugin is ready."


@pytest.fixture
def repo(tmp_path: Path) -> Repository:
    return SQLiteRepository(str(tmp_path / "odi.db"))


def _reopen(repo: Repository) -> ODIService:
    """A fresh service over the same store, as a restarted process would build."""
    if isinstance(repo, SQLiteRepository):
        repo.reload()
    return ODIService(repo)


def _rows(outcome_id: str, count: int, importance: float, satisfaction: float):
    return [
        {
            "outcome_id": outcome_id,
            "importance": importance,
            "satisfaction": satisfaction,
            "respondent_id": f"r{i}",
        }
        for i in range(count)
    ]


def test_one_fixture_imports_ranks_explains_and_caves_over_a_replay(
    repo: Repository,
) -> None:
    service = ODIService(repo)
    job = service.add_job("Publish a plugin")

    # A bare estimate: it has a score but no sample, so it is not evidence.
    estimate = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0)
    # An unscored outcome: it must be counted, never ranked as a zero.
    unscored = service.add_outcome(
        job.id, "Minimize the cost to debug when a build breaks.", 5.0, 5.0
    )
    service.update_outcome(unscored.id, {"importance": None, "satisfaction": None})

    # 1. Import one fixture with per-outcome counts and a real spread.
    rows = [
        {
            "outcome_id": estimate.id,
            "importance": 10.0 if i % 2 else 6.0,
            "satisfaction": 2.0 if i % 2 else 8.0,
            "respondent_id": f"r{i}",
        }
        for i in range(40)
    ]
    service.import_survey(rows)

    # 2. Persisted and replayed: a reopened service sees the same evidence.
    replayed = _reopen(repo)
    landed = replayed.get_outcome(estimate.id)
    assert landed is not None
    assert (landed.importance_n, landed.satisfaction_n) == (40, 40)
    assert landed.score_method == "survey"
    assert landed.opportunity_low is not None and landed.opportunity_high is not None
    assert landed.opportunity_high > landed.opportunity_low

    # 3. Ranked without mixing absent scores into zeroes: the measured survey
    #    outranks the unscored outcome, which is counted but never a zero.
    ranking = replayed.rank_outcomes_for_job(job.id)
    assert ranking["counts"] == {"measured": 1, "thin": 0, "none": 1, "total": 2}
    measured_ids = [entry["id"] for entry in ranking["sections"]["measured"]]
    none_ids = [entry["id"] for entry in ranking["sections"]["none"]]
    assert measured_ids == [estimate.id]
    assert none_ids == [unscored.id]
    unscored_entry = ranking["sections"]["none"][0]
    assert unscored_entry["opportunity_score"] is None
    assert unscored_entry["confidence"] == "none"

    # 4. Explained with recorded arithmetic/method: the ranking entry carries the
    #    same numbers a reviewer can recompute, and the history records the method.
    entry = ranking["sections"]["measured"][0]
    assert entry["score_method"] == "survey"
    assert entry["importance_n"] == 40
    assert landed.importance is not None and landed.satisfaction is not None
    assert entry["opportunity_score"] == pytest.approx(
        landed.importance + max(landed.importance - landed.satisfaction, 0.0)
    )
    history = replayed.get_score_history(estimate.id)
    assert history[-1].method == "survey"
    assert history[-1].opportunity_score == landed.opportunity_score

    # 5. Shown with caveats: the band is reported with its provenance, not as a
    #    bare point, and the class names how much evidence stands behind it.
    assert entry["confidence"] == "measured"
    assert landed.interval_n == 40
    assert landed.interval_seed is not None
    assert landed.interval_confidence_level is not None
    assert landed.interval_computed_at

    # 6. An invalid import leaves the prior state unchanged.
    with pytest.raises(ValidationError):
        replayed.import_survey(_rows("no-such-outcome", 40, 8.0, 4.0))
    still = _reopen(repo).get_outcome(estimate.id)
    assert still is not None
    assert still.opportunity_score == landed.opportunity_score
    assert still.opportunity_low == landed.opportunity_low

    # 7. A score edit invalidates the stale band in the same write. (The import
    #    landed a satisfaction mean of exactly 5.0, so edit to a different value.)
    edited = replayed.update_outcome(estimate.id, {"satisfaction": 6.0})
    assert edited.opportunity_low is None
    assert edited.opportunity_high is None
    assert edited.interval_n is None
    assert edited.interval_seed is None
    assert edited.interval_confidence_level is None
    assert edited.interval_computed_at is None
