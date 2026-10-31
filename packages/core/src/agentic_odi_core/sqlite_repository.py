"""SQLite-backed repository using append-only IntentStore for events/audit."""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ValidationError

from agentic_odi_core.errors import ValidationError as OdiValidationError
from agentic_odi_core.events import DEFAULT_DEVICE, DEFAULT_WORKSPACE, Event
from agentic_odi_core.intent_store import IntentStore
from agentic_odi_core.models import (
    Alternative,
    AlternativeLink,
    CustomerOutcome,
    Evidence,
    Job,
    Outcome,
    ScheduledWork,
    ScoreSnapshot,
    Segment,
    Signal,
    Step,
    Strategy,
    SurveyInputSet,
    compute_opportunity_score,
)
from agentic_odi_core.repository import (
    Repository,
    page,
    rank_signals,
    sort_outcomes,
    unread_signals,
)


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
        self._legacy_method_ids: set[str] = set()
        self._method_backfilled_ids: set[str] = set()
        self._load_snapshot()
        self._backfill_outcome_method()
        self._backfill_legacy_outcomes()

    def _load_snapshot(self) -> None:
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
        self.segments: dict[str, Segment] = {}
        self.strategies: dict[str, Strategy] = {}
        self._last_event_id = 0
        self._legacy_method_ids = set()
        self._method_backfilled_ids = set()
        for ev in self.store.get_stream(workspace_id=self._workspace_id, replay_order=True):
            self._apply_event(ev)

    def _backfill_outcome_method(self) -> None:
        """One-time migration: label legacy outcomes with their score method.

        Rows written before the method field existed are estimates by
        definition, so each gets an ``OUTCOME_METHOD_BACKFILLED`` event carrying
        ``score_method='estimate'``. The event is a no-op state-wise (the model
        default already produces it) but it is the auditable record that the
        label was applied rather than inferred. The pending set is derived from
        the replayed stream, so re-running adds no duplicate events.
        """
        pending = self._legacy_method_ids - self._method_backfilled_ids
        if not pending:
            return
        for outcome_id in sorted(pending):
            self.store.append(
                "OUTCOME_METHOD_BACKFILLED",
                {"id": outcome_id, "updates": {"score_method": "estimate"}},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
        self._sync()

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
            if "score_method" not in p:
                # A payload written before the method field existed: an estimate
                # by definition, labelled once by the method backfill.
                self._legacy_method_ids.add(p["id"])
            self.outcomes[p["id"]] = Outcome.model_validate(p)
        elif et == "OUTCOME_METHOD_BACKFILLED":
            self._method_backfilled_ids.add(p["id"])
            self._merge_updates(self.outcomes, p, Outcome)
        elif et == "CUSTOMER_OUTCOME_CREATED":
            self.customer_outcomes[p["id"]] = CustomerOutcome.model_validate(p)
        elif et == "EVIDENCE_CREATED":
            self.evidence[p["id"]] = Evidence.model_validate(p)
        elif et == "SCORE_SNAPSHOT_RECORDED":
            self.score_snapshots.append(ScoreSnapshot.model_validate(p))
        elif et == "SURVEY_INPUTS_RETAINED":
            input_set = SurveyInputSet.model_validate(p)
            self.survey_input_sets[input_set.outcome_id] = input_set
        elif et == "SURVEY_INPUTS_DELETED":
            self.survey_input_sets.pop(p["outcome_id"], None)
        elif et == "JOB_UPDATED":
            self._merge_updates(self.jobs, p, Job)
        elif et == "STEP_UPDATED":
            self._merge_updates(self.steps, p, Step)
        elif et == "OUTCOME_UPDATED":
            self._merge_updates(self.outcomes, p, Outcome)
        elif et == "CUSTOMER_OUTCOME_UPDATED":
            self._merge_updates(self.customer_outcomes, p, CustomerOutcome)
        elif et == "ALTERNATIVE_CREATED":
            self.alternatives[p["id"]] = Alternative.model_validate(p)
        elif et == "ALTERNATIVE_UPDATED":
            self._merge_updates(self.alternatives, p, Alternative)
        elif et == "ALTERNATIVE_DELETED":
            self.alternatives.pop(p["id"], None)
            for link_key in [k for k in self.alternative_links if k[1] == p["id"]]:
                del self.alternative_links[link_key]
        elif et == "ALTERNATIVE_LINKED":
            link = AlternativeLink.model_validate(p)
            self.alternative_links[(link.outcome_id, link.alternative_id)] = link
        elif et == "ALTERNATIVE_UNLINKED":
            self.alternative_links.pop((p["outcome_id"], p["alternative_id"]), None)
        elif et == "JOB_DELETED":
            job_id = p["id"]
            self.jobs.pop(job_id, None)
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
            self._drop_orphan_survey_input_sets()
        elif et == "STEP_DELETED":
            step_id = p["id"]
            self.steps.pop(step_id, None)
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
            self._drop_orphan_survey_input_sets()
        elif et == "OUTCOME_DELETED":
            outcome_id = p["id"]
            self.outcomes.pop(outcome_id, None)
            for key in [k for k, v in self.evidence.items() if v.outcome_id == outcome_id]:
                del self.evidence[key]
            self.score_snapshots = [s for s in self.score_snapshots if s.outcome_id != outcome_id]
            self.survey_input_sets.pop(outcome_id, None)
            self._drop_orphan_alternative_links()
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
        elif et == "SEGMENT_CREATED":
            self.segments[p["id"]] = Segment.model_validate(p)
        elif et == "SEGMENT_UPDATED":
            self._merge_updates(self.segments, p, Segment)
        elif et == "STRATEGY_CREATED":
            self.strategies[p["id"]] = Strategy.model_validate(p)
        elif et == "STRATEGY_UPDATED":
            self._merge_updates(self.strategies, p, Strategy)
        self._last_event_id = max(self._last_event_id, ev["id"])

    def _drop_orphan_survey_input_sets(self) -> None:
        """Drop retained inputs whose outcome no longer exists.

        Deleting a job or step removes its outcomes; the paired inputs those
        outcomes were bootstrapped from must go with them rather than outliving
        their outcome as an orphan set.
        """
        for outcome_id in [k for k in self.survey_input_sets if k not in self.outcomes]:
            del self.survey_input_sets[outcome_id]

    def _drop_orphan_alternative_links(self) -> None:
        """Drop links whose outcome or alternative no longer exists."""
        for key in [
            k
            for k in self.alternative_links
            if k[0] not in self.outcomes or k[1] not in self.alternatives
        ]:
            del self.alternative_links[key]

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

    def add_score_snapshot(self, snapshot: ScoreSnapshot) -> ScoreSnapshot:
        with self._lock:
            self.store.append(
                "SCORE_SNAPSHOT_RECORDED",
                snapshot.model_dump(),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return snapshot

    def list_score_snapshots(self, outcome_id: str | None = None) -> list[ScoreSnapshot]:
        with self._lock:
            self._sync()
            if outcome_id is None:
                return list(self.score_snapshots)
            return [s for s in self.score_snapshots if s.outcome_id == outcome_id]

    def add_survey_input_set(self, input_set: SurveyInputSet) -> SurveyInputSet:
        with self._lock:
            self._sync()
            outcome = self.outcomes.get(input_set.outcome_id)
            if outcome is None:
                raise OdiValidationError(
                    f"cannot retain inputs for unknown outcome {input_set.outcome_id!r}"
                )
            if outcome.job_id != input_set.job_id:
                raise OdiValidationError(
                    "a retained input set must belong to the outcome's own job; "
                    f"outcome job {outcome.job_id!r} != input set job {input_set.job_id!r}"
                )
            self.store.append(
                "SURVEY_INPUTS_RETAINED",
                input_set.model_dump(),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return input_set

    def get_survey_input_set(self, outcome_id: str) -> SurveyInputSet | None:
        with self._lock:
            self._sync()
            return self.survey_input_sets.get(outcome_id)

    def delete_survey_input_set(self, outcome_id: str) -> bool:
        with self._lock:
            self._sync()
            if outcome_id not in self.survey_input_sets:
                return False
            self.store.append(
                "SURVEY_INPUTS_DELETED",
                {"outcome_id": outcome_id},
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

    def add_alternative(self, alternative: Alternative) -> Alternative:
        with self._lock:
            self.store.append(
                "ALTERNATIVE_CREATED",
                alternative.model_dump(),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return alternative

    def get_alternative(self, alternative_id: str) -> Alternative | None:
        with self._lock:
            self._sync()
            return self.alternatives.get(alternative_id)

    def list_alternatives(
        self, job_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Alternative]:
        with self._lock:
            self._sync()
            if job_id is None:
                items = list(self.alternatives.values())
            else:
                items = [a for a in self.alternatives.values() if a.job_id == job_id]
            return page(items, limit, offset)

    def delete_alternative(self, alternative_id: str) -> bool:
        with self._lock:
            self._sync()
            if alternative_id not in self.alternatives:
                return False
            self.store.append(
                "ALTERNATIVE_DELETED",
                {"id": alternative_id},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return True

    def link_alternative(self, link: AlternativeLink) -> AlternativeLink:
        with self._lock:
            self.store.append(
                "ALTERNATIVE_LINKED",
                link.model_dump(),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return link

    def get_alternative_link(self, outcome_id: str, alternative_id: str) -> AlternativeLink | None:
        with self._lock:
            self._sync()
            return self.alternative_links.get((outcome_id, alternative_id))

    def list_alternative_links(
        self,
        outcome_id: str | None = None,
        alternative_id: str | None = None,
        job_id: str | None = None,
    ) -> list[AlternativeLink]:
        with self._lock:
            self._sync()
            items = list(self.alternative_links.values())
            if outcome_id is not None:
                items = [link for link in items if link.outcome_id == outcome_id]
            if alternative_id is not None:
                items = [link for link in items if link.alternative_id == alternative_id]
            if job_id is not None:
                items = [
                    link
                    for link in items
                    if (alternative := self.alternatives.get(link.alternative_id)) is not None
                    and alternative.job_id == job_id
                ]
            return items

    def unlink_alternative(self, outcome_id: str, alternative_id: str) -> bool:
        with self._lock:
            self._sync()
            if (outcome_id, alternative_id) not in self.alternative_links:
                return False
            self.store.append(
                "ALTERNATIVE_UNLINKED",
                {"outcome_id": outcome_id, "alternative_id": alternative_id},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return True

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

    def add_segment(self, segment: Segment) -> Segment:
        with self._lock:
            self.store.append(
                "SEGMENT_CREATED",
                segment.model_dump(mode="json"),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return segment

    def get_segment(self, segment_id: str) -> Segment | None:
        with self._lock:
            self._sync()
            return self.segments.get(segment_id)

    def list_segments(self, job_id: str | None = None) -> list[Segment]:
        with self._lock:
            self._sync()
            items = list(self.segments.values())
            if job_id is not None:
                items = [segment for segment in items if segment.job_id == job_id]
            return items

    def update_segment(self, segment_id: str, updates: dict[str, Any]) -> Segment | None:
        with self._lock:
            self._sync()
            segment = self.segments.get(segment_id)
            if segment is None:
                return None
            current = segment.model_dump(exclude_unset=True)
            current.update(updates)
            try:
                new_segment = segment.model_validate(current)
            except ValidationError:
                return None
            self.store.append(
                "SEGMENT_UPDATED",
                {"id": segment_id, "updates": updates},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return new_segment

    def add_strategy(self, strategy: Strategy) -> Strategy:
        with self._lock:
            self.store.append(
                "STRATEGY_CREATED",
                strategy.model_dump(mode="json"),
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return strategy

    def get_strategy(self, strategy_id: str) -> Strategy | None:
        with self._lock:
            self._sync()
            return self.strategies.get(strategy_id)

    def list_strategies(self, segment_id: str | None = None) -> list[Strategy]:
        with self._lock:
            self._sync()
            items = list(self.strategies.values())
            if segment_id is not None:
                items = [strategy for strategy in items if strategy.segment_id == segment_id]
            return items

    def update_strategy(self, strategy_id: str, updates: dict[str, Any]) -> Strategy | None:
        with self._lock:
            self._sync()
            strategy = self.strategies.get(strategy_id)
            if strategy is None:
                return None
            current = strategy.model_dump(exclude_unset=True)
            current.update(updates)
            try:
                new_strategy = strategy.model_validate(current)
            except ValidationError:
                return None
            self.store.append(
                "STRATEGY_UPDATED",
                {"id": strategy_id, "updates": updates},
                workspace_id=self._workspace_id,
                device_id=self._device_id,
            )
            self._sync()
            return new_strategy

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

    def health(self) -> bool:
        """True when the SQLite connection answers a trivial query."""
        with self._lock:
            try:
                self.store.conn.execute("SELECT 1").fetchone()
            except sqlite3.Error:
                return False
            return True
