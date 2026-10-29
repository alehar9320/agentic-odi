"""Service layer implementing business logic."""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from agentic_odi_core.errors import ConflictError, NotFoundError, ValidationError
from agentic_odi_core.evaluation import (
    OutcomeStatementError,
    evaluate_outcome_statement,
    require_outcome_statement,
)
from agentic_odi_core.models import (
    BET_TRANSITIONS,
    JOB_STAGE_INDEX,
    JOB_STAGE_ORDER,
    Bet,
    BetMeasurementResult,
    BetStatus,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Decision,
    DecisionConfidence,
    Direction,
    Evidence,
    EvidenceItemType,
    Job,
    JobStage,
    NotificationRule,
    Outcome,
    RejectedOutcome,
    ScheduledWork,
    ScheduledWorkStatus,
    ScheduledWorkTriggerType,
    ScoreSnapshot,
    Signal,
    SignalKind,
    Step,
    compute_opportunity_score,
)
from agentic_odi_core.repository import Repository, page
from agentic_odi_core.signals import DEFAULT_SCORE_MOVE_THRESHOLD


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


class DecisionNotFoundError(NotFoundError):
    def __init__(self, decision_id: str) -> None:
        self.decision_id = decision_id
        super().__init__(decision_id, "decision")


class BetNotFoundError(NotFoundError):
    def __init__(self, bet_id: str) -> None:
        self.bet_id = bet_id
        super().__init__(bet_id, "bet")


class ScoreSnapshotNotFoundError(NotFoundError):
    def __init__(self, snapshot_id: str) -> None:
        self.snapshot_id = snapshot_id
        super().__init__(snapshot_id, "score_snapshot")


class InvalidBetTransitionError(ConflictError):
    """An illegal bet status transition, naming the legal successors."""

    def __init__(self, current: BetStatus, requested: BetStatus) -> None:
        legal = BET_TRANSITIONS.get(current, ())
        legal_text = ", ".join(status.value for status in legal) or "none (terminal)"
        super().__init__(
            f"cannot move a bet from '{current.value}' to '{requested.value}'; "
            f"legal next states: {legal_text}"
        )


class EvidenceNotFoundError(NotFoundError, ValueError):
    """Raised when an evidence record cannot be located.

    Also a :class:`ValueError`, because the caller supplied an id that does not
    resolve — an invalid argument value.
    """

    def __init__(self, evidence_id: str, hint: str | None = None) -> None:
        self.evidence_id = evidence_id
        super().__init__(evidence_id, "evidence", hint)


class ValueOutOfRangeError(ValidationError):
    pass


class SignalNotFoundError(NotFoundError):
    def __init__(self, signal_id: str) -> None:
        self.signal_id = signal_id
        super().__init__(signal_id, "signal")


DEFAULT_SIGNAL_DAILY_CAP = 20

_SEVERITY_RANK: dict[str, int] = {"info": 0, "notice": 1, "urgent": 2}


@dataclass
class SignalBudget:
    """The attention budget: a daily cap on surfaced signals and a floor.

    Signals past the cap are still recorded but marked ``suppressed``, so the
    badge never counts them. ``urgent`` signals bypass the cap entirely — a cap
    that can be silenced by an emergency is not a budget.
    """

    daily_cap: int = DEFAULT_SIGNAL_DAILY_CAP
    min_severity: str = "info"

    @classmethod
    def from_env(cls) -> SignalBudget:
        raw = os.environ.get("AGENTIC_ODI_SIGNAL_BUDGET", "")
        try:
            cap = int(raw) if raw else DEFAULT_SIGNAL_DAILY_CAP
        except ValueError:
            cap = DEFAULT_SIGNAL_DAILY_CAP
        return cls(daily_cap=max(cap, 0))

    def surfaces(self, severity: str, surfaced_today: int) -> bool:
        if severity == "urgent":
            return True
        if _SEVERITY_RANK[severity] < _SEVERITY_RANK[self.min_severity]:
            return False
        return surfaced_today < self.daily_cap


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


def _opportunity_crossing(before: float | None, after: float | None) -> tuple[str, str] | None:
    """Did the opportunity score cross 10, and in which direction?

    Crossing up is urgent — a big unserved opportunity just surfaced;
    crossing down is a notice.
    """
    if before is None or after is None:
        return None
    if before < 10.0 <= after:
        return ("up", "urgent")
    if before >= 10.0 > after:
        return ("down", "notice")
    return None


