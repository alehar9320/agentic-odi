"""Persistence parity: in-memory and SQLite/replay agree on the new entities.

The epic's persistence checklist says a new entity touches every link or the
replay diverges silently. These tests build the same fixture twice — once on
``InMemoryRepository``, once on ``SQLiteRepository`` — and assert the two
stores read back identical ``Bet`` and ``ScoreSnapshot`` state, including the
baseline a bet captured at creation and the snapshots behind a review.
"""

from __future__ import annotations

from datetime import date

from agentic_odi_core.models import BetStatus
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository

_STATEMENT = "Minimize the time it takes to publish a plugin when a release is ready"


def _build(service: ODIService):
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0, at="2026-01-01T00:00:00Z")
    decision = service.record_decision(
        job.id,
        [outcome.id],
        rationale="Publishing speed blocks every release.",
        decided_by="alex",
        decided_at="2026-01-02T00:00:00Z",
    )
    bet = service.record_bet(
        decision.id,
        outcome.id,
        "Publishing gets under 5 minutes",
        target=6.0,
        measure_by="2026-04-01",
        at="2026-01-02T01:00:00Z",
    )
    service.update_outcome(outcome.id, {"satisfaction": 4.5}, at="2026-03-01T00:00:00Z")
    service.advance_bet(bet.id, "running")
    return job, outcome, decision, bet


def _snapshot_state(service: ODIService):
    """The replayed state with random ids stripped, so two builds compare."""

    def strip(record: dict) -> dict:
        return {k: v for k, v in record.items() if not k.endswith("_id") and k != "id"}

    return (
        [strip(b.model_dump(mode="json")) for b in service.list_bets()],
        [strip(s.model_dump(mode="json")) for s in service.list_score_snapshots()],
    )


def test_in_memory_and_sqlite_read_back_the_same_bets_and_snapshots(tmp_path) -> None:
    memory_service = ODIService(InMemoryRepository())
    _build(memory_service)

    path = str(tmp_path / "parity.db")
    sqlite_service = ODIService(SQLiteRepository(db_path=path))
    _build(sqlite_service)
    sqlite_service.repo.commit()
    sqlite_service.repo.close()

    # Replay from disk, so the assertion is over replayed state, not live state.
    replayed = ODIService(SQLiteRepository(db_path=path))
    assert _snapshot_state(replayed) == _snapshot_state(memory_service)
    replayed.repo.close()


def test_a_bet_baseline_does_not_drift_across_replay(tmp_path) -> None:
    path = str(tmp_path / "baseline.db")
    service = ODIService(SQLiteRepository(db_path=path))
    _, outcome, _, bet = _build(service)
    created = service.get_bet(bet.id)
    assert created is not None
    captured = created.baseline
    service.repo.commit()
    service.repo.close()

    replayed = ODIService(SQLiteRepository(db_path=path))
    reread = replayed.get_bet(bet.id)
    assert reread is not None
    assert reread.baseline == captured
    assert reread.status is BetStatus.RUNNING
    # The live score moved; the baseline did not follow it.
    live = replayed.get_outcome(outcome.id)
    assert live is not None and live.satisfaction == 4.5
    assert reread.baseline != live.satisfaction
    replayed.repo.close()


def test_a_review_reads_the_same_after_replay(tmp_path) -> None:
    path = str(tmp_path / "review.db")
    service = ODIService(SQLiteRepository(db_path=path))
    _, _, decision, _ = _build(service)
    before = service.review_decision(decision.id, today=date(2026, 4, 1))
    service.repo.commit()
    service.repo.close()

    replayed = ODIService(SQLiteRepository(db_path=path))
    after = replayed.review_decision(decision.id, today=date(2026, 4, 1))
    assert [(o.state, o.satisfaction_change) for o in after.outcomes] == [
        (o.state, o.satisfaction_change) for o in before.outcomes
    ]
    replayed.repo.close()


