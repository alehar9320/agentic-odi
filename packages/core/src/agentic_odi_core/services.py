"""Service layer implementing business logic."""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from agentic_odi_core.bulk import (
    BulkReport,
    apply_tags,
    apply_themes,
    changed_fields,
    image,
    theme_delta,
)
from agentic_odi_core.errors import NotFoundError, ValidationError
from agentic_odi_core.evaluation import (
    OutcomeStatementError,
    classify_opportunity,
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
    BulkChange,
    BulkOperation,
    BusinessValue,
    ClaimCheck,
    ClaimSkip,
    CustomerOutcome,
    CustomerValue,
    Evidence,
    EvidenceItemType,
    Job,
    JobStage,
    Outcome,
    ScheduledWork,
    ScheduledWorkStatus,
    ScheduledWorkTriggerType,
    Segment,
    SegmentVerdict,
    Signal,
    SignalKind,
    Step,
    Strategy,
    Study,
    StudyStatus,
    Theme,
    compute_opportunity_score,
)
from agentic_odi_core.query import OutcomeQuery, search_outcomes
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


class ThemeNotFoundError(NotFoundError, ValueError):
    """Raised when a theme id does not resolve."""

    def __init__(self, theme_id: str, hint: str | None = None) -> None:
        self.theme_id = theme_id
        super().__init__(theme_id, "theme", hint)


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
        if importance is not None and satisfaction is not None:
            updates = dict(updates)
            updates["opportunity_score"] = compute_opportunity_score(importance, satisfaction)
        else:
            updates = dict(updates)
            updates["opportunity_score"] = None
        theme_ids = updates.get("theme_ids")
        if theme_ids is not None:
            for theme_id in theme_ids:
                theme = self.repo.get_theme(theme_id)
                if theme is None:
                    raise ThemeNotFoundError(theme_id)
                if theme.job_id is not None and theme.job_id != existing.job_id:
                    raise ValidationError(
                        f"Theme {theme_id} organizes job {theme.job_id}, not the outcome's job "
                        f"{existing.job_id}; an outcome may only join a theme in its scope."
                    )
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
                f"Opportunity score {before.opportunity_score} -> {after.opportunity_score} "
                f'({direction}): "{after.statement[:60]}"',
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
        importance: float | None = None,
        satisfaction: float | None = None,
        step_id: str | None = None,
        validate_statement: bool = True,
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
        outcome = Outcome(
            id=str(uuid.uuid4()),
            job_id=job_id,
            step_id=step_id,
            statement=statement,
            importance=importance,
            satisfaction=satisfaction,
            opportunity_score=opportunity_score,
            claim_check=check,
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

    def search_outcomes(
        self,
        text: str | None = None,
        stage: str | None = None,
        theme_ids: list[str] | None = None,
        confidence: str | None = None,
        tags: list[str] | None = None,
        min_score: float | None = None,
        max_score: float | None = None,
        job_id: str | None = None,
        sort: str = "opportunity_score",
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Narrow the library through the shared query, writing nothing.

        This is the composition point for the CLI, the API, and later bulk
        edit and saved views: same parameters in, same ids, total, and facet
        counts out on every surface.
        """
        if job_id is not None and self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        #: A dataclass is not a validator, so bounds arriving as prose are
        #: caught where they first have to behave like a number.
        for name, bound in (("min_score", min_score), ("max_score", max_score)):
            if bound is not None:
                try:
                    float(bound)
                except (TypeError, ValueError) as exc:
                    raise ValidationError(f"{name} must be a number: {exc}") from exc
        #: ``page()`` guards the slice with a bare ValueError, which every caller
        #: facing a surface would report as an internal failure. A nonsensical
        #: number is a bad request, so it arrives as the established error here.
        for name, number in (("limit", limit), ("offset", offset)):
            if number is not None and number < 0:
                raise ValueOutOfRangeError(f"{name} must be >= 0")
        query = OutcomeQuery(
            text=text,
            stage=str(stage) if stage is not None else None,
            theme_ids=list(theme_ids or []),
            confidence=confidence,
            tags=list(tags or []),
            min_score=min_score,
            max_score=max_score,
            job_id=job_id,
            sort=sort,
        )
        return search_outcomes(self.repo, query, limit, offset)

    # --- bulk change (ALH-196 / M2-03.1) ------------------------------------

    def bulk_update_outcomes(
        self,
        outcome_ids: list[str] | None,
        *,
        add_theme_ids: list[str] | None = None,
        remove_theme_ids: list[str] | None = None,
        stage: str | None = None,
        add_tags: list[str] | None = None,
        query: OutcomeQuery | None = None,
        dry_run: bool = False,
    ) -> BulkReport:
        """Organise a filtered set in one reviewable operation.

        Each row succeeds or reports its own reason: a missing outcome, a theme that does not
        organise this outcome's job, or a job with no such stage skips that row and leaves the
        others applied. ``dry_run`` walks the whole pipeline and writes nothing, so the ids and
        the change table it lists are the ones a real run on unchanged input produces — and it
        produces no undo token.

        A contradiction is a bad request rather than a silent ordering: one theme both added
        and removed refuses the whole call, and so does a stage outside the job map.
        """
        add, remove, tags = self._bulk_request(add_theme_ids, remove_theme_ids, add_tags)
        if stage is not None and stage not in {value.value for value in JobStage}:
            raise ValidationError(f"Unknown stage: {stage}")
        contradictions = [theme_id for theme_id in add if theme_id in remove]
        if contradictions:
            raise ValidationError(
                f"Theme {contradictions[0]} is both added and removed; a bulk change picks one."
            )
        if not add and not remove and stage is None and not tags:
            raise ValidationError(
                "Nothing to change: name a theme to add or remove, a stage, or a tag."
            )
        targets = self._bulk_targets(outcome_ids, query)
        if not targets:
            raise ValidationError("No outcomes selected")

        report = BulkReport(requested=len(targets))
        planned: list[BulkChange] = []
        for outcome_id in targets:
            outcome = self.repo.get_outcome(outcome_id)
            if outcome is None:
                report.skipped.append({"id": outcome_id, "reason": "outcome not found"})
                continue
            problem, after = self._bulk_after_image(outcome, add, remove, stage, tags)
            if problem is not None:
                report.skipped.append({"id": outcome_id, "reason": problem})
                continue
            before = image(outcome)
            moved = changed_fields(before, after)
            if not moved:
                report.skipped.append({"id": outcome_id, "reason": "no change"})
                continue
            for field_name in moved:
                report.changes.append(
                    {
                        "outcome_id": outcome_id,
                        "field": field_name,
                        "from": before[field_name],
                        "to": after[field_name],
                    }
                )
            planned.append(BulkChange(outcome_id=outcome_id, before=before, after=after))
            if not dry_run:
                self._write_bulk_row(outcome, after)
            report.changed.append(outcome_id)

        if dry_run or not planned:
            return report
        operation = self.repo.add_bulk_operation(
            BulkOperation(
                applied_at=datetime.now(timezone.utc),
                requested=report.requested,
                changes=planned,
                skipped=list(report.skipped),
            )
        )
        report.undo_token = operation.id
        return report

    @staticmethod
    def _bulk_request(
        add_theme_ids: list[str] | None,
        remove_theme_ids: list[str] | None,
        add_tags: list[str] | None,
    ) -> tuple[list[str], list[str], list[str]]:
        return (
            list(dict.fromkeys(add_theme_ids or [])),
            list(dict.fromkeys(remove_theme_ids or [])),
            list(dict.fromkeys(add_tags or [])),
        )

    def _bulk_targets(self, outcome_ids: list[str] | None, query: OutcomeQuery | None) -> list[str]:
        """The distinct ids this run owns: those named, plus every match of the narrowing.

        The query runs without a page limit: a bulk change over "everything missing a stage"
        means the library's whole answer, not the first screen of it.
        """
        ids: list[str] = list(dict.fromkeys(outcome_ids or []))
        if query is not None:
            matched = search_outcomes(self.repo, query).get("items", [])
            ids += [str(item["id"]) for item in matched if item.get("id") not in ids]
        return list(dict.fromkeys(ids))

    def _bulk_after_image(
        self,
        outcome: Outcome,
        add: list[str],
        remove: list[str],
        stage: str | None,
        tags: list[str],
    ) -> tuple[str | None, dict[str, Any]]:
        """(reason, None) when this row cannot change; (None, the new fields) when it can."""
        themes: list[str] = []
        for theme_id in add:
            theme = self.repo.get_theme(theme_id)
            if theme is None:
                return f"unknown theme: {theme_id}", {}
            if theme.job_id is not None and theme.job_id != outcome.job_id:
                return (
                    f"Theme {theme.id} organizes job {theme.job_id}, not the outcome's job "
                    f"{outcome.job_id}; an outcome may only join a theme in its scope.",
                    {},
                )
            themes.append(theme_id)
        for theme_id in remove:
            if self.repo.get_theme(theme_id) is None:
                return f"unknown theme: {theme_id}", {}

        step_id = outcome.step_id
        if stage is not None:
            step = self._stage_step(outcome, stage)
            if step is None:
                return f"job has no stage '{stage}'", {}
            step_id = step.id

        after: dict[str, Any] = image(outcome)
        after["step_id"] = step_id
        after["theme_ids"] = apply_themes(outcome.theme_ids, add, remove)
        after["tags"] = apply_tags(outcome.tags, tags)
        return None, after

    def _stage_step(self, outcome: Outcome, stage: str) -> Step | None:
        """The job's step that holds this stage, chosen the same way every time."""
        candidates = [
            step
            for step in self.repo.get_steps_for_job(outcome.job_id)
            if step.stage is not None and step.stage.value == stage
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda step: (step.stage_index or 0, step.order, step.id))

    def _write_bulk_row(self, outcome: Outcome, after: dict[str, Any]) -> None:
        """One row through the paths a single edit takes, so no validator is skipped."""
        added, removed = theme_delta(outcome.theme_ids, after["theme_ids"])
        if added or removed:
            if self.repo.change_theme_membership(outcome.id, added=added, removed=removed) is None:
                raise OutcomeNotFoundError(outcome.id)
        updates: dict[str, Any] = {}
        if after["step_id"] != outcome.step_id:
            updates["step_id"] = after["step_id"]
        if set(after["tags"]) != set(outcome.tags):
            updates["tags"] = after["tags"]
        if updates:
            self.update_outcome(outcome.id, updates)

    def undo_bulk(self, token: str) -> BulkReport:
        """Take a bulk run back, row by row, through the same validators.

        The token is single-use and single-active: it is refused once undone, and refused in
        favour of the newest run. A row someone edited since the bulk change is left alone and
        reported — undo must not overwrite a deliberate later answer.
        """
        operation = self.repo.get_bulk_operation(token)
        if operation is None:
            raise ValidationError(f"Unknown bulk token: {token}")
        if operation.undone_at is not None:
            raise ValidationError(f"Bulk {token} is already undone.")
        newer = [op for op in self.repo.list_bulk_operations() if op.id != token]
        if newer:
            raise ValidationError(
                f"Bulk {token} expired: bulk {newer[-1].id} wrote after it. "
                "One bulk run stays undoable at a time."
            )

        report = BulkReport(requested=len(operation.changes))
        restored: list[str] = []
        for change in operation.changes:
            outcome = self.repo.get_outcome(change.outcome_id)
            if outcome is None:
                report.skipped.append({"id": change.outcome_id, "reason": "outcome not found"})
                continue
            current = image(outcome)
            if changed_fields(change.after, current):
                report.skipped.append(
                    {
                        "id": change.outcome_id,
                        "reason": "changed since the bulk update",
                    }
                )
                continue
            moved = changed_fields(current, change.before)
            for field_name in moved:
                report.changes.append(
                    {
                        "outcome_id": change.outcome_id,
                        "field": field_name,
                        "from": current[field_name],
                        "to": change.before[field_name],
                    }
                )
            self._write_bulk_row(outcome, change.before)
            restored.append(change.outcome_id)
            report.changed.append(change.outcome_id)

        if restored:
            self.repo.update_bulk_operation(token, {"undone_at": datetime.now(timezone.utc)})
        return report

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

    # -- Themes: a shallow named tree over the outcome library ----------------

    def add_theme(
        self,
        name: str,
        job_id: str | None = None,
        parent_id: str | None = None,
        description: str | None = None,
        ordinal: int = 0,
    ) -> Theme:
        """Add one theme, refusing a placement the two-level tree cannot hold.

        Scope has exactly one meaning: a theme with a ``job_id`` organizes that
        job's outcomes only, and a theme without one is workspace-wide — its
        children must match its scope, so a job theme never hangs off a
        workspace theme or the other way round.
        """
        if job_id is not None and self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        if parent_id is not None:
            self._validate_theme_placement(parent_id, job_id)
        theme = Theme(
            job_id=job_id, parent_id=parent_id, name=name, description=description, ordinal=ordinal
        )
        return self.repo.add_theme(theme)

    def _validate_theme_placement(self, parent_id: str, job_id: str | None) -> Theme:
        parent = self.repo.get_theme(parent_id)
        if parent is None:
            raise ValidationError(f"Theme parent {parent_id} does not exist; add it first.")
        if parent.parent_id is not None:
            raise ValidationError(
                f"Theme {parent_id} is already a child of {parent.parent_id}; themes go two "
                "levels deep at most, so nothing can go under it."
            )
        if parent.job_id != job_id:
            raise ValidationError(
                f"Theme parent has scope job_id={parent.job_id!r}, the child asks for "
                f"job_id={job_id!r}; a theme and its parent must share a scope — "
                "a workspace theme (job_id=None) organizes any job's outcomes, "
                "a job theme only its own."
            )
        return parent

    def get_theme(self, theme_id: str) -> Theme:
        theme = self.repo.get_theme(theme_id)
        if theme is None:
            raise ThemeNotFoundError(theme_id, "add a theme first")
        return theme

    def list_themes(self, job_id: str | None = None) -> list[Theme]:
        return self.repo.list_themes(job_id=job_id)

    def rename_theme(
        self,
        theme_id: str,
        name: str | None = None,
        description: str | None = None,
        ordinal: int | None = None,
        parent_id: str | None = None,
    ) -> Theme:
        """Rename a theme, or move it under a parent; omitted fields stay as they are."""
        theme = self.get_theme(theme_id)
        updates: dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if ordinal is not None:
            updates["ordinal"] = ordinal
        if parent_id is not None:
            self._validate_theme_placement(parent_id, theme.job_id)
            has_children = any(t.parent_id == theme_id for t in self.repo.themes.values())
            if has_children:
                raise ValidationError(
                    f"Theme {theme_id} still has children; moving it down would make them a "
                    "third level, and themes go two levels deep. Move the children first."
                )
            updates["parent_id"] = parent_id
        if not updates:
            return theme
        renamed = self.repo.update_theme(theme_id, updates)
        if renamed is None:
            raise ThemeNotFoundError(theme_id)
        return renamed

    def delete_theme(self, theme_id: str) -> dict[str, Any]:
        """Delete a theme; its children rise to its parent and no outcome is deleted.

        Deleting an outcome through a theme would destroy research to tidy a
        label, so the cascade stops at membership: outcomes lose this one
        theme id and keep every other. The reparented ids ride the event, so a
        reload reproduces the same tree.
        """
        theme = self.get_theme(theme_id)
        reparented = [t.id for t in self.repo.themes.values() if t.parent_id == theme_id]
        self.repo.delete_theme(theme_id)
        return {
            "theme_id": theme_id,
            "name": theme.name,
            "reparented_to": theme.parent_id,
            "reparented": reparented,
        }

    def assign_theme(self, outcome_ids: list[str], theme_id: str) -> list[Outcome]:
        """File outcomes under a theme; every one must exist and match its scope."""
        theme = self.get_theme(theme_id)
        self._check_membership_targets(outcome_ids, theme)
        results = []
        for outcome_id in outcome_ids:
            updated = self.repo.change_theme_membership(outcome_id, added=[theme_id], removed=[])
            if updated is None:
                raise OutcomeNotFoundError(outcome_id)
            results.append(updated)
        return results

    def unassign_theme(self, outcome_ids: list[str], theme_id: str) -> list[Outcome]:
        """Take outcomes out of one theme; their other memberships stay."""
        self.get_theme(theme_id)
        missing = [oid for oid in outcome_ids if self.repo.get_outcome(oid) is None]
        if missing:
            raise OutcomeNotFoundError(missing[0])
        results = []
        for outcome_id in outcome_ids:
            updated = self.repo.change_theme_membership(outcome_id, added=[], removed=[theme_id])
            if updated is None:
                raise OutcomeNotFoundError(outcome_id)
            results.append(updated)
        return results

    def _check_membership_targets(self, outcome_ids: list[str], theme: Theme) -> None:
        missing = [oid for oid in outcome_ids if self.repo.get_outcome(oid) is None]
        if missing:
            raise OutcomeNotFoundError(missing[0])
        if theme.job_id is not None:
            foreign = []
            for oid in outcome_ids:
                existing = self.repo.get_outcome(oid)
                if existing is not None and existing.job_id != theme.job_id:
                    foreign.append(oid)
            if foreign:
                raise ValidationError(
                    f"Theme {theme.id} organizes job {theme.job_id}; outcomes "
                    f"{', '.join(foreign)} belong to other jobs. A workspace theme "
                    "(job_id=None) is the one that spans jobs."
                )

    def _validate_theme_membership(self, theme_ids: list[str]) -> None:
        for theme_id in theme_ids:
            theme = self.repo.get_theme(theme_id)
            if theme is None:
                raise ThemeNotFoundError(theme_id)

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
