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


def _commit_disproof(service: ODIService, bet_id: str, **overrides) -> None:
    """Commit one valid disproof condition, so a bet may move to running."""
    fields = {
        "metric": "opportunity",
        "operator": "at_or_below",
        "threshold": 11.0,
        "by_date": date(2026, 6, 1),
        "rationale": "no movement would disprove it",
    }
    fields.update(overrides)
    service.add_disproof(bet_id, fields)


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
        _commit_disproof(service, bet.id)
        service.transition_bet(bet.id, BetStatus.RUNNING)
    if target is BetStatus.RUNNING:
        _commit_disproof(service, bet.id)
    if legal:
        assert service.transition_bet(bet.id, target).status is target
    else:
        with pytest.raises(ConflictError):
            service.transition_bet(bet.id, target)


def test_a_bet_cannot_run_without_a_disproof_condition(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))
    with pytest.raises(ValidationError, match="disproof"):
        service.transition_bet(bet.id, BetStatus.RUNNING)
    # The refusal wrote nothing: the bet is still planned and has no condition.
    assert service.get_bet(bet.id).status is BetStatus.PLANNED
    assert service.get_bet(bet.id).disproof == []


def test_refused_running_transition_writes_no_event(tmp_path) -> None:
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    service = ODIService(repo)
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))
    before = len(repo.store.get_stream())
    with pytest.raises(ValidationError, match="disproof"):
        service.transition_bet(bet.id, BetStatus.RUNNING)
    assert len(repo.store.get_stream()) == before


@pytest.mark.parametrize(
    ("operator", "observed", "expected"),
    [
        # Equality is the boundary the contract pins explicitly.
        ("below", 5.0, "holding"),
        ("below", 4.0, "disproved"),
        ("at_or_below", 5.0, "disproved"),
        ("at_or_below", 6.0, "holding"),
        ("above", 5.0, "holding"),
        ("above", 6.0, "disproved"),
        ("at_or_above", 5.0, "disproved"),
        ("at_or_above", 4.0, "holding"),
    ],
)
def test_every_operator_boundary_including_equality(
    service: ODIService, operator, observed, expected
) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 20.0, date(2026, 6, 1))
    # The metric is importance directly, so the observed value is unambiguous.
    _commit_disproof(service, bet.id, metric="importance", operator=operator, threshold=5.0)
    service.update_outcome(outcome.id, {"importance": observed, "satisfaction": observed})
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    report = service.evaluate_disproof(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    line = report["conditions"][0]
    assert line["observed"] == observed
    assert line["verdict"] == expected
    assert line["snapshot_id"]
    assert line["condition"]["operator"] == operator


def test_multiple_conditions_keep_their_own_identities(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)  # opportunity 12, importance 8
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 20.0, date(2026, 6, 1))
    _commit_disproof(service, bet.id, metric="opportunity", operator="at_or_below", threshold=11.0)
    _commit_disproof(service, bet.id, metric="importance", operator="below", threshold=9.0)
    service.update_outcome(outcome.id, {"importance": 6.0, "satisfaction": 6.0})  # opp 6
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    report = service.evaluate_disproof(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    lines = report["conditions"]
    assert [line["index"] for line in lines] == [0, 1]
    assert lines[0]["verdict"] == "disproved"  # opportunity 6 <= 11
    assert lines[1]["verdict"] == "disproved"  # importance 6 < 9
    assert lines[0]["observed"] == 6.0
    assert lines[1]["observed"] == 6.0
    assert report["summary"] == {"disproved": 2, "holding": 0, "no_data": 0}


def test_evaluate_disproof_unknown_bet_id_is_not_a_verdict(service: ODIService) -> None:
    with pytest.raises(NotFoundError):
        service.evaluate_disproof("does-not-exist")


def test_disproof_conditions_are_locked_once_measured(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))
    _commit_disproof(service, bet.id)
    service.transition_bet(bet.id, BetStatus.RUNNING)
    service.transition_bet(bet.id, BetStatus.MEASURED)
    with pytest.raises(ConflictError):
        _commit_disproof(service, bet.id)
    with pytest.raises(ConflictError):
        service.remove_disproof(bet.id, 0)


