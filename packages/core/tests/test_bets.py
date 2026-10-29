"""Pin the bet contract (E1/ALH-46).

Readiness choices pinned here:

* **A baseline is captured at creation and stored, never recomputed.** A later
  re-score does not move it, and it survives replay, a SQLite restart, and a
  remote round-trip.
* **The outcome must belong to the decision.** A linked decision's existence
  alone does not prove ownership.
* **Transitions are validated in the model.** ``planned→running→measured`` and
  ``planned→abandoned``; ``measured`` and ``abandoned`` are terminal. An illegal
  transition names the legal successors and appends no event.
* **``measure_by`` is a date**, not a datetime, and is validated.
* **Nonfinite numbers and blank hypotheses are refused atomically.**
"""

from __future__ import annotations

import pytest
from agentic_odi_core.errors import ConflictError, ValidationError
from agentic_odi_core.models import BET_TRANSITIONS, Bet, BetStatus
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import (
    BetNotFoundError,
    DecisionNotFoundError,
    ODIService,
    OutcomeNotFoundError,
)
from agentic_odi_core.sqlite_repository import SQLiteRepository

_STATEMENT = "Minimize the time it takes to publish a plugin when a release is ready"


@pytest.fixture()
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _decision_with_outcome(service: ODIService):
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0, at="2026-01-01T00:00:00Z")
    other = service.add_outcome(
        job.id, "Minimize the cost of supporting a plugin when it ships", 5.0, 7.0
    )
    decision = service.record_decision(
        job.id,
        [outcome.id],
        rationale="Publishing speed blocks every release.",
        decided_by="alex",
        decided_at="2026-01-02T00:00:00Z",
    )
    return job, outcome, other, decision


def test_a_bet_requires_its_fields(service) -> None:
    _, outcome, _, decision = _decision_with_outcome(service)
    bet = service.record_bet(
        decision.id,
        outcome.id,
        "Publishing gets under 5 minutes",
        target=6.0,
        measure_by="2026-04-01",
    )
    assert bet.decision_id == decision.id
    assert bet.outcome_id == outcome.id
    assert bet.status is BetStatus.PLANNED
    assert bet.measure_by == "2026-04-01"


def test_a_bet_without_a_decision_is_refused(service) -> None:
    _, outcome, _, _ = _decision_with_outcome(service)
    with pytest.raises(DecisionNotFoundError):
        service.record_bet("nope", outcome.id, "h", target=6.0, measure_by="2026-04-01")


def test_a_bet_for_an_outcome_the_decision_did_not_choose_is_refused(service) -> None:
    _, _, other, decision = _decision_with_outcome(service)
    with pytest.raises(ValidationError, match="not one the decision"):
        service.record_bet(decision.id, other.id, "h", target=6.0, measure_by="2026-04-01")


def test_a_bet_with_an_unknown_outcome_is_refused(service) -> None:
    _, _, _, decision = _decision_with_outcome(service)
    with pytest.raises(OutcomeNotFoundError):
        service.record_bet(decision.id, "ghost", "h", target=6.0, measure_by="2026-04-01")


def test_blank_hypothesis_is_refused(service) -> None:
    _, outcome, _, decision = _decision_with_outcome(service)
    with pytest.raises(ValidationError, match="hypothesis"):
        service.record_bet(decision.id, outcome.id, "   ", target=6.0, measure_by="2026-04-01")


def test_nonfinite_and_malformed_values_are_refused(service) -> None:
    _, outcome, _, decision = _decision_with_outcome(service)
    with pytest.raises(ValidationError, match="finite"):
        service.record_bet(
            decision.id, outcome.id, "h", target=float("inf"), measure_by="2026-04-01"
        )
    with pytest.raises(ValidationError, match="ISO-8601 date"):
        service.record_bet(decision.id, outcome.id, "h", target=6.0, measure_by="soon")


def test_a_baseline_is_captured_and_never_recomputed(service) -> None:
    _, outcome, _, decision = _decision_with_outcome(service)
    bet = service.record_bet(decision.id, outcome.id, "h", target=6.0, measure_by="2026-04-01")
    captured = bet.baseline

    # The outcome is re-scored; the bet's baseline must not move.
    service.update_outcome(outcome.id, {"satisfaction": 9.0}, at="2026-02-01T00:00:00Z")

    reread = service.get_bet(bet.id)
    assert reread is not None
    assert reread.baseline == captured