def test_deleting_a_job_cascades_identically_in_both_stores(tmp_path) -> None:
    memory_service = ODIService(InMemoryRepository())
    job, _, _, _ = _build(memory_service)
    memory_service.delete_job(job.id)

    path = str(tmp_path / "cascade.db")
    sqlite_service = ODIService(SQLiteRepository(db_path=path))
    job2, _, _, _ = _build(sqlite_service)
    sqlite_service.delete_job(job2.id)
    sqlite_service.repo.commit()
    sqlite_service.repo.close()

    replayed = ODIService(SQLiteRepository(db_path=path))
    assert replayed.list_bets() == memory_service.list_bets() == []
    assert replayed.list_score_snapshots() == memory_service.list_score_snapshots() == []
    replayed.repo.close()


def _normalise(record: dict) -> dict:
    """Replace random ids with their position so two builds compare.

    A segment's member ids are freshly generated per build, so the cross-store
    assertion is over structure: the same name, criterion, origin and *shape* of
    membership. Reload parity (below) keeps the real ids.
    """
    normalised = {k: v for k, v in record.items() if not k.endswith("_id") and k != "id"}
    members = normalised.pop("outcome_ids", None)
    if members is not None:
        normalised["member_count"] = len(members)
    return normalised


def _build_segment(service: ODIService):
    """One job with three underserved outcomes, a segment, and a strategy."""
    job = service.add_job("Publish a plugin")
    outcomes = [
        service.add_outcome(job.id, _STATEMENT, 9.0, 3.0, at="2026-01-01T00:00:00Z"),
        service.add_outcome(
            job.id,
            "Minimize the cost of supporting a plugin when it ships",
            9.0,
            2.0,
            at="2026-01-01T00:00:00Z",
        ),
        service.add_outcome(
            job.id,
            "Minimize the time it takes to resolve a support ticket after a bug",
            9.0,
            4.0,
            at="2026-01-01T00:00:00Z",
        ),
    ]
    segment = service.add_segment(
        job.id,
        "Release engineers",
        "They own the publish step.",
        [o.id for o in outcomes],
        origin="manual",
    )
    strategy = service.choose_strategy(
        segment.id,
        "differentiated",
        rationale="The publish path blocks every release.",
        expected_effect="Shorter publish time.",
        chosen_at="2026-01-05T00:00:00Z",
    )
    return job, outcomes, segment, strategy


def test_in_memory_and_sqlite_read_back_the_same_segments_and_strategies(tmp_path) -> None:
    memory_service = ODIService(InMemoryRepository())
    _, _, memory_segment, memory_strategy = _build_segment(memory_service)

    path = str(tmp_path / "segments.db")
    sqlite_service = ODIService(SQLiteRepository(db_path=path))
    _, _, sqlite_segment, sqlite_strategy = _build_segment(sqlite_service)
    sqlite_service.repo.commit()
    sqlite_service.repo.close()

    replayed = ODIService(SQLiteRepository(db_path=path))
    stored_segment = replayed.get_segment(sqlite_segment.id)
    assert stored_segment is not None
    assert _normalise(stored_segment.model_dump(mode="json")) == _normalise(
        memory_segment.model_dump(mode="json")
    )
    stored_strategy = replayed.get_strategy(sqlite_strategy.id)
    assert stored_strategy is not None
    assert _normalise(stored_strategy.model_dump(mode="json")) == _normalise(
        memory_strategy.model_dump(mode="json")
    )
    replayed.repo.close()


def test_deleting_a_segment_removes_its_strategies_across_replay(tmp_path) -> None:
    path = str(tmp_path / "segment-delete.db")
    service = ODIService(SQLiteRepository(db_path=path))
    _, outcomes, segment, _ = _build_segment(service)
    service.delete_segment(segment.id)
    service.repo.commit()
    service.repo.close()

    replayed = ODIService(SQLiteRepository(db_path=path))
    assert replayed.list_segments() == []
    assert replayed.list_strategies() == []
    # The outcomes survive: the segment was a lens, not their owner.
    assert all(replayed.get_outcome(o.id) is not None for o in outcomes)
    replayed.repo.close()
