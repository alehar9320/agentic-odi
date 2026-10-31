"""Service layer implementing business logic."""

from __future__ import annotations

import hashlib
import math
import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from agentic_odi_core.brief import BriefInput, BriefOutcome
from agentic_odi_core.compare import (
    MAX_COMPARE_OUTCOMES,
    MIN_COMPARE_OUTCOMES,
    CompareCandidate,
    OutcomeComparison,
    align_outcomes,
)
from agentic_odi_core.errors import ConflictError, NotFoundError, ValidationError
from agentic_odi_core.evaluation import (
    OutcomeStatementError,
    evaluate_outcome_statement,
    require_outcome_statement,
)
from agentic_odi_core.models import (
    JOB_STAGE_INDEX,
    JOB_STAGE_ORDER,
    MAX_SNAPSHOT_NOTE,
    MAX_VALUE_SOURCE,
    Bet,
    BetStatus,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Decision,
    DecisionConfidence,
    Evidence,
    EvidenceItemType,
    Job,
    JobStage,
    Outcome,
    Rejection,
    ScheduledWork,
    ScheduledWorkStatus,
    ScheduledWorkTriggerType,
    ScoreMethod,
    ScoreSnapshot,
    Signal,
    SignalKind,
    Step,
    ValueBasis,
    ValueUnit,
    compute_opportunity_score,
)
from agentic_odi_core.repository import Repository, page
from agentic_odi_core.review import DecisionReview, review_decision
from agentic_odi_core.roadmap import Roadmap, build_roadmap


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


class DecisionNotFoundError(NotFoundError):
    def __init__(self, decision_id: str) -> None:
        self.decision_id = decision_id
        super().__init__(decision_id, "decision")


class BetNotFoundError(NotFoundError):
    def __init__(self, bet_id: str) -> None:
        self.bet_id = bet_id
        super().__init__(bet_id, "bet")


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


def _pydantic_message(exc: PydanticValidationError) -> str:
    """The validator's own sentence, not pydantic's ``N validation errors`` header.

    ``str(exc)`` begins with a count line, so taking its first line drops the
    reason a user needs. The first error's ``msg`` keeps the sentence the model
    wrote (``A value_basis of 'market' requires a value_source ...``).
    """
    errors = exc.errors()
    if not errors:
        return _first_line(str(exc))
    message = str(errors[0].get("msg", "")).strip()
    return message.removeprefix("Value error, ") or _first_line(str(exc))


def _now_iso() -> str:
    """The current UTC timestamp, ISO-8601.

    Only called at a write boundary when the caller did not supply ``at``; every
    pure renderer and derivation takes its clock as an argument instead.
    """
    return datetime.now(timezone.utc).isoformat()


def _require_finite(value: float, field: str) -> None:
    """Refuse NaN/inf: a nonfinite number is not a measurement."""
    if not math.isfinite(value):
        raise ValidationError(f"{field} must be a finite number.")


