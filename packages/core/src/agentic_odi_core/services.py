"""Service layer implementing business logic."""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from agentic_odi_core.errors import NotFoundError, ValidationError
from agentic_odi_core.evaluation import (
    OutcomeStatementError,
    evaluate_outcome_statement,
    require_outcome_statement,
)
from agentic_odi_core.messages import (
    candidate_reason_required,
    merge_source_already_merged,
    merge_source_cannot_absorb_evidence,
    merge_target_must_be_outcome,
)
from agentic_odi_core.models import (
    JOB_STAGE_INDEX,
    JOB_STAGE_ORDER,
    BusinessValue,
    CandidateStatus,
    CustomerOutcome,
    CustomerValue,
    Evidence,
    EvidenceItemType,
    Interview,
    InterviewQuote,
    Job,
    JobStage,
    Outcome,
    OutcomeCandidate,
    ScheduledWork,
    ScheduledWorkStatus,
    ScheduledWorkTriggerType,
    Segment,
    SegmentVerdict,
    Signal,
    SignalKind,
    Step,
    Strategy,
    compute_opportunity_score,
)
from agentic_odi_core.repository import Repository, page
from agentic_odi_core.segmentation import (
    MIN_OUTCOMES_PER_SEGMENT,
    OutcomeClusterStrategy,
    SegmentationStrategy,
    unclustered_outcomes,
)
from agentic_odi_core.similarity import DUPLICATE_THRESHOLD, find_duplicate_groups, normalize
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


class InterviewNotFoundError(NotFoundError):
    def __init__(self, interview_id: str) -> None:
        self.interview_id = interview_id
        super().__init__(interview_id, "interview")


class QuoteNotFoundError(NotFoundError):
    def __init__(self, quote_id: str) -> None:
        self.quote_id = quote_id
        super().__init__(quote_id, "quote")


