"""Repository interfaces and in-memory implementation."""

from __future__ import annotations

from typing import Protocol

from core.models import CustomerOutcome, Job, Outcome, Step


class Repository(Protocol):
    def add_job(self, job: Job) -> Job: ...
    def list_jobs(self) -> list[Job]: ...
    def get_job(self, job_id: str) -> Job | None: ...
    def add_step(self, step: Step) -> Step: ...
    def get_steps_for_job(self, job_id: str) -> list[Step]: ...
    def add_outcome(self, outcome: Outcome) -> Outcome: ...
    def get_outcomes(self, job_id: str, step_id: str | None = None) -> list[Outcome]: ...
    def add_customer_outcome(self, co: CustomerOutcome) -> CustomerOutcome: ...
    def get_customer_outcome(self, outcome_id: str) -> CustomerOutcome | None: ...
    def list_customer_outcomes(self, job_id: str | None = None) -> list[CustomerOutcome]: ...
    def update_customer_outcome(self, outcome_id: str, updates: dict) -> CustomerOutcome | None: ...
    def delete_customer_outcome(self, outcome_id: str) -> bool: ...
    def clear(self) -> None: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.steps: dict[str, Step] = {}
        self.outcomes: dict[str, Outcome] = {}
        self.customer_outcomes: dict[str, CustomerOutcome] = {}

    def add_job(self, job: Job) -> Job:
        self.jobs[job.id] = job
        return job

    def list_jobs(self) -> list[Job]:
        return list(self.jobs.values())

    def get_job(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def add_step(self, step: Step) -> Step:
        self.steps[step.id] = step
        return step

    def get_steps_for_job(self, job_id: str) -> list[Step]:
        return [s for s in self.steps.values() if s.job_id == job_id]

    def add_outcome(self, outcome: Outcome) -> Outcome:
        self.outcomes[outcome.id] = outcome
        return outcome

    def get_outcomes(self, job_id: str, step_id: str | None = None) -> list[Outcome]:
        outs = [o for o in self.outcomes.values() if o.job_id == job_id]
        if step_id is not None:
            outs = [o for o in outs if o.step_id == step_id]
        return outs

    def add_customer_outcome(self, co: CustomerOutcome) -> CustomerOutcome:
        self.customer_outcomes[co.id] = co
        return co

    def get_customer_outcome(self, outcome_id: str) -> CustomerOutcome | None:
        return self.customer_outcomes.get(outcome_id)

    def list_customer_outcomes(self, job_id: str | None = None) -> list[CustomerOutcome]:
        if job_id is None:
            return list(self.customer_outcomes.values())
        return [co for co in self.customer_outcomes.values() if co.job_id == job_id]

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

    def clear(self) -> None:
        self.jobs.clear()
        self.steps.clear()
        self.outcomes.clear()
        self.customer_outcomes.clear()
