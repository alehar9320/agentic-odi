"""A field added on one persistence link must exist on all of them.

The persistence checklist requires models, the in-memory repository and the
SQLite repository to round-trip the same fields. This module fails loudly when a
field is added to one and forgotten on another, instead of letting the two
backends diverge silently after a reload.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agentic_odi_core.models import (
    BusinessImpactCategory,
    BusinessValue,
    CandidateStatus,
    CustomerOutcome,
    CustomerValue,
    Direction,
    Evidence,
    Interview,
    InterviewQuote,
    Job,
    Outcome,
    OutcomeCandidate,
    ScoreSnapshot,
    Step,
)
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


def test_retained_survey_inputs_survive_every_repository(repo: Repository) -> None:
    from agentic_odi_core.models import SurveyInputSet

    outcome = repo.add_outcome(
        Outcome(
            job_id="job-1",
            statement=_STATEMENT,
            importance=8.0,
            satisfaction=6.0,
            importance_n=2,
            satisfaction_n=2,
            score_method="survey",
        )
    )
    pairs = [(8.0, 6.0), (3.0, 9.0)]
    repo.add_survey_input_set(
        SurveyInputSet(
            outcome_id=outcome.id,
            job_id=outcome.job_id,
            input_ref="survey-inputs-v1:test",
            pairs=pairs,
            respondent_refs=["r-1", "r-2"],
        )
    )

    loaded = _reopen(repo).get_survey_input_set(outcome.id)
    assert loaded is not None
    assert loaded.pairs == pairs
    assert loaded.respondent_refs == ["r-1", "r-2"]
    assert loaded.input_ref == "survey-inputs-v1:test"


def test_alternatives_survive_every_repository(repo: Repository) -> None:
    from agentic_odi_core.models import Alternative, AlternativeLink

    outcome = _seed(repo)
    alternative = repo.add_alternative(
        Alternative(
            job_id=outcome.job_id,
            name="Spreadsheet",
            kind="manual",
            notes="kept by hand",
            source_kind="interview",
        )
    )
    link = repo.link_alternative(
        AlternativeLink(
            outcome_id=outcome.id, alternative_id=alternative.id, adequacy=7.0, usage_n=12
        )
    )

    reloaded = _reopen(repo)
    loaded = reloaded.get_alternative(alternative.id)
    assert loaded is not None
    assert (loaded.name, loaded.kind, loaded.notes, loaded.source_kind) == (
        "Spreadsheet",
        "manual",
        "kept by hand",
        "interview",
    )
    links = reloaded.list_alternative_links(outcome_id=outcome.id)
    assert [(item.alternative_id, item.adequacy, item.usage_n) for item in links] == [
        (alternative.id, link.adequacy, 12)
    ]


Snapshot = dict[str, Any]


def _snapshot(repo: Repository) -> Snapshot:
    """A comparable read of every entity surface the Repository exposes."""
    return {
        #: The write counter names the change a signal points at, and services
        #: fold it into their fingerprints: two backends that agree on rows but
        #: not on this still dedupe each other's signals away.
        "last_event_id": repo.last_event_id(),
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
        "outcome_candidates": sorted(
            (c.model_dump(mode="json") for c in repo.list_outcome_candidates()),
            key=lambda d: d["id"],
        ),
    }


def _seed_entities(repo: Repository) -> None:
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
    repo.add_outcome_candidate(
        OutcomeCandidate(
            id="candidate-1",
            interview_id="interview-1",
            quote_id="quote-1",
            statement="Minimize the time it takes to get set up when onboarding",
            confidence=0.6,
            status=CandidateStatus.PROPOSED,
        )
    )


def test_in_memory_and_sqlite_agree_on_a_full_seed(tmp_path) -> None:
    memory = InMemoryRepository()
    _seed_entities(memory)

    sqlite = SQLiteRepository(str(tmp_path / "odi.db"))
    _seed_entities(sqlite)

    assert _snapshot(sqlite) == _snapshot(memory)


def test_sqlite_reload_reproduces_the_same_state(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    _seed_entities(repo)
    live = _snapshot(repo)

    repo.reload()
    assert _snapshot(repo) == live

    reopened = SQLiteRepository(db)
    assert _snapshot(reopened) == live


def test_interview_delete_cascade_survives_replay(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    _seed_entities(repo)
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
    # The candidate belonged to the deleted interview.
    assert repo.get_candidate("candidate-1") is None


def test_job_delete_cascades_interviews_and_quotes(tmp_path) -> None:
    for repo in (InMemoryRepository(), SQLiteRepository(str(tmp_path / "odi.db"))):
        _seed_entities(repo)
        assert repo.delete_job("job-1") is True
        assert repo.get_interview("interview-1") is None
        assert repo.get_quote("quote-1") is None
        assert repo.list_interviews() == []
        assert repo.list_outcome_candidates() == []


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
        "outcome_candidates",
    ],
)
def test_every_entity_round_trips(tmp_path, entity: str) -> None:
    """A new entity with no SQLite link fails here, not silently on replay."""
    sqlite = SQLiteRepository(str(tmp_path / "odi.db"))
    _seed_entities(sqlite)
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
