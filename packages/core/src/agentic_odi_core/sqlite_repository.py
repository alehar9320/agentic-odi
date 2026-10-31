"""SQLite-backed repository using append-only IntentStore for events/audit."""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ValidationError

from agentic_odi_core.events import DEFAULT_DEVICE, DEFAULT_WORKSPACE, Event
from agentic_odi_core.intent_store import IntentStore
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
    compute_opportunity_score,
)
from agentic_odi_core.repository import (
    Repository,
    page,
    rank_signals,
    sort_outcomes,
    unread_signals,
)

DEFAULT_DB_PATH = os.path.expanduser("~/.agentic-odi/odi.db")


def resolve_db_path(db_path: str | None = None) -> str:
    """The store path a command will actually open.

    One place resolves the default so every surface — a write, a read, and the
    ``store`` report — names the same file rather than each guessing.
    """
    if db_path:
        return db_path
    return os.environ.get("AGENTIC_ODI_DB") or DEFAULT_DB_PATH


class SQLiteRepository(Repository):
    def __init__(
        self,
        db_path: str | None = None,
        workspace_id: str | None = None,
        device_id: str | None = None,
    ) -> None:
        db_path = resolve_db_path(db_path)
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._lock = threading.RLock()
        self._workspace_id = workspace_id or os.environ.get(
            "AGENTIC_ODI_WORKSPACE", DEFAULT_WORKSPACE
        )
        self._device_id = device_id or os.environ.get("AGENTIC_ODI_DEVICE_ID", DEFAULT_DEVICE)
        self.store = IntentStore(db_path, check_same_thread=False)
        self._last_event_id = 0
        self._backfilled = False
        self._load_snapshot()
        self._backfill_legacy_outcomes()

    def _load_snapshot(self) -> None:
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
        self._last_event_id = 0
        for ev in self.store.get_stream(workspace_id=self._workspace_id, replay_order=True):
            self._apply_event(ev)

    def _backfill_legacy_outcomes(self) -> None:
        """One-time migration: backfill null scores on legacy outcomes.

        Assigns importance=5.0, satisfaction=5.0 to any outcome missing either
        score, records an OUTCOME_BACKFILLED event per outcome, and marks the
        repository as backfilled so reloads do not repeat the migration.
        """
        if self._backfilled:
            return
        needs_backfill = [
            o for o in self.outcomes.values() if o.importance is None or o.satisfaction is None
        ]
        if not needs_backfill:
            self._backfilled = True
            return
        for outcome in needs_backfill:
            updates: dict[str, Any] = {}
            importance = outcome.importance
            if importance is None:
                importance = 5.0
                updates["importance"] = importance
            satisfaction = outcome.satisfaction
            if satisfaction is None:
                satisfaction = 5.0
                updates["satisfaction"] = satisfaction
            updates["opportunity_score"] = compute_opportunity_score(
                importance,
                satisfaction,
            )
            self.store.append(
                "OUTCOME_BACKFILLED",
                {"id": outcome.id, "updates": updates},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
        self._sync()
        self._backfilled = True

    def _sync(self) -> None:
        for ev in self.store.get_stream(workspace_id=self._workspace_id):
            if ev["id"] > self._last_event_id:
                self._apply_event(ev)

    def _apply_event(self, ev: Event) -> None:
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
        elif et == "EVIDENCE_CREATED":
            self.evidence[p["id"]] = Evidence.model_validate(p)
        elif et == "CANDIDATE_CREATED":
            self.candidates[p["id"]] = OutcomeCandidate.model_validate(p)
        elif et == "DECISION_CREATED":
            self.decisions[p["id"]] = DecisionRecord.model_validate(p)
        elif et == "BET_CREATED":
            self.bets[p["id"]] = BetRecord.model_validate(p)
        elif et == "MEASUREMENT_CREATED":
            self.measurements[p["id"]] = MeasurementRecord.model_validate(p)
        elif et == "JOB_UPDATED":
            self._merge_updates(self.jobs, p, Job)
        elif et == "STEP_UPDATED":
            self._merge_updates(self.steps, p, Step)
        elif et == "OUTCOME_UPDATED":
            self._merge_updates(self.outcomes, p, Outcome)
        elif et == "CUSTOMER_OUTCOME_UPDATED":
            self._merge_updates(self.customer_outcomes, p, CustomerOutcome)
        elif et == "JOB_DELETED":
            job_id = p["id"]
            self.jobs.pop(job_id, None)
            for key in [k for k, v in self.steps.items() if v.job_id == job_id]:
                del self.steps[key]
            for key in [k for k, v in self.outcomes.items() if v.job_id == job_id]:
                del self.outcomes[key]
            for key in [k for k, v in self.customer_outcomes.items() if v.job_id == job_id]:
                del self.customer_outcomes[key]
            for key in [k for k, v in self.candidates.items() if v.job_id == job_id]:
                del self.candidates[key]
            self._cascade_decisions()
            for key in [
                k
                for k, v in self.evidence.items()
                if v.job_id == job_id
                or (v.step_id is not None and v.step_id not in self.steps)
                or (v.outcome_id is not None and v.outcome_id not in self.outcomes)
            ]:
                del self.evidence[key]
        elif et == "STEP_DELETED":
            step_id = p["id"]
            self.steps.pop(step_id, None)
            for key in [k for k, v in self.outcomes.items() if v.step_id == step_id]:
                del self.outcomes[key]
            for key in [k for k, v in self.customer_outcomes.items() if v.step_id == step_id]:
                del self.customer_outcomes[key]
            for key in [k for k, v in self.candidates.items() if v.step_id == step_id]:
                del self.candidates[key]
            self._cascade_decisions()
            for key in [
                k
                for k, v in self.evidence.items()
                if v.step_id == step_id
                or (v.outcome_id is not None and v.outcome_id not in self.outcomes)
            ]:
                del self.evidence[key]
        elif et == "OUTCOME_DELETED":
            outcome_id = p["id"]
            self.outcomes.pop(outcome_id, None)
            for key in [k for k, v in self.evidence.items() if v.outcome_id == outcome_id]:
                del self.evidence[key]
            for key in [k for k, v in self.candidates.items() if v.outcome_id == outcome_id]:
                del self.candidates[key]
            self._cascade_decisions()
        elif et == "EVIDENCE_DELETED":
            self.evidence.pop(p["id"], None)
        elif et == "CANDIDATE_UPDATED":
            self._merge_updates(self.candidates, p, OutcomeCandidate)
        elif et == "CANDIDATE_DELETED":
            self.candidates.pop(p["id"], None)
        elif et == "DECISION_DELETED":
            decision_id = p["id"]
            self.decisions.pop(decision_id, None)
            for key in [k for k, v in self.bets.items() if v.decision_id == decision_id]:
                del self.bets[key]
        elif et == "BET_DELETED":
            bet_id = p["id"]
            self.bets.pop(bet_id, None)
            for key in [k for k, v in self.measurements.items() if v.bet_id == bet_id]:
                del self.measurements[key]
        elif et == "MEASUREMENT_DELETED":
            self.measurements.pop(p["id"], None)
        elif et == "SCHEDULED_WORK_CREATED":
            self.scheduled_work[p["id"]] = ScheduledWork.model_validate(p)
        elif et == "SCHEDULED_WORK_UPDATED":
            self._merge_updates(self.scheduled_work, p, ScheduledWork)
        elif et == "SCHEDULED_WORK_DELETED":
            self.scheduled_work.pop(p["id"], None)

        elif et == "CUSTOMER_OUTCOME_DELETED":
            self.customer_outcomes.pop(p["id"], None)
        elif et == "SIGNAL_CREATED":
            self.signals[p["id"]] = Signal.model_validate(p)
        elif et == "SIGNAL_READ":
            self._merge_updates(self.signals, p, Signal)
        elif et == "SIGNAL_DISMISSED":
            self._merge_updates(self.signals, p, Signal)
        self._last_event_id = max(self._last_event_id, ev["id"])

    def _cascade_decisions(self) -> None:
        """Drop decisions whose subject is gone, and their bets and measurements.

        A decision names an outcome as its subject; when that outcome is deleted
        the decision (and everything measured against it) no longer has a
        referent, so it is removed with it rather than left dangling.
        """
        orphaned = [k for k, d in self.decisions.items() if d.subject_id not in self.outcomes]
        for decision_id in orphaned:
            del self.decisions[decision_id]
        for key in [k for k, b in self.bets.items() if b.decision_id not in self.decisions]:
            del self.bets[key]
        for key in [k for k, m in self.measurements.items() if m.bet_id not in self.bets]:
            del self.measurements[key]

    @staticmethod
    def _merge_updates(entities: dict[str, Any], p: dict, model: type[BaseModel]) -> None:
        entity = entities.get(p["id"])
        if entity is None:
            return
        current = entity.model_dump(exclude_unset=True)
        current.update(p.get("updates", {}))
        try:
            entities[p["id"]] = model.model_validate(current)
        except ValidationError:
            pass

    def add_job(self, job: Job) -> Job:
        with self._lock:
            self.store.append(
                "JOB_CREATED",
                job.model_dump(),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return job

    def list_jobs(self, limit: int | None = None, offset: int = 0) -> list[Job]:
        with self._lock:
            self._sync()
            return page(list(self.jobs.values()), limit, offset)

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            self._sync()
            return self.jobs.get(job_id)

    def update_job(self, job_id: str, updates: dict) -> Job | None:
        with self._lock:
            self._sync()
            job = self.jobs.get(job_id)
            if not job:
                return None
            current = job.model_dump(exclude_unset=True)
            current.update(updates)
            new_job = job.model_validate(current)
            self.store.append(
                "JOB_UPDATED",
                {"id": job_id, "updates": updates},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return new_job

    def delete_job(self, job_id: str) -> bool:
        with self._lock:
            self._sync()
            if job_id not in self.jobs:
                return False
            self.store.append(
                "JOB_DELETED",
                {"id": job_id},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return True

    def add_step(self, step: Step) -> Step:
        with self._lock:
            self.store.append(
                "STEP_CREATED",
                step.model_dump(),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return step

    def get_step(self, step_id: str) -> Step | None:
        with self._lock:
            self._sync()
            return self.steps.get(step_id)

    def get_steps_for_job(
        self, job_id: str, limit: int | None = None, offset: int = 0
    ) -> list[Step]:
        with self._lock:
            self._sync()
            steps = [s for s in self.steps.values() if s.job_id == job_id]
            return page(steps, limit, offset)

    def update_step(self, step_id: str, updates: dict) -> Step | None:
        with self._lock:
            self._sync()
            step = self.steps.get(step_id)
            if not step:
                return None
            current = step.model_dump(exclude_unset=True)
            current.update(updates)
            new_step = step.model_validate(current)
            self.store.append(
                "STEP_UPDATED",
                {"id": step_id, "updates": updates},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return new_step

    def delete_step(self, step_id: str) -> bool:
        with self._lock:
            self._sync()
            if step_id not in self.steps:
                return False
            self.store.append(
                "STEP_DELETED",
                {"id": step_id},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return True

    def add_outcome(self, outcome: Outcome) -> Outcome:
        with self._lock:
            self.store.append(
                "OUTCOME_CREATED",
                outcome.model_dump(),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return outcome

    def get_outcome(self, outcome_id: str) -> Outcome | None:
        with self._lock:
            self._sync()
            return self.outcomes.get(outcome_id)

    def get_outcomes(
        self,
        job_id: str,
        step_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: str = "opportunity_score",
    ) -> list[Outcome]:
        with self._lock:
            self._sync()
            outs = [o for o in self.outcomes.values() if o.job_id == job_id]
            if step_id is not None:
                outs = [o for o in outs if o.step_id == step_id]
            return page(sort_outcomes(outs, sort), limit, offset)

    def update_outcome(self, outcome_id: str, updates: dict) -> Outcome | None:
        with self._lock:
            self._sync()
            outcome = self.outcomes.get(outcome_id)
            if not outcome:
                return None
            current = outcome.model_dump(exclude_unset=True)
            current.update(updates)
            new_outcome = outcome.model_validate(current)
            self.store.append(
                "OUTCOME_UPDATED",
                {"id": outcome_id, "updates": updates},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return new_outcome

    def delete_outcome(self, outcome_id: str) -> bool:
        with self._lock:
            self._sync()
            if outcome_id not in self.outcomes:
                return False
            self.store.append(
                "OUTCOME_DELETED",
                {"id": outcome_id},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return True

    def add_customer_outcome(self, co: CustomerOutcome) -> CustomerOutcome:
        with self._lock:
            self.store.append(
                "CUSTOMER_OUTCOME_CREATED",
                co.model_dump(),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return co

    def get_customer_outcome(self, outcome_id: str) -> CustomerOutcome | None:
        with self._lock:
            self._sync()
            return self.customer_outcomes.get(outcome_id)

    def list_customer_outcomes(
        self,
        job_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[CustomerOutcome]:
        with self._lock:
            self._sync()
            if job_id is None:
                items = list(self.customer_outcomes.values())
            else:
                items = [co for co in self.customer_outcomes.values() if co.job_id == job_id]
            return page(items, limit, offset)

    def update_customer_outcome(
        self, outcome_id: str, updates: dict[str, Any]
    ) -> CustomerOutcome | None:
        with self._lock:
            self._sync()
            co = self.customer_outcomes.get(outcome_id)
            if not co:
                return None
            current = co.model_dump(exclude_unset=True)
            current.update(updates)
            try:
                new_co = co.model_validate(current)
            except ValidationError:
                return None
            self.store.append(
                "CUSTOMER_OUTCOME_UPDATED",
                {"id": outcome_id, "updates": updates},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return new_co

    def add_evidence(self, evidence: Evidence) -> Evidence:
        with self._lock:
            self.store.append(
                "EVIDENCE_CREATED",
                evidence.model_dump(),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return evidence

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        with self._lock:
            self._sync()
            return self.evidence.get(evidence_id)

    def list_evidence(
        self,
        job_id: str | None = None,
        step_id: str | None = None,
        outcome_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Evidence]:
        with self._lock:
            self._sync()
            items = list(self.evidence.values())
            if job_id is not None:
                items = [item for item in items if item.job_id == job_id]
            if step_id is not None:
                items = [item for item in items if item.step_id == step_id]
            if outcome_id is not None:
                items = [item for item in items if item.outcome_id == outcome_id]
            return page(items, limit, offset)

    def delete_evidence(self, evidence_id: str) -> bool:
        with self._lock:
            self._sync()
            if evidence_id not in self.evidence:
                return False
            self.store.append(
                "EVIDENCE_DELETED",
                {"id": evidence_id},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return True

    def delete_customer_outcome(self, outcome_id: str) -> bool:
        with self._lock:
            self._sync()
            if outcome_id in self.customer_outcomes:
                self.store.append(
                    "CUSTOMER_OUTCOME_DELETED",
                    {"id": outcome_id},
                    workspace_id=self._workspace_id,
                    device_id=self._device_id,
                )
                self._sync()
                return True
            return False

    def add_candidate(self, candidate: OutcomeCandidate) -> OutcomeCandidate:
        with self._lock:
            self.store.append(
                "CANDIDATE_CREATED",
                candidate.model_dump(mode="json"),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return candidate

    def get_candidate(self, candidate_id: str) -> OutcomeCandidate | None:
        with self._lock:
            self._sync()
            return self.candidates.get(candidate_id)

    def list_candidates(
        self,
        quote_id: str | None = None,
        job_id: str | None = None,
        status: CandidateStatus | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[OutcomeCandidate]:
        with self._lock:
            self._sync()
            items = list(self.candidates.values())
            if quote_id is not None:
                items = [c for c in items if c.quote_id == quote_id]
            if job_id is not None:
                items = [c for c in items if c.job_id == job_id]
            if status is not None:
                items = [c for c in items if c.status is status]
            return page(items, limit, offset)

    def update_candidate(self, candidate_id: str, updates: dict) -> OutcomeCandidate | None:
        with self._lock:
            self._sync()
            candidate = self.candidates.get(candidate_id)
            if not candidate:
                return None
            # Full dump so the generated id is preserved, never regenerated.
            current = candidate.model_dump()
            current.update(updates)
            new_candidate = candidate.model_validate(current)
            self.store.append(
                "CANDIDATE_UPDATED",
                {"id": candidate_id, "updates": updates},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return new_candidate

    def add_decision(self, decision: DecisionRecord) -> DecisionRecord:
        with self._lock:
            self.store.append(
                "DECISION_CREATED",
                decision.model_dump(mode="json"),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return decision

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        with self._lock:
            self._sync()
            return self.decisions.get(decision_id)

    def list_decisions(
        self, subject_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[DecisionRecord]:
        with self._lock:
            self._sync()
            items = list(self.decisions.values())
            if subject_id is not None:
                items = [d for d in items if d.subject_id == subject_id]
            return page(items, limit, offset)

    def add_bet(self, bet: BetRecord) -> BetRecord:
        with self._lock:
            self.store.append(
                "BET_CREATED",
                bet.model_dump(mode="json"),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return bet

    def get_bet(self, bet_id: str) -> BetRecord | None:
        with self._lock:
            self._sync()
            return self.bets.get(bet_id)

    def list_bets(
        self, decision_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[BetRecord]:
        with self._lock:
            self._sync()
            items = list(self.bets.values())
            if decision_id is not None:
                items = [b for b in items if b.decision_id == decision_id]
            return page(items, limit, offset)

    def add_measurement(self, measurement: MeasurementRecord) -> MeasurementRecord:
        with self._lock:
            self.store.append(
                "MEASUREMENT_CREATED",
                measurement.model_dump(mode="json"),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return measurement

    def get_measurement(self, measurement_id: str) -> MeasurementRecord | None:
        with self._lock:
            self._sync()
            return self.measurements.get(measurement_id)

    def list_measurements(
        self, bet_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[MeasurementRecord]:
        with self._lock:
            self._sync()
            items = list(self.measurements.values())
            if bet_id is not None:
                items = [m for m in items if m.bet_id == bet_id]
            return page(items, limit, offset)

    def add_signal(self, signal: Signal) -> Signal:
        with self._lock:
            self.store.append(
                "SIGNAL_CREATED",
                signal.model_dump(mode="json"),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return signal

    def get_signal(self, signal_id: str) -> Signal | None:
        with self._lock:
            self._sync()
            return self.signals.get(signal_id)

    def list_signals(self, unread_only: bool = False, limit: int = 50) -> list[Signal]:
        with self._lock:
            self._sync()
            items = (
                unread_signals(list(self.signals.values()))
                if unread_only
                else rank_signals(list(self.signals.values()))
            )
            return page(items, limit)

    def mark_signal_read(self, signal_id: str) -> Signal | None:
        return self._stamp_signal(signal_id, "SIGNAL_READ", "read_at")

    def dismiss_signal(self, signal_id: str) -> Signal | None:
        return self._stamp_signal(signal_id, "SIGNAL_DISMISSED", "dismissed_at")

    def _stamp_signal(self, signal_id: str, event_type: str, field: str) -> Signal | None:
        with self._lock:
            self._sync()
            signal = self.signals.get(signal_id)
            if signal is None:
                return None
            if getattr(signal, field) is None:
                self.store.append(
                    event_type,
                    {"id": signal_id, "updates": {field: datetime.now(timezone.utc).isoformat()}},
                    workspace_id=self._workspace_id,
                    device_id=self._device_id,
                )
                self._sync()
                signal = self.signals[signal_id]
            return signal

    def count_unread_signals(self) -> int:
        with self._lock:
            self._sync()
            return len(unread_signals(list(self.signals.values())))

    def add_scheduled_work(self, work: ScheduledWork) -> ScheduledWork:
        with self._lock:
            self.store.append(
                "SCHEDULED_WORK_CREATED",
                work.model_dump(),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return work

    def get_scheduled_work(self, work_id: str) -> ScheduledWork | None:
        with self._lock:
            self._sync()
            return self.scheduled_work.get(work_id)

    def list_scheduled_work(
        self, job_id: str | None = None, status: str | None = None
    ) -> list[ScheduledWork]:
        with self._lock:
            self._sync()
            items = list(self.scheduled_work.values())
            if job_id is not None:
                items = [item for item in items if item.job_id == job_id]
            if status is not None:
                items = [item for item in items if item.status == status]
            return items

    def update_scheduled_work(self, work_id: str, updates: dict[str, Any]) -> ScheduledWork | None:
        with self._lock:
            self._sync()
            work = self.scheduled_work.get(work_id)
            if not work:
                return None
            current = work.model_dump(exclude_unset=True)
            current.update(updates)
            try:
                new_work = work.model_validate(current)
            except ValidationError:
                return None
            self.store.append(
                "SCHEDULED_WORK_UPDATED",
                {"id": work_id, "updates": updates},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return new_work

    def delete_scheduled_work(self, work_id: str) -> bool:
        with self._lock:
            self._sync()
            if work_id in self.scheduled_work:
                self.store.append(
                    "SCHEDULED_WORK_DELETED",
                    {"id": work_id},
                    workspace_id=self._workspace_id,
                    device_id=self._device_id,
                )
                self._sync()
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self.store.clear()
            self._load_snapshot()

    def reload(self) -> None:
        """Re‑load the local snapshot from the event store."""
        self._load_snapshot()

    def commit(self) -> None:
        """Flush any open transaction in the event store to disk."""
        with self._lock:
            self.store.commit()

    def close(self) -> None:
        """Close the event store and let SQLite clean up its journal files."""
        with self._lock:
            self.store.close()
