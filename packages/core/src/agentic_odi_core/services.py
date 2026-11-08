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

from agentic_odi_core.brief import (
    BriefInput,
    BriefOutcome,
    BriefSegment,
    BriefStrategy,
    BriefStrategyRecord,
    select_brief_strategy,
)
from agentic_odi_core.compare import (
    MAX_COMPARE_OUTCOMES,
    MIN_COMPARE_OUTCOMES,
    CompareCandidate,
    OutcomeComparison,
    align_outcomes,
)
from agentic_odi_core.errors import ConflictError, NotFoundError, ValidationError
from agentic_odi_core.errors import NotFoundError, ValidationError
from agentic_odi_core.evaluation import (
    OutcomeStatementError,
    classify_opportunity,
    evaluate_outcome_statement,
    require_outcome_statement,
)
from agentic_odi_core.funnel import FIRST_OUTCOME, FIRST_SCORE, count_milestone
from agentic_odi_core.mapping import (
    HeuristicProposalStrategy,
    OutcomeProposal,
    ProposalStatus,
    ProposalStrategy,
)
from agentic_odi_core.models import (
    JOB_STAGE_INDEX,
    JOB_STAGE_ORDER,
    MAX_SNAPSHOT_NOTE,
    MAX_VALUE_SOURCE,
    Bet,
    BetStatus,
    BusinessValue,
    ClaimCheck,
    ClaimSkip,
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
    Segment,
    SegmentVerdict,
    Signal,
    SignalKind,
    Step,
    Strategy,
    StrategyKind,
    ValueBasis,
    ValueUnit,
    compute_opportunity_score,
)
from agentic_odi_core.repository import Repository, page
from agentic_odi_core.review import DecisionReview, review_decision
from agentic_odi_core.roadmap import Roadmap, build_roadmap
from agentic_odi_core.segment_profile import SegmentProfile, build_segment_profile
from agentic_odi_core.segmentation import (
    SegmentCandidateSet,
    suggest_segment_candidates,
)
    Study,
    StudyStatus,
    compute_opportunity_score,
)
from agentic_odi_core.repository import Repository, page
from agentic_odi_core.segmentation import (
    MIN_OUTCOMES_PER_SEGMENT,
    OutcomeClusterStrategy,
    SegmentationStrategy,
    unclustered_outcomes,
)
from agentic_odi_core.strategy import propose_strategy as build_strategy


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
class StudyNotFoundError(NotFoundError):
    """Raised when a study id does not resolve."""

    def __init__(self, study_id: str, hint: str | None = None) -> None:
        self.study_id = study_id
        super().__init__(study_id, "study", hint)


class ScheduledWorkNotFoundError(NotFoundError, ValueError):
    """Raised when scheduled work cannot be located.

    Also a :class:`ValueError`, because the caller supplied an id that does not
    resolve — an invalid argument value.
    """

    def __init__(self, work_id: str, hint: str | None = None) -> None:
        self.work_id = work_id
        super().__init__(work_id, "scheduled work", hint)


class SegmentNotFoundError(NotFoundError):
    def __init__(self, segment_id: str) -> None:
        self.segment_id = segment_id
        super().__init__(segment_id, "segment")


class StrategyNotFoundError(NotFoundError):
    def __init__(self, strategy_id: str) -> None:
        self.strategy_id = strategy_id
        super().__init__(strategy_id, "strategy")


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


class SegmentNotFoundError(NotFoundError, ValueError):
    """Raised when a segment id does not resolve.

    Also a :class:`ValueError`, because the caller supplied an id that does not
    resolve — an invalid argument value.
    """

    def __init__(self, segment_id: str, hint: str | None = None) -> None:
        self.segment_id = segment_id
        super().__init__(segment_id, "segment", hint)


class StrategyNotFoundError(NotFoundError, ValueError):
    """Raised when a strategy id does not resolve."""

    def __init__(self, strategy_id: str, hint: str | None = None) -> None:
        self.strategy_id = strategy_id
        super().__init__(strategy_id, "strategy", hint)


class NoStrategyEvidenceError(ValidationError):
    """No strategic path has evidence behind it.

    Raised instead of returning a strategy built on nothing: a bet the data does
    not support is the fabrication Stage 6 exists to avoid.
    """


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


class ClaimCheckError(ValidationError):
    """A claim check does not record the questions behind a score.

    Raised when a check is empty, an answer has no question behind it, or a
    skip carries no reason. Each message names the fix so the agent can ask
    again instead of writing the score anyway.
    """