def test_disproof_condition_validates_metric_operator_and_rationale(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))
    with pytest.raises(ValidationError):
        service.add_disproof(
            bet.id,
            {
                "metric": "revenue",
                "operator": "above",
                "threshold": 1.0,
                "by_date": date(2026, 6, 1),
                "rationale": "unsupported metric",
            },
        )
    with pytest.raises(ValidationError):
        service.add_disproof(
            bet.id,
            {
                "metric": "opportunity",
                "operator": "sideways",
                "threshold": 1.0,
                "by_date": date(2026, 6, 1),
                "rationale": "unsupported operator",
            },
        )
    with pytest.raises(ValidationError):
        service.add_disproof(
            bet.id,
            {
                "metric": "opportunity",
                "operator": "above",
                "threshold": 1.0,
                "by_date": date(2026, 6, 1),
                "rationale": "   ",
            },
        )
    with pytest.raises(ValidationError):
        service.add_disproof(
            bet.id,
            {
                "metric": "opportunity",
                "operator": "above",
                "threshold": float("inf"),
                "by_date": date(2026, 6, 1),
                "rationale": "nonfinite threshold",
            },
        )
    assert service.get_bet(bet.id).disproof == []


def test_disproof_can_be_edited_while_running(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))
    _commit_disproof(service, bet.id, threshold=11.0)
    service.transition_bet(bet.id, BetStatus.RUNNING)
    edited = service.add_disproof(
        bet.id,
        {
            "metric": "opportunity",
            "operator": "at_or_below",
            "threshold": 9.0,
            "by_date": date(2026, 6, 1),
            "rationale": "sharpened before judging",
        },
        index=0,
    )
    assert edited.disproof[0].threshold == 9.0
    removed = service.remove_disproof(bet.id, 0)
    assert removed.disproof == []


def test_terminal_transition_names_legal_successors(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))
    service.transition_bet(bet.id, BetStatus.ABANDONED)
    with pytest.raises(ConflictError, match="terminal"):
        service.transition_bet(bet.id, BetStatus.RUNNING)


# -- Measurement ------------------------------------------------------------


def test_evaluate_disproof_is_no_data_without_an_observation(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 20.0, date(2026, 6, 1))
    _commit_disproof(service, bet.id)
    report = service.evaluate_disproof(bet.id, looked_at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    assert report["summary"] == {"disproved": 0, "holding": 0, "no_data": 1}
    line = report["conditions"][0]
    assert line["verdict"] == "no_data"
    assert line["observed"] is None
    # no_data is never rendered as holding.
    assert "holding" not in line["verdict"]


def test_evaluate_disproof_disproves_when_the_condition_holds(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)  # opportunity 12
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 20.0, date(2026, 6, 1))
    _commit_disproof(service, bet.id, operator="at_or_below", threshold=11.0)
    # Opportunity stays at 12: the "no movement" condition never crosses.
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    report = service.evaluate_disproof(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert report["summary"]["holding"] == 1
    assert report["conditions"][0]["verdict"] == "holding"
    assert report["conditions"][0]["observed"] == 12.0

    # A later snapshot that drops the opportunity below the threshold disproves it.
    service.update_outcome(outcome.id, {"importance": 4.0, "satisfaction": 3.0})  # 5
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 4, tzinfo=timezone.utc))
    report = service.evaluate_disproof(bet.id, looked_at=datetime(2026, 6, 5, tzinfo=timezone.utc))
    assert report["summary"]["disproved"] == 1
    assert report["conditions"][0]["observed"] == 5.0


def test_evaluate_disproof_reads_the_bets_own_outcome_and_window(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 20.0, date(2026, 6, 10))
    _commit_disproof(service, bet.id, by_date=date(2026, 6, 10))
    # A snapshot before measure_by is outside the window and cannot be used.
    service.update_outcome(outcome.id, {"importance": 2.0, "satisfaction": 2.0})
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 1, tzinfo=timezone.utc))
    report = service.evaluate_disproof(bet.id, looked_at=datetime(2026, 6, 11, tzinfo=timezone.utc))
    assert report["summary"] == {"disproved": 0, "holding": 0, "no_data": 1}


