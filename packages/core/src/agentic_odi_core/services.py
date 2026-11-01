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
from agentic_odi_core.mapping import (
    HeuristicProposalStrategy,
    OutcomeProposal,
    ProposalStatus,
    ProposalStrategy,
)
from agentic_odi_core.models import (
    JOB_STAGE_INDEX,
    JOB_STAGE_ORDER,
    V2MOM,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Evidence,
    EvidenceItemType,
    Job,
    JobStage,
    Outcome,
    OutcomeAlignment,
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
from agentic_odi_core.strategy import propose_strategy as build_strategy
from agentic_odi_core.traceability import (
    Objective,
    TraceabilityReport,
    compute_traceability_report,
    objective_key,
    objectives_from_v2mom,
)


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

    # -- Traceability: what an outcome advances ------------------------------

    def save_v2mom(self, v2mom: V2MOM) -> V2MOM:
        """Persist the vision, values, methods, obstacles, and measures."""
        return self.repo.add_v2mom(v2mom)

    def get_v2mom(self) -> V2MOM | None:
        """The stored vision and its lists, or ``None`` when none was captured."""
        return self.repo.get_v2mom()

    def link_outcome(self, outcome_id: str, field: str, text: str) -> Outcome:
        """Record that an outcome advances one V2MOM method or measure.

        The target must exist *now*: ``text`` is matched against the current
        vision under ``field`` and unknown text is a validation error naming the
        entries that do exist, never a fuzzy match. Linking the same pair twice
        is idempotent.
        """
        outcome = self.repo.get_outcome(outcome_id)
        if outcome is None:
            raise OutcomeNotFoundError(outcome_id)
        objective = self._resolve_objective(field, text)
        alignment = OutcomeAlignment(field=field, key=objective.key, text=objective.text)
        if any(
            existing.field == alignment.field and existing.key == alignment.key
            for existing in outcome.trace
        ):
            return outcome
        # The repository event payload must stay JSON-serializable, so the link
        # travels as its plain dict form rather than as the model.
        trace = [*outcome.trace, alignment.model_dump(mode="json")]
        updated = self.repo.update_outcome(outcome_id, {"trace": trace})
        if updated is None:
            raise OutcomeNotFoundError(outcome_id)
        return updated

    def unlink_outcome(self, outcome_id: str, field: str, key: str) -> Outcome:
        """Remove one link from an outcome. Removing a link that is not there is a no-op."""
        outcome = self.repo.get_outcome(outcome_id)
        if outcome is None:
            raise OutcomeNotFoundError(outcome_id)
        remaining = [
            alignment.model_dump(mode="json")
            for alignment in outcome.trace
            if not (alignment.field == field and alignment.key == key)
        ]
        updated = self.repo.update_outcome(outcome_id, {"trace": remaining})
        if updated is None:
            raise OutcomeNotFoundError(outcome_id)
        return updated

    def list_alignments(self, outcome_id: str | None = None) -> list[dict[str, str]]:
        """Every recorded link, optionally for one outcome."""
        outcomes = (
            [self.repo.get_outcome(outcome_id)]
            if outcome_id is not None
            else list(self.repo.outcomes.values())
        )
        return [
            {
                "outcome_id": outcome.id,
                "field": alignment.field,
                "key": alignment.key,
                "text": alignment.text,
            }
            for outcome in outcomes
            if outcome is not None
            for alignment in outcome.trace
        ]

    def traceability_report(self) -> TraceabilityReport:
        """The three failures: orphans, unfunded objectives, and drift.

        Read-only: it never repairs a link, and with no objectives defined it
        says so rather than returning three empty sections.
        """
        return compute_traceability_report(self.repo.get_v2mom(), list(self.repo.outcomes.values()))

    def _resolve_objective(self, field: str, text: str) -> Objective:
        """Find the current objective named by ``text``, or refuse.

        The refusal names the entries that do exist, because "unknown objective"
        with no list is a dead end for the caller.
        """
        objectives = [item for item in objectives_from_v2mom(self.repo.get_v2mom())]
        available = [item for item in objectives if item.field == field]
        wanted = objective_key(field, text)
        for objective in available:
            if objective.key == wanted:
                return objective
        known = ", ".join(f'"{item.text}"' for item in available) or "none"
        raise ValidationError(
            f"No {field} in the vision matches {text!r}. Current {field}s: {known}."
        )
