"""Repository interfaces and in-memory implementation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Protocol, TypeVar

from agentic_odi_core.mapping import OutcomeProposal, ProposalStatus
from agentic_odi_core.models import (
    V2MOM,
    CustomerOutcome,
    Evidence,
    Job,
    Outcome,
    ScheduledWork,
    Segment,
    Signal,
    Step,
    Strategy,
)

_Item = TypeVar("_Item")

#: A workspace has exactly one V2MOM, and the model carries no id, so the store
#: keys it by this constant rather than a generated one.
V2MOM_ID = "v2mom"


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


def compute_evidence_fingerprint(
    source_kind: str,
    source_name: str,
    name: str,
    content: str,
    url: str | None,
    raw: dict[str, Any] | None,
) -> str:
    """Fingerprint for an evidence record: sha256 over its content-defining fields.

    Records that share ``source_kind``, ``source_name``, ``name``, ``content``,
    ``url`` and ``raw`` describe the same customer quote / observation, so a
    repeat import or promotion must not create a duplicate evidence row.
    """
    payload = "|".join(
        [
            source_kind,
            source_name,
            name,
            content,
            url or "",
            json.dumps(raw or {}, sort_keys=True),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Repository(Protocol):
    jobs: dict[str, Job]
    steps: dict[str, Step]
    outcomes: dict[str, Outcome]
    proposals: dict[str, OutcomeProposal]
    customer_outcomes: dict[str, CustomerOutcome]
    evidence: dict[str, Evidence]
    signals: dict[str, Signal]
    scheduled_work: dict[str, ScheduledWork]
    segments: dict[str, Segment]
    strategies: dict[str, Strategy]
    v2mom: dict[str, V2MOM]

    def add_job(self, job: Job) -> Job: ...
    def list_jobs(self, limit: int | None = None, offset: int = 0) -> list[Job]: ...
    def get_job(self, job_id: str) -> Job | None: ...
    def update_job(self, job_id: str, updates: dict) -> Job | None: ...
    def delete_job(self, job_id: str) -> bool: ...
    def add_step(self, step: Step) -> Step: ...
    def get_step(self, step_id: str) -> Step | None: ...
    def list_steps(self, limit: int | None = None, offset: int = 0) -> list[Step]: ...
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
    def get_evidence_by_fingerprint(
        self,
        source_kind: str,
        source_name: str,
        name: str,
        content: str,
        url: str | None,
        raw: dict[str, Any] | None,
    ) -> Evidence | None: ...
    def update_evidence(self, evidence_id: str, updates: dict[str, Any]) -> Evidence | None: ...
    def list_evidence(
        self,
        job_id: str | None = None,
        step_id: str | None = None,
        outcome_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Evidence]: ...
    def delete_evidence(self, evidence_id: str) -> bool: ...
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
    def add_segment(self, segment: Segment) -> Segment: ...
    def get_segment(self, segment_id: str) -> Segment | None: ...
    def list_segments(self, job_id: str | None = None) -> list[Segment]: ...
    def update_segment(self, segment_id: str, updates: dict) -> Segment | None: ...
    def add_strategy(self, strategy: Strategy) -> Strategy: ...
    def get_strategy(self, strategy_id: str) -> Strategy | None: ...
    def list_strategies(self, segment_id: str | None = None) -> list[Strategy]: ...
    def update_strategy(self, strategy_id: str, updates: dict) -> Strategy | None: ...
    def add_proposal(self, proposal: OutcomeProposal) -> OutcomeProposal: ...
    def get_proposal(self, proposal_id: str) -> OutcomeProposal | None: ...
    def list_proposals(self, status: ProposalStatus | None = None) -> list[OutcomeProposal]: ...
    def update_proposal(self, proposal_id: str, updates: dict) -> OutcomeProposal | None: ...
    def add_v2mom(self, v2mom: V2MOM) -> V2MOM: ...
    def get_v2mom(self) -> V2MOM | None: ...

    def clear(self) -> None: ...
    def reload(self) -> None: ...
    def commit(self) -> None: ...
    def close(self) -> None: ...
    def health(self) -> bool: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.steps: dict[str, Step] = {}
        self.outcomes: dict[str, Outcome] = {}
        self.proposals: dict[str, OutcomeProposal] = {}
        self.customer_outcomes: dict[str, CustomerOutcome] = {}
        self.evidence: dict[str, Evidence] = {}
        self.signals: dict[str, Signal] = {}
        self.scheduled_work: dict[str, ScheduledWork] = {}
        self.segments: dict[str, Segment] = {}
        self.strategies: dict[str, Strategy] = {}
        #: The store holds one vision; it is keyed by a fixed name rather than a
        #: generated id because a workspace has exactly one V2MOM.
        self.v2mom: dict[str, V2MOM] = {}

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
        deleted_steps = {k for k, v in self.steps.items() if v.job_id == job_id}
        for key in deleted_steps:
            del self.steps[key]
        deleted_outcomes = {k for k, v in self.outcomes.items() if v.job_id == job_id}
        for key in deleted_outcomes:
            del self.outcomes[key]
        for key in [k for k, v in self.customer_outcomes.items() if v.job_id == job_id]:
            del self.customer_outcomes[key]
        #: Do not destroy research evidence: unlink references to the removed
        #: job, its steps and its outcomes instead of deleting the rows.
        for key, ev in list(self.evidence.items()):
            updates: dict[str, Any] = {}
            if ev.job_id == job_id:
                updates["job_id"] = None
            if ev.step_id in deleted_steps:
                updates["step_id"] = None
            if ev.outcome_id in deleted_outcomes:
                updates["outcome_id"] = None
            if updates:
                current = ev.model_dump(exclude_unset=True)
                current.update(updates)
                self.evidence[key] = Evidence.model_validate(current)
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
        #: Unlink evidence instead of destroying it.
        for key, ev in list(self.evidence.items()):
            if ev.step_id == step_id:
                current = ev.model_dump(exclude_unset=True)
                current["step_id"] = None
                self.evidence[key] = Evidence.model_validate(current)
        return True

    def list_steps(self, limit: int | None = None, offset: int = 0) -> list[Step]:
        return page(list(self.steps.values()), limit, offset)

    def add_proposal(self, proposal: OutcomeProposal) -> OutcomeProposal:
        self.proposals[proposal.id] = proposal
        return proposal

    def get_proposal(self, proposal_id: str) -> OutcomeProposal | None:
        return self.proposals.get(proposal_id)

    def list_proposals(self, status: ProposalStatus | None = None) -> list[OutcomeProposal]:
        props = list(self.proposals.values())
        if status is not None:
            props = [p for p in props if p.status == status]
        return props

    def update_proposal(self, proposal_id: str, updates: dict) -> OutcomeProposal | None:
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return None
        current = proposal.model_dump(exclude_unset=True)
        current.update(updates)
        new_proposal = OutcomeProposal.model_validate(current)
        self.proposals[proposal_id] = new_proposal
        return new_proposal

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
            #: Unlink evidence instead of destroying it: point outcome_id to NULL
            #: so the quote survives the outcome's removal.
            for key, ev in list(self.evidence.items()):
                if ev.outcome_id == outcome_id:
                    current = ev.model_dump(exclude_unset=True)
                    current["outcome_id"] = None
                    self.evidence[key] = Evidence.model_validate(current)
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

    def get_evidence_by_fingerprint(
        self,
        source_kind: str,
        source_name: str,
        name: str,
        content: str,
        url: str | None,
        raw: dict[str, Any] | None,
    ) -> Evidence | None:
        fingerprint = compute_evidence_fingerprint(
            source_kind, source_name, name, content, url, raw
        )
        for existing in self.evidence.values():
            if (
                compute_evidence_fingerprint(
                    existing.source_kind,
                    existing.source_name,
                    existing.name,
                    existing.content,
                    existing.url,
                    existing.raw,
                )
                == fingerprint
            ):
                return existing
        return None

    def update_evidence(self, evidence_id: str, updates: dict[str, Any]) -> Evidence | None:
        evidence = self.evidence.get(evidence_id)
        if not evidence:
            return None
        current = evidence.model_dump(exclude_unset=True)
        current.update(updates)
        new_evidence = evidence.model_validate(current)
        self.evidence[evidence_id] = new_evidence
        return new_evidence

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

    def add_segment(self, segment: Segment) -> Segment:
        self.segments[segment.id] = segment
        return segment

    def get_segment(self, segment_id: str) -> Segment | None:
        return self.segments.get(segment_id)

    def list_segments(self, job_id: str | None = None) -> list[Segment]:
        items = list(self.segments.values())
        if job_id is not None:
            items = [segment for segment in items if segment.job_id == job_id]
        return items

    def update_segment(self, segment_id: str, updates: dict) -> Segment | None:
        segment = self.segments.get(segment_id)
        if segment is None:
            return None
        current = segment.model_dump(exclude_unset=True)
        current.update(updates)
        new_segment = segment.model_validate(current)
        self.segments[segment_id] = new_segment
        return new_segment

    def add_strategy(self, strategy: Strategy) -> Strategy:
        self.strategies[strategy.id] = strategy
        return strategy

    def get_strategy(self, strategy_id: str) -> Strategy | None:
        return self.strategies.get(strategy_id)

    def list_strategies(self, segment_id: str | None = None) -> list[Strategy]:
        items = list(self.strategies.values())
        if segment_id is not None:
            items = [strategy for strategy in items if strategy.segment_id == segment_id]
        return items

    def update_strategy(self, strategy_id: str, updates: dict) -> Strategy | None:
        strategy = self.strategies.get(strategy_id)
        if strategy is None:
            return None
        current = strategy.model_dump(exclude_unset=True)
        current.update(updates)
        new_strategy = strategy.model_validate(current)
        self.strategies[strategy_id] = new_strategy
        return new_strategy

    def add_v2mom(self, v2mom: V2MOM) -> V2MOM:
        self.v2mom[V2MOM_ID] = v2mom
        return v2mom

    def get_v2mom(self) -> V2MOM | None:
        return next(iter(self.v2mom.values()), None)

    def clear(self) -> None:
        self.jobs.clear()
        self.scheduled_work.clear()
        self.steps.clear()
        self.outcomes.clear()
        self.customer_outcomes.clear()
        self.evidence.clear()
        self.signals.clear()
        self.segments.clear()
        self.strategies.clear()
        self.v2mom.clear()

    def reload(self) -> None:
        """Reset in-memory state; there is no external store to re-read."""
        self.clear()

    def commit(self) -> None:
        """No-op: an in-memory store has nothing to flush."""

    def close(self) -> None:
        """No-op: an in-memory store holds no resources."""

    def health(self) -> bool:
        """An in-memory store is always reachable while the process is alive."""
        return True