def test_a_baseline_survives_sqlite_replay(tmp_path) -> None:
    path = str(tmp_path / "bets.db")
    repo = SQLiteRepository(db_path=path)
    service = ODIService(repo)
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0, at="2026-01-01T00:00:00Z")
    decision = service.record_decision(
        job.id, [outcome.id], rationale="r", decided_by="a", decided_at="2026-01-02T00:00:00Z"
    )
    bet = service.record_bet(decision.id, outcome.id, "h", target=6.0, measure_by="2026-04-01")
    service.update_outcome(outcome.id, {"satisfaction": 9.5}, at="2026-02-01T00:00:00Z")
    repo.commit()
    repo.close()

    replay = ODIService(SQLiteRepository(db_path=path))
    reread = replay.get_bet(bet.id)
    assert reread is not None
    assert reread.baseline == bet.baseline
    assert reread.status is BetStatus.PLANNED
    replay.repo.close()


def test_every_legal_transition_succeeds(service) -> None:
    _, outcome, _, decision = _decision_with_outcome(service)
    bet = service.record_bet(decision.id, outcome.id, "h", target=6.0, measure_by="2026-04-01")

    running = service.advance_bet(bet.id, "running")
    assert running.status is BetStatus.RUNNING
    measured = service.advance_bet(bet.id, "measured", at="2026-04-02T00:00:00Z")
    assert measured.status is BetStatus.MEASURED
    assert measured.measured_at == "2026-04-02T00:00:00Z"
    assert measured.is_terminal()


def test_planned_can_be_abandoned(service) -> None:
    _, outcome, _, decision = _decision_with_outcome(service)
    bet = service.record_bet(decision.id, outcome.id, "h", target=6.0, measure_by="2026-04-01")
    assert service.advance_bet(bet.id, "abandoned").status is BetStatus.ABANDONED


def test_an_illegal_transition_names_the_legal_ones(service) -> None:
    _, outcome, _, decision = _decision_with_outcome(service)
    bet = service.record_bet(decision.id, outcome.id, "h", target=6.0, measure_by="2026-04-01")
    with pytest.raises(ConflictError) as excinfo:
        service.advance_bet(bet.id, "measured")
    message = str(excinfo.value)
    assert "running" in message
    assert "abandoned" in message
    # The refusal appended no event: the bet is untouched.
    assert service.get_bet(bet.id).status is BetStatus.PLANNED


def test_running_cannot_be_abandoned(service) -> None:
    """``running→abandoned`` is deliberately not a transition (ALH-46)."""
    _, outcome, _, decision = _decision_with_outcome(service)
    bet = service.record_bet(decision.id, outcome.id, "h", target=6.0, measure_by="2026-04-01")
    service.advance_bet(bet.id, "running")
    with pytest.raises(ConflictError):
        service.advance_bet(bet.id, "abandoned")


def test_a_terminal_bet_has_no_successors(service) -> None:
    _, outcome, _, decision = _decision_with_outcome(service)
    bet = service.record_bet(decision.id, outcome.id, "h", target=6.0, measure_by="2026-04-01")
    service.advance_bet(bet.id, "abandoned")
    with pytest.raises(ConflictError):
        service.advance_bet(bet.id, "running")


def test_unknown_status_is_refused(service) -> None:
    _, outcome, _, decision = _decision_with_outcome(service)
    bet = service.record_bet(decision.id, outcome.id, "h", target=6.0, measure_by="2026-04-01")
    with pytest.raises(ValidationError, match="Unknown bet status"):
        service.advance_bet(bet.id, "done")


def test_unknown_bet_is_refused(service) -> None:
    with pytest.raises(BetNotFoundError):
        service.advance_bet("nope", "running")


def test_transition_table_is_the_contract() -> None:
    assert BET_TRANSITIONS[BetStatus.PLANNED] == (BetStatus.RUNNING, BetStatus.ABANDONED)
    assert BET_TRANSITIONS[BetStatus.RUNNING] == (BetStatus.MEASURED,)
    assert BET_TRANSITIONS[BetStatus.MEASURED] == ()
    assert BET_TRANSITIONS[BetStatus.ABANDONED] == ()
    assert (
        Bet(
            hypothesis="h",
            decision_id="d",
            outcome_id="o",
            baseline=1.0,
            target=2.0,
            measure_by="2026-04-01",
        ).status
        is BetStatus.PLANNED
    )


def test_listing_bets_filters_by_job_and_decision(service) -> None:
    job, outcome, _, decision = _decision_with_outcome(service)
    bet = service.record_bet(decision.id, outcome.id, "h", target=6.0, measure_by="2026-04-01")
    assert [b.id for b in service.list_bets(job_id=job.id)] == [bet.id]
    assert [b.id for b in service.list_bets(decision_id=decision.id)] == [bet.id]
    assert service.list_bets(job_id="other") == []


def test_deleting_the_job_cascades_to_its_bets(service) -> None:
    job, outcome, _, decision = _decision_with_outcome(service)
    bet = service.record_bet(decision.id, outcome.id, "h", target=6.0, measure_by="2026-04-01")
    service.delete_job(job.id)
    assert service.get_bet(bet.id) is None
    assert service.list_bets() == []