def require_claim_check(check: ClaimCheck | dict[str, Any] | None) -> ClaimCheck | None:
    """Validate a claim check, or pass ``None`` through unchanged.

    ``None`` is legal: an outcome may be captured unscored or without a
    recorded interrogation. A check that *is* supplied must be honest — it
    names at least one question, every answer rests on a question that was
    asked, and every skip carries a reason. A malformed check is reported as a
    :class:`ClaimCheckError` naming the fix, not as a raw model error.
    """
    if check is None:
        return None
    if not isinstance(check, ClaimCheck):
        try:
            check = ClaimCheck.model_validate(check)
        except PydanticValidationError as exc:
            raise ClaimCheckError(
                "claim_check is malformed; pass asked/answers/skips with each skip "
                f"carrying a reason. {exc}"
            ) from exc
    if not check.asked and not check.answers and not check.skips:
        raise ClaimCheckError(
            "A claim check must record at least one question; ask the customer before scoring."
        )
    if len(check.answers) > len(check.asked):
        raise ClaimCheckError(
            "Every answer must answer a question that was asked; "
            "do not invent answers to satisfy the check."
        )
    for answer in check.answers:
        if not answer.strip():
            raise ClaimCheckError("An answer cannot be blank.")
    for skip in check.skips:
        if not skip.reason.strip():
            raise ClaimCheckError(
                f"A skip needs a reason: the question {skip.question!r} was skipped with none."
            )
    return check


def manual_claim_check(
    reason: str = "Score entered by hand; no customer questions were asked.",
) -> ClaimCheck:
    """The provenance of a by-hand score: a skip with its reason.

    A person typing two numbers into a form is not an interview. Recording
    that honestly keeps a manual score from borrowing the confidence of an
    interrogated one: nothing was ``asked``, the verification is skipped, and
    the reason says why.
    """
    return ClaimCheck(
        skips=[ClaimSkip(question="Was this score produced by asking the customer?", reason=reason)]
    )


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


