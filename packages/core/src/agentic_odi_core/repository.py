"""Repository interfaces and in-memory implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, TypeVar

from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import (
    Alternative,
    AlternativeLink,
    CustomerOutcome,
    Evidence,
    Job,
    Outcome,
    ScheduledWork,
    ScoreSnapshot,
    Signal,
    Step,
    SurveyInputSet,
)

_Item = TypeVar("_Item")


def rank_outcomes(outcomes: list[Outcome], by: str = "opportunity_score") -> list[Outcome]:
    """Rank outcomes, highest first, unscored last.

    ``by`` keeps ``opportunity_score`` as the default so no existing caller
    changes silently. ``by="opportunity_low"`` ranks by the low end of the band
    — the honest ordering — falling back to the point score when no band is
    stored, and keeps unscored outcomes last rather than sorting them as zero.
    An unknown ``by`` is rejected rather than silently ignored.
    """
    if by not in ("opportunity_score", "opportunity_low"):
        raise ValueError(f"unknown ranking key {by!r}")

    def key(outcome: Outcome) -> tuple[bool, float]:
        if by == "opportunity_low":
            basis = outcome.opportunity_low
            if basis is None:
                basis = outcome.opportunity_score
        else:
            basis = outcome.opportunity_score
        return (basis is None, -(basis or 0.0))

    return sorted(outcomes, key=key)


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
    alternatives: dict[str, Alternative]
    alternative_links: dict[tuple[str, str], AlternativeLink]
    evidence: dict[str, Evidence]
    signals: dict[str, Signal]
    scheduled_work: dict[str, ScheduledWork]
    score_snapshots: list[ScoreSnapshot]
    survey_input_sets: dict[str, SurveyInputSet]

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
    def add_alternative(self, alternative: Alternative) -> Alternative: ...
    def get_alternative(self, alternative_id: str) -> Alternative | None: ...
    def list_alternatives(
        self, job_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Alternative]: ...
    def delete_alternative(self, alternative_id: str) -> bool: ...
    def link_alternative(self, link: AlternativeLink) -> AlternativeLink: ...
    def get_alternative_link(
        self, outcome_id: str, alternative_id: str
    ) -> AlternativeLink | None: ...
    def list_alternative_links(
        self,
        outcome_id: str | None = None,
        alternative_id: str | None = None,
        job_id: str | None = None,
    ) -> list[AlternativeLink]: ...
    def unlink_alternative(self, outcome_id: str, alternative_id: str) -> bool: ...
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

    def add_score_snapshot(self, snapshot: ScoreSnapshot) -> ScoreSnapshot: ...
    def list_score_snapshots(self, outcome_id: str | None = None) -> list[ScoreSnapshot]: ...
    def add_survey_input_set(self, input_set: SurveyInputSet) -> SurveyInputSet: ...
    def get_survey_input_set(self, outcome_id: str) -> SurveyInputSet | None: ...
    def delete_survey_input_set(self, outcome_id: str) -> bool: ...
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
        self.alternatives: dict[str, Alternative] = {}
        self.alternative_links: dict[tuple[str, str], AlternativeLink] = {}
        self.evidence: dict[str, Evidence] = {}
        self.signals: dict[str, Signal] = {}
        self.scheduled_work: dict[str, ScheduledWork] = {}
        self.score_snapshots: list[ScoreSnapshot] = []
        self.survey_input_sets: dict[str, SurveyInputSet] = {}

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
        for key in [k for k, v in self.alternatives.items() if v.job_id == job_id]:
            del self.alternatives[key]
        self._drop_orphan_alternative_links()
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
        self._drop_orphan_alternative_links()
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
            self.score_snapshots = [s for s in self.score_snapshots if s.outcome_id != outcome_id]
            self.survey_input_sets.pop(outcome_id, None)
            self._drop_orphan_alternative_links()
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

    def add_alternative(self, alternative: Alternative) -> Alternative:
        self.alternatives[alternative.id] = alternative
        return alternative

    def get_alternative(self, alternative_id: str) -> Alternative | None:
        return self.alternatives.get(alternative_id)

    def list_alternatives(
        self, job_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Alternative]:
        if job_id is None:
            items = list(self.alternatives.values())
        else:
            items = [a for a in self.alternatives.values() if a.job_id == job_id]
        return page(items, limit, offset)

    def delete_alternative(self, alternative_id: str) -> bool:
        if alternative_id not in self.alternatives:
            return False
        del self.alternatives[alternative_id]
        for key in [k for k in self.alternative_links if k[1] == alternative_id]:
            del self.alternative_links[key]
        return True

    def link_alternative(self, link: AlternativeLink) -> AlternativeLink:
        self.alternative_links[(link.outcome_id, link.alternative_id)] = link
        return link

    def get_alternative_link(self, outcome_id: str, alternative_id: str) -> AlternativeLink | None:
        return self.alternative_links.get((outcome_id, alternative_id))

    def list_alternative_links(
        self,
        outcome_id: str | None = None,
        alternative_id: str | None = None,
        job_id: str | None = None,
    ) -> list[AlternativeLink]:
        items = list(self.alternative_links.values())
        if outcome_id is not None:
            items = [link for link in items if link.outcome_id == outcome_id]
        if alternative_id is not None:
            items = [link for link in items if link.alternative_id == alternative_id]
        if job_id is not None:
            # A link carries no job of its own; it belongs to the job its
            # alternative belongs to. Reading a whole job's links in one call is
            # what lets a facet avoid one request per outcome.
            items = [
                link
                for link in items
                if (alternative := self.alternatives.get(link.alternative_id)) is not None
                and alternative.job_id == job_id
            ]
        return items

    def unlink_alternative(self, outcome_id: str, alternative_id: str) -> bool:
        return self.alternative_links.pop((outcome_id, alternative_id), None) is not None

    def _drop_orphan_alternative_links(self) -> None:
        """Drop links whose outcome or alternative no longer exists.

        An alternative or outcome deletion must not leave a link that reads as a
        live observation of something that is gone.
        """
        for key in [
            k
            for k in self.alternative_links
            if k[0] not in self.outcomes or k[1] not in self.alternatives
        ]:
            del self.alternative_links[key]

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

    def add_score_snapshot(self, snapshot: ScoreSnapshot) -> ScoreSnapshot:
        self.score_snapshots.append(snapshot)
        return snapshot

    def list_score_snapshots(self, outcome_id: str | None = None) -> list[ScoreSnapshot]:
        if outcome_id is None:
            return list(self.score_snapshots)
        return [s for s in self.score_snapshots if s.outcome_id == outcome_id]

    def add_survey_input_set(self, input_set: SurveyInputSet) -> SurveyInputSet:
        outcome = self.outcomes.get(input_set.outcome_id)
        if outcome is None:
            raise ValidationError(
                f"cannot retain inputs for unknown outcome {input_set.outcome_id!r}"
            )
        if outcome.job_id != input_set.job_id:
            raise ValidationError(
                "a retained input set must belong to the outcome's own job; "
                f"outcome job {outcome.job_id!r} != input set job {input_set.job_id!r}"
            )
        self.survey_input_sets[input_set.outcome_id] = input_set
        return input_set

    def get_survey_input_set(self, outcome_id: str) -> SurveyInputSet | None:
        return self.survey_input_sets.get(outcome_id)

    def delete_survey_input_set(self, outcome_id: str) -> bool:
        return self.survey_input_sets.pop(outcome_id, None) is not None

    def clear(self) -> None:
        self.jobs.clear()
        self.scheduled_work.clear()
        self.steps.clear()
        self.outcomes.clear()
        self.customer_outcomes.clear()
        self.alternatives.clear()
        self.alternative_links.clear()
        self.evidence.clear()
        self.signals.clear()
        self.score_snapshots.clear()
        self.survey_input_sets.clear()

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