def _require_iso_date(value: str, field: str) -> None:
    """Refuse a value that is not a plain ISO-8601 calendar date."""
    try:
        date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValidationError(f"{field} must be an ISO-8601 date, got {value!r}.") from exc


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

    def _capture_snapshot(
        self,
        outcome: Outcome,
        *,
        at: str,
        note: str | None = None,
    ) -> ScoreSnapshot:
        """Record one accepted score state. The single writer for every path.

        Called from ``add_outcome``, ``update_outcome``, and
        ``promote_evidence``. Append-only: a snapshot is never edited. ``at`` is
        supplied by the caller so the write is reproducible.
        """
        if note is not None and len(note) > MAX_SNAPSHOT_NOTE:
            raise ValidationError(f"A snapshot note may be at most {MAX_SNAPSHOT_NOTE} characters.")
        snapshot = ScoreSnapshot(
            outcome_id=outcome.id,
            at=at,
            importance=outcome.importance,
            satisfaction=outcome.satisfaction,
            opportunity_score=outcome.opportunity_score,
            importance_n=outcome.importance_n,
            satisfaction_n=outcome.satisfaction_n,
            score_method=outcome.score_method,
            note=note,
        )
        return self.repo.add_score_snapshot(snapshot)

    def update_outcome(
        self,
        outcome_id: str,
        updates: dict[str, Any],
        *,
        at: str | None = None,
        note: str | None = None,
    ) -> Outcome:
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
        updates = dict(updates)
        if importance is not None and satisfaction is not None:
            updates["opportunity_score"] = compute_opportunity_score(importance, satisfaction)
        else:
            updates["opportunity_score"] = None
        # Validate the *whole* resulting record before mutating, so switching a
        # survey to an estimate with a sample still attached fails atomically.
        current = existing.model_dump(exclude_unset=True)
        current.update(updates)
        try:
            Outcome.model_validate(current)
        except PydanticValidationError as exc:
            raise ValidationError(_first_line(str(exc))) from exc
        res = self.repo.update_outcome(outcome_id, updates)
        if not res:
            raise OutcomeNotFoundError(outcome_id)
        self._emit_outcome_updates(existing, res)
        self._capture_snapshot(res, at=at or _now_iso(), note=note)
        return res

    def set_outcome_value(
        self,
        outcome_id: str,
        estimate: float | None,
        *,
        unit: ValueUnit | None = None,
        basis: ValueBasis = "estimate",
        n: int | None = None,
        source: str | None = None,
    ) -> Outcome:
        """Record what an opportunity is worth, with its basis (W1/ALH-64).

        The estimate is a judgement the caller supplies — it is never derived
        from the opportunity score, and never summed across outcomes. A
        ``market`` or ``pilot`` basis requires a named source; the model enforces
        that, and this raises the same refusal as a validation error so the CLI
        and the API fail identically.
        """
        existing = self.repo.get_outcome(outcome_id)
        if existing is None:
            raise OutcomeNotFoundError(outcome_id)
        if estimate is not None:
            _require_finite(estimate, "value_estimate")
            if estimate < 0:
                raise ValueOutOfRangeError("value_estimate must not be negative")
        if n is not None and n < 1:
            raise ValueOutOfRangeError("value_n must be at least 1")
        if source is not None:
            source = source.strip()
            if not source:
                raise ValidationError("value_source must not be blank.")
            if len(source) > MAX_VALUE_SOURCE:
                raise ValidationError(
                    f"value_source must be at most {MAX_VALUE_SOURCE} characters."
                )
        if estimate is None:
            # Clearing the estimate clears its companions: a unit, basis or
            # source with no number describes nothing and would render as a
            # sized value with nothing to show.
            updates: dict[str, Any] = {
                "value_estimate": None,
                "value_unit": None,
                "value_basis": "estimate",
                "value_n": None,
                "value_source": None,
            }
        else:
            if unit is None:
                raise ValidationError(
                    "A value estimate needs a unit (currency, users, accounts, hours)."
                )
            updates = {
                "value_estimate": estimate,
                "value_unit": unit,
                "value_basis": basis,
                "value_n": n,
                "value_source": source,
            }
        current = existing.model_dump(exclude_unset=True)
        current.update(updates)
        try:
            Outcome.model_validate(current)
        except PydanticValidationError as exc:
            raise ValidationError(_pydantic_message(exc)) from exc
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
        importance_n: int | None = None,
        satisfaction_n: int | None = None,
        score_method: ScoreMethod = "estimate",
        at: str | None = None,
        note: str | None = None,
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
        try:
            outcome = Outcome(
                id=str(uuid.uuid4()),
                job_id=job_id,
                step_id=step_id,
                statement=statement,
                importance=importance,
                satisfaction=satisfaction,
                opportunity_score=opportunity_score,
                importance_n=importance_n,
                satisfaction_n=satisfaction_n,
                score_method=score_method,
            )
        except PydanticValidationError as exc:
            raise ValidationError(_first_line(str(exc))) from exc
        stored = self.repo.add_outcome(outcome)
        self._capture_snapshot(stored, at=at or _now_iso(), note=note)
        return stored

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

    # ------------------------------------------------------------- decisions

    def compare_outcomes(self, outcome_ids: list[str]) -> OutcomeComparison:
        """Align two or three outcomes on shared axes for a side-by-side read.

        The ids are taken explicitly and in order: the comparison never widens
        the request or deduplicates it silently. Each outcome is read once —
        no per-outcome fetch beyond its own record and its evidence — and the
        whole call leaves repository and event state unchanged.
        """
        if len(outcome_ids) < MIN_COMPARE_OUTCOMES:
            raise ValidationError(
                f"compare needs at least {MIN_COMPARE_OUTCOMES} outcomes; got {len(outcome_ids)}"
            )
        if len(outcome_ids) > MAX_COMPARE_OUTCOMES:
            raise ValidationError(
                f"compare accepts at most {MAX_COMPARE_OUTCOMES} outcomes; got {len(outcome_ids)}"
            )
        if len(set(outcome_ids)) != len(outcome_ids):
            raise ValidationError("compare ids must be distinct")

        candidates: list[CompareCandidate] = []
        for outcome_id in outcome_ids:
            outcome = self.repo.get_outcome(outcome_id)
            if outcome is None:
                raise OutcomeNotFoundError(outcome_id)
            step = self.repo.get_step(outcome.step_id) if outcome.step_id else None
            evidence = self.repo.list_evidence(outcome_id=outcome_id)
            candidates.append(
                CompareCandidate(
                    outcome_id=outcome.id,
                    statement=outcome.statement,
                    score=outcome.opportunity_score,
                    importance=outcome.importance,
                    satisfaction=outcome.satisfaction,
                    stage=step.name if step else None,
                    evidence_count=len(evidence),
                    sample_size=None,
                    effort=None,
                )
            )
        return align_outcomes(candidates)

    def build_roadmap(
        self,
        job_id: str,
        *,
        horizon: int = 4,
        today: date | None = None,
        order_by: str = "quarter",
    ) -> Roadmap:
        """Derive a job's outcome roadmap from its recorded decisions.

        This is the only place the fetch happens: the pure ``build_roadmap`` in
        ``roadmap.py`` receives the records and owns the grouping. The live
        outcome score is never read as a baseline — no measurement source
        exists yet (``ALH-46``/``ALH-29``), so baselines and targets stay
        ``None`` and render as ``not measured`` rather than a zero.

        ``order_by="value"`` is opt-in (W1/ALH-64): the recorded value estimates
        are supplied to the derivation, and the default ordering is untouched.
        """
        if self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        decisions = self.repo.list_decisions(job_id, limit=None)
        outcomes = self.repo.get_outcomes(job_id, limit=None)
        values = {outcome.id: outcome.value_estimate for outcome in outcomes}
        return build_roadmap(
            job_id,
            decisions,
            outcomes,
            horizon=horizon,
            today=today,
            values=values,
            order_by=order_by,
        )

    def record_decision(
        self,
        job_id: str,
        chosen_outcome_ids: list[str],
        rationale: str,
        decided_by: str,
        decided_at: str,
        rejected: list[Rejection] | None = None,
        confidence: DecisionConfidence | str = DecisionConfidence.MEDIUM,
        supersedes: str | None = None,
    ) -> Decision:
        """Record a decision, superseding a predecessor instead of overwriting it.

        Every referenced outcome must belong to ``job_id``; a decision that
        points at another job's outcome is refused before an event is appended.
        """
        job = self.repo.get_job(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        if not chosen_outcome_ids:
            raise ValidationError("A decision must choose at least one outcome.")
        rationale = rationale.strip()
        if not rationale:
            raise ValidationError("A decision needs a rationale.")
        decided_by = decided_by.strip()
        if not decided_by:
            raise ValidationError("A decision needs a decided_by attribution.")

        try:
            resolved_confidence = DecisionConfidence(confidence)
        except ValueError as exc:
            raise ValidationError(
                f"Unknown confidence: {confidence!r}. "
                f"Use one of {[c.value for c in DecisionConfidence]}."
            ) from exc

        job_outcome_ids = {o.id for o in self.repo.get_outcomes(job_id=job_id, limit=None)}
        for outcome_id in chosen_outcome_ids:
            if outcome_id not in job_outcome_ids:
                raise OutcomeNotFoundError(outcome_id)

        rejections: list[Rejection] = []
        for rejection in rejected or []:
            reason = rejection.reason.strip()
            if not reason:
                raise ValidationError("A rejected option needs a reason.")
            if rejection.outcome_id not in job_outcome_ids:
                raise OutcomeNotFoundError(rejection.outcome_id)
            rejections.append(Rejection(outcome_id=rejection.outcome_id, reason=reason))

        predecessor = None
        if supersedes is not None:
            predecessor = self.repo.get_decision(supersedes)
            if predecessor is None:
                raise DecisionNotFoundError(supersedes)
            if predecessor.job_id != job_id:
                raise ValidationError("A decision can only supersede one from the same job.")

        decision = Decision(
            job_id=job_id,
            chosen_outcome_ids=list(chosen_outcome_ids),
            rejected=rejections,
            rationale=rationale,
            decided_by=decided_by,
            decided_at=decided_at,
            confidence=resolved_confidence,
        )
        self.repo.add_decision(decision)

        if predecessor is not None:
            self.repo.update_decision(
                predecessor.id,
                {"superseded_at": decided_at, "superseded_by": decision.id},
            )
        return decision

    def get_decision(self, decision_id: str) -> Decision | None:
        return self.repo.get_decision(decision_id)

    def list_decisions(
        self, job_id: str, limit: int | None = None, offset: int = 0
    ) -> list[Decision]:
        return self.repo.list_decisions(job_id, limit=limit, offset=offset)

    def latest_decision(self, job_id: str) -> Decision | None:
        history = self.repo.list_decisions(job_id, limit=None)
        return history[-1] if history else None

    # -------------------------------------------------------------------- bets

    def record_bet(
        self,
        decision_id: str,
        outcome_id: str,
        hypothesis: str,
        target: float,
        measure_by: str,
        *,
        baseline: float | None = None,
        at: str | None = None,
    ) -> Bet:
        """Create a bet, capturing its baseline at creation (E1/ALH-46).

        ``baseline`` is copied from the outcome's current score when the caller
        does not supply one, and stored — never recomputed. The whole value of a
        bet is that its starting point cannot move with the score. A bet without
        a decision is refused, and the outcome must belong to that decision.
        """
        decision = self.repo.get_decision(decision_id)
        if decision is None:
            raise DecisionNotFoundError(decision_id)
        hypothesis = hypothesis.strip()
        if not hypothesis:
            raise ValidationError("A bet needs a hypothesis.")
        outcome = self.repo.get_outcome(outcome_id)
        if outcome is None:
            raise OutcomeNotFoundError(outcome_id)
        # A linked decision's existence alone does not prove the outcome belongs
        # to it; the outcome must be one the decision chose.
        if outcome_id not in decision.chosen_outcome_ids:
            raise ValidationError(
                f"Outcome {outcome_id} is not one the decision {decision_id} chose."
            )
        if baseline is None:
            if outcome.opportunity_score is None:
                raise ValidationError(
                    "This outcome has no score to capture as a baseline; "
                    "supply one explicitly or score the outcome first."
                )
            baseline = outcome.opportunity_score
        _require_finite(baseline, "baseline")
        _require_finite(target, "target")
        _require_iso_date(measure_by, "measure_by")

        bet = Bet(
            decision_id=decision_id,
            outcome_id=outcome_id,
            hypothesis=hypothesis,
            baseline=baseline,
            target=target,
            measure_by=measure_by,
            status=BetStatus.PLANNED,
            measured_at=at if at is not None else None,
        )
        return self.repo.add_bet(bet)

    def get_bet(self, bet_id: str) -> Bet | None:
        return self.repo.get_bet(bet_id)

    def list_bets(
        self,
        job_id: str | None = None,
        decision_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Bet]:
        return self.repo.list_bets(job_id, decision_id, limit=limit, offset=offset)

    def advance_bet(self, bet_id: str, status: BetStatus | str, *, at: str | None = None) -> Bet:
        """Move a bet to a new status, refusing an illegal transition.

        The refusal names the legal successors, and no event is appended when the
        transition is refused.
        """
        bet = self.repo.get_bet(bet_id)
        if bet is None:
            raise BetNotFoundError(bet_id)
        try:
            resolved = BetStatus(status)
        except ValueError as exc:
            raise ValidationError(
                f"Unknown bet status: {status!r}. Use one of {[s.value for s in BetStatus]}."
            ) from exc
        if resolved not in bet.next_statuses():
            legal = [s.value for s in bet.next_statuses()] or ["(terminal)"]
            raise ConflictError(
                f"A bet cannot move from {bet.status.value} to {resolved.value}. "
                f"Legal next: {', '.join(legal)}."
            )
        updates: dict[str, Any] = {"status": resolved.value}
        if resolved is BetStatus.MEASURED:
            updates["measured_at"] = at or _now_iso()
        return self.repo.update_bet(bet_id, updates) or bet

    # ------------------------------------------------------------------ review

    def review_decision(self, decision_id: str, *, today: date) -> DecisionReview:
        """Re-examine a past decision against today's numbers (C8/ALH-39).

        ``today`` is supplied so the review is reproducible. Every chosen
        outcome is one of improved, degraded, no evidence, no change, or
        orphaned; a missing measurement is never reported as no change.
        """
        decision = self.repo.get_decision(decision_id)
        if decision is None:
            raise DecisionNotFoundError(decision_id)
        outcomes = self.repo.get_outcomes(decision.job_id, limit=None)
        snapshots = self.repo.list_score_snapshots()
        return review_decision(decision, outcomes, snapshots, today=today)

    def list_score_snapshots(self, outcome_id: str | None = None) -> list[ScoreSnapshot]:
        return self.repo.list_score_snapshots(outcome_id)

    # ------------------------------------------------------------------ brief

    def build_brief(self, job_id: str, *, generated_at: str) -> BriefInput:
        """Assemble the brief inputs for a job from what is actually recorded.

        The clock is supplied, never read here, so a rendered brief is
        reproducible. Every measurement comes from the stored records; a field
        nobody supplied stays ``None`` and the renderer shows it as
        ``not measured`` rather than a zero.
        """
        job = self.repo.get_job(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        outcomes = self.repo.get_outcomes(job_id)
        brief_outcomes: list[BriefOutcome] = []
        for outcome in outcomes:
            evidence = self.repo.list_evidence(outcome_id=outcome.id)
            brief_outcomes.append(
                BriefOutcome(
                    outcome_id=outcome.id,
                    statement=outcome.statement,
                    score=outcome.opportunity_score,
                    n=None,
                    method=None,
                    quote=None,
                    sources=tuple(record.name for record in evidence),
                    value_estimate=outcome.value_estimate,
                    value_unit=outcome.value_unit,
                    value_basis=outcome.value_basis,
                    value_n=outcome.value_n,
                    value_source=outcome.value_source,
                )
            )
        decision = self.latest_decision(job_id)
        consideration = None
        if decision is not None:
            chosen = ", ".join(decision.chosen_outcome_ids)
            consideration = f"Recorded decision {decision.id} chose {chosen}."
        return BriefInput(
            job_id=job.id,
            job_name=job.name,
            generated_at=generated_at,
            outcomes=tuple(brief_outcomes),
            decision_consideration=consideration,
            evidence_count=len(self.repo.list_evidence(job_id=job_id)),
        )

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