class ODIService:
    def __init__(self, repo: Repository, budget: SignalBudget | None = None) -> None:
        self.repo = repo
        #: ``None`` re-reads ``AGENTIC_ODI_SIGNAL_BUDGET`` per signal so a
        #: long-running sidecar picks up a changed cap without a restart.
        self.budget = budget

    def record_signal(
        self,
        kind: SignalKind,
        title: str,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        severity: str = "info",
        detail: str | None = None,
        discriminator: str = "",
        magnitude: float | None = None,
    ) -> Signal:
        """Record one fact. A signal with the same fingerprint already exists.

        ``discriminator`` is the thing that changed (a new score, a record id);
        the fingerprint is sha256 over ``kind|subject_kind|subject_id|
        discriminator``, so re-recording the same fact returns the first signal
        instead of spamming the feed.
        """
        fingerprint = hashlib.sha256(
            "|".join([kind.value, subject_kind or "", subject_id or "", discriminator]).encode(
                "utf-8"
            )
        ).hexdigest()
        for existing in self.repo.signals.values():
            if existing.fingerprint == fingerprint:
                return existing
        budget = self.budget or SignalBudget.from_env()
        today = datetime.now(timezone.utc).date()
        surfaced_today = sum(
            1
            for signal in self.repo.signals.values()
            if signal.created_at.date() == today
            and not signal.suppressed
            and signal.severity != "urgent"
        )
        signal = Signal(
            kind=kind,
            title=title[:120],
            detail=detail,
            subject_kind=subject_kind,  # type: ignore[arg-type]
            subject_id=subject_id,
            severity=severity,  # type: ignore[arg-type]
            suppressed=not budget.surfaces(severity, surfaced_today),
            magnitude=magnitude,
            fingerprint=fingerprint,
        )
        return self.repo.add_signal(signal)

    def list_signals(self, unread_only: bool = False, limit: int = 50) -> list[Signal]:
        return self.repo.list_signals(unread_only=unread_only, limit=limit)

    def mark_signal_read(self, signal_id: str) -> Signal:
        signal = self.repo.mark_signal_read(signal_id)
        if signal is None:
            raise SignalNotFoundError(signal_id)
        return signal

    def dismiss_signal(self, signal_id: str) -> Signal:
        signal = self.repo.dismiss_signal(signal_id)
        if signal is None:
            raise SignalNotFoundError(signal_id)
        return signal

    def count_unread_signals(self) -> int:
        return self.repo.count_unread_signals()

    def add_job(self, name: str, description: str | None = None) -> Job:
        job = Job(name=name, description=description)
        job = self.repo.add_job(job)
        self.record_signal(
            SignalKind.JOB_ADDED,
            f'Job added: "{job.name}"',
            subject_kind="job",
            subject_id=job.id,
            discriminator=job.id,
        )
        return job

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
        if "stage" in updates:
            self._emit_job_map_completed(res.job_id)
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
        self._emit_outcome_updates(existing, res)
        return res

    def _emit_outcome_updates(self, before: Outcome, after: Outcome) -> None:
        if before.importance != after.importance or before.satisfaction != after.satisfaction:
            self.record_signal(
                SignalKind.OUTCOME_SCORED,
                f'Outcome re-scored: "{after.statement[:60]}"',
                subject_kind="outcome",
                subject_id=after.id,
                detail=(
                    f"importance {before.importance} -> {after.importance}, "
                    f"satisfaction {before.satisfaction} -> {after.satisfaction}"
                ),
                discriminator=f"importance={after.importance},satisfaction={after.satisfaction}",
            )
        crossing = _opportunity_crossing(before.opportunity_score, after.opportunity_score)
        if crossing is not None:
            direction, severity = crossing
            self.record_signal(
                SignalKind.OPPORTUNITY_CROSSED,
                f'Opportunity score crossed 10 ({direction}): "{after.statement[:60]}"',
                subject_kind="outcome",
                subject_id=after.id,
                severity=severity,
                detail=f"{before.opportunity_score} -> {after.opportunity_score}",
                discriminator=f"{direction}:{after.opportunity_score}",
            )

    def _emit_job_map_completed(self, job_id: str) -> None:
        stages = {
            step.stage for step in self.repo.get_steps_for_job(job_id) if step.stage is not None
        }
        if len(stages) < len(JOB_STAGE_ORDER):
            return
        job = self.repo.get_job(job_id)
        label = job.name if job is not None else job_id
        self.record_signal(
            SignalKind.JOB_MAP_COMPLETED,
            f'Job map complete: "{label}" covers all {len(JOB_STAGE_ORDER)} stages',
            subject_kind="job",
            subject_id=job_id,
            severity="notice",
            discriminator="all-stages",
        )

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
        step = self.repo.add_step(step)
        self._emit_job_map_completed(job_id)
        return step

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
        evidence = self.repo.add_evidence(evidence)
        self.record_signal(
            SignalKind.EVIDENCE_INGESTED,
            f'Evidence from "{evidence.source_name}": {evidence.name[:60]}',
            subject_kind="evidence",
            subject_id=evidence.id,
            discriminator=evidence.id,
        )
        return evidence

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
            outcome = self.add_outcome(
                target_job_id,
                text,
                importance=importance,
                satisfaction=satisfaction,
                step_id=evidence.step_id,
            )
            self.record_signal(
                SignalKind.EVIDENCE_PROMOTED,
                f'Evidence promoted to an outcome: "{outcome.statement[:60]}"',
                subject_kind="outcome",
                subject_id=outcome.id,
                severity="notice",
                discriminator=outcome.id,
            )
            return outcome
        raise ValidationError(f"Unknown promotion target: {target}")

    def compute_opportunity(self, importance: float, satisfaction: float) -> float:
        return compute_opportunity_score(importance, satisfaction)

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

    # -- Decisions (C6) ----------------------------------------------------

    def record_decision(
        self,
        job_id: str,
        chosen_outcome_ids: list[str],
        rationale: str,
        decided_by: str,
        rejected: list[dict[str, Any]] | None = None,
        confidence: DecisionConfidence | str = DecisionConfidence.MEDIUM,
        decided_at: datetime | None = None,
    ) -> Decision:
        """Record a decision; a later decision supersedes the previous one.

        A decision that resolves to a choice must name at least one outcome.
        Referenced outcomes must belong to the decision's job, and a rejected
        alternative must carry a non-empty reason — the reason is the point of
        keeping rejected options.
        """
        if self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        if not rationale or not rationale.strip():
            raise ValidationError("decision rationale cannot be empty")
        if not decided_by or not decided_by.strip():
            raise ValidationError("decided_by cannot be empty")

        chosen = list(dict.fromkeys(chosen_outcome_ids or []))
        if not chosen:
            raise ValidationError("a decision must choose at least one outcome")

        rejected_models: list[RejectedOutcome] = []
        for raw in rejected or []:
            rejected_models.append(
                raw if isinstance(raw, RejectedOutcome) else RejectedOutcome.model_validate(raw)
            )

        chosen_set = set(chosen)
        rejected_ids = {item.outcome_id for item in rejected_models}
        if chosen_set & rejected_ids:
            raise ValidationError("an outcome cannot be both chosen and rejected")

        for outcome_id in chosen:
            outcome = self.repo.get_outcome(outcome_id)
            if outcome is None:
                raise OutcomeNotFoundError(outcome_id)
            if outcome.job_id != job_id:
                raise ValidationError(f"outcome {outcome_id} does not belong to job {job_id}")
        for item in rejected_models:
            outcome = self.repo.get_outcome(item.outcome_id)
            if outcome is None:
                raise OutcomeNotFoundError(item.outcome_id)
            if outcome.job_id != job_id:
                raise ValidationError(f"outcome {item.outcome_id} does not belong to job {job_id}")
            if not item.reason.strip():
                raise ValidationError("a rejected outcome needs a non-empty reason")

        if isinstance(confidence, str):
            confidence = DecisionConfidence(confidence)

        when = decided_at or _utcnow()
        decision = Decision(
            id=str(uuid.uuid4()),
            job_id=job_id,
            chosen_outcome_ids=chosen,
            rejected=rejected_models,
            rationale=rationale.strip(),
            decided_by=decided_by.strip(),
            decided_at=when,
            confidence=confidence,
        )

        # A new decision supersedes the previous live decision for the job
        # rather than overwriting it: the record of the argument that lost
        # is the product's memory.
        previous = [
            d
            for d in self.repo.list_decisions(job_id)
            if d.superseded_by is None and d.superseded_at is None
        ]
        created = self.repo.add_decision(decision)
        for prior in previous:
            if prior.id == created.id:
                continue
            self.repo.supersede_decision(
                prior.id,
                superseded_by=created.id,
                superseded_at=when,
            )
            self.record_signal(
                SignalKind.DECISION_SUPERSEDED,
                f"Decision superseded: {prior.rationale[:80]}",
                subject_kind="decision",
                subject_id=prior.id,
                severity="notice",
                detail=f"Replaced by {created.id}",
                discriminator=created.id,
            )
        return created

    def get_decision(self, decision_id: str) -> Decision:
        decision = self.repo.get_decision(decision_id)
        if decision is None:
            raise DecisionNotFoundError(decision_id)
        return decision

    def list_decisions(self, job_id: str) -> list[Decision]:
        if self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        return self.repo.list_decisions(job_id)

    def latest_decision(self, job_id: str) -> Decision | None:
        decisions = self.list_decisions(job_id)
        live = [d for d in decisions if d.superseded_by is None and d.superseded_at is None]
        if live:
            return live[-1]
        return decisions[-1] if decisions else None

    # -- Score snapshots (B6) ---------------------------------------------

    def record_score_snapshot(
        self,
        outcome_id: str,
        *,
        at: datetime | None = None,
        method: str | None = None,
        note: str | None = None,
        importance_n: int | None = None,
        satisfaction_n: int | None = None,
    ) -> ScoreSnapshot:
        """Capture the outcome's current accepted score as an append-only snapshot.

        The snapshot stores the score *and* its evidence companions, so a later
        delta can distinguish "the evidence changed" from "the estimate changed".
        """
        outcome = self.repo.get_outcome(outcome_id)
        if outcome is None:
            raise OutcomeNotFoundError(outcome_id)
        if outcome.importance is None or outcome.satisfaction is None:
            raise ValidationError(
                f"outcome {outcome_id} has no complete score to snapshot; "
                "set importance and satisfaction first"
            )
        if note is not None and len(note) > 500:
            raise ValidationError("score note cannot exceed 500 characters")
        snapshot = ScoreSnapshot(
            id=str(uuid.uuid4()),
            outcome_id=outcome_id,
            job_id=outcome.job_id,
            at=at or _utcnow(),
            importance=outcome.importance,
            satisfaction=outcome.satisfaction,
            importance_n=importance_n,
            satisfaction_n=satisfaction_n,
            method=method,
            note=note,
        )
        earlier = self.repo.list_score_snapshots(outcome_id)
        saved = self.repo.add_score_snapshot(snapshot)
        if earlier:
            delta = snapshot.opportunity_score - earlier[0].opportunity_score
            if abs(delta) >= DEFAULT_SCORE_MOVE_THRESHOLD:
                self.record_signal(
                    SignalKind.SCORE_MOVED,
                    f"Opportunity score moved {'up' if delta > 0 else 'down'} {abs(delta):.2f}",
                    subject_kind="outcome",
                    subject_id=outcome_id,
                    severity="urgent" if delta > 0 else "notice",
                    detail=f"{earlier[0].opportunity_score:.2f} → {snapshot.opportunity_score:.2f}",
                    discriminator=saved.id,
                    magnitude=delta,
                )
        return saved

    def list_score_snapshots(self, outcome_id: str) -> list[ScoreSnapshot]:
        if self.repo.get_outcome(outcome_id) is None:
            raise OutcomeNotFoundError(outcome_id)
        return self.repo.list_score_snapshots(outcome_id)

    def outcome_delta(self, outcome_id: str, since: datetime | None = None) -> dict[str, Any]:
        """Signed change from an earlier snapshot to the latest one.

        With no ``since`` the earliest snapshot is the baseline. The result is
        descriptive, never a significance claim.
        """
        snapshots = self.list_score_snapshots(outcome_id)
        if not snapshots:
            return {
                "outcome_id": outcome_id,
                "available": False,
                "reason": "no snapshots recorded for this outcome",
            }
        baseline = snapshots[0]
        if since is not None:
            eligible = [s for s in snapshots if s.at >= since]
            if not eligible:
                return {
                    "outcome_id": outcome_id,
                    "available": False,
                    "reason": f"no snapshot at or after {since.isoformat()}",
                }
            baseline = eligible[0]
        latest = snapshots[-1]
        return {
            "outcome_id": outcome_id,
            "available": True,
            "baseline": {
                "id": baseline.id,
                "at": baseline.at.isoformat(),
                "importance": baseline.importance,
                "satisfaction": baseline.satisfaction,
                "opportunity": baseline.opportunity_score,
            },
            "latest": {
                "id": latest.id,
                "at": latest.at.isoformat(),
                "importance": latest.importance,
                "satisfaction": latest.satisfaction,
                "opportunity": latest.opportunity_score,
            },
            "delta": {
                "importance": latest.importance - baseline.importance,
                "satisfaction": latest.satisfaction - baseline.satisfaction,
                "opportunity": latest.opportunity_score - baseline.opportunity_score,
            },
        }

    def outcome_history(self, outcome_id: str) -> list[ScoreSnapshot]:
        return self.list_score_snapshots(outcome_id)

    # -- Bets (E1) ---------------------------------------------------------

    def create_bet(
        self,
        decision_id: str,
        outcome_id: str,
        hypothesis: str,
        target: float,
        measure_by: date,
        *,
        direction: Direction | str = Direction.MAXIMIZE,
        created_at: datetime | None = None,
    ) -> Bet:
        """Create a bet with a baseline frozen from the outcome's score now.

        The baseline is captured from the latest snapshot (or the outcome's
        current score) and stored, never recomputed. A bet without a decision is
        refused, and the decision's outcomes must include the bet's outcome.
        """
        decision = self.repo.get_decision(decision_id)
        if decision is None:
            raise DecisionNotFoundError(decision_id)
        outcome = self.repo.get_outcome(outcome_id)
        if outcome is None:
            raise OutcomeNotFoundError(outcome_id)
        if outcome.job_id != decision.job_id:
            raise ValidationError(f"outcome {outcome_id} does not belong to decision {decision_id}")
        if outcome_id not in decision.chosen_outcome_ids:
            raise ValidationError(f"decision {decision_id} did not choose outcome {outcome_id}")
        if not hypothesis or not hypothesis.strip():
            raise ValidationError("bet hypothesis cannot be empty")

        if direction is not None and isinstance(direction, str):
            direction = Direction(direction)

        baseline = _finite_float(target, "target")
        if baseline != baseline or baseline in (float("inf"), float("-inf")):
            raise ValidationError("target must be a finite number")

        snapshots = self.repo.list_score_snapshots(outcome_id)
        baseline_snapshot_id: str | None = None
        if snapshots:
            source = snapshots[-1]
            baseline_value = source.opportunity_score
            baseline_importance = source.importance
            baseline_satisfaction = source.satisfaction
            baseline_snapshot_id = source.id
        else:
            if outcome.importance is None or outcome.satisfaction is None:
                raise ValidationError(
                    f"outcome {outcome_id} has no score; set importance and satisfaction "
                    "or record a snapshot before creating a bet"
                )
            baseline_value = compute_opportunity_score(outcome.importance, outcome.satisfaction)
            baseline_importance = outcome.importance
            baseline_satisfaction = outcome.satisfaction

        when = created_at or _utcnow()
        bet = Bet(
            id=str(uuid.uuid4()),
            decision_id=decision_id,
            outcome_id=outcome_id,
            job_id=outcome.job_id,
            hypothesis=hypothesis.strip(),
            baseline=baseline_value,
            target=baseline,
            measure_by=measure_by,
            direction=direction,
            status=BetStatus.PLANNED,
            measured_at=None,
            created_at=when,
            baseline_snapshot_id=baseline_snapshot_id,
            baseline_importance=baseline_importance,
            baseline_satisfaction=baseline_satisfaction,
        )
        return self.repo.add_bet(bet)

    def get_bet(self, bet_id: str) -> Bet:
        bet = self.repo.get_bet(bet_id)
        if bet is None:
            raise BetNotFoundError(bet_id)
        return bet

    def list_bets(self, job_id: str | None = None) -> list[Bet]:
        if job_id is not None and self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        return self.repo.list_bets(job_id)

    def transition_bet(
        self,
        bet_id: str,
        status: BetStatus | str,
        *,
        measured_at: datetime | None = None,
    ) -> Bet:
        """Move a bet through a legal transition, or refuse naming the legal ones."""
        bet = self.get_bet(bet_id)
        if isinstance(status, str):
            status = BetStatus(status)
        legal = BET_TRANSITIONS.get(bet.status, ())
        if status not in legal:
            raise InvalidBetTransitionError(bet.status, status)
        updates: dict[str, Any] = {"status": status}
        if status is BetStatus.MEASURED:
            updates["measured_at"] = measured_at or _utcnow()
        return self.repo.update_bet(bet_id, updates) or bet

    def measure_bet(self, bet_id: str, *, looked_at: datetime | None = None) -> dict[str, Any]:
        """Compare the latest eligible snapshot against the bet's stored baseline.

        The eligible snapshot is the latest one at or after ``measure_by``. If
        none exists the answer is ``no_data`` with the date it looked — never the
        latest snapshot overall (which would measure the wrong period), never a
        zero, and never an exception. Measuring twice writes nothing.
        """
        bet = self.get_bet(bet_id)
        when = looked_at or _utcnow()
        cutoff = bet.measure_by
        eligible = [
            s
            for s in self.repo.list_score_snapshots(bet.outcome_id)
            if s.at.date() >= cutoff and s.at <= when
        ]
        if not eligible:
            return {
                "bet_id": bet.id,
                "result": BetMeasurementResult.NO_DATA.value,
                "looked_at": when.isoformat(),
                "measure_by": cutoff.isoformat(),
                "reason": f"no snapshot at or after {cutoff.isoformat()} for outcome {bet.outcome_id}",
                "baseline": bet.baseline,
                "target": bet.target,
                "direction": bet.direction.value,
            }

        latest = eligible[-1]
        observed = latest.opportunity_score
        if bet.direction is Direction.MAXIMIZE:
            met = observed >= bet.target
        else:
            met = observed <= bet.target
        return {
            "bet_id": bet.id,
            "result": (
                BetMeasurementResult.MET.value if met else BetMeasurementResult.MISSED.value
            ),
            "looked_at": when.isoformat(),
            "measure_by": cutoff.isoformat(),
            "baseline": bet.baseline,
            "target": bet.target,
            "direction": bet.direction.value,
            "observed": observed,
            "delta": observed - bet.baseline,
            "snapshot_id": latest.id,
            "snapshot_at": latest.at.isoformat(),
            "baseline_snapshot_id": bet.baseline_snapshot_id,
        }

    # -- Signals (E3) ------------------------------------------------------

    def emit_know_signals(
        self,
        *,
        job_id: str | None = None,
        now: datetime | None = None,
    ) -> list[Signal]:
        """Record the "know" signals the store can prove, and return what is current.

        Idempotent: every emission carries a deterministic discriminator, so a
        second pass over an unchanged store records nothing new. Nothing is
        invented — an empty store records nothing.
        """
        from agentic_odi_core.signals import emit_know_signals as _emit

        return _emit(self, job_id=job_id, now=now)

    # -- Notification rules (E6) ------------------------------------------

    def set_notification_rule(
        self, kind: SignalKind | str, *, threshold: float = 0.0, enabled: bool = True
    ) -> NotificationRule:
        if isinstance(kind, str):
            kind = SignalKind(kind)
        if threshold < 0:
            raise ValidationError("notification threshold cannot be negative")
        rule = NotificationRule(kind=kind, threshold=threshold, enabled=enabled)
        return self.repo.set_notification_rule(rule)

    def list_notification_rules(self) -> list[NotificationRule]:
        from agentic_odi_core.signals import default_rules

        stored = {rule.kind: rule for rule in self.repo.list_notification_rules()}
        return [stored.get(kind, rule) for kind, rule in default_rules().items()]


def _finite_float(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a number") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ValidationError(f"{field} must be a finite number")
    return number
