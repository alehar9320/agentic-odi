"""Repository interfaces and in-memory implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from agentic_odi_core.models import (
    Brief,
    Conversation,
    CustomerOutcome,
    Evidence,
    Job,
    Message,
    Observation,
    Outcome,
    ScheduledWork,
    Signal,
    Step,
)

_Item = TypeVar("_Item")
_Model = TypeVar("_Model", bound=BaseModel)


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


def epoch_seconds(moment: datetime) -> float:
    """Comparable timestamp for ordering; a naive value is read as UTC."""
    aware = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return aware.timestamp()


def thread_window(messages: list[Message], limit: int | None, before: str | None) -> list[Message]:
    """Select the window of a thread to return, oldest first.

    ``before`` is a message id used as a backwards cursor, so a client paging
    through history asks for "what came before this one". ``limit`` then keeps
    the most recent entries of that window, which is what a reload needs: the
    tail of the thread, still in order.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must be >= 0")
    window = messages
    if before is not None:
        cut = next((index for index, item in enumerate(window) if item.id == before), len(window))
        window = window[:cut]
    if limit is None:
        return list(window)
    return list(window[-limit:]) if limit else []


def apply_updates(entity: _Model, updates: dict[str, Any]) -> _Model:
    """Merge updates over the fields a stored entity actually carries.

    ``exclude_unset`` matters: revalidating a full dump would re-require
    derived fields the model computes for itself. A generated id is unset but
    must never be re-rolled, so it is pinned back explicitly.
    """
    current = entity.model_dump(exclude_unset=True)
    current.update(updates)
    identifier = getattr(entity, "id", None)
    if identifier is not None:
        current["id"] = identifier
    return type(entity).model_validate(current)


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
    conversations: dict[str, Conversation]
    messages: dict[str, Message]
    observations: dict[str, Observation]
    brief: Brief | None
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
    def add_conversation(self, conversation: Conversation) -> Conversation: ...
    def get_conversation(self, conversation_id: str) -> Conversation | None: ...
    def list_conversations(
        self, limit: int | None = None, offset: int = 0
    ) -> list[Conversation]: ...
    def update_conversation(self, conversation_id: str, updates: dict) -> Conversation | None: ...
    def delete_conversation(self, conversation_id: str) -> bool: ...
    def add_message(self, message: Message) -> Message: ...
    def get_message(self, message_id: str) -> Message | None: ...
    def list_messages(
        self, conversation_id: str, limit: int | None = None, before: str | None = None
    ) -> list[Message]: ...
    def add_observation(self, observation: Observation) -> Observation: ...
    def get_observation(self, observation_id: str) -> Observation | None: ...
    def list_observations(
        self, status: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Observation]: ...
    def update_observation(self, observation_id: str, updates: dict) -> Observation | None: ...
    def delete_observation(self, observation_id: str) -> bool: ...
    def save_brief(self, brief: Brief) -> Brief: ...
    def get_brief(self) -> Brief | None: ...
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
    def health(self) -> bool: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.steps: dict[str, Step] = {}
        self.outcomes: dict[str, Outcome] = {}
        self.customer_outcomes: dict[str, CustomerOutcome] = {}
        self.evidence: dict[str, Evidence] = {}
        self.conversations: dict[str, Conversation] = {}
        self.messages: dict[str, Message] = {}
        self.observations: dict[str, Observation] = {}
        self.brief: Brief | None = None
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

    def add_conversation(self, conversation: Conversation) -> Conversation:
        self.conversations[conversation.id] = conversation
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        return self.conversations.get(conversation_id)

    def list_conversations(self, limit: int | None = None, offset: int = 0) -> list[Conversation]:
        ordered = sorted(
            self.conversations.values(),
            key=lambda conversation: epoch_seconds(conversation.updated_at),
            reverse=True,
        )
        return page(ordered, limit, offset)

    def update_conversation(self, conversation_id: str, updates: dict) -> Conversation | None:
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return None
        new_conversation = apply_updates(conversation, updates)
        self.conversations[conversation_id] = new_conversation
        return new_conversation

    def delete_conversation(self, conversation_id: str) -> bool:
        if conversation_id not in self.conversations:
            return False
        del self.conversations[conversation_id]
        for key in [k for k, v in self.messages.items() if v.conversation_id == conversation_id]:
            del self.messages[key]
        return True

    def add_message(self, message: Message) -> Message:
        self.messages[message.id] = message
        return message

    def get_message(self, message_id: str) -> Message | None:
        return self.messages.get(message_id)

    def list_messages(
        self, conversation_id: str, limit: int | None = None, before: str | None = None
    ) -> list[Message]:
        thread = [m for m in self.messages.values() if m.conversation_id == conversation_id]
        return thread_window(thread, limit, before)

    def add_observation(self, observation: Observation) -> Observation:
        self.observations[observation.id] = observation
        return observation

    def get_observation(self, observation_id: str) -> Observation | None:
        return self.observations.get(observation_id)

    def list_observations(
        self, status: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Observation]:
        items = sorted(
            self.observations.values(),
            key=lambda observation: epoch_seconds(observation.created_at),
            reverse=True,
        )
        if status is not None:
            items = [item for item in items if item.status == status]
        return page(items, limit, offset)

    def update_observation(self, observation_id: str, updates: dict) -> Observation | None:
        observation = self.observations.get(observation_id)
        if not observation:
            return None
        new_observation = apply_updates(observation, updates)
        self.observations[observation_id] = new_observation
        return new_observation

    def delete_observation(self, observation_id: str) -> bool:
        return self.observations.pop(observation_id, None) is not None

    def save_brief(self, brief: Brief) -> Brief:
        self.brief = brief
        return brief

    def get_brief(self) -> Brief | None:
        return self.brief

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
        self.conversations.clear()
        self.messages.clear()
        self.observations.clear()
        self.brief = None
        self.signals.clear()

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
