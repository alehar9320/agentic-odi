"""SQLite-backed repository using append-only IntentStore for events/audit."""

from __future__ import annotations

import os
import threading
from typing import Any

from pydantic import BaseModel, ValidationError

from agentic_odi_core.events import DEFAULT_WORKSPACE, Event, resolve_device_id
from agentic_odi_core.intent_store import IntentStore
from agentic_odi_core.models import (
    Brief,
    Conversation,
    CustomerOutcome,
    Evidence,
    Job,
    Message,
    Observation,
    Outcome,
    Step,
    compute_opportunity_score,
)
from agentic_odi_core.repository import (
    Repository,
    epoch_seconds,
    page,
    rank_outcomes,
    thread_window,
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
        # A real device id, persisted on first use, so two installs are
        # distinguishable in the event log instead of both claiming "local".
        self._device_id = device_id or resolve_device_id()
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
        self.conversations: dict[str, Conversation] = {}
        self.messages: dict[str, Message] = {}
        self.observations: dict[str, Observation] = {}
        self.brief: Brief | None = None
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
        elif et == "CUSTOMER_OUTCOME_DELETED":
            self.customer_outcomes.pop(p["id"], None)
        elif et == "CONVERSATION_CREATED":
            self.conversations[p["id"]] = Conversation.model_validate(p)
        elif et == "CONVERSATION_UPDATED":
            self._merge_updates(self.conversations, p, Conversation)
        elif et == "CONVERSATION_DELETED":
            conversation_id = p["id"]
            self.conversations.pop(conversation_id, None)
            for key in [
                k for k, v in self.messages.items() if v.conversation_id == conversation_id
            ]:
                del self.messages[key]
        elif et == "MESSAGE_APPENDED":
            message = Message.model_validate(p)
            self.messages[message.id] = message
        elif et == "OBSERVATION_CREATED":
            observation = Observation.model_validate(p)
            self.observations[observation.id] = observation
        elif et == "OBSERVATION_UPDATED":
            self._merge_updates(self.observations, p, Observation)
        elif et == "BRIEF_SAVED":
            self.brief = Brief.model_validate(p)
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
    ) -> list[Outcome]:
        with self._lock:
            self._sync()
            outs = [o for o in self.outcomes.values() if o.job_id == job_id]
            if step_id is not None:
                outs = [o for o in outs if o.step_id == step_id]
            return page(rank_outcomes(outs), limit, offset)

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

    def _append(self, event_type: str, payload: dict) -> None:
        self.store.append(
            event_type,
            payload,
            workspace_id=self._workspace_id,
            device_id=self._device_id,
        )

    def add_conversation(self, conversation: Conversation) -> Conversation:
        with self._lock:
            stored = conversation.model_copy(
                update={"workspace_id": self._workspace_id, "device_id": self._device_id}
            )
            self._append("CONVERSATION_CREATED", stored.model_dump(mode="json"))
            self._sync()
            return stored

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._lock:
            self._sync()
            return self.conversations.get(conversation_id)

    def list_conversations(self, limit: int | None = None, offset: int = 0) -> list[Conversation]:
        with self._lock:
            self._sync()
            ordered = sorted(
                self.conversations.values(),
                key=lambda conversation: epoch_seconds(conversation.updated_at),
                reverse=True,
            )
            return page(ordered, limit, offset)

    def update_conversation(self, conversation_id: str, updates: dict) -> Conversation | None:
        with self._lock:
            self._sync()
            if conversation_id not in self.conversations:
                return None
            self._append(
                "CONVERSATION_UPDATED",
                {"id": conversation_id, "updates": updates},
            )
            self._sync()
            return self.conversations.get(conversation_id)

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._lock:
            self._sync()
            if conversation_id not in self.conversations:
                return False
            self._append("CONVERSATION_DELETED", {"id": conversation_id})
            self._sync()
            return True

    def add_message(self, message: Message) -> Message:
        with self._lock:
            stored = message.model_copy(update={"workspace_id": self._workspace_id})
            self._append("MESSAGE_APPENDED", stored.model_dump(mode="json"))
            self._sync()
            return stored

    def get_message(self, message_id: str) -> Message | None:
        with self._lock:
            self._sync()
            return self.messages.get(message_id)

    def list_messages(
        self, conversation_id: str, limit: int | None = None, before: str | None = None
    ) -> list[Message]:
        with self._lock:
            self._sync()
            thread = [m for m in self.messages.values() if m.conversation_id == conversation_id]
            return thread_window(thread, limit, before)

    def add_observation(self, observation: Observation) -> Observation:
        with self._lock:
            stored = observation.model_copy(update={"workspace_id": self._workspace_id})
            self._append("OBSERVATION_CREATED", stored.model_dump(mode="json"))
            self._sync()
            return stored

    def get_observation(self, observation_id: str) -> Observation | None:
        with self._lock:
            self._sync()
            return self.observations.get(observation_id)

    def list_observations(
        self, status: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Observation]:
        with self._lock:
            self._sync()
            items = sorted(
                self.observations.values(),
                key=lambda observation: epoch_seconds(observation.created_at),
                reverse=True,
            )
            if status is not None:
                items = [item for item in items if item.status == status]
            return page(items, limit, offset)

    def update_observation(self, observation_id: str, updates: dict) -> Observation | None:
        with self._lock:
            self._sync()
            if observation_id not in self.observations:
                return None
            self._append("OBSERVATION_UPDATED", {"id": observation_id, "updates": updates})
            self._sync()
            return self.observations.get(observation_id)

    def save_brief(self, brief: Brief) -> Brief:
        with self._lock:
            stored = brief.model_copy(update={"workspace_id": self._workspace_id})
            self._append("BRIEF_SAVED", stored.model_dump(mode="json"))
            self._sync()
            return stored

    def get_brief(self) -> Brief | None:
        with self._lock:
            self._sync()
            return self.brief

    def clear(self) -> None:
        with self._lock:
            self.store.clear()
            self._load_snapshot()

    def reload(self) -> None:
        """Re‑load the local snapshot from the event store."""
        self._load_snapshot()

    def close(self) -> None:
        """Close the event store and let SQLite clean up its journal files."""
        with self._lock:
            self.store.close()
