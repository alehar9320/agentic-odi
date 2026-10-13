"""Service layer implementing business logic."""

from __future__ import annotations

import uuid
from typing import Any

from core.models import (
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Job,
    Outcome,
    Step,
    compute_opportunity_score,
)
from core.repository import Repository


class JobNotFoundError(Exception):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(job_id)


class CustomerOutcomeNotFoundError(Exception):
    def __init__(self, outcome_id: str) -> None:
        self.outcome_id = outcome_id
        super().__init__(outcome_id)


class ValueOutOfRangeError(Exception):
    pass


class ODIService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def add_job(self, name: str, description: str | None = None) -> Job:
        job = Job(name=name, description=description)
        return self.repo.add_job(job)

    def get_jobs(self) -> list[Job]:
        return self.repo.list_jobs()

    def get_job(self, job_id: str) -> Job | None:
        return self.repo.get_job(job_id)

    def add_step(self, job_id: str, name: str, order: int) -> Step:
        step = Step(id=str(uuid.uuid4()), job_id=job_id, name=name, order=order)
        return self.repo.add_step(step)

    def get_job_map(self, job_id: str) -> list[Step]:
        steps = self.repo.get_steps_for_job(job_id)
        return sorted(steps, key=lambda s: s.order)

    def add_outcome(
        self,
        job_id: str,
        statement: str,
        importance: float | None = None,
        satisfaction: float | None = None,
        step_id: str | None = None,
    ) -> Outcome:
        if importance is not None and not (1.0 <= importance <= 10.0):
            raise ValueOutOfRangeError()
        if satisfaction is not None and not (1.0 <= satisfaction <= 10.0):
            raise ValueOutOfRangeError()
        opportunity_score = None
        if importance is not None and satisfaction is not None:
            opportunity_score = compute_opportunity_score(importance, satisfaction)
        outcome = Outcome(
            id=str(uuid.uuid4()),
            job_id=job_id,
            step_id=step_id,
            statement=statement,
            importance=importance,
            satisfaction=satisfaction,
            opportunity_score=opportunity_score,
        )
        return self.repo.add_outcome(outcome)

    def get_outcomes(self, job_id: str, step_id: str | None = None) -> list[Outcome]:
        return self.repo.get_outcomes(job_id, step_id)

    def add_customer_outcome(
        self,
        job_id: str,
        customer_value: CustomerValue | dict[str, Any],
        business_value: BusinessValue | dict[str, Any],
        step_id: str | None = None,
    ) -> CustomerOutcome:
        if isinstance(customer_value, dict):
            cv = CustomerValue.model_validate(customer_value)
        else:
            cv = customer_value
        if isinstance(business_value, dict):
            bv = BusinessValue.model_validate(business_value)
        else:
            bv = business_value
        co = CustomerOutcome(
            id=str(uuid.uuid4()),
            job_id=job_id,
            step_id=step_id,
            customer_value=cv,
            business_value=bv,
        )
        return self.repo.add_customer_outcome(co)

    def get_customer_outcome(self, outcome_id: str) -> CustomerOutcome:
        co = self.repo.get_customer_outcome(outcome_id)
        if not co:
            raise CustomerOutcomeNotFoundError(outcome_id)
        return co

    def list_customer_outcomes(self, job_id: str | None = None) -> list[CustomerOutcome]:
        return self.repo.list_customer_outcomes(job_id)

    def update_customer_outcome(self, outcome_id: str, updates: dict[str, Any]) -> CustomerOutcome:
        res = self.repo.update_customer_outcome(outcome_id, updates)
        if not res:
            raise CustomerOutcomeNotFoundError(outcome_id)
        return res

    def delete_customer_outcome(self, outcome_id: str) -> None:
        ok = self.repo.delete_customer_outcome(outcome_id)
        if not ok:
            raise CustomerOutcomeNotFoundError(outcome_id)

    def compute_opportunity(self, importance: float, satisfaction: float) -> float:
        return compute_opportunity_score(importance, satisfaction)
