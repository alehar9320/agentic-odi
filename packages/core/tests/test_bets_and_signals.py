"""Tests for the Pillar 4 spine: decisions, snapshots, bets and signals.

These cover the happy path, the boundaries, the empty store, refusals and
repeat reads for the entities E1/E2/E3 introduce.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from agentic_odi_core.errors import ConflictError, NotFoundError, ValidationError
from agentic_odi_core.models import BetStatus, SignalKind
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService

STATEMENT = "Minimize the time it takes to onboard a customer when they sign up"


@pytest.fixture
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _job_with_outcome(service: ODIService, *, importance: float = 8.0, satisfaction: float = 4.0):
    job = service.add_job("Onboard customers")
    outcome = service.add_outcome(job.id, STATEMENT, importance, satisfaction)
    return job, outcome


def _decision_for(service: ODIService, job, outcome):
    return service.record_decision(job.id, [outcome.id], "The gap is largest", "alex")


# -- Decisions --------------------------------------------------------------


def test_record_decision_and_read_back(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    assert decision.chosen_outcome_ids == [outcome.id]
    assert service.list_decisions(job.id) == [decision]


def test_a_later_decision_supersedes_and_both_stay_readable(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    first = _decision_for(service, job, outcome)
    second = service.record_decision(job.id, [outcome.id], "Reconsidered", "alex")

    history = service.list_decisions(job.id)
    assert [d.id for d in history] == [first.id, second.id]
    superseded = service.get_decision(first.id)
    assert superseded.superseded_by == second.id
    assert superseded.superseded_at is not None
    latest = service.latest_decision(job.id)
    assert latest is not None and latest.id == second.id


def test_decision_requires_a_choice_and_a_rationale(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    with pytest.raises(ValidationError):
        service.record_decision(job.id, [], "why", "alex")
    with pytest.raises(ValidationError):
        service.record_decision(job.id, [outcome.id], "   ", "alex")
    with pytest.raises(ValidationError):
        service.record_decision(job.id, [outcome.id], "why", "")


def test_decision_refuses_foreign_or_overlapping_outcomes(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    other_job, other_outcome = _job_with_outcome(service)
    with pytest.raises(ValidationError):
        service.record_decision(job.id, [other_outcome.id], "why", "alex")
    with pytest.raises(NotFoundError):
        service.record_decision(job.id, ["missing"], "why", "alex")
    with pytest.raises(ValidationError):
        service.record_decision(
            job.id,
            [outcome.id],
            "why",
            "alex",
            rejected=[{"outcome_id": outcome.id, "reason": "both"}],
        )


def test_rejected_outcome_needs_a_reason(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    second = service.add_outcome(job.id, STATEMENT.replace("sign up", "check out"), 5, 5)
    decision = service.record_decision(
        job.id,
        [outcome.id],
        "why",
        "alex",
        rejected=[{"outcome_id": second.id, "reason": "smaller gap"}],
    )
    assert decision.rejected[0].reason == "smaller gap"


# -- Score snapshots --------------------------------------------------------


def test_snapshots_are_append_only_and_ordered(service: ODIService) -> None:
    _job, outcome = _job_with_outcome(service)
    first = service.record_score_snapshot(outcome.id)
    service.update_outcome(outcome.id, {"satisfaction": 6.0})
    second = service.record_score_snapshot(outcome.id)
    history = service.list_score_snapshots(outcome.id)
    assert [s.id for s in history] == [first.id, second.id]
    assert history[0].satisfaction == 4.0
    assert history[1].satisfaction == 6.0


def test_outcome_delta_is_signed_and_explicit_when_unavailable(service: ODIService) -> None:
    _job, outcome = _job_with_outcome(service)
    unavailable = service.outcome_delta(outcome.id)
    assert unavailable["available"] is False

    service.record_score_snapshot(outcome.id)
    service.update_outcome(outcome.id, {"satisfaction": 6.0})
    service.record_score_snapshot(outcome.id)
    delta = service.outcome_delta(outcome.id)
    assert delta["available"] is True
    assert delta["delta"]["satisfaction"] == 2.0
    assert delta["delta"]["opportunity"] == -2.0


def test_snapshot_note_is_bounded(service: ODIService) -> None:
    _job, outcome = _job_with_outcome(service)
    with pytest.raises(ValidationError):
        service.record_score_snapshot(outcome.id, note="x" * 501)


# -- Bets -------------------------------------------------------------------


def test_create_bet_freezes_the_baseline(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "Time drops", 12.0, date(2026, 6, 1))
    assert bet.baseline == 12.0  # importance 8, satisfaction 4 → 8 + 4
    assert bet.target == 12.0
    assert bet.status is BetStatus.PLANNED

    # Re-scoring the outcome must not move the stored baseline.
    service.update_outcome(outcome.id, {"importance": 3.0, "satisfaction": 3.0})
    assert service.get_bet(bet.id).baseline == 12.0


def test_bet_requires_a_decision_that_chose_the_outcome(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    with pytest.raises(NotFoundError):
        service.create_bet("missing", outcome.id, "h", 1.0, date(2026, 6, 1))
    other = service.add_outcome(job.id, STATEMENT.replace("sign up", "sign in"), 5, 5)
    decision = _decision_for(service, job, outcome)
    with pytest.raises(ValidationError):
        service.create_bet(decision.id, other.id, "h", 1.0, date(2026, 6, 1))


def test_bet_refuses_blank_hypothesis_and_nonfinite_target(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    with pytest.raises(ValidationError):
        service.create_bet(decision.id, outcome.id, "  ", 1.0, date(2026, 6, 1))
    with pytest.raises(ValidationError):
        service.create_bet(decision.id, outcome.id, "h", float("inf"), date(2026, 6, 1))


@pytest.mark.parametrize(
    ("start", "target", "legal"),
    [
        (BetStatus.PLANNED, BetStatus.RUNNING, True),
        (BetStatus.PLANNED, BetStatus.ABANDONED, True),
        (BetStatus.PLANNED, BetStatus.MEASURED, False),
        (BetStatus.RUNNING, BetStatus.MEASURED, True),
        (BetStatus.RUNNING, BetStatus.ABANDONED, False),
    ],
)
def test_bet_transitions(service: ODIService, start, target, legal) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))
    if start is BetStatus.RUNNING:
        service.transition_bet(bet.id, BetStatus.RUNNING)
    if legal:
        assert service.transition_bet(bet.id, target).status is target
    else:
        with pytest.raises(ConflictError):
            service.transition_bet(bet.id, target)


def test_terminal_transition_names_legal_successors(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))
    service.transition_bet(bet.id, BetStatus.ABANDONED)
    with pytest.raises(ConflictError, match="terminal"):
        service.transition_bet(bet.id, BetStatus.RUNNING)


# -- Measurement ------------------------------------------------------------


def test_measure_bet_is_no_data_without_an_eligible_snapshot(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 20.0, date(2026, 6, 1))
    result = service.measure_bet(bet.id, looked_at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    assert result["result"] == "no_data"
    assert "observed" not in result


def test_measure_bet_met_and_missed(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))

    service.update_outcome(outcome.id, {"importance": 9.0, "satisfaction": 2.0})  # 16
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    met = service.measure_bet(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert met["result"] == "met"
    assert met["observed"] == 16.0
    assert met["delta"] == 4.0

    service.update_outcome(outcome.id, {"importance": 5.0, "satisfaction": 5.0})  # 5
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 4, tzinfo=timezone.utc))
    missed = service.measure_bet(bet.id, looked_at=datetime(2026, 6, 5, tzinfo=timezone.utc))
    assert missed["result"] == "missed"
    assert missed["observed"] == 5.0


def test_measure_bet_ignores_snapshots_before_measure_by(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 10))
    service.update_outcome(outcome.id, {"importance": 9.0, "satisfaction": 2.0})
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 1, tzinfo=timezone.utc))
    result = service.measure_bet(bet.id, looked_at=datetime(2026, 6, 11, tzinfo=timezone.utc))
    assert result["result"] == "no_data"


def test_measuring_twice_writes_nothing(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))
    service.update_outcome(outcome.id, {"importance": 9.0, "satisfaction": 2.0})
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    before = len(service.repo.score_snapshots)
    first = service.measure_bet(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    second = service.measure_bet(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert first == second
    assert len(service.repo.score_snapshots) == before
    assert service.get_bet(bet.id).status is BetStatus.PLANNED


# -- Signals ----------------------------------------------------------------


def test_empty_store_has_no_signals(service: ODIService) -> None:
    assert service.emit_know_signals() == []
    assert service.list_signals() == []


def test_emission_is_idempotent(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    service.create_bet(decision.id, outcome.id, "h", 12.0, date(2020, 1, 1))
    first = service.emit_know_signals(now=datetime(2026, 6, 1, tzinfo=timezone.utc))
    after_first = len(service.list_signals())
    second = service.emit_know_signals(now=datetime(2026, 6, 1, tzinfo=timezone.utc))
    assert [s.id for s in first] == [s.id for s in second]
    assert len(service.list_signals()) == after_first


def test_a_moved_score_produces_exactly_one_signal(service: ODIService) -> None:
    _job, outcome = _job_with_outcome(service)
    service.record_score_snapshot(outcome.id, at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    service.update_outcome(outcome.id, {"satisfaction": 8.0})
    service.record_score_snapshot(outcome.id, at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    moved = [s for s in service.list_signals() if s.kind is SignalKind.SCORE_MOVED]
    assert len(moved) == 1
    assert moved[0].subject_id == outcome.id
    assert moved[0].magnitude == -4.0


def test_a_due_bet_produces_one_signal(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "Time drops", 12.0, date(2026, 1, 1))
    service.emit_know_signals(now=datetime(2026, 2, 1, tzinfo=timezone.utc))
    due = [s for s in service.list_signals() if s.kind is SignalKind.BET_DUE]
    assert len(due) == 1
    assert due[0].subject_id == bet.id


def test_decision_superseded_signal(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    first = _decision_for(service, job, outcome)
    service.record_decision(job.id, [outcome.id], "Reconsidered", "alex")
    superseded = [s for s in service.list_signals() if s.kind is SignalKind.DECISION_SUPERSEDED]
    assert [s.subject_id for s in superseded] == [first.id]


def test_coverage_gap_signal_for_uncovered_stages(service: ODIService) -> None:
    _job, _outcome = _job_with_outcome(service)
    service.emit_know_signals(now=datetime(2026, 6, 1, tzinfo=timezone.utc))
    gaps = [s for s in service.list_signals() if s.kind is SignalKind.COVERAGE_GAP]
    assert len(gaps) == 8  # all eight universal stages are uncovered


def test_should_notify_respects_threshold_and_enabled(service: ODIService) -> None:
    from agentic_odi_core.models import NotificationRule, Signal
    from agentic_odi_core.signals import should_notify

    small = Signal(
        kind=SignalKind.SCORE_MOVED,
        title="moved",
        subject_kind="outcome",
        subject_id="o",
        magnitude=0.2,
        fingerprint="f-small",
    )
    assert should_notify(small) is False

    big = small.model_copy(update={"magnitude": -1.2})
    assert should_notify(big) is True

    gap = small.model_copy(
        update={"kind": SignalKind.COVERAGE_GAP, "magnitude": None, "fingerprint": "f-gap"}
    )
    assert should_notify(gap) is False
    rules = {SignalKind.COVERAGE_GAP: NotificationRule(kind=SignalKind.COVERAGE_GAP, enabled=True)}
    assert should_notify(gap, rules) is True


def test_notification_rules_have_documented_defaults(service: ODIService) -> None:
    rules = {rule.kind: rule for rule in service.list_notification_rules()}
    assert rules[SignalKind.SCORE_MOVED].threshold == 0.5
    assert rules[SignalKind.COVERAGE_GAP].enabled is False
    updated = service.set_notification_rule(SignalKind.SCORE_MOVED, threshold=1.0)
    assert updated.threshold == 1.0
    assert {rule.kind: rule for rule in service.list_notification_rules()}[
        SignalKind.SCORE_MOVED
    ].threshold == 1.0


def test_emission_records_only_what_the_store_proves(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    service.create_bet(decision.id, outcome.id, "h", 12.0, date(2020, 1, 1))
    service.emit_know_signals(now=datetime(2026, 6, 1, tzinfo=timezone.utc))
    before = len(service.list_signals())
    service.emit_know_signals(now=datetime(2026, 6, 1, tzinfo=timezone.utc))
    assert len(service.list_signals()) == before


def test_measure_bet_excludes_future_dated_snapshots(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))
    service.update_outcome(outcome.id, {"importance": 9.0, "satisfaction": 2.0})
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    # A snapshot dated after the moment we look must not be used.
    service.record_score_snapshot(outcome.id, at=datetime(2099, 1, 1, tzinfo=timezone.utc))
    result = service.measure_bet(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert result["result"] == "met"
    assert result["observed"] == 16.0