def test_evaluate_disproof_writes_nothing(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 20.0, date(2026, 6, 1))
    _commit_disproof(service, bet.id)
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    before = len(service.repo.score_snapshots)
    first = service.evaluate_disproof(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    second = service.evaluate_disproof(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert first == second
    assert len(service.repo.score_snapshots) == before
    assert service.get_bet(bet.id).status is BetStatus.PLANNED


def test_measure_bet_folds_in_disproof_verdicts(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))
    _commit_disproof(service, bet.id, operator="at_or_below", threshold=11.0)
    service.update_outcome(outcome.id, {"importance": 4.0, "satisfaction": 3.0})  # 7
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    result = service.measure_bet(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert result["result"] == "missed"
    assert result["disproof"][0]["verdict"] == "disproved"


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


def test_measure_bet_reports_importance_satisfaction_and_opportunity_deltas(
    service: ODIService,
) -> None:
    job, outcome = _job_with_outcome(service)  # importance 8, satisfaction 4 → 12
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 20.0, date(2026, 6, 1))
    # The baseline provenance is frozen on the bet, so the deltas are auditable.
    assert bet.baseline_importance == 8.0
    assert bet.baseline_satisfaction == 4.0

    service.update_outcome(outcome.id, {"importance": 9.0, "satisfaction": 2.0})  # 16
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    result = service.measure_bet(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert result["delta_importance"] == 1.0
    assert result["delta_satisfaction"] == -2.0
    assert result["delta_opportunity"] == 4.0
    assert result["observed_importance"] == 9.0
    assert result["observed_satisfaction"] == 2.0
    # The selected snapshot is named so the comparison can be audited.
    assert result["snapshot_id"]
    assert result["baseline_snapshot_id"] == bet.baseline_snapshot_id


def test_measure_bet_is_no_data_when_baseline_provenance_is_missing(
    service: ODIService,
) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 20.0, date(2026, 6, 1))
    # Simulate a legacy bet whose per-component baseline was never captured.
    service.repo.update_bet(bet.id, {"baseline_importance": None, "baseline_satisfaction": None})
    service.update_outcome(outcome.id, {"importance": 9.0, "satisfaction": 2.0})
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    result = service.measure_bet(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    # Not like-for-like: an explicit no_data with a reason, never a guessed delta.
    assert result["result"] == "no_data"
    assert "baseline provenance" in result["reason"]
    assert "observed" not in result
    assert "delta_importance" not in result


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


@pytest.mark.parametrize(
    ("magnitude", "expected"),
    [
        (0.0, False),
        (0.2, False),  # a wobble does not interrupt
        (-0.2, False),
        (0.5, True),  # the boundary is inclusive
        (-0.5, True),
        (1.2, True),
        (-1.2, True),
        (None, False),  # missing comparable value cannot be proven to cross
    ],
)
def test_should_notify_score_move_boundaries(magnitude: float | None, expected: bool) -> None:
    from agentic_odi_core.models import Signal
    from agentic_odi_core.signals import should_notify

    signal = Signal(
        kind=SignalKind.SCORE_MOVED,
        title="moved",
        subject_kind="outcome",
        subject_id="o",
        magnitude=magnitude,
        fingerprint="f-boundary",
    )
    assert should_notify(signal) is expected


def test_should_notify_unsupported_kind_has_an_explicit_result() -> None:
    from agentic_odi_core.models import Signal
    from agentic_odi_core.signals import should_notify

    # A kind with no rule of its own never interrupts: it stays in the feed
    # rather than raising, so an unruled kind is an explicit "no".
    signal = Signal(
        kind=SignalKind.JOB_ADDED,
        title="Job added",
        subject_kind="job",
        subject_id="j",
        fingerprint="f-unsupported",
    )
    assert should_notify(signal) is False


def test_count_notifiable_matches_should_notify_per_signal() -> None:
    from agentic_odi_core.models import Signal
    from agentic_odi_core.signals import count_notifiable, default_rules

    rules = list(default_rules().values())
    due = Signal(
        kind=SignalKind.BET_DUE,
        title="due",
        subject_kind="bet",
        subject_id="b",
        fingerprint="f-due",
    )
    wobble = Signal(
        kind=SignalKind.SCORE_MOVED,
        title="moved",
        subject_kind="outcome",
        subject_id="o",
        magnitude=0.2,
        fingerprint="f-wobble",
    )
    crossing = wobble.model_copy(update={"magnitude": -1.2, "fingerprint": "f-cross"})
    gap = Signal(
        kind=SignalKind.COVERAGE_GAP,
        title="gap",
        subject_kind="job_stage",
        subject_id="s",
        fingerprint="f-gap",
    )
    # Only the due bet and the real crossing may interrupt; the wobble and the
    # off-by-default gap stay in the feed but do not ring the bell.
    assert count_notifiable([due, wobble, crossing, gap], rules) == 2
    assert count_notifiable([], rules) == 0


def test_bell_count_applies_the_policy_at_read_time(service: ODIService) -> None:
    from agentic_odi_core.models import SignalKind

    # A coverage gap is real feed data but off by default; a bet coming due
    # interrupts. The bell is the interruption count, so it counts one.
    service.record_signal(
        SignalKind.COVERAGE_GAP, "stage uncovered", subject_kind="job_stage", subject_id="s-1"
    )
    service.record_signal(SignalKind.BET_DUE, "bet due", subject_kind="bet", subject_id="b-1")
    assert service.count_unread_signals() == 2
    assert service.count_notifiable_signals() == 1

    # Turning the gap on changes the count immediately, without marking the
    # signal read or dismissing it.
    service.set_notification_rule(SignalKind.COVERAGE_GAP, enabled=True)
    assert service.count_notifiable_signals() == 2
    gap = next(s for s in service.list_signals() if s.kind is SignalKind.COVERAGE_GAP)
    assert gap.read_at is None and gap.dismissed_at is None

    # Reading the bet drops it from the bell; the count follows the state.
    bet = next(s for s in service.list_signals() if s.kind is SignalKind.BET_DUE)
    service.mark_signal_read(bet.id)
    assert service.count_notifiable_signals() == 1


def test_invalid_rule_edit_leaves_the_previous_rule_effective(service: ODIService) -> None:
    before = {rule.kind: rule for rule in service.list_notification_rules()}
    with pytest.raises(ValidationError):
        service.set_notification_rule(SignalKind.SCORE_MOVED, threshold=-1.0)
    after = {rule.kind: rule for rule in service.list_notification_rules()}
    assert after[SignalKind.SCORE_MOVED] == before[SignalKind.SCORE_MOVED]


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


def test_measure_bet_unknown_id_is_an_error_not_no_data(service: ODIService) -> None:
    from agentic_odi_core.errors import NotFoundError

    with pytest.raises(NotFoundError):
        service.measure_bet("does-not-exist")


def test_measure_bet_never_selects_another_outcomes_snapshot(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    other = service.add_outcome(job.id, STATEMENT, 8.0, 4.0)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))
    # A snapshot on a different outcome must not be read as this bet's movement.
    service.record_score_snapshot(other.id, at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    result = service.measure_bet(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert result["result"] == "no_data"
    assert "observed" not in result


def test_measure_bet_exact_target_is_met_for_both_directions(service: ODIService) -> None:
    from agentic_odi_core.models import Direction

    job, outcome = _job_with_outcome(service)  # opportunity 12
    decision = _decision_for(service, job, outcome)
    # Maximize: observed exactly equals the target → met.
    up = service.create_bet(decision.id, outcome.id, "up", 12.0, date(2026, 6, 1))
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    assert (
        service.measure_bet(up.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))["result"]
        == "met"
    )

    # Minimize: a lower target is met by a value at or below it, equality included.
    down = service.create_bet(
        decision.id, outcome.id, "down", 12.0, date(2026, 6, 1), direction=Direction.MINIMIZE
    )
    service.record_score_snapshot(outcome.id, at=datetime(2026, 6, 4, tzinfo=timezone.utc))
    result = service.measure_bet(down.id, looked_at=datetime(2026, 6, 5, tzinfo=timezone.utc))
    assert result["result"] == "met"
    assert result["direction"] == "minimize"


def test_measure_bet_names_the_selected_snapshot_and_its_time(service: ODIService) -> None:
    job, outcome = _job_with_outcome(service)
    decision = _decision_for(service, job, outcome)
    bet = service.create_bet(decision.id, outcome.id, "h", 12.0, date(2026, 6, 1))
    service.record_score_snapshot(
        outcome.id, at=datetime(2026, 6, 2, 9, 30, tzinfo=timezone.utc), method="survey"
    )
    result = service.measure_bet(bet.id, looked_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert result["snapshot_at"] == "2026-06-02T09:30:00+00:00"
    assert result["snapshot_method"] == "survey"
    assert result["snapshot_id"]
    # The result is descriptive, never a significance claim.
    assert "p_value" not in result
    assert "significant" not in result
