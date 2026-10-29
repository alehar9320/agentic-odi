"""Repository interfaces and in-memory implementation."""

from __future__ import annotations

from typing import Protocol, TypeVar

from agentic_odi_core.models import CustomerOutcome, Evidence, Job, Outcome, ScheduledWork, Step

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

    def reload(self) -> None:
        """Reset in-memory state; there is no external store to re-read."""
        self.clear()

    def commit(self) -> None:
        """No-op: an in-memory store has nothing to flush."""

    def close(self) -> None:
        """No-op: an in-memory store holds no resources."""
