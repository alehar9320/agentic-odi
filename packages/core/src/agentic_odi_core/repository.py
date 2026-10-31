"""Repository interfaces and in-memory implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, TypeVar

from agentic_odi_core.models import (
    BetRecord,
    CandidateStatus,
    CustomerOutcome,
    DecisionRecord,
    Evidence,
    Job,
    MeasurementRecord,
    Outcome,
    OutcomeCandidate,
    ScheduledWork,
    Signal,
    Step,
)

_Item = TypeVar("_Item")


def rank_outcomes(outcomes: list[Outcome]) -> list[Outcome]:
    """Rank outcomes by opportunity score, highest first, unscored last."""
    return sorted(
        outcomes,
        key=lambda outcome: (
            outcome.opportunity_score is None,
            -(outcome.opportunity_score or 0.0),
        ),
    )


def page(items: list[_Item], limit: int | None = None, offset: int = 0) -> list[_Item]:
    """Slice a list for pagination; no arguments returns everything.

    ``limit``/``offset`` are validated here so both repositories reject a
    nonsensical page the same way instead of silently slicing from the end.
    """
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if limit is not None and limit < 0:
        raise ValueError("limit must be >= 0")
    sliced = items[offset:] if offset else items
    return sliced if limit is None else sliced[:limit]


def rank_signals(signals: list[Signal]) -> list[Signal]:
    """Surfaced signals, newest first.

    Dismissed signals left the feed; budget-suppressed ones were recorded but
    are not surfaced, so neither kind appears. Urgent signals bypass the
    budget, so they were never suppressed in the first place.
    """
    return sorted(
        (signal for signal in signals if signal.dismissed_at is None and not signal.suppressed),
        key=lambda signal: signal.created_at,
        reverse=True,
    )


def unread_signals(signals: list[Signal]) -> list[Signal]:
    """Unread means unseen: surfaced and not yet read."""
    return [signal for signal in rank_signals(signals) if signal.read_at is None]


OUTCOME_SORTS = ("opportunity_score", "insertion")


def sort_outcomes(items: list[Outcome], sort: str = "opportunity_score") -> list[Outcome]:
    """Order outcomes for reading, best opportunity first by default.

    ``opportunity_score`` puts the highest scores first and leaves unscored
    outcomes last, since a missing score is not evidence of low opportunity.
    ``insertion`` keeps whatever order the store produced.
    """
    if sort == "insertion":
        return list(items)
    if sort not in OUTCOME_SORTS:
        raise ValueError(f"Unknown outcome sort: {sort}")
    return rank_outcomes(items)


class Repository(Protocol):
    jobs: dict[str, Job]
    steps: dict[str, Step]
    outcomes: dict[str, Outcome]
    customer_outcomes: dict[str, CustomerOutcome]
    evidence: dict[str, Evidence]
    candidates: dict[str, OutcomeCandidate]
    decisions: dict[str, DecisionRecord]
    bets: dict[str, BetRecord]
    measurements: dict[str, MeasurementRecord]
    signals: dict[str, Signal]
    scheduled_work: dict[str, ScheduledWork]

    def add_job(self, job: Job) -> Job: ...
    def list_jobs(self, limit: int | None = None, offset: int = 0) -> list[Job]: ...
    def get_job(self, job_id: str) -> Job | None: ...
    def update_job(self, job_id: str, updates: dict) -> Job | None: ...
    def delete_job(self, job_id: str) -> bool: ...
    def add_step(self, step: Step) -> Step: ...
    def get_step(self, step_id: str) -> Step | None: ...
    def get_steps_for_job(
        self, job_id: str, limit: int | None = None, offset: int = 0
    ) -> list[Step]: ...
    def update_step(self, step_id: str, updates: dict) -> Step | None: ...
    def delete_step(self, step_id: str) -> bool: ...
    def add_outcome(self, outcome: Outcome) -> Outcome: ...
    def get_outcome(self, outcome_id: str) -> Outcome | None: ...
    def get_outcomes(
        self,
        job_id: str,
        step_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: str = "opportunity_score",
    ) -> list[Outcome]: ...
    def update_outcome(self, outcome_id: str, updates: dict) -> Outcome | None: ...
    def delete_outcome(self, outcome_id: str) -> bool: ...
    def add_customer_outcome(self, co: CustomerOutcome) -> CustomerOutcome: ...
    def get_customer_outcome(self, outcome_id: str) -> CustomerOutcome | None: ...
    def list_customer_outcomes(
        self,
        job_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[CustomerOutcome]: ...
    def update_customer_outcome(self, outcome_id: str, updates: dict) -> CustomerOutcome | None: ...
    def delete_customer_outcome(self, outcome_id: str) -> bool: ...
    def add_evidence(self, evidence: Evidence) -> Evidence: ...
    def get_evidence(self, evidence_id: str) -> Evidence | None: ...
    def list_evidence(
        self,
        job_id: str | None = None,
        step_id: str | None = None,
        outcome_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Evidence]: ...
    def delete_evidence(self, evidence_id: str) -> bool: ...
    def add_candidate(self, candidate: OutcomeCandidate) -> OutcomeCandidate: ...
    def get_candidate(self, candidate_id: str) -> OutcomeCandidate | None: ...
    def list_candidates(
        self,
        quote_id: str | None = None,
        job_id: str | None = None,
        status: CandidateStatus | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[OutcomeCandidate]: ...
    def update_candidate(self, candidate_id: str, updates: dict) -> OutcomeCandidate | None: ...
    def add_decision(self, decision: DecisionRecord) -> DecisionRecord: ...
    def get_decision(self, decision_id: str) -> DecisionRecord | None: ...
    def list_decisions(
        self, subject_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[DecisionRecord]: ...
    def add_bet(self, bet: BetRecord) -> BetRecord: ...
    def get_bet(self, bet_id: str) -> BetRecord | None: ...
    def list_bets(
        self, decision_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[BetRecord]: ...
    def add_measurement(self, measurement: MeasurementRecord) -> MeasurementRecord: ...
    def get_measurement(self, measurement_id: str) -> MeasurementRecord | None: ...
    def list_measurements(
        self, bet_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[MeasurementRecord]: ...
    def add_signal(self, signal: Signal) -> Signal: ...
    def get_signal(self, signal_id: str) -> Signal | None: ...
    def list_signals(self, unread_only: bool = False, limit: int = 50) -> list[Signal]: ...
    def mark_signal_read(self, signal_id: str) -> Signal | None: ...
    def dismiss_signal(self, signal_id: str) -> Signal | None: ...
    def count_unread_signals(self) -> int: ...
    def add_scheduled_work(self, work: ScheduledWork) -> ScheduledWork: ...
    def get_scheduled_work(self, work_id: str) -> ScheduledWork | None: ...
    def list_scheduled_work(
        self, job_id: str | None = None, status: str | None = None
    ) -> list[ScheduledWork]: ...
    def update_scheduled_work(self, work_id: str, updates: dict) -> ScheduledWork | None: ...
    def delete_scheduled_work(self, work_id: str) -> bool: ...

    def clear(self) -> None: ...
    def reload(self) -> None: ...
    def commit(self) -> None: ...
    def close(self) -> None: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.steps: dict[str, Step] = {}
        self.outcomes: dict[str, Outcome] = {}
        self.customer_outcomes: dict[str, CustomerOutcome] = {}
        self.evidence: dict[str, Evidence] = {}
        self.candidates: dict[str, OutcomeCandidate] = {}
        self.decisions: dict[str, DecisionRecord] = {}
        self.bets: dict[str, BetRecord] = {}
        self.measurements: dict[str, MeasurementRecord] = {}
        self.signals: dict[str, Signal] = {}
        self.scheduled_work: dict[str, ScheduledWork] = {}

    def add_job(self, job: Job) -> Job:
        self.jobs[job.id] = job
        return job

    def list_jobs(self, limit: int | None = None, offset: int = 0) -> list[Job]:
        return page(list(self.jobs.values()), limit, offset)

    def get_job(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def update_job(self, job_id: str, updates: dict) -> Job | None:
        job = self.jobs.get(job_id)
        if not job:
            return None
        current = job.model_dump(exclude_unset=True)
        current.update(updates)
        new_job = job.model_validate(current)
        self.jobs[job_id] = new_job
        return new_job

    def delete_job(self, job_id: str) -> bool:
        if job_id not in self.jobs:
            return False
        del self.jobs[job_id]
        for key in [k for k, v in self.steps.items() if v.job_id == job_id]:
            del self.steps[key]
        for key in [k for k, v in self.outcomes.items() if v.job_id == job_id]:
            del self.outcomes[key]
        for key in [k for k, v in self.customer_outcomes.items() if v.job_id == job_id]:
            del self.customer_outcomes[key]
        for key in [
            k
            for k, v in self.evidence.items()
            if v.job_id == job_id
            or (v.step_id is not None and v.step_id not in self.steps)
            or (v.outcome_id is not None and v.outcome_id not in self.outcomes)
        ]:
            del self.evidence[key]
        return True

    def add_step(self, step: Step) -> Step:
        self.steps[step.id] = step
        return step

    def get_step(self, step_id: str) -> Step | None:
        return self.steps.get(step_id)

    def get_steps_for_job(
        self, job_id: str, limit: int | None = None, offset: int = 0
    ) -> list[Step]:
        steps = [s for s in self.steps.values() if s.job_id == job_id]
        return page(steps, limit, offset)

    def update_step(self, step_id: str, updates: dict) -> Step | None:
        step = self.steps.get(step_id)
        if not step:
            return None
        current = step.model_dump(exclude_unset=True)
        current.update(updates)
        new_step = step.model_validate(current)
        self.steps[step_id] = new_step
        return new_step

    def delete_step(self, step_id: str) -> bool:
        if step_id not in self.steps:
            return False
        del self.steps[step_id]
        for key in [k for k, v in self.outcomes.items() if v.step_id == step_id]:
            del self.outcomes[key]
        for key in [k for k, v in self.customer_outcomes.items() if v.step_id == step_id]:
            del self.customer_outcomes[key]
        for key in [
            k
            for k, v in self.evidence.items()
            if v.step_id == step_id
            or (v.outcome_id is not None and v.outcome_id not in self.outcomes)
        ]:
            del self.evidence[key]
        return True

    def add_outcome(self, outcome: Outcome) -> Outcome:
        self.outcomes[outcome.id] = outcome
        return outcome

    def get_outcome(self, outcome_id: str) -> Outcome | None:
        return self.outcomes.get(outcome_id)

    def get_outcomes(
        self,
        job_id: str,
        step_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: str = "opportunity_score",
    ) -> list[Outcome]:
        outs = [o for o in self.outcomes.values() if o.job_id == job_id]
        if step_id is not None:
            outs = [o for o in outs if o.step_id == step_id]
        return page(sort_outcomes(outs, sort), limit, offset)

    def update_outcome(self, outcome_id: str, updates: dict) -> Outcome | None:
        outcome = self.outcomes.get(outcome_id)
        if not outcome:
            return None
        current = outcome.model_dump(exclude_unset=True)
        current.update(updates)
        new_outcome = outcome.model_validate(current)
        self.outcomes[outcome_id] = new_outcome
        return new_outcome

    def delete_outcome(self, outcome_id: str) -> bool:
        if outcome_id in self.outcomes:
            del self.outcomes[outcome_id]
            for key in [k for k, v in self.evidence.items() if v.outcome_id == outcome_id]:
                del self.evidence[key]
            return True
        return False

    def add_customer_outcome(self, co: CustomerOutcome) -> CustomerOutcome:
        self.customer_outcomes[co.id] = co
        return co

    def get_customer_outcome(self, outcome_id: str) -> CustomerOutcome | None:
        return self.customer_outcomes.get(outcome_id)

    def list_customer_outcomes(
        self,
        job_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[CustomerOutcome]:
        if job_id is None:
            items = list(self.customer_outcomes.values())
        else:
            items = [co for co in self.customer_outcomes.values() if co.job_id == job_id]
        return page(items, limit, offset)

    def update_customer_outcome(self, outcome_id: str, updates: dict) -> CustomerOutcome | None:
        co = self.customer_outcomes.get(outcome_id)
        if not co:
            return None
        current = co.model_dump(exclude_unset=True)
        current.update(updates)
        new_co = co.model_validate(current)
        self.customer_outcomes[outcome_id] = new_co
        return new_co

    def delete_customer_outcome(self, outcome_id: str) -> bool:
        if outcome_id in self.customer_outcomes:
            del self.customer_outcomes[outcome_id]
            return True
        return False

    def add_evidence(self, evidence: Evidence) -> Evidence:
        self.evidence[evidence.id] = evidence
        return evidence

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        return self.evidence.get(evidence_id)

    def list_evidence(
        self,
        job_id: str | None = None,
        step_id: str | None = None,
        outcome_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Evidence]:
        items = list(self.evidence.values())
        if job_id is not None:
            items = [item for item in items if item.job_id == job_id]
        if step_id is not None:
            items = [item for item in items if item.step_id == step_id]
        if outcome_id is not None:
            items = [item for item in items if item.outcome_id == outcome_id]
        return page(items, limit, offset)

    def delete_evidence(self, evidence_id: str) -> bool:
        if evidence_id in self.evidence:
            del self.evidence[evidence_id]
            return True
        return False

    def add_candidate(self, candidate: OutcomeCandidate) -> OutcomeCandidate:
        self.candidates[candidate.id] = candidate
        return candidate

    def get_candidate(self, candidate_id: str) -> OutcomeCandidate | None:
        return self.candidates.get(candidate_id)

    def list_candidates(
        self,
        quote_id: str | None = None,
        job_id: str | None = None,
        status: CandidateStatus | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[OutcomeCandidate]:
        items = list(self.candidates.values())
        if quote_id is not None:
            items = [c for c in items if c.quote_id == quote_id]
        if job_id is not None:
            items = [c for c in items if c.job_id == job_id]
        if status is not None:
            items = [c for c in items if c.status is status]
        return page(items, limit, offset)

    def update_candidate(self, candidate_id: str, updates: dict) -> OutcomeCandidate | None:
        candidate = self.candidates.get(candidate_id)
        if not candidate:
            return None
        # A full dump, not ``exclude_unset``: the id is generated by a factory and
        # would otherwise be dropped and regenerated, silently re-keying the
        # candidate out from under the caller that just decided it.
        current = candidate.model_dump()
        current.update(updates)
        new_candidate = candidate.model_validate(current)
        self.candidates[candidate_id] = new_candidate
        return new_candidate

    def add_decision(self, decision: DecisionRecord) -> DecisionRecord:
        self.decisions[decision.id] = decision
        return decision

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        return self.decisions.get(decision_id)

    def list_decisions(
        self, subject_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[DecisionRecord]:
        items = list(self.decisions.values())
        if subject_id is not None:
            items = [d for d in items if d.subject_id == subject_id]
        return page(items, limit, offset)

    def add_bet(self, bet: BetRecord) -> BetRecord:
        self.bets[bet.id] = bet
        return bet

    def get_bet(self, bet_id: str) -> BetRecord | None:
        return self.bets.get(bet_id)

    def list_bets(
        self, decision_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[BetRecord]:
        items = list(self.bets.values())
        if decision_id is not None:
            items = [b for b in items if b.decision_id == decision_id]
        return page(items, limit, offset)

    def add_measurement(self, measurement: MeasurementRecord) -> MeasurementRecord:
        self.measurements[measurement.id] = measurement
        return measurement

    def get_measurement(self, measurement_id: str) -> MeasurementRecord | None:
        return self.measurements.get(measurement_id)

    def list_measurements(
        self, bet_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[MeasurementRecord]:
        items = list(self.measurements.values())
        if bet_id is not None:
            items = [m for m in items if m.bet_id == bet_id]
        return page(items, limit, offset)

    def add_signal(self, signal: Signal) -> Signal:
        self.signals[signal.id] = signal
        return signal

    def get_signal(self, signal_id: str) -> Signal | None:
        return self.signals.get(signal_id)

    def list_signals(self, unread_only: bool = False, limit: int = 50) -> list[Signal]:
        items = (
            unread_signals(list(self.signals.values()))
            if unread_only
            else rank_signals(list(self.signals.values()))
        )
        return page(items, limit)

    def mark_signal_read(self, signal_id: str) -> Signal | None:
        signal = self.signals.get(signal_id)
        if signal is None:
            return None
        if signal.read_at is None:
            signal.read_at = datetime.now(timezone.utc)
        return signal

    def dismiss_signal(self, signal_id: str) -> Signal | None:
        signal = self.signals.get(signal_id)
        if signal is None:
            return None
        if signal.dismissed_at is None:
            signal.dismissed_at = datetime.now(timezone.utc)
        return signal

    def count_unread_signals(self) -> int:
        return len(unread_signals(list(self.signals.values())))

    def add_scheduled_work(self, work: ScheduledWork) -> ScheduledWork:
        self.scheduled_work[work.id] = work
        return work

    def get_scheduled_work(self, work_id: str) -> ScheduledWork | None:
        return self.scheduled_work.get(work_id)

    def list_scheduled_work(
        self, job_id: str | None = None, status: str | None = None
    ) -> list[ScheduledWork]:
        items = list(self.scheduled_work.values())
        if job_id is not None:
            items = [item for item in items if item.job_id == job_id]
        if status is not None:
            items = [item for item in items if item.status == status]
        return items

    def update_scheduled_work(self, work_id: str, updates: dict) -> ScheduledWork | None:
        work = self.scheduled_work.get(work_id)
        if not work:
            return None
        current = work.model_dump(exclude_unset=True)
        current.update(updates)
        new_work = work.model_validate(current)
        self.scheduled_work[work_id] = new_work
        return new_work

    def delete_scheduled_work(self, work_id: str) -> bool:
        if work_id in self.scheduled_work:
            del self.scheduled_work[work_id]
            return True
        return False

    def clear(self) -> None:
        self.jobs.clear()
        self.scheduled_work.clear()
        self.steps.clear()
        self.outcomes.clear()
        self.customer_outcomes.clear()
        self.evidence.clear()
        self.candidates.clear()
        self.decisions.clear()
        self.bets.clear()
        self.measurements.clear()
        self.signals.clear()

    def reload(self) -> None:
        """Reset in-memory state; there is no external store to re-read."""
        self.clear()

    def commit(self) -> None:
        """No-op: an in-memory store has nothing to flush."""

    def close(self) -> None:
        """No-op: an in-memory store holds no resources."""