def _normalise_member_ids(outcome_ids: list[str]) -> list[str]:
    """Deduplicate member ids, keeping first-seen order.

    A repeated id is the same member twice, not two members; storing it twice
    would inflate every count built on the segment.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for outcome_id in outcome_ids:
        if outcome_id in seen:
            continue
        seen.add(outcome_id)
        ordered.append(outcome_id)
    return ordered


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
    """Did the opportunity score enter or leave the underserved bucket?

    The line is ``classify_opportunity``'s, not a second threshold: underserved
    is strictly above 10, so a score that climbs onto exactly 10 has crossed
    nothing and one that moves from 10 to 11 has. Entering is urgent — a real
    unserved opportunity just surfaced; leaving is a notice.
    """
    was = classify_opportunity(before)
    now = classify_opportunity(after)
    if was != "underserved" and now == "underserved":
        return ("up", "urgent")
    if was == "underserved" and now != "underserved":
        return ("down", "notice")
    return None


class ODIService:
    def __init__(
        self,
        repo: Repository,
        budget: SignalBudget | None = None,
        segmentation: SegmentationStrategy | None = None,
    ) -> None:
        self.repo = repo
        #: ``None`` re-reads ``AGENTIC_ODI_SIGNAL_BUDGET`` per signal so a
        #: long-running sidecar picks up a changed cap without a restart.
        self.budget = budget
        #: ``None`` uses the deterministic outcome-cluster strategy, rebuilt per
        #: call so it sees the job map as it stands at that moment.
        self.segmentation = segmentation

    def record_signal(
        self,
        kind: SignalKind,
        title: str,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        severity: str = "info",
        detail: str | None = None,
        discriminator: str = "",
        source_event_id: int | None = None,
    ) -> Signal:
        """Record one fact. A signal with the same fingerprint already exists.

        ``discriminator`` is the thing that changed (a new score, a record id) and
        ``source_event_id`` the store event that carried the change. The fingerprint
        is sha256 over ``kind|subject_kind|subject_id|discriminator``, with the source
        id appended when one is given. Naming the change and not only the value it
        landed on is what lets a second move to the same score be its own signal,
        while a retry of one change stays one signal. Without a source id the
        fingerprint is exactly what it was before, so stored signals still dedupe.
        """
        fact = [kind.value, subject_kind or "", subject_id or "", discriminator]
        if source_event_id is not None:
            fact.append(str(source_event_id))
        fingerprint = hashlib.sha256("|".join(fact).encode("utf-8")).hexdigest()
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
        study_id = updates.get("study_id")
        if study_id is not None:
            self._validate_study_scope(existing, study_id)
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
        self._count_outcome_milestones(res)
        return res

    def _count_outcome_milestones(self, outcome: Outcome) -> None:
        """Tell the onboarding funnel how far this workspace has got.

        Both milestones are first-ever-per-workspace, so offering them on every
        outcome is cheaper and truer than trying to remember which one was first.
        A score milestone needs both scores: an outcome with one is not yet a
        ranked opportunity, and the funnel must not claim it is.
        """
        count_milestone(self.repo, FIRST_OUTCOME)
        if outcome.importance is not None and outcome.satisfaction is not None:
            count_milestone(self.repo, FIRST_SCORE)

    def _emit_outcome_updates(self, before: Outcome, after: Outcome) -> None:
        #: The write that produced these facts: two changes landing on the same
        #: score are two changes, one change reported twice is one signal.
        source_event_id = self.repo.last_event_id()
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
                source_event_id=source_event_id,
            )
        crossing = _opportunity_crossing(before.opportunity_score, after.opportunity_score)
        if crossing is not None:
            direction, severity = crossing
            self.record_signal(
                SignalKind.OPPORTUNITY_CROSSED,
                f"Opportunity score {before.opportunity_score} -> {after.opportunity_score} "
                f'({direction}): "{after.statement[:60]}"',
                subject_kind="outcome",
                subject_id=after.id,
                severity=severity,
                detail=f"{before.opportunity_score} -> {after.opportunity_score}",
                discriminator=f"{direction}:{after.opportunity_score}",
                source_event_id=source_event_id,
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
        importance: float | None = None,
        satisfaction: float | None = None,
        step_id: str | None = None,
        validate_statement: bool = True,
        importance_n: int | None = None,
        satisfaction_n: int | None = None,
        score_method: ScoreMethod = "estimate",
        at: str | None = None,
        note: str | None = None,
        claim_check: ClaimCheck | dict[str, Any] | None = None,
    ) -> Outcome:
        if self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        if step_id is not None and self.repo.get_step(step_id) is None:
            raise StepNotFoundError(step_id)
        if importance is not None and not (1.0 <= importance <= 10.0):
            raise ValueOutOfRangeError("importance must be between 1.0 and 10.0")
        if satisfaction is not None and not (1.0 <= satisfaction <= 10.0):
            raise ValueOutOfRangeError("satisfaction must be between 1.0 and 10.0")
        if validate_statement:
            verdict = evaluate_outcome_statement(statement)
            if not verdict["valid"]:
                raise InvalidOutcomeStatementError(verdict)
        check = require_claim_check(claim_check)
        #: Unscored outcomes stay legal: a score is optional, and an outcome
        #: without one carries no opportunity_score to stand behind.
        if importance is not None and satisfaction is not None:
            opportunity_score: float | None = compute_opportunity_score(importance, satisfaction)
        else:
            opportunity_score = None
        try:
            outcome = Outcome(
                id=str(uuid.uuid4()),
                job_id=job_id,
                step_id=step_id,
                statement=statement,
                importance=importance,
                satisfaction=satisfaction,
                opportunity_score=opportunity_score,
                claim_check=check,
                importance_n=importance_n,
                satisfaction_n=satisfaction_n,
                score_method=score_method,
            )
        except PydanticValidationError as exc:
            raise ValidationError(_first_line(str(exc))) from exc
        stored = self.repo.add_outcome(outcome)
        self._capture_snapshot(stored, at=at or _now_iso(), note=note)
        self._count_outcome_milestones(stored)
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

    # -- Studies: one named pass over a Job, and the wave inside it ----------

    def open_study(
        self, job_id: str, name: str, wave: int, method_notes: str | None = None
    ) -> Study:
        """Open a study — one named pass over a Job, at a given wave number.

        A study opens ``planned``; ``fielding`` and ``closed`` are later
        transitions and nothing here moves to them automatically. The same
        ``(job_id, name)`` may not repeat a wave, so an accidental re-run of a
        pass is refused while a deliberate later wave is expressible.
        """
        if self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        clash = next(
            (
                study
                for study in self.repo.list_studies(job_id)
                if study.name == name and study.wave == wave
            ),
            None,
        )
        if clash is not None:
            raise ValidationError(
                f"Study '{name}' already has wave {wave} for this job; open wave {wave + 1} instead."
            )
        study = Study(job_id=job_id, name=name, wave=wave, method_notes=method_notes)
        return self.repo.add_study(study)

    def close_study(self, study_id: str) -> Study:
        """Close a study once. A second close keeps the first ``closed_at``."""
        study = self.repo.get_study(study_id)
        if study is None:
            raise StudyNotFoundError(study_id)
        if study.status is StudyStatus.CLOSED:
            return study
        closed = self.repo.update_study(
            study_id,
            {
                "status": StudyStatus.CLOSED.value,
                "closed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if closed is None:
            raise StudyNotFoundError(study_id)
        return closed

    def list_studies(self, job_id: str | None = None) -> list[Study]:
        return self.repo.list_studies(job_id=job_id)

    def get_study(self, study_id: str) -> Study:
        study = self.repo.get_study(study_id)
        if study is None:
            raise StudyNotFoundError(study_id, "open a study first")
        return study

    def _validate_study_scope(self, outcome: Outcome, study_id: str) -> None:
        study = self.repo.get_study(study_id)
        if study is None:
            raise StudyNotFoundError(study_id)
        if study.job_id != outcome.job_id:
            raise ValidationError(
                f"Study {study_id} belongs to job {study.job_id}, not the outcome's job "
                f"{outcome.job_id}; an outcome may only join a study of its own job."
            )

    def add_customer_outcome(
        self,
        job_id: str,
        customer_value: CustomerValue | dict[str, Any],
        business_value: BusinessValue | dict[str, Any],
        step_id: str | None = None,
        quote_id: str | None = None,
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
            quote_id=quote_id,
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
        #: Dedupe: the same quote imported twice must not become two evidence
        #: records. Return the existing record instead of appending.
        duplicate = self.repo.get_evidence_by_fingerprint(
            evidence.source_kind,
            evidence.source_name,
            evidence.name,
            evidence.content,
            evidence.url,
            evidence.raw,
        )
        if duplicate is not None:
            return duplicate
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
            #: Idempotent promotion: if this evidence was already promoted to an
            #: outcome, return the existing outcome instead of creating a copy.
            if evidence.outcome_id is not None:
                existing = self.repo.get_outcome(evidence.outcome_id)
                if existing is not None:
                    return existing
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
            #: Record the bidirectional link: evidence → outcome.
            self.repo.update_evidence(evidence.id, {"outcome_id": outcome.id})
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

    def propose_outcome_from_evidence(self, evidence_id: str) -> OutcomeProposal:
        """Propose a desired outcome from one evidence record.

        Uses the default heuristic strategy (deterministic, offline, no LLM).
        Returns the proposal; nothing is written to the ODI store until the
        proposal is approved.
        """
        strategy: ProposalStrategy = HeuristicProposalStrategy()
        evidence = self.repo.get_evidence(evidence_id)
        if evidence is None:
            raise EvidenceNotFoundError(
                evidence_id,
                "List the stored records with list_evidence() to find a valid id.",
            )
        jobs = self.repo.list_jobs()
        steps = self.repo.list_steps()
        proposal = strategy.propose(evidence, jobs, steps)
        if proposal is None:
            raise ValidationError(
                f"No candidate outcome could be extracted from evidence {evidence_id}. "
                "The record does not contain a recognizable customer problem."
            )
        # Persist the proposal so it can be approved/rejected later.
        return self.repo.add_proposal(proposal)

    def propose_outcomes_from_batch(self, evidence_ids: list[str]) -> list[OutcomeProposal]:
        """Propose desired outcomes from a batch of evidence records.

        Each record is proposed independently. Records that yield no candidate
        outcome are skipped (not raised) so a batch can contain mixed content.
        """
        proposals: list[OutcomeProposal] = []
        strategy: ProposalStrategy = HeuristicProposalStrategy()
        jobs = self.repo.list_jobs()
        steps = self.repo.list_steps()
        for evidence_id in evidence_ids:
            evidence = self.repo.get_evidence(evidence_id)
            if evidence is None:
                continue
            proposal = strategy.propose(evidence, jobs, steps)
            if proposal is not None:
                proposals.append(self.repo.add_proposal(proposal))
        return proposals

    def list_proposals(self, status: ProposalStatus | None = None) -> list[OutcomeProposal]:
        """List all proposals, optionally filtered by status."""
        return self.repo.list_proposals(status=status)

    def approve_proposal(
        self,
        proposal_id: str,
        statement: str | None = None,
        importance: float | None = None,
        satisfaction: float | None = None,
    ) -> Outcome:
        """Approve a proposal and write it as an Outcome through add_outcome.

        If ``statement`` is provided, the edited statement is validated before
        writing. Importance/satisfaction defaults come from the proposal.
        """
        proposal = self.repo.get_proposal(proposal_id)
        if proposal is None:
            raise ValidationError(f"Proposal {proposal_id} not found.")
        if proposal.status != ProposalStatus.PROPOSED:
            raise ValidationError(
                f"Proposal {proposal_id} is already {proposal.status.value}; "
                "cannot approve a non-proposed proposal."
            )

        final_statement = statement or proposal.statement
        # Validate the (possibly edited) statement through the same path as any
        # other outcome write.
        verdict = evaluate_outcome_statement(final_statement)
        if not verdict["valid"]:
            raise InvalidOutcomeStatementError(verdict)

        final_importance = proposal.importance if importance is None else importance
        final_satisfaction = proposal.satisfaction if satisfaction is None else satisfaction
        if final_importance is None or final_satisfaction is None:
            raise ValidationError(
                f"Proposal {proposal_id} has no scored importance or satisfaction; "
                "approve it with explicit importance and satisfaction values."
            )

        if proposal.job_id is None:
            raise ValidationError(f"Proposal {proposal_id} has no routed job; cannot approve.")

        outcome = self.add_outcome(
            proposal.job_id,
            final_statement,
            importance=final_importance,
            satisfaction=final_satisfaction,
            step_id=proposal.step_id,
        )
        # Mark the proposal as approved (or edited if statement changed).
        new_status = ProposalStatus.EDITED if statement is not None else ProposalStatus.APPROVED
        self.repo.update_proposal(proposal_id, {"status": new_status, "outcome_id": outcome.id})
        return outcome

    def reject_proposal(self, proposal_id: str) -> OutcomeProposal:
        """Reject a proposal. Nothing is written to the ODI store."""
        proposal = self.repo.get_proposal(proposal_id)
        if proposal is None:
            raise ValidationError(f"Proposal {proposal_id} not found.")
        if proposal.status != ProposalStatus.PROPOSED:
            raise ValidationError(
                f"Proposal {proposal_id} is already {proposal.status.value}; "
                "cannot reject a non-proposed proposal."
            )
        rejected = self.repo.update_proposal(proposal_id, {"status": ProposalStatus.REJECTED})
        if rejected is None:
            raise ValidationError(f"Proposal {proposal_id} not found.")
        return rejected

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

    # ---------------------------------------------------------------- segments

    def add_segment(
        self,
        job_id: str,
        name: str,
        criterion: str,
        outcome_ids: list[str],
        notes: str | None = None,
        origin: SegmentOrigin | str = SegmentOrigin.MANUAL,
        candidate_fingerprint: str | None = None,
    ) -> Segment:
        """Create a segment: a named group defined by the outcomes it cares about.

        Every member must belong to ``job_id``; a cross-job or missing member is
        refused before any write, because a segment that spans jobs would corrupt
        every profile built on it. Duplicate member ids are normalised to one
        occurrence, keeping first-seen order. No demographic field exists, by
        design — that is the method's actual claim.
        """
        if self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        name = name.strip()
        if not name:
            raise ValidationError("A segment needs a name.")
        criterion = criterion.strip()
        if not criterion:
            raise ValidationError("A segment needs a criterion saying why the group is coherent.")

        members = _normalise_member_ids(outcome_ids)
        if not members:
            raise ValidationError("A segment needs at least one member outcome.")
        for outcome_id in members:
            outcome = self.repo.get_outcome(outcome_id)
            if outcome is None:
                raise OutcomeNotFoundError(outcome_id)
            if outcome.job_id != job_id:
                raise ValidationError(
                    f"Outcome {outcome_id} belongs to a different job; "
                    "a segment's members must all come from its job."
                )

        try:
            resolved_origin = SegmentOrigin(origin)
        except ValueError as exc:
            raise ValidationError(
                f"Unknown segment origin: {origin!r}. "
                f"Use one of {[o.value for o in SegmentOrigin]}."
            ) from exc

        segment = Segment(
            job_id=job_id,
            name=name,
            criterion=criterion,
            outcome_ids=members,
            notes=notes,
            origin=resolved_origin,
            candidate_fingerprint=candidate_fingerprint,
        )
        return self.repo.add_segment(segment)

    def get_segment(self, segment_id: str) -> Segment | None:
        return self.repo.get_segment(segment_id)

    def list_segments(
        self, job_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Segment]:
        return self.repo.list_segments(job_id, limit=limit, offset=offset)

    def delete_segment(self, segment_id: str) -> None:
        """Delete a segment. Outcomes are never touched — only the lens on them."""
        if not self.repo.delete_segment(segment_id):
            raise SegmentNotFoundError(segment_id)

    def suggest_segments(self, job_id: str) -> SegmentCandidateSet:
        """Propose segment candidates from the scores. Persists nothing (D2).

        The repository is untouched: a suggestion is a read, and the same
        landscape yields the same candidates every time.
        """
        if self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        outcomes = self.repo.get_outcomes(job_id, limit=None)
        return suggest_segment_candidates(outcomes)

    def accept_segment_candidate(
        self,
        job_id: str,
        fingerprint: str,
        name: str | None = None,
        criterion: str | None = None,
    ) -> Segment:
        """Accept exactly the candidate the person saw (D2.2/ALH-161).

        The candidate is recomputed from the current landscape and matched by its
        stable fingerprint, so acceptance targets precisely the proposal that was
        shown. A fingerprint that no longer matches is **stale** (membership
        changed since it was suggested) and is refused with a message naming the
        reason rather than silently accepting a different group.

        Repeat acceptance is idempotent: a segment already created from this
        fingerprint is returned instead of creating a second one, so a retry
        cannot duplicate a segment. ``name`` and ``criterion`` are the
        human-confirmed labels; they default to the candidate's own so acceptance
        needs no extra typing.
        """
        candidates = self.suggest_segments(job_id)
        match = next((c for c in candidates.candidates if c.fingerprint == fingerprint), None)
        if match is None:
            raise ValidationError(
                "No candidate matches that fingerprint for this job; it is stale "
                "(the scores changed since it was proposed). Suggest again and accept "
                "the candidate you are shown."
            )

        for existing in self.repo.list_segments(job_id, limit=None):
            if (
                existing.origin is SegmentOrigin.CANDIDATE
                and existing.candidate_fingerprint == fingerprint
            ):
                return existing

        return self.add_segment(
            job_id=job_id,
            name=name if name is not None else match.name,
            criterion=criterion if criterion is not None else match.rationale,
            outcome_ids=list(match.members),
            origin=SegmentOrigin.CANDIDATE,
            candidate_fingerprint=fingerprint,
        )

    def segment_profile(self, segment_id: str) -> SegmentProfile:
        """Read a segment's servability, split into underserved and overserved.

        A read-only projection: nothing is written. A member that no longer
        resolves is reported as a gap, never silently dropped.
        """
        segment = self.repo.get_segment(segment_id)
        if segment is None:
            raise SegmentNotFoundError(segment_id)
        resolved: list[Outcome] = []
        missing: list[str] = []
        for outcome_id in segment.outcome_ids:
            outcome = self.repo.get_outcome(outcome_id)
            if outcome is None:
                missing.append(outcome_id)
            else:
                resolved.append(outcome)
        return build_segment_profile(segment, resolved, missing_ids=missing)

    # -------------------------------------------------------------- strategies

    def choose_strategy(
        self,
        segment_id: str,
        kind: StrategyKind | str,
        rationale: str,
        expected_effect: str,
        chosen_at: str | None = None,
    ) -> Strategy:
        """Record a strategy for a segment, refusing one its data does not support.

        Each kind has a guardrail that fails with a message naming the missing
        condition, so a strategy is a claim with evidence rather than a slogan:

        * ``differentiated`` needs at least one underserved outcome in the segment.
        * ``disruptive`` needs at least one overserved outcome.
        * ``new_market`` needs an outcome with no evidence of an existing solution.
          That evidence (alternatives data, ``M2-07``/``ALH-71``) is not in the
          product yet, so the rule cannot distinguish an *unchecked* absence from
          an explicit ``nothing`` alternative. Rather than treat unchecked absence
          as proof, the write is refused and the missing evidence is named.
        """
        segment = self.repo.get_segment(segment_id)
        if segment is None:
            raise SegmentNotFoundError(segment_id)
        try:
            resolved_kind = StrategyKind(kind)
        except ValueError as exc:
            raise ValidationError(
                f"Unknown strategy kind: {kind!r}. Use one of {[k.value for k in StrategyKind]}."
            ) from exc
        rationale = rationale.strip()
        if not rationale:
            raise ValidationError("A strategy needs a rationale.")
        expected_effect = expected_effect.strip()
        if not expected_effect:
            raise ValidationError("A strategy needs an expected_effect.")

        profile = self.segment_profile(segment_id)
        if resolved_kind is StrategyKind.DIFFERENTIATED and profile.underserved_count < 1:
            raise ValidationError(
                "A differentiated strategy needs at least one underserved outcome "
                "in the segment; this segment has none."
            )
        if resolved_kind is StrategyKind.DISRUPTIVE and profile.overserved_count < 1:
            raise ValidationError(
                "A disruptive strategy needs at least one overserved outcome "
                "in the segment; this segment has none."
            )
        if resolved_kind is StrategyKind.NEW_MARKET:
            raise ValidationError(
                "A new-market strategy needs evidence that no existing solution "
                "serves the outcome. That alternatives data is not recorded yet "
                "(M2-07/ALH-71), so an unchecked absence cannot stand in for a "
                "checked one. Record the alternatives first."
            )

        strategy = Strategy(
            segment_id=segment_id,
            kind=resolved_kind,
            rationale=rationale,
            chosen_at=chosen_at or _now_iso(),
            expected_effect=expected_effect,
        )
        return self.repo.add_strategy(strategy)

    def get_strategy(self, strategy_id: str) -> Strategy | None:
        return self.repo.get_strategy(strategy_id)

    def list_strategies(
        self, segment_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Strategy]:
        return self.repo.list_strategies(segment_id, limit=limit, offset=offset)

    def latest_strategy(self, segment_id: str) -> Strategy | None:
        """The most recently chosen strategy for a segment, or ``None``."""
        history = self.repo.list_strategies(segment_id, limit=None)
        history.sort(key=lambda s: (s.chosen_at, s.id))
        return history[-1] if history else None

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
            strategy=self._brief_strategy(job_id, decision),
        )

    def _brief_strategy(self, job_id: str, decision: Decision | None) -> BriefStrategy | None:
        """The recorded strategy to show in the brief, or ``None``.

        Sourced from a segment whose membership overlaps the latest decision's
        chosen outcomes — the segment the decision was actually about. With no
        such segment, or no strategy on it, the brief omits the section rather
        than showing a slogan. The selection rule is the shared pure
        :func:`select_brief_strategy`, so the CLI's export path cannot drift.
        """
        if decision is None:
            return None
        segments = [
            BriefSegment(segment_id=s.id, name=s.name, outcome_ids=tuple(s.outcome_ids))
            for s in self.repo.list_segments(job_id, limit=None)
        ]
        strategies = [
            BriefStrategyRecord(
                strategy_id=s.id,
                segment_id=s.segment_id,
                chosen_at=s.chosen_at,
                kind=s.kind.value,
                rationale=s.rationale,
                expected_effect=s.expected_effect,
            )
            for s in self.repo.list_strategies(limit=None)
        ]
        return select_brief_strategy(decision.chosen_outcome_ids, segments, strategies)

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
        from .schedule import compute_next_run, validate_schedule_expression

        validate_schedule_expression(schedule_expression)
        next_run = compute_next_run(schedule_expression)
        work = ScheduledWork(
            id=str(uuid.uuid4()),
            name=name,
            agent_id=agent_id,
            trigger_type=trigger_type,
            schedule_expression=schedule_expression,
            payload=payload or {},
            status=ScheduledWorkStatus.SCHEDULED,
            job_id=job_id,
            next_run_at=next_run.isoformat(),
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
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        from .schedule import compute_next_run

        try:
            next_run = compute_next_run(work.schedule_expression, now=now)
            next_str = next_run.isoformat()
        except ValueError:
            next_str = None
        updates = {
            "status": ScheduledWorkStatus.RUNNING,
            "last_run_at": now_str,
            "next_run_at": next_str,
            "result_summary": (
                f"Dispatched at {now_str}; no executor is installed, so nothing has run."
            ),
        }
        updated = self.repo.update_scheduled_work(work_id, updates)
        if updated is None:
            raise ScheduledWorkNotFoundError(work_id)
        return updated

    # -- Stage 5: outcome-based segments -------------------------------------

    def segment_market(self, job_id: str | None = None, people: str | None = None) -> list[Segment]:
        """Cluster the outcomes into segments and persist what the clustering found.

        ``people`` is the group described in the customer's own words when the
        caller has them; a group derived from the outcomes is labelled inferred.
        Re-running is safe: a cluster keeps the same id, so the stored segment is
        updated with the new evidence instead of a second copy appearing.
        """
        jobs = [job for job in self.repo.list_jobs() if job_id is None or job.id == job_id]
        if job_id is not None and not jobs:
            raise JobNotFoundError(job_id)
        outcomes = list(self.repo.outcomes.values())
        strategy = self.segmentation or OutcomeClusterStrategy(
            steps=list(self.repo.steps.values()), people=people
        )
        return [self.save_segment(item) for item in strategy.segment(jobs, outcomes)]

    def list_segments(self, job_id: str | None = None) -> list[Segment]:
        return self.repo.list_segments(job_id=job_id)

    def get_segment(self, segment_id: str) -> Segment:
        segment = self.repo.get_segment(segment_id)
        if segment is None:
            raise SegmentNotFoundError(segment_id, "run segment_market to produce segments")
        return segment

    def save_segment(self, segment: Segment) -> Segment:
        """Persist one segment, rejecting one the store cannot vouch for."""
        if segment.job_id is not None and self.repo.get_job(segment.job_id) is None:
            raise JobNotFoundError(segment.job_id)
        missing = [oid for oid in segment.outcome_ids if self.repo.get_outcome(oid) is None]
        if missing:
            raise ValidationError(f"Segment cites outcomes that do not exist: {', '.join(missing)}")
        if len(segment.outcome_ids) < MIN_OUTCOMES_PER_SEGMENT:
            raise ValidationError(
                f"A segment needs at least {MIN_OUTCOMES_PER_SEGMENT} outcomes; "
                f"{segment.name} has {len(segment.outcome_ids)}. "
                "It is a hypothesis, and belongs in the unclustered group."
            )
        existing = self.repo.get_segment(segment.id)
        saved = (
            self.repo.update_segment(
                segment.id, segment.model_dump(mode="json", exclude={"id", "created_at"})
            )
            if existing is not None
            else self.repo.add_segment(segment)
        )
        if saved is None:
            raise SegmentNotFoundError(segment.id)
        self._emit_segment_signal(saved, is_new=existing is None)
        return saved

    def _emit_segment_signal(self, segment: Segment, *, is_new: bool) -> None:
        severity = "notice" if segment.verdict is SegmentVerdict.UNDERSERVED else "info"
        self.record_signal(
            SignalKind.SEGMENT_IDENTIFIED,
            f'{"Segment identified" if is_new else "Segment re-scored"}: "{segment.name}"',
            subject_kind="segment",
            subject_id=segment.id,
            severity=severity,
            detail=segment.rationale[:500],
            discriminator=f"verdict={segment.verdict},confidence={segment.confidence}",
            source_event_id=self.repo.last_event_id(),
        )

    def unclustered_outcomes(self, job_id: str | None = None) -> list[Outcome]:
        """Outcomes that joined no segment — reported, never dropped."""
        outcomes = list(self.repo.outcomes.values())
        if job_id is not None:
            outcomes = [outcome for outcome in outcomes if outcome.job_id == job_id]
        return unclustered_outcomes(self.repo.list_segments(), outcomes)

    # -- Stage 6: the strategy they imply ------------------------------------

    def propose_strategy(
        self, segment_ids: list[str] | None = None, job_id: str | None = None
    ) -> Strategy:
        """Recommend the one path the evidence supports, and persist it.

        ``job_id`` narrows the scope to that job's segments. Raises
        :class:`NoStrategyEvidenceError` when no path has evidence: a bet built
        on nothing is the fabrication this stage exists to avoid.
        """
        if job_id is not None and self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        segments = self._segments_in_scope(segment_ids, job_id)
        jobs = self.repo.list_jobs()
        outcomes = list(self.repo.outcomes.values())
        strategy = build_strategy(segments, jobs, outcomes)
        if strategy is None:
            underserved = sum(1 for item in segments if item.verdict is SegmentVerdict.UNDERSERVED)
            overserved = sum(1 for item in segments if item.verdict is SegmentVerdict.OVERSERVED)
            known = {job.id for job in jobs}
            orphans = [item for item in outcomes if item.job_id not in known]
            leftover = len(unclustered_outcomes(segments, outcomes))
            raise NoStrategyEvidenceError(
                f"No path is supported yet: {len(segments)} segment(s) in scope, "
                f"{underserved} underserved, {overserved} overserved, "
                f"{len(orphans)} outcome(s) outside a stored job, {leftover} unclustered. "
                "Score outcomes against a job map before asking for a strategy."
            )
        return self.save_strategy(strategy)

    def _segments_in_scope(
        self, segment_ids: list[str] | None, job_id: str | None = None
    ) -> list[Segment]:
        if segment_ids is None:
            return self.repo.list_segments(job_id=job_id)
        return [self.get_segment(segment_id) for segment_id in segment_ids]

    def list_strategies(self, segment_id: str | None = None) -> list[Strategy]:
        return self.repo.list_strategies(segment_id=segment_id)

    def get_strategy(self) -> Strategy | None:
        """The most recently recorded strategy, or ``None``."""
        strategies = self.repo.list_strategies()
        return strategies[-1] if strategies else None

    def save_strategy(self, strategy: Strategy) -> Strategy:
        """Persist a strategy, requiring the alternatives it beat."""
        if not strategy.rejected:
            raise ValidationError(
                "A strategy without its rejected alternatives is a conclusion, "
                "not a recommendation."
            )
        if strategy.segment_id is not None and self.repo.get_segment(strategy.segment_id) is None:
            raise SegmentNotFoundError(strategy.segment_id, "propose_strategy from stored segments")
        existing = self.repo.get_strategy(strategy.id)
        saved = (
            self.repo.update_strategy(
                strategy.id, strategy.model_dump(mode="json", exclude={"id", "created_at"})
            )
            if existing is not None
            else self.repo.add_strategy(strategy)
        )
        if saved is None:
            raise StrategyNotFoundError(strategy.id)
        self.record_signal(
            SignalKind.STRATEGY_PROPOSED,
            f"Strategy proposed: {saved.kind.value}",
            subject_kind="strategy",
            subject_id=saved.id,
            severity="notice",
            detail=saved.thesis[:500],
            discriminator=f"kind={saved.kind.value},segment={saved.segment_id or ''}",
        )
        return saved