class CandidateNotFoundError(NotFoundError):
    def __init__(self, candidate_id: str) -> None:
        self.candidate_id = candidate_id
        super().__init__(candidate_id, "outcome candidate")


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

    def add_interview(
        self,
        title: str,
        participant_label: str,
        job_id: str | None = None,
        participant_role: str | None = None,
        conducted_at: str | None = None,
        source_kind: str = "manual",
        notes: str | None = None,
    ) -> Interview:
        if job_id is not None and self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        interview = Interview(
            id=str(uuid.uuid4()),
            job_id=job_id,
            title=title,
            participant_label=participant_label,
            participant_role=participant_role,
            conducted_at=conducted_at,
            source_kind=source_kind,
            notes=notes,
        )
        return self.repo.add_interview(interview)

    def get_interview(self, interview_id: str) -> Interview | None:
        return self.repo.get_interview(interview_id)

    def list_interviews(
        self,
        job_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Interview]:
        return self.repo.list_interviews(job_id, limit=limit, offset=offset)

    def update_interview(self, interview_id: str, updates: dict[str, Any]) -> Interview:
        res = self.repo.update_interview(interview_id, updates)
        if not res:
            raise InterviewNotFoundError(interview_id)
        return res

    def delete_interview(self, interview_id: str) -> list[str]:
        """Delete an interview; return the ids of the quotes removed with it."""
        if self.repo.get_interview(interview_id) is None:
            raise InterviewNotFoundError(interview_id)
        return self.repo.delete_interview(interview_id)

    def add_quote(
        self,
        interview_id: str,
        text: str,
        speaker: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> InterviewQuote:
        """Append a quote to an interview.

        The ordinal is assigned here as ``max(ordinal)+1`` within the
        interview, so two quotes created in the same millisecond still have a
        deterministic order. A missing interview is rejected before any event
        is written.
        """
        if self.repo.get_interview(interview_id) is None:
            raise InterviewNotFoundError(interview_id)
        existing = self.repo.list_quotes(interview_id)
        next_ordinal = (existing[-1].ordinal + 1) if existing else 0
        quote = InterviewQuote(
            id=str(uuid.uuid4()),
            interview_id=interview_id,
            speaker=speaker,
            text=text,
            ordinal=next_ordinal,
            start_ms=start_ms,
            end_ms=end_ms,
        )
        return self.repo.add_quote(quote)

    def list_quotes(self, interview_id: str) -> list[InterviewQuote]:
        return self.repo.list_quotes(interview_id)

    def get_quote(self, quote_id: str) -> InterviewQuote | None:
        return self.repo.get_quote(quote_id)

    def import_transcript(
        self,
        text: str,
        *,
        title: str,
        participant_label: str,
        filename: str | None = None,
        fmt: str | None = None,
        job_id: str | None = None,
        participant_role: str | None = None,
        conducted_at: str | None = None,
        source_kind: str = "transcript",
    ) -> tuple[Interview, list[InterviewQuote]]:
        """Parse a transcript, then persist it as one interview.

        The parse is pure and runs first, so a malformed transcript raises
        before any interview or quote is written — there is no partial state.
        """
        from agentic_odi_core.transcript import detect_format, parse_transcript

        resolved = fmt or detect_format(text, filename)
        turns = parse_transcript(text, resolved)
        interview = self.add_interview(
            title=title,
            participant_label=participant_label,
            job_id=job_id,
            participant_role=participant_role,
            conducted_at=conducted_at,
            source_kind=source_kind,
        )
        quotes = [
            self.add_quote(
                interview.id,
                turn.text,
                speaker=turn.speaker,
                start_ms=turn.start_ms,
                end_ms=turn.end_ms,
            )
            for turn in turns
        ]
        return interview, quotes

    def extract_candidates(
        self,
        quote_id: str,
        extractor: Any,
        stage_hint: str | None = None,
    ) -> list[OutcomeCandidate]:
        """Propose candidates from one quote, storing each proposal once.

        Every proposal is validated with :func:`evaluate_outcome_statement`. An
        invalid one is stored as ``rejected`` with the validator's message in
        ``rationale`` — the evidence that the extractor is wrong is kept, not
        hidden. Candidates are keyed on ``(quote_id, normalised_statement)`` so
        re-running extraction adds nothing and never resets a human decision.
        No :class:`Outcome` is created here; only a person accepts a candidate.
        """
        quote = self.repo.get_quote(quote_id)
        if quote is None:
            raise QuoteNotFoundError(quote_id)
        interview = self.repo.get_interview(quote.interview_id)
        if interview is None:
            raise InterviewNotFoundError(quote.interview_id)

        existing = self._candidates_by_key(quote_id)
        # Validate every proposal before the first write: a malformed payload or
        # an out-of-range confidence must not leave a partly-written quote.
        proposals = list(extractor.propose(quote, interview, stage_hint))
        planned: list[tuple[str, OutcomeCandidate]] = []
        for proposal in proposals:
            statement = getattr(proposal, "statement", None)
            if not isinstance(statement, str):
                raise ValidationError(
                    f"extractor returned a proposal without a statement: {proposal!r}"
                )
            key = normalize(statement)
            if key in existing:
                continue
            verdict = evaluate_outcome_statement(statement)
            if verdict["valid"]:
                status = CandidateStatus.PROPOSED
                rationale = proposal.rationale
            else:
                status = CandidateStatus.REJECTED
                rationale = " ".join(verdict["issues"])
            planned.append(
                (
                    key,
                    OutcomeCandidate(
                        id=str(uuid.uuid4()),
                        interview_id=interview.id,
                        quote_id=quote_id,
                        statement=statement,
                        rationale=rationale,
                        confidence=proposal.confidence,
                        status=status,
                    ),
                )
            )
            # Collapse repeated statements within this same batch.
            existing.add(key)

        created: list[OutcomeCandidate] = []
        for _, candidate in planned:
            created.append(self.repo.add_candidate(candidate))
        return created

    def _candidates_by_key(self, quote_id: str) -> set[str]:
        """The normalised statements already stored for a quote."""
        return {
            normalize(c.statement) for c in self.repo.list_candidates() if c.quote_id == quote_id
        }

    def get_candidate(self, candidate_id: str) -> OutcomeCandidate | None:
        return self.repo.get_candidate(candidate_id)

    def list_candidates(
        self,
        interview_id: str | None = None,
        status: CandidateStatus | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[OutcomeCandidate]:
        return self.repo.list_candidates(interview_id, status, limit=limit, offset=offset)

    def update_candidate(self, candidate_id: str, updates: dict[str, Any]) -> OutcomeCandidate:
        candidate = self.repo.update_candidate(candidate_id, updates)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        return candidate

    def delete_candidate(self, candidate_id: str) -> None:
        if not self.repo.delete_candidate(candidate_id):
            raise CandidateNotFoundError(candidate_id)

    def accept_candidate(
        self,
        candidate_id: str,
        *,
        importance: float,
        satisfaction: float,
        statement: str | None = None,
        step_id: str | None = None,
    ) -> tuple[OutcomeCandidate, Outcome, Evidence]:
        """Turn one proposed candidate into exactly one outcome with its evidence.

        The edited ``statement`` (or the proposed one) is validated *before* any
        write, then ``add_outcome`` runs, then the verbatim quote is written as
        an ``Evidence`` row, and only then is the candidate marked ``accepted``
        with the new ``outcome_id``. If the evidence write fails the new outcome
        is removed again, so a failure can never leave an accepted candidate
        without evidence or an orphan outcome.

        Accepting an already-accepted candidate is a no-op that returns what the
        first acceptance produced, so a retry cannot duplicate either the
        outcome or the evidence.
        """
        candidate = self.repo.get_candidate(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)

        if candidate.status == CandidateStatus.ACCEPTED and candidate.outcome_id:
            outcome = self.repo.get_outcome(candidate.outcome_id)
            if outcome is not None:
                return candidate, outcome, self._candidate_evidence(candidate)
        if candidate.status is not CandidateStatus.PROPOSED:
            raise ValidationError(
                f"Outcome candidate {candidate_id} is {candidate.status.value}, not proposed"
            )

        quote = self.repo.get_quote(candidate.quote_id)
        if quote is None:
            raise QuoteNotFoundError(candidate.quote_id)
        interview = self.repo.get_interview(candidate.interview_id)
        if interview is None:
            raise InterviewNotFoundError(candidate.interview_id)
        if interview.job_id is None:
            raise ValidationError(
                f"Interview {interview.id} is not linked to a job, so a candidate cannot "
                "become an outcome. Link the interview to a job first."
            )

        text = (statement or candidate.statement).strip()
        verdict = evaluate_outcome_statement(text)
        if not verdict["valid"]:
            raise InvalidOutcomeStatementError(verdict)

        outcome = self.add_outcome(
            interview.job_id,
            text,
            importance=importance,
            satisfaction=satisfaction,
            step_id=step_id,
        )
        try:
            evidence = self.add_evidence(
                source_name=interview.title,
                source_kind="interview",
                name="quote",
                content=quote.text,
                item_type="manual",
                raw={"interview_id": interview.id, "quote_id": quote.id},
                outcome_id=outcome.id,
            )
        except Exception:
            self.repo.delete_outcome(outcome.id)
            raise
        accepted = self.repo.update_candidate(
            candidate.id,
            {
                "status": CandidateStatus.ACCEPTED,
                "statement": text,
                "outcome_id": outcome.id,
            },
        )
        assert accepted is not None  # the candidate existed a moment ago
        return accepted, outcome, evidence

    def reject_candidate(self, candidate_id: str, *, reason: str) -> OutcomeCandidate:
        """Reject a candidate, keeping it and a nonblank reason.

        The quote stays attached, so a rejected idea is still auditable. An
        empty reason is refused without touching the store.
        """
        candidate = self.repo.get_candidate(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        cleaned = (reason or "").strip()
        if not cleaned:
            raise ValidationError(candidate_reason_required(candidate_id))
        if candidate.status is CandidateStatus.ACCEPTED:
            raise ValidationError(
                f"Outcome candidate {candidate_id} was accepted; rejecting it would orphan "
                "the outcome it produced."
            )
        rejected = self.repo.update_candidate(
            candidate_id,
            {"status": CandidateStatus.REJECTED, "decision_reason": cleaned},
        )
        assert rejected is not None
        return rejected

    def _candidate_evidence(self, candidate: OutcomeCandidate) -> Evidence:
        """The evidence row acceptance wrote for a candidate."""
        for item in self.repo.list_evidence(outcome_id=candidate.outcome_id):
            if item.raw.get("quote_id") == candidate.quote_id:
                return item
        raise EvidenceNotFoundError(
            candidate.outcome_id or candidate.id,
            "Acceptance should have written one evidence row for this candidate.",
        )

    def suggest_duplicate_groups(
        self,
        interview_id: str | None = None,
        threshold: float = DUPLICATE_THRESHOLD,
    ) -> list[list[str]]:
        """Candidate id groups that look like the same need. Read-only.

        Only candidates still ``proposed`` are compared — an accepted or
        rejected candidate is a settled decision, not a merge source. Nothing is
        written, so a suggestion can never itself change the store.
        """
        candidates = [
            candidate
            for candidate in self.repo.list_candidates(interview_id)
            if candidate.status is CandidateStatus.PROPOSED
        ]
        return find_duplicate_groups(candidates, threshold)

    def merge_candidates(
        self,
        target_id: str,
        merged_ids: list[str],
    ) -> tuple[Outcome, list[Evidence], list[OutcomeCandidate]]:
        """Absorb other candidates' quotes into one accepted outcome.

        ``target_id`` is an **outcome** id — the outcome a person already
        accepted. Each id in ``merged_ids`` is a *proposed* candidate whose
        verbatim quote is written as an additional ``Evidence`` row on that
        outcome and then marked ``merged`` with ``merged_into=target_id``. No
        second outcome is created, and the source candidate and its quote are
        retained, so the original can be recovered by re-extraction.

        Everything is validated before any write: an unknown target, a source
        that is accepted/rejected, or a source already merged elsewhere fails
        without moving anything. A source already merged into this same target
        is skipped, so repeating a merge changes nothing and duplicates no
        evidence. If an evidence write fails part-way, the evidence rows and
        candidate updates made by this call are rolled back.
        """
        target = self.repo.get_outcome(target_id)
        if target is None:
            # A candidate id here is the common mistake: name it, rather than
            # reporting a bare "outcome not found".
            if self.repo.get_candidate(target_id) is not None:
                raise ValidationError(merge_target_must_be_outcome(target_id))
            raise OutcomeNotFoundError(target_id)

        sources: list[OutcomeCandidate] = []
        seen: set[str] = set()
        for candidate_id in merged_ids:
            if candidate_id in seen:
                continue
            seen.add(candidate_id)
            candidate = self.repo.get_candidate(candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(candidate_id)
            if candidate.status is CandidateStatus.MERGED:
                if candidate.merged_into == target_id:
                    continue  # already absorbed here; repeating changes nothing
                raise ValidationError(
                    merge_source_already_merged(candidate_id, candidate.merged_into)
                )
            if candidate.status is not CandidateStatus.PROPOSED:
                raise ValidationError(
                    merge_source_cannot_absorb_evidence(candidate_id, candidate.status.value)
                )
            sources.append(candidate)

        written_evidence: list[Evidence] = []
        merged: list[OutcomeCandidate] = []
        try:
            for candidate in sources:
                quote = self.repo.get_quote(candidate.quote_id)
                if quote is None:
                    raise QuoteNotFoundError(candidate.quote_id)
                interview = self.repo.get_interview(candidate.interview_id)
                if interview is None:
                    raise InterviewNotFoundError(candidate.interview_id)
                evidence = self.add_evidence(
                    source_name=interview.title,
                    source_kind="interview",
                    name="quote",
                    content=quote.text,
                    item_type="manual",
                    raw={
                        "interview_id": interview.id,
                        "quote_id": quote.id,
                        "merged_from_candidate_id": candidate.id,
                    },
                    outcome_id=target_id,
                )
                written_evidence.append(evidence)
                updated = self.repo.update_candidate(
                    candidate.id,
                    {"status": CandidateStatus.MERGED, "merged_into": target_id},
                )
                assert updated is not None  # the candidate existed a moment ago
                merged.append(updated)
        except Exception:
            for evidence in written_evidence:
                self.repo.delete_evidence(evidence.id)
            for candidate in merged:
                self.repo.update_candidate(
                    candidate.id,
                    {"status": CandidateStatus.PROPOSED, "merged_into": None},
                )
            raise
        return target, written_evidence, merged

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
