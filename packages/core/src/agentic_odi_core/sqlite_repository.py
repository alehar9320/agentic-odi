"""SQLite-backed repository using append-only IntentStore for events/audit."""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ValidationError

from agentic_odi_core.events import DEFAULT_DEVICE, DEFAULT_WORKSPACE, Event
from agentic_odi_core.intent_store import IntentStore
from agentic_odi_core.models import (
    Bet,
    CustomerOutcome,
    Decision,
    Evidence,
    Job,
    NotificationRule,
    Outcome,
    ScheduledWork,
    ScoreSnapshot,
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


def _jsonable_updates(updates: dict[str, Any]) -> dict[str, Any]:
    """Coerce update values to JSON-safe forms for the append-only event log.

    ``measured_at`` is a ``datetime`` and ``status`` is an enum; the event store
    serializes payloads with ``json.dumps``, so they must be encoded here rather
    than failing at append time.
    """
    from datetime import date as _date
    from datetime import datetime as _datetime

    from pydantic import BaseModel as _BaseModel

    def encode(value: Any) -> Any:
        if isinstance(value, _BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, _datetime):
            return value.isoformat()
        if isinstance(value, _date):
            return value.isoformat()
        if hasattr(value, "value"):  # Enum
            return value.value
        return value

    return {key: encode(value) for key, value in updates.items()}


class SQLiteRepository(Repository):
    def __init__(
        self,
        db_path: str | None = None,
        workspace_id: str | None = None,
        device_id: str | None = None,
    ) -> None:
        if db_path is None:
            db_path = os.environ.get("AGENTIC_ODI_DB", os.path.expanduser("~/.agentic-odi/odi.db"))
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
        self.signals: dict[str, Signal] = {}
        self.scheduled_work: dict[str, ScheduledWork] = {}
        self.decisions: dict[str, Decision] = {}
        self.score_snapshots: dict[str, ScoreSnapshot] = {}
        self.bets: dict[str, Bet] = {}
        self.notification_rules: dict[str, NotificationRule] = {}
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
        elif et == "EVIDENCE_DELETED":
            self.evidence.pop(p["id"], None)
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
        elif et == "DECISION_RECORDED":
            self.decisions[p["id"]] = Decision.model_validate(p)
        elif et == "DECISION_SUPERSEDED":
            decision = self.decisions.get(p["id"])
            if decision is not None:
                merged = decision.model_dump()
                merged["superseded_by"] = p.get("superseded_by")
                merged["superseded_at"] = p.get("superseded_at")
                try:
                    self.decisions[p["id"]] = Decision.model_validate(merged)
                except ValidationError:
                    pass
        elif et == "SCORE_SNAPSHOT_RECORDED":
            self.score_snapshots[p["id"]] = ScoreSnapshot.model_validate(p)
        elif et == "BET_CREATED":
            self.bets[p["id"]] = Bet.model_validate(p)
        elif et == "BET_UPDATED":
            self._merge_updates(self.bets, p, Bet)
        elif et == "NOTIFICATION_RULE_SET":
            rule = NotificationRule.model_validate(p)
            self.notification_rules[rule.kind.value] = rule
        self._last_event_id = max(self._last_event_id, ev["id"])

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

    def list_signals(
        self, unread_only: bool = False, limit: int | None = 50, job_id: str | None = None
    ) -> list[Signal]:
        with self._lock:
            self._sync()
            candidates = [
                signal
                for signal in self.signals.values()
                if job_id is None or signal.job_id == job_id
            ]
            items = unread_signals(candidates) if unread_only else rank_signals(candidates)
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

    def add_decision(self, decision: Decision) -> Decision:
        with self._lock:
            self.store.append(
                "DECISION_RECORDED",
                decision.model_dump(mode="json"),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return decision

    def get_decision(self, decision_id: str) -> Decision | None:
        with self._lock:
            self._sync()
            return self.decisions.get(decision_id)

    def list_decisions(self, job_id: str) -> list[Decision]:
        with self._lock:
            self._sync()
            items = [d for d in self.decisions.values() if d.job_id == job_id]
            return sorted(items, key=lambda d: (d.decided_at, d.id))

    def supersede_decision(
        self, decision_id: str, *, superseded_by: str, superseded_at: datetime
    ) -> Decision | None:
        with self._lock:
            self._sync()
            if decision_id not in self.decisions:
                return None
            self.store.append(
                "DECISION_SUPERSEDED",
                {
                    "id": decision_id,
                    "superseded_by": superseded_by,
                    "superseded_at": _jsonable_updates({"v": superseded_at})["v"],
                },
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return self.decisions.get(decision_id)

    def add_score_snapshot(self, snapshot: ScoreSnapshot) -> ScoreSnapshot:
        with self._lock:
            self.store.append(
                "SCORE_SNAPSHOT_RECORDED",
                snapshot.model_dump(mode="json"),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return snapshot

    def get_score_snapshot(self, snapshot_id: str) -> ScoreSnapshot | None:
        with self._lock:
            self._sync()
            return self.score_snapshots.get(snapshot_id)

    def list_score_snapshots(self, outcome_id: str) -> list[ScoreSnapshot]:
        with self._lock:
            self._sync()
            items = [s for s in self.score_snapshots.values() if s.outcome_id == outcome_id]
            return sorted(items, key=lambda s: (s.at, s.id))

    def add_bet(self, bet: Bet) -> Bet:
        with self._lock:
            self.store.append(
                "BET_CREATED",
                bet.model_dump(mode="json"),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return bet

    def get_bet(self, bet_id: str) -> Bet | None:
        with self._lock:
            self._sync()
            return self.bets.get(bet_id)

    def list_bets(self, job_id: str | None = None) -> list[Bet]:
        with self._lock:
            self._sync()
            items = list(self.bets.values())
            if job_id is not None:
                items = [b for b in items if b.job_id == job_id]
            return sorted(items, key=lambda b: (b.measure_by, b.created_at, b.id))

    def update_bet(self, bet_id: str, updates: dict) -> Bet | None:
        with self._lock:
            self._sync()
            bet = self.bets.get(bet_id)
            if not bet:
                return None
            current = bet.model_dump()
            current.update(updates)
            try:
                new_bet = Bet.model_validate(current)
            except ValidationError:
                return None
            self.store.append(
                "BET_UPDATED",
                {"id": bet_id, "updates": _jsonable_updates(updates)},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return new_bet

    def set_notification_rule(self, rule: NotificationRule) -> NotificationRule:
        with self._lock:
            self.store.append(
                "NOTIFICATION_RULE_SET",
                rule.model_dump(mode="json"),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return rule

    def list_notification_rules(self) -> list[NotificationRule]:
        with self._lock:
            self._sync()
            return sorted(self.notification_rules.values(), key=lambda r: r.kind.value)

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

    def health(self) -> bool:
        """True when the SQLite connection answers a trivial query."""
        with self._lock:
            try:
                self.store.conn.execute("SELECT 1").fetchone()
            except sqlite3.Error:
                return False
            return True
