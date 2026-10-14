"""SQLite-backed repository using append-only IntentStore for events/audit."""

from __future__ import annotations

import os
from typing import Any

from core.intent_store import IntentStore
from core.models import CustomerOutcome, Job, Outcome, Step
from core.repository import Repository


class SQLiteRepository(Repository):
    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            db_path = os.environ.get("AGENTIC_ODI_DB", os.path.expanduser("~/.agentic-odi/odi.db"))
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.store = IntentStore(db_path)
        # For compatibility with existing semantics, we also maintain a materialized
        # view in memory for fast reads (in-memory snapshot) - simple approach for now.
        self._load_snapshot()

    def _load_snapshot(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.steps: dict[str, Step] = {}
        self.outcomes: dict[str, Outcome] = {}
        self.customer_outcomes: dict[str, CustomerOutcome] = {}
        for ev in self.store.get_stream():
            et = ev["type"]
            p = ev["payload"]
            if et == "JOB_CREATED":
                self.jobs[p["id"]] = Job.model_validate(p)
            elif et == "STEP_CREATED":
                self.steps[p["id"]] = Step.model_validate(p)
            elif et == "OUTCOME_CREATED":
                self.outcomes[p["id"]] = Outcome.model_validate(p)
            elif et == "CUSTOMER_OUTCOME_CREATED":
                self.customer_outcomes[p["id"]] = CustomerOutcome.model_validate(p)
            elif et == "CUSTOMER_OUTCOME_UPDATED":
                cid = p["id"]
                co = self.customer_outcomes.get(cid)
                if co is not None:
                    current = co.model_dump(exclude_unset=True)
                    current.update(p.get("updates", {}))
                    try:
                        self.customer_outcomes[cid] = co.model_validate(current)
                    except Exception:  # noqa: BLE001  # nosec B110
                        pass
            elif et == "CUSTOMER_OUTCOME_DELETED":
                cid = p["id"]
                self.customer_outcomes.pop(cid, None)
        # also snapshot jobs/steps/outcomes? we emitted above

    def add_job(self, job: Job) -> Job:
        self.store.append("JOB_CREATED", job.model_dump())
        self.jobs[job.id] = job
        return job

    def list_jobs(self) -> list[Job]:
        return list(self.jobs.values())

    def get_job(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def add_step(self, step: Step) -> Step:
        self.store.append("STEP_CREATED", step.model_dump())
        self.steps[step.id] = step
        return step

    def get_steps_for_job(self, job_id: str) -> list[Step]:
        return [s for s in self.steps.values() if s.job_id == job_id]

    def add_outcome(self, outcome: Outcome) -> Outcome:
        self.store.append("OUTCOME_CREATED", outcome.model_dump())
        self.outcomes[outcome.id] = outcome
        return outcome

    def get_outcomes(self, job_id: str, step_id: str | None = None) -> list[Outcome]:
        outs = [o for o in self.outcomes.values() if o.job_id == job_id]
        if step_id is not None:
            outs = [o for o in outs if o.step_id == step_id]
        return outs

    def add_customer_outcome(self, co: CustomerOutcome) -> CustomerOutcome:
        self.store.append("CUSTOMER_OUTCOME_CREATED", co.model_dump())
        self.customer_outcomes[co.id] = co
        return co

    def get_customer_outcome(self, outcome_id: str) -> CustomerOutcome | None:
        return self.customer_outcomes.get(outcome_id)

    def list_customer_outcomes(self, job_id: str | None = None) -> list[CustomerOutcome]:
        if job_id is None:
            return list(self.customer_outcomes.values())
        return [co for co in self.customer_outcomes.values() if co.job_id == job_id]

    def update_customer_outcome(
        self, outcome_id: str, updates: dict[str, Any]
    ) -> CustomerOutcome | None:
        co = self.customer_outcomes.get(outcome_id)
        if not co:
            return None
        current = co.model_dump(exclude_unset=True)
        current.update(updates)
        try:
            new_co = co.model_validate(current)
        except Exception:  # noqa: BLE001
            return None
        self.store.append("CUSTOMER_OUTCOME_UPDATED", {"id": outcome_id, "updates": updates})
        self.customer_outcomes[outcome_id] = new_co
        return new_co

    def delete_customer_outcome(self, outcome_id: str) -> bool:
        if outcome_id in self.customer_outcomes:
            self.store.append("CUSTOMER_OUTCOME_DELETED", {"id": outcome_id})
            del self.customer_outcomes[outcome_id]
            return True
        return False

    def clear(self) -> None:
        self.store.clear()
        self._load_snapshot()
