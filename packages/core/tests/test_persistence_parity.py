"""Persistence parity: every adapter must replay the same domain state.

Each entity is written through one adapter, then read back through a fresh
adapter over the same store (in-memory reset, SQLite restart, and a second
SQLite connection). A missed persistence link shows up here as a diverging
snapshot instead of a silent replay difference.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from agentic_odi_core.models import (
    Bet,
    BetStatus,
    Decision,
    DecisionConfidence,
    NotificationRule,
    Outcome,
    RejectedOutcome,
    ScoreSnapshot,
    SignalKind,
)
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository

WHEN = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def _seed(service: ODIService) -> dict[str, str]:
    job = service.add_job("Onboard customers")
    outcome = service.add_outcome(
        job.id,
        "Minimize the time it takes to onboard a customer when they sign up",
        8.0,
        4.0,
    )
    other = service.add_outcome(
        job.id,
        "Minimize the time it takes to close a ticket when support is busy",
        6.0,
        6.0,
    )
    snapshot = service.record_score_snapshot(outcome.id, at=WHEN, method="survey")
    decision = service.record_decision(
        job.id,
        [outcome.id],
        "The gap is largest",
        "alex",
        rejected=[{"outcome_id": other.id, "reason": "smaller gap"}],
        confidence=DecisionConfidence.HIGH,
    )
    bet = service.create_bet(decision.id, outcome.id, "Time drops", 12.0, date(2026, 7, 1))
    service.transition_bet(bet.id, BetStatus.RUNNING)
    service.set_notification_rule(SignalKind.SCORE_MOVED, threshold=0.75)
    return {
        "job": job.id,
        "outcome": outcome.id,
        "other": other.id,
        "snapshot": snapshot.id,
        "decision": decision.id,
        "bet": bet.id,
    }


def _assert_state(service: ODIService, ids: dict[str, str]) -> None:
    bet = service.get_bet(ids["bet"])
    assert bet.baseline == 12.0
    assert bet.status is BetStatus.RUNNING
    assert bet.measure_by == date(2026, 7, 1)

    decision = service.get_decision(ids["decision"])
    assert decision.chosen_outcome_ids == [ids["outcome"]]
    assert decision.rejected == [RejectedOutcome(outcome_id=ids["other"], reason="smaller gap")]
    assert decision.confidence is DecisionConfidence.HIGH

    snapshots = service.list_score_snapshots(ids["outcome"])
    assert [s.id for s in snapshots] == [ids["snapshot"]]
    assert snapshots[0].method == "survey"
    assert snapshots[0].opportunity_score == 12.0

    rules = {r.kind: r for r in service.list_notification_rules()}
    assert rules[SignalKind.SCORE_MOVED].threshold == 0.75

    # A signal's job survives replay, so a scoped feed is stable across adapters.
    signals = {s.kind: s for s in service.list_signals(limit=1000)}
    assert signals[SignalKind.JOB_ADDED].job_id == ids["job"]


def test_in_memory_parity() -> None:
    repo = InMemoryRepository()
    service = ODIService(repo)
    ids = _seed(service)
    _assert_state(service, ids)


def test_sqlite_replay_parity(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    writer = ODIService(SQLiteRepository(db))
    ids = _seed(writer)

    # A brand-new adapter over the same file replays the event log.
    reader = ODIService(SQLiteRepository(db))
    _assert_state(reader, ids)


def test_sqlite_reload_parity(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    service = ODIService(repo)
    ids = _seed(service)
    repo.reload()
    _assert_state(service, ids)


def test_entities_are_reachable_through_repository_protocol(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    service = ODIService(repo)
    ids = _seed(service)

    assert isinstance(repo.get_bet(ids["bet"]), Bet)
    assert isinstance(repo.get_decision(ids["decision"]), Decision)
    assert isinstance(repo.get_score_snapshot(ids["snapshot"]), ScoreSnapshot)
    assert isinstance(repo.get_outcome(ids["outcome"]), Outcome)
    assert isinstance(repo.list_notification_rules()[0], NotificationRule)


def test_decision_supersession_survives_restart(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    writer = ODIService(SQLiteRepository(db))
    job = writer.add_job("Onboard")
    outcome = writer.add_outcome(
        job.id,
        "Minimize the time it takes to onboard a customer when they sign up",
        8.0,
        4.0,
    )
    first = writer.record_decision(job.id, [outcome.id], "first", "alex")
    second = writer.record_decision(job.id, [outcome.id], "second", "alex")

    reader = ODIService(SQLiteRepository(db))
    replayed = reader.get_decision(first.id)
    assert replayed.superseded_by == second.id
    assert replayed.superseded_at is not None


@pytest.mark.parametrize("bet_status", [BetStatus.PLANNED, BetStatus.RUNNING])
def test_bet_status_round_trips_through_sqlite(tmp_path, bet_status) -> None:
    db = str(tmp_path / "odi.db")
    writer = ODIService(SQLiteRepository(db))
    job = writer.add_job("Onboard")
    outcome = writer.add_outcome(
        job.id,
        "Minimize the time it takes to onboard a customer when they sign up",
        8.0,
        4.0,
    )
    decision = writer.record_decision(job.id, [outcome.id], "why", "alex")
    bet = writer.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 7, 1))
    if bet_status is BetStatus.RUNNING:
        writer.transition_bet(bet.id, BetStatus.RUNNING)

    reader = ODIService(SQLiteRepository(db))
    assert reader.get_bet(bet.id).status is bet_status
