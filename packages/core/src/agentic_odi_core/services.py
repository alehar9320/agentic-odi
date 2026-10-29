"""Service layer implementing business logic."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from agentic_odi_core.errors import NotFoundError, ValidationError
from agentic_odi_core.evaluation import (
    OutcomeStatementError,
    evaluate_outcome_statement,
    require_outcome_statement,
)
from agentic_odi_core.models import (
    JOB_STAGE_INDEX,
    Brief,
    BusinessValue,
    Conversation,
    CustomerOutcome,
    CustomerValue,
    Evidence,
    EvidenceItemType,
    Job,
    JobStage,
    Message,
    MessageRole,
    Observation,
    ObservationCategory,
    ObservationStatus,
    Outcome,
    ScheduledWork,
    ScheduledWorkStatus,
    ScheduledWorkTriggerType,
    Step,
    V2MOM,
    compute_opportunity_score,
)
from agentic_odi_core.repository import Repository, page


class JobNotFoundError(NotFoundError):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(job_id, "job")


class StepNotFoundError(NotFoundError):
    def __init__(self, step_id: str) -> None:
        self.step_id = step_id
        super().__init__(step_id, "step")


class OutcomeNotFoundError(NotFoundError):
    def __init__(self, outcome_id: str) -> None:
        self.outcome_id = outcome_id
        super().__init__(outcome_id, "outcome")


class CustomerOutcomeNotFoundError(NotFoundError):
    def __init__(self, outcome_id: str) -> None:
        self.outcome_id = outcome_id
        super().__init__(outcome_id, "customer_outcome")


class ScheduledWorkNotFoundError(NotFoundError, ValueError):
    """Raised when scheduled work cannot be located.

    Also a :class:`ValueError`, because the caller supplied an id that does not
    resolve — an invalid argument value.
    """

    def __init__(self, work_id: str, hint: str | None = None) -> None:
        self.work_id = work_id
        super().__init__(work_id, "scheduled work", hint)


class EvidenceNotFoundError(NotFoundError, ValueError):
    """Raised when an evidence record cannot be located.

    Also a :class:`ValueError`, because the caller supplied an id that does not
    resolve — an invalid argument value.
    """

    def __init__(self, evidence_id: str, hint: str | None = None) -> None:
        self.evidence_id = evidence_id
        super().__init__(evidence_id, "evidence", hint)


class ConversationNotFoundError(NotFoundError):
    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        super().__init__(conversation_id, "conversation")


class ObservationNotFoundError(NotFoundError):
    def __init__(self, observation_id: str) -> None:
        self.observation_id = observation_id
        super().__init__(observation_id, "observation")


class ValueOutOfRangeError(ValidationError):
    pass


class InvalidOutcomeStatementError(OutcomeStatementError):
    """A statement does not match the ODI desired-outcome format.

    Carries the individual issues so the caller can show the fix next to the
    field that needs it instead of a single opaque message.
    """

    def __init__(self, verdict: dict[str, Any]) -> None:
        super().__init__(verdict)


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


_TITLE_LENGTH = 80


def _now_iso() -> str:
    """A JSON-safe timestamp, since updates travel to the event log as payloads."""
    return datetime.now(timezone.utc).isoformat()


class ODIService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def add_job(self, name: str, description: str | None = None) -> Job:
        job = Job(name=name, description=description)
        return self.repo.add_job(job)

    def get_jobs(self, limit: int | None = None, offset: int = 0) -> list[Job]:
        return self.repo.list_jobs(limit=limit, offset=offset)

    def get_job(self, job_id: str) -> Job | None:
        return self.repo.get_job(job_id)

    def get_step(self, step_id: str) -> Step | None:
        return self.repo.get_step(step_id)

    def get_outcome(self, outcome_id: str) -> Outcome | None:
        return self.repo.get_outcome(outcome_id)

    def update_job(self, job_id: str, updates: dict[str, Any]) -> Job:
        res = self.repo.update_job(job_id, updates)
        if not res:
            raise JobNotFoundError(job_id)
        return res

    def delete_job(self, job_id: str) -> None:
        ok = self.repo.delete_job(job_id)
        if not ok:
            raise JobNotFoundError(job_id)

    def update_step(self, step_id: str, updates: dict[str, Any]) -> Step:
        res = self.repo.update_step(step_id, updates)
        if not res:
            raise StepNotFoundError(step_id)
        return res

    def delete_step(self, step_id: str) -> None:
        ok = self.repo.delete_step(step_id)
        if not ok:
            raise StepNotFoundError(step_id)

    def update_outcome(self, outcome_id: str, updates: dict[str, Any]) -> Outcome:
        existing = self.repo.get_outcome(outcome_id)
        if existing is None:
            raise OutcomeNotFoundError(outcome_id)
        statement = updates.get("statement", existing.statement)
        importance = updates.get("importance", existing.importance)
        satisfaction = updates.get("satisfaction", existing.satisfaction)
        if importance is not None and not (1.0 <= importance <= 10.0):
            raise ValueOutOfRangeError("importance must be between 1.0 and 10.0")
        if satisfaction is not None and not (1.0 <= satisfaction <= 10.0):
            raise ValueOutOfRangeError("satisfaction must be between 1.0 and 10.0")
        require_outcome_statement(statement)
        if importance is not None and satisfaction is not None:
            updates = dict(updates)
            updates["opportunity_score"] = compute_opportunity_score(importance, satisfaction)
        else:
            updates = dict(updates)
            updates["opportunity_score"] = None
        res = self.repo.update_outcome(outcome_id, updates)
        if not res:
            raise OutcomeNotFoundError(outcome_id)
        return res

    def delete_outcome(self, outcome_id: str) -> None:
        ok = self.repo.delete_outcome(outcome_id)
        if not ok:
            raise OutcomeNotFoundError(outcome_id)

    def add_step(
        self,
        job_id: str,
        name: str,
        order: int,
        stage: JobStage | None = None,
        allow_empty_job_map: bool = False,
    ) -> Step:
        if self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        if not 1 <= order <= 8:
            raise ValueOutOfRangeError("Step order must be between 1 and 8 (Ulwick's job map).")
        existing_outcomes = self.repo.get_outcomes(job_id)
        existing_customer_outcomes = self.repo.list_customer_outcomes(job_id)
        if not existing_outcomes and not existing_customer_outcomes and not allow_empty_job_map:
            raise ValidationError(
                "Add at least one desired outcome before building the job map; "
                "outcomes are what give the steps their meaning. "
                "Use allow_empty_job_map=True to stage a map deliberately (audited)."
            )
        stage_index = JOB_STAGE_INDEX.get(stage) if stage is not None else None
        step = Step(
            id=str(uuid.uuid4()),
            job_id=job_id,
            name=name,
            order=order,
            stage=stage,
            stage_index=stage_index,
        )
        return self.repo.add_step(step)

    def get_job_map(self, job_id: str, limit: int | None = None, offset: int = 0) -> list[Step]:
        # Sort by canonical stage_index when present, falling back to order:
        # a page of the map must be the first steps by stage, not whichever
        # steps happened to be stored first.
        steps = list(self.repo.get_steps_for_job(job_id))
        steps.sort(key=lambda s: (s.stage_index if s.stage_index is not None else 99, s.order))
        return page(steps, limit, offset)

    def add_outcome(
        self,
        job_id: str,
        statement: str,
        importance: float,
        satisfaction: float,
        step_id: str | None = None,
        validate_statement: bool = True,
    ) -> Outcome:
        if self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        if step_id is not None and self.repo.get_step(step_id) is None:
            raise StepNotFoundError(step_id)
        if not (1.0 <= importance <= 10.0):
            raise ValueOutOfRangeError("importance must be between 1.0 and 10.0")
        if not (1.0 <= satisfaction <= 10.0):
            raise ValueOutOfRangeError("satisfaction must be between 1.0 and 10.0")
        if validate_statement:
            verdict = evaluate_outcome_statement(statement)
            if not verdict["valid"]:
                raise InvalidOutcomeStatementError(verdict)
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

    def get_outcomes(
        self,
        job_id: str,
        step_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: str = "opportunity_score",
    ) -> list[Outcome]:
        return self.repo.get_outcomes(job_id, step_id, limit=limit, offset=offset, sort=sort)

    def add_customer_outcome(
        self,
        job_id: str,
        customer_value: CustomerValue | dict[str, Any],
        business_value: BusinessValue | dict[str, Any],
        step_id: str | None = None,
    ) -> CustomerOutcome:
        if self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        if step_id is not None and self.repo.get_step(step_id) is None:
            raise StepNotFoundError(step_id)
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

    def list_customer_outcomes(
        self,
        job_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[CustomerOutcome]:
        return self.repo.list_customer_outcomes(job_id, limit=limit, offset=offset)

    def update_customer_outcome(self, outcome_id: str, updates: dict[str, Any]) -> CustomerOutcome:
        res = self.repo.update_customer_outcome(outcome_id, updates)
        if not res:
            raise CustomerOutcomeNotFoundError(outcome_id)
        return res

    def delete_customer_outcome(self, outcome_id: str) -> None:
        ok = self.repo.delete_customer_outcome(outcome_id)
        if not ok:
            raise CustomerOutcomeNotFoundError(outcome_id)

    def add_evidence(
        self,
        source_name: str,
        source_kind: str,
        name: str,
        content: str,
        item_type: EvidenceItemType = "manual",
        url: str | None = None,
        raw: dict[str, Any] | None = None,
        job_id: str | None = None,
        step_id: str | None = None,
        outcome_id: str | None = None,
    ) -> Evidence:
        resolved_job_id = job_id
        if step_id is not None:
            step = self.repo.get_step(step_id)
            if step is None:
                raise StepNotFoundError(step_id)
            if resolved_job_id is None:
                resolved_job_id = step.job_id
            elif step.job_id != resolved_job_id:
                raise ValidationError("step_id does not belong to job_id")
        if outcome_id is not None:
            outcome = self.repo.get_outcome(outcome_id)
            if outcome is None:
                raise OutcomeNotFoundError(outcome_id)
            if resolved_job_id is None:
                resolved_job_id = outcome.job_id
            elif outcome.job_id != resolved_job_id:
                raise ValidationError("outcome_id does not belong to job_id")
            if step_id is not None and outcome.step_id not in (None, step_id):
                raise ValidationError("outcome_id does not belong to step_id")
        if resolved_job_id is not None and self.repo.get_job(resolved_job_id) is None:
            raise JobNotFoundError(resolved_job_id)
        evidence = Evidence(
            id=str(uuid.uuid4()),
            source_name=source_name,
            source_kind=source_kind,
            item_type=item_type,
            name=name,
            content=content,
            url=url,
            raw=raw or {},
            job_id=resolved_job_id,
            step_id=step_id,
            outcome_id=outcome_id,
        )
        return self.repo.add_evidence(evidence)

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        return self.repo.get_evidence(evidence_id)

    def list_evidence(
        self,
        job_id: str | None = None,
        step_id: str | None = None,
        outcome_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Evidence]:
        return self.repo.list_evidence(
            job_id=job_id, step_id=step_id, outcome_id=outcome_id, limit=limit, offset=offset
        )

    def delete_evidence(self, evidence_id: str) -> None:
        if not self.repo.delete_evidence(evidence_id):
            raise EvidenceNotFoundError(
                evidence_id,
                "List the stored records with list_evidence() to find a valid id.",
            )

    def promote_evidence(
        self,
        evidence_id: str,
        target: str,
        job_id: str | None = None,
        statement: str | None = None,
        name: str | None = None,
        importance: float | None = None,
        satisfaction: float | None = None,
    ) -> Job | Outcome:
        evidence = self.repo.get_evidence(evidence_id)
        if evidence is None:
            raise EvidenceNotFoundError(
                evidence_id,
                "List the stored records with list_evidence() to find a valid id.",
            )
        if target == "job":
            label = (
                (name or evidence.name).strip() or _first_line(evidence.content) or "Imported job"
            )
            return self.add_job(label, description=evidence.content or None)
        if target == "outcome":
            target_job_id = job_id or evidence.job_id
            if target_job_id is None:
                raise ValidationError("job_id is required to promote evidence to an outcome")
            text = (
                statement
                or evidence.name.strip()
                or _first_line(evidence.content)
                or "Untitled outcome"
            )
            if importance is None or satisfaction is None:
                raise ValidationError(
                    "Promoting evidence to an outcome requires both importance and satisfaction scores."
                )
            return self.add_outcome(
                target_job_id,
                text,
                importance=importance,
                satisfaction=satisfaction,
                step_id=evidence.step_id,
            )
        raise ValidationError(f"Unknown promotion target: {target}")

    def compute_opportunity(self, importance: float, satisfaction: float) -> float:
        return compute_opportunity_score(importance, satisfaction)

    def start_conversation(self, title: str | None = None) -> Conversation:
        return self.repo.add_conversation(Conversation(title=title))

    def list_conversations(self, limit: int | None = None, offset: int = 0) -> list[Conversation]:
        return self.repo.list_conversations(limit=limit, offset=offset)

    def get_conversation(self, conversation_id: str) -> Conversation:
        conversation = self.repo.get_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    def conversation_thread(
        self, conversation_id: str, limit: int | None = None, before: str | None = None
    ) -> list[Message]:
        """The thread oldest first — the order a reloaded transcript renders in."""
        self.get_conversation(conversation_id)
        return self.repo.list_messages(conversation_id, limit=limit, before=before)

    def append_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str = "",
        parts: list[dict[str, Any]] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        model: str | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        message_id: str | None = None,
        parent_id: str | None = None,
    ) -> Message:
        conversation = self.get_conversation(conversation_id)
        message = self.repo.add_message(
            Message(
                id=message_id or str(uuid.uuid4()),
                conversation_id=conversation_id,
                parent_id=parent_id,
                role=role,
                content=content,
                parts=list(parts or []),
                tool_calls=list(tool_calls or []),
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
        )
        updates: dict[str, Any] = {"updated_at": _now_iso(), "head_id": message.id}
        if conversation.title is None and role == "user":
            title = _first_line(content)[:_TITLE_LENGTH]
            if title:
                updates["title"] = title
        self.repo.update_conversation(conversation_id, updates)
        return message

    def update_conversation(self, conversation_id: str, updates: dict[str, Any]) -> Conversation:
        updated = self.repo.update_conversation(
            conversation_id, {**updates, "updated_at": _now_iso()}
        )
        if updated is None:
            raise ConversationNotFoundError(conversation_id)
        return updated

    def delete_conversation(self, conversation_id: str) -> None:
        if not self.repo.delete_conversation(conversation_id):
            raise ConversationNotFoundError(conversation_id)

    def remember(
        self,
        text: str,
        category: ObservationCategory = "other",
        conversation_id: str | None = None,
        source_message_id: str | None = None,
        data: dict[str, Any] | None = None,
        confidence: float = 0.5,
    ) -> Observation:
        """Write what the agent learned as a proposal, never as a confirmed fact."""
        stripped = text.strip()
        if not stripped:
            raise ValidationError("an observation needs text")
        return self.repo.add_observation(
            Observation(
                text=stripped,
                category=category,
                conversation_id=conversation_id,
                source_message_id=source_message_id,
                data=dict(data or {}),
                confidence=confidence,
            )
        )

    def list_observations(
        self, status: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Observation]:
        return self.repo.list_observations(status=status, limit=limit, offset=offset)

    def confirmed_observations(self) -> list[Observation]:
        """The only observations an agent may carry forward into a prompt."""
        return self.repo.list_observations(status="confirmed")

    def get_observation(self, observation_id: str) -> Observation:
        observation = self.repo.get_observation(observation_id)
        if observation is None:
            raise ObservationNotFoundError(observation_id)
        return observation

    def update_observation(self, observation_id: str, updates: dict[str, Any]) -> Observation:
        updated = self.repo.update_observation(
            observation_id, {**updates, "updated_at": _now_iso()}
        )
        if updated is None:
            raise ObservationNotFoundError(observation_id)
        return updated

    def set_observation_status(self, observation_id: str, status: ObservationStatus) -> Observation:
        if status not in ("confirmed", "dismissed", "proposed"):
            raise ValidationError(f"unknown observation status: {status}")
        return self.update_observation(observation_id, {"status": status})

    def delete_observation(self, observation_id: str) -> None:
        if not self.repo.delete_observation(observation_id):
            raise ObservationNotFoundError(observation_id)

    def save_brief(
        self,
        product_name: str = "",
        product_url: str = "",
        target_user: str = "",
        job_statement: str = "",
        core_problem: str = "",
        v2mom: V2MOM | None = None,
    ) -> Brief:
        return self.repo.save_brief(
            Brief(
                product_name=product_name,
                product_url=product_url,
                target_user=target_user,
                job_statement=job_statement,
                core_problem=core_problem,
                v2mom=v2mom,
            )
        )

    def get_brief(self) -> Brief | None:
        return self.repo.get_brief()

    def schedule_work(
        self,
        name: str,
        schedule_expression: str,
        agent_id: str = "default-agent",
        trigger_type: ScheduledWorkTriggerType | str = ScheduledWorkTriggerType.ONESHOT,
        payload: dict[str, Any] | None = None,
        job_id: str | None = None,
    ) -> ScheduledWork:
        if job_id is not None and self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        if isinstance(trigger_type, str):
            trigger_type = ScheduledWorkTriggerType(trigger_type)
        work = ScheduledWork(
            id=str(uuid.uuid4()),
            name=name,
            agent_id=agent_id,
            trigger_type=trigger_type,
            schedule_expression=schedule_expression,
            payload=payload or {},
            status=ScheduledWorkStatus.SCHEDULED,
            job_id=job_id,
        )
        return self.repo.add_scheduled_work(work)

    def get_scheduled_work(self, work_id: str) -> ScheduledWork:
        work = self.repo.get_scheduled_work(work_id)
        if work is None:
            raise ScheduledWorkNotFoundError(work_id)
        return work

    def list_scheduled_work(
        self, job_id: str | None = None, status: str | None = None
    ) -> list[ScheduledWork]:
        return self.repo.list_scheduled_work(job_id=job_id, status=status)

    def cancel_scheduled_work(self, work_id: str) -> ScheduledWork:
        work = self.repo.get_scheduled_work(work_id)
        if work is None:
            raise ScheduledWorkNotFoundError(work_id)
        updated = self.repo.update_scheduled_work(
            work_id, {"status": ScheduledWorkStatus.CANCELLED}
        )
        if updated is None:
            raise ScheduledWorkNotFoundError(work_id)
        return updated

    def trigger_scheduled_work(self, work_id: str) -> ScheduledWork:
        from datetime import datetime, timezone

        work = self.repo.get_scheduled_work(work_id)
        if work is None:
            raise ScheduledWorkNotFoundError(work_id)
        now_str = datetime.now(timezone.utc).isoformat()
        # No executor exists yet (#95): the work is dispatched and this is the
        # record of it. Claiming a result would be inventing one.
        updates = {
            "status": ScheduledWorkStatus.RUNNING,
            "last_run_at": now_str,
            "result_summary": (
                f"Dispatched at {now_str}; no executor is installed, so nothing has run."
            ),
        }
        updated = self.repo.update_scheduled_work(work_id, updates)
        if updated is None:
            raise ScheduledWorkNotFoundError(work_id)
        return updated
