"""Service layer implementing business logic."""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from agentic_odi_core.errors import NotFoundError, ValidationError
from agentic_odi_core.evaluation import (
    OutcomeStatementError,
    evaluate_outcome_statement,
    n_advisory,
    require_outcome_statement,
)
from agentic_odi_core.models import (
    ALTERNATIVE_SOURCE_KINDS,
    JOB_STAGE_INDEX,
    JOB_STAGE_ORDER,
    SCORE_SNAPSHOT_NOTE_MAX,
    Alternative,
    AlternativeLink,
    BusinessValue,
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
    ScoreMethod,
    ScoreSnapshot,
    Segment,
    SegmentVerdict,
    Signal,
    SignalKind,
    Step,
    Strategy,
    compute_opportunity_score,
    utc_now_iso,
)
from agentic_odi_core.repository import Repository, page
from agentic_odi_core.segmentation import (
    MIN_OUTCOMES_PER_SEGMENT,
    OutcomeClusterStrategy,
    SegmentationStrategy,
    unclustered_outcomes,
)
from agentic_odi_core.stats import DEFAULT_SEED, opportunity_interval
from agentic_odi_core.strategy import propose_strategy as build_strategy
from agentic_odi_core.survey import SurveyPlan, aggregate_survey, parse_survey, plan_survey
from agentic_odi_core.trust import (
    IntervalProvenance,
    OutcomeDelta,
    build_survey_input_set,
    classify_confidence,
    outcome_delta,
    persisted_interval,
    rank_outcomes_honestly,
    retained_survey_inputs,
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


class AlternativeNotFoundError(NotFoundError):
    def __init__(self, alternative_id: str) -> None:
        self.alternative_id = alternative_id
        super().__init__(alternative_id, "alternative")


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


class SnapshotNoteError(ValueOutOfRangeError):
    """A score snapshot note is longer than the allowed limit.

    A subclass of :class:`ValueOutOfRangeError` so callers that already handle
    an out-of-range value keep working, while the note path can report the
    limit by name.
    """


def _solution_state(
    pairs: list[tuple[Alternative, AlternativeLink]],
) -> Literal["yes", "no_linked_nothing", "no_link_at_all"]:
    """The one solution-state rule every surface reads (M2-07 / M2-07.2).

    Only ``yes`` records a solution: any linked alternative whose kind is not
    ``nothing``. ``no_linked_nothing`` means we asked and the customer uses
    nothing today; ``no_link_at_all`` means we have not asked. The rule lives in
    one place so the brief, the CLI and the Studio facet cannot disagree, and so
    an empty inventory is never read as evidence of no solution.
    """
    if not pairs:
        return "no_link_at_all"
    if any(alternative.kind != "nothing" for alternative, _ in pairs):
        return "yes"
    return "no_linked_nothing"


def _validate_snapshot_note(note: str | None) -> str | None:
    """Reject an over-long note before any score mutation is attempted."""
    if note is not None and len(note) > SCORE_SNAPSHOT_NOTE_MAX:
        raise SnapshotNoteError(f"note must be {SCORE_SNAPSHOT_NOTE_MAX} characters or fewer")
    return note


def _snapshot_from_outcome(outcome: Outcome, note: str | None = None) -> ScoreSnapshot:
    """Capture an accepted outcome's score, sample and method as one snapshot.

    The single place a snapshot is built, so every score-mutating path records
    the same shape. A snapshot stores the companions of the score, because a
    history of bare numbers cannot answer "did the evidence change or the
    estimate?".
    """
    return ScoreSnapshot(
        outcome_id=outcome.id,
        importance=outcome.importance,
        satisfaction=outcome.satisfaction,
        opportunity_score=outcome.opportunity_score,
        importance_n=outcome.importance_n,
        satisfaction_n=outcome.satisfaction_n,
        method=outcome.score_method,
        note=note,
    )


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


def _reject_estimate_with_a_sample(
    method: str, importance_n: int | None, satisfaction_n: int | None
) -> None:
    """Refuse a sample count on an estimate.

    A count above one means people were asked; an estimate cannot have asked
    them. Mirrors the model validator so the service fails with the same message
    the model would, on both the create and partial-update paths.
    """
    if method == "estimate" and ((importance_n or 0) > 1 or (satisfaction_n or 0) > 1):
        raise ValueOutOfRangeError(
            "score_method 'estimate' cannot carry a sample count above 1; "
            "use 'survey' or 'import' when people were asked"
        )


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

    def update_outcome(
        self,
        outcome_id: str,
        updates: dict[str, Any],
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
        # Validate the whole resulting record, not just the patched fields: a
        # partial update that switches a survey to an estimate must still be
        # rejected when the untouched count would then be invalid.
        method = updates.get("score_method", existing.score_method)
        importance_n = updates.get("importance_n", existing.importance_n)
        satisfaction_n = updates.get("satisfaction_n", existing.satisfaction_n)
        _reject_estimate_with_a_sample(method, importance_n, satisfaction_n)
        _validate_snapshot_note(note)
        require_outcome_statement(statement)
        if importance is not None and satisfaction is not None:
            updates = dict(updates)
            updates["opportunity_score"] = compute_opportunity_score(importance, satisfaction)
        else:
            updates = dict(updates)
            updates["opportunity_score"] = None
        # A band describes one exact score and sample. When a caller changes the
        # score without supplying a fresh band, the old band is stale: clear it in
        # the same write rather than letting a new number carry an old range.
        if "opportunity_low" not in updates and "opportunity_high" not in updates:
            score_changed = (importance, satisfaction) != (
                existing.importance,
                existing.satisfaction,
            )
            method_changed = method != existing.score_method
            if existing.opportunity_low is not None and (score_changed or method_changed):
                updates["opportunity_low"] = None
                updates["opportunity_high"] = None
                updates["interval_n"] = None
                # The retained paired inputs described the band that was just
                # invalidated. Keeping them would let a later reader reproduce a
                # band for a score that no longer exists, so they go with it.
                self.repo.delete_survey_input_set(outcome_id)
        res = self.repo.update_outcome(outcome_id, updates)
        if not res:
            raise OutcomeNotFoundError(outcome_id)
        self._emit_outcome_updates(existing, res)
        self._record_score_snapshot(res, note)
        return res

    def get_outcome_delta(self, outcome_id: str, since: str | None = None) -> OutcomeDelta:
        """The signed change across an outcome's recorded snapshots (B6.1).

        Reads the recorded snapshots rather than regenerating a series, so the
        delta is a subtraction over the same history a reviewer can see.
        """
        history = self.get_score_history(outcome_id)
        return outcome_delta(history, since)

    def get_outcome_interval(self, outcome_id: str) -> IntervalProvenance | None:
        """The stored band and its provenance, or ``None`` for a no-band score (B3.2).

        Reads the persisted ``opportunity_low``/``opportunity_high`` off the
        outcome together with the recorded sample, seed, confidence level and
        computed-at, and marks the band stale when a later accepted snapshot
        moved the score it was computed from. ``None`` means the outcome carries
        no band at all — an estimate or an unscored outcome — which is a
        distinct state from a band, and never a zero-width one.
        """
        outcome = self.get_outcome(outcome_id)
        if outcome is None:
            raise OutcomeNotFoundError(outcome_id)
        if outcome.opportunity_low is None or outcome.opportunity_high is None:
            return None
        history = self.repo.list_score_snapshots(outcome_id)
        return persisted_interval(outcome, history)

    def rank_outcomes_for_job(self, job_id: str) -> dict[str, Any]:
        """Partition and rank a job's outcomes by evidence strength (B4/B4.1).

        One shared read for the landscape, ``odi top`` and ``odi coverage``, so
        the CLI, the API and the SPA cannot disagree. Returns measured, thin and
        none sections whose union is the input set; within a section, outcomes
        are ordered by the low end of the band (falling back to the point score)
        descending. Unscored outcomes stay in the ``none`` section, never sorted
        as a zero.
        """
        if self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        outcomes = self.repo.get_outcomes(job_id)
        sections: dict[str, list[dict[str, Any]]] = {"measured": [], "thin": [], "none": []}
        for outcome in rank_outcomes_honestly(outcomes):
            sections[classify_confidence(outcome)].append(self._ranking_entry(outcome))
        return {
            "job_id": job_id,
            "sections": sections,
            "counts": {
                "measured": len(sections["measured"]),
                "thin": len(sections["thin"]),
                "none": len(sections["none"]),
                "total": len(outcomes),
            },
        }

    def _ranking_entry(self, outcome: Outcome) -> dict[str, Any]:
        """The shared ranking entry: score, band, sample, method and advisory (B4)."""
        advisory = n_advisory(outcome)
        return {
            "id": outcome.id,
            "statement": outcome.statement,
            "opportunity_score": outcome.opportunity_score,
            "opportunity_low": outcome.opportunity_low,
            "opportunity_high": outcome.opportunity_high,
            "importance_n": outcome.importance_n,
            "satisfaction_n": outcome.satisfaction_n,
            "score_method": outcome.score_method,
            "confidence": classify_confidence(outcome),
            "advisory": (
                None
                if advisory is None
                else {
                    "n": advisory.n,
                    "threshold": advisory.threshold,
                    "method": advisory.method,
                    "dimension": advisory.dimension,
                    "message": advisory.message,
                }
            ),
        }

    def _survey_reference_index(self) -> tuple[set[str], dict[str, str | None]]:
        """The exact-match resolution tables for a survey import (B2).

        ``known_ids`` is every outcome id in the store; ``id_by_statement`` maps
        a statement to its single outcome id, or to ``None`` when the statement
        is ambiguous. Both are job-agnostic because an import may reference any
        outcome the store holds.
        """
        outcomes = [
            outcome for job in self.repo.list_jobs() for outcome in self.repo.get_outcomes(job.id)
        ]
        known_ids = {outcome.id for outcome in outcomes}
        id_by_statement: dict[str, str | None] = {}
        for outcome in outcomes:
            if outcome.statement in id_by_statement:
                id_by_statement[outcome.statement] = None  # ambiguous
            else:
                id_by_statement[outcome.statement] = outcome.id
        return known_ids, id_by_statement

    def get_survey_import_plan(
        self,
        rows: list[dict[str, Any]],
        *,
        confirmed_matches: dict[str, str] | None = None,
    ) -> SurveyPlan:
        """Build a side-effect-free import plan that accounts for every row (B2.2).

        Resolves references against the whole store exactly as :meth:`import_survey`
        does, but writes nothing: the plan names each row's fate and line number,
        so a dry run prints the report the real run would produce.
        """
        known_ids, id_by_statement = self._survey_reference_index()
        return plan_survey(
            rows,
            id_by_statement=id_by_statement,
            known_ids=known_ids,
            confirmed_matches=confirmed_matches,
        )

    def commit_survey_import(
        self,
        rows: list[dict[str, Any]],
        *,
        confirmed_matches: dict[str, str] | None = None,
    ) -> dict[str, Outcome]:
        """Plan and write a survey import, refusing any unresolved row (B2.2).

        Re-plans from the same rows and writes only when every row is accepted,
        so a dry run and the real run agree and a partial write is impossible.
        """
        plan = self.get_survey_import_plan(rows, confirmed_matches=confirmed_matches)
        return self.commit_survey_plan(plan)

    def commit_survey_plan(self, plan: SurveyPlan) -> dict[str, Outcome]:
        """Write an already-reviewed, fully-accepted plan (B2.2).

        Refuses a plan with any rejected row, so a partial write is impossible:
        the caller must resolve or explicitly confirm every row first. Accepted
        rows land through the same band/sample path as :meth:`import_survey`.
        """
        if not plan.writable:
            rejected = ", ".join(f"line {row.line} ({row.status})" for row in plan.rejected)
            raise ValidationError(
                f"import plan has {len(plan.rejected)} unresolved row(s): {rejected}; "
                "resolve or confirm every row before writing"
            )
        observations: dict[str, list[tuple[float, float]]] = {}
        respondent_refs: dict[str, list[str]] = {}
        for response in plan.accepted:
            observations.setdefault(response.outcome_ref, []).append(
                (response.importance, response.satisfaction)
            )
            respondent_refs.setdefault(response.outcome_ref, []).append(response.respondent)
        updated: dict[str, Outcome] = {}
        for outcome_id, aggregate in plan.aggregates.items():
            if self.get_outcome(outcome_id) is None:
                raise OutcomeNotFoundError(outcome_id)
            updates: dict[str, Any] = {
                "importance": round(aggregate.importance_mean, 6),
                "satisfaction": round(aggregate.satisfaction_mean, 6),
                "importance_n": aggregate.n,
                "satisfaction_n": aggregate.n,
                "score_method": "survey",
            }
            updates.update(self._band_for(observations.get(outcome_id, [])))
            updated[outcome_id] = self.update_outcome(outcome_id, updates)
            self._retain_inputs(
                updated[outcome_id],
                observations.get(outcome_id, []),
                respondent_refs.get(outcome_id, []),
            )
        return updated

    def import_survey(
        self,
        rows: list[dict[str, Any]],
    ) -> dict[str, Outcome]:
        """Land a survey's per-outcome means on the matching outcomes (B2).

        Parses and aggregates first, so a malformed file or an unresolved
        reference fails before any outcome is written; then updates each outcome
        through :meth:`update_outcome` so all score validation still applies and
        the write records ``method='survey'`` with its per-dimension ``n`` and a
        band bootstrapped from the real paired responses. Nothing is written for
        a reference that does not resolve.
        """
        responses = parse_survey(rows)
        known_ids, id_by_statement = self._survey_reference_index()
        result = aggregate_survey(responses, id_by_statement=id_by_statement, known_ids=known_ids)

        # The band is bootstrapped from the paired responses, not from the mean,
        # so the correlation between the two dimensions survives.
        observations: dict[str, list[tuple[float, float]]] = {}
        respondent_refs: dict[str, list[str]] = {}
        for response in responses:
            outcome_id = (
                response.outcome_ref
                if response.outcome_ref_kind == "outcome_id"
                else id_by_statement[response.outcome_ref]
            )
            if outcome_id is None:
                continue
            observations.setdefault(outcome_id, []).append(
                (response.importance, response.satisfaction)
            )
            respondent_refs.setdefault(outcome_id, []).append(response.respondent)

        updated: dict[str, Outcome] = {}
        for outcome_id, aggregate in result.aggregates.items():
            existing = self.get_outcome(outcome_id)
            if existing is None:
                raise OutcomeNotFoundError(outcome_id)
            updates: dict[str, Any] = {
                "importance": round(aggregate.importance_mean, 6),
                "satisfaction": round(aggregate.satisfaction_mean, 6),
                "importance_n": aggregate.n,
                "satisfaction_n": aggregate.n,
                "score_method": "survey",
            }
            updates.update(self._band_for(observations.get(outcome_id, [])))
            updated[outcome_id] = self.update_outcome(outcome_id, updates)
            self._retain_inputs(
                updated[outcome_id],
                observations.get(outcome_id, []),
                respondent_refs.get(outcome_id, []),
            )
        return updated

    def _retain_inputs(
        self,
        outcome: Outcome,
        pairs: list[tuple[float, float]],
        respondent_refs: list[str],
    ) -> None:
        """Persist the accepted paired inputs a band is reproduced from (B3.1).

        Called only after the outcome write succeeded, so a refused or dry-run
        import retains nothing. The set is de-identified (opaque per-pair tokens,
        no names) and carries a versioned ref so the band can name its inputs.
        """
        if not pairs:
            return
        input_set = build_survey_input_set(outcome, pairs, respondent_refs=respondent_refs)
        self.repo.add_survey_input_set(input_set)

    def get_outcome_inputs(self, outcome_id: str) -> list[Any] | None:
        """The paired inputs a stored band was reproduced from (B3.1), or ``None``.

        Reads the persisted input set for the outcome. ``None`` means no input
        set is retained — a legacy or aggregate-only outcome — which is a
        distinct state from a retained set, and never an empty list that would
        read as "zero responses".
        """
        outcome = self.get_outcome(outcome_id)
        if outcome is None:
            raise OutcomeNotFoundError(outcome_id)
        input_set = self.repo.get_survey_input_set(outcome_id)
        if input_set is None:
            return None
        return retained_survey_inputs(input_set)

    def _band_for(self, observations: list[tuple[float, float]]) -> dict[str, Any]:
        """Compute the stored band and provenance from paired responses (B3/B3.2).

        Uses the real per-respondent pairs, not the aggregated mean: a bootstrap
        over the means would report a zero-width band for a spread-out sample.
        """
        if not observations:
            return {}
        importance = [pair[0] for pair in observations]
        satisfaction = [pair[1] for pair in observations]
        interval = opportunity_interval(importance, satisfaction)
        return {
            "opportunity_low": interval.low,
            "opportunity_high": interval.high,
            "interval_n": interval.n,
            "interval_seed": DEFAULT_SEED,
            "interval_confidence_level": interval.confidence_level,
            "interval_computed_at": utc_now_iso(),
        }

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

    def _record_score_snapshot(self, outcome: Outcome, note: str | None = None) -> ScoreSnapshot:
        """Write one snapshot for an accepted score state.

        Called from every score-mutating path, so a future path cannot skip the
        history. The snapshot records the *accepted* state, so it is written
        after the mutation succeeds and never for a rejected one.
        """
        return self.repo.add_score_snapshot(_snapshot_from_outcome(outcome, note))

    def get_score_history(self, outcome_id: str) -> list[ScoreSnapshot]:
        """Return an outcome's snapshots in the order they were accepted."""
        if self.repo.get_outcome(outcome_id) is None:
            raise OutcomeNotFoundError(outcome_id)
        return self.repo.list_score_snapshots(outcome_id)

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
        _reject_estimate_with_a_sample(score_method, importance_n, satisfaction_n)
        _validate_snapshot_note(note)
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
            importance_n=importance_n,
            satisfaction_n=satisfaction_n,
            score_method=score_method,
        )
        created = self.repo.add_outcome(outcome)
        self._record_score_snapshot(created, note)
        return created

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

    def add_alternative(
        self,
        job_id: str,
        name: str,
        kind: str,
        notes: str | None = None,
        source_kind: str = "manual",
    ) -> Alternative:
        """Record what a customer uses today for one Job (M2-07).

        Never inferred from a score or an import: the caller supplies the
        customer's own inventory. An unknown job or an unapproved source_kind is
        refused rather than silently accepted.
        """
        if self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        if source_kind not in ALTERNATIVE_SOURCE_KINDS:
            raise ValidationError(
                f"source_kind {source_kind!r} is not one of {', '.join(ALTERNATIVE_SOURCE_KINDS)}"
            )
        alternative = Alternative(
            job_id=job_id, name=name, kind=kind, notes=notes, source_kind=source_kind
        )
        return self.repo.add_alternative(alternative)

    def get_alternative(self, alternative_id: str) -> Alternative:
        alternative = self.repo.get_alternative(alternative_id)
        if alternative is None:
            raise AlternativeNotFoundError(alternative_id)
        return alternative

    def list_alternatives(
        self, job_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Alternative]:
        return self.repo.list_alternatives(job_id, limit=limit, offset=offset)

    def delete_alternative(self, alternative_id: str) -> None:
        if not self.repo.delete_alternative(alternative_id):
            raise AlternativeNotFoundError(alternative_id)

    def link_alternative(
        self,
        outcome_id: str,
        alternative_id: str,
        adequacy: float,
        usage_n: int | None = None,
        note: str | None = None,
    ) -> AlternativeLink:
        """Rate one alternative against one outcome, from the customer (M2-07).

        Refuses a cross-job link: the outcome and the alternative must belong to
        the same Job, or the link would compare unrelated work.
        """
        outcome = self.repo.get_outcome(outcome_id)
        if outcome is None:
            raise OutcomeNotFoundError(outcome_id)
        alternative = self.repo.get_alternative(alternative_id)
        if alternative is None:
            raise AlternativeNotFoundError(alternative_id)
        if outcome.job_id != alternative.job_id:
            raise ValidationError(
                "an alternative link must join an outcome and an alternative in the "
                f"same job; outcome job {outcome.job_id!r} != alternative job "
                f"{alternative.job_id!r}"
            )
        link = AlternativeLink(
            outcome_id=outcome_id,
            alternative_id=alternative_id,
            adequacy=adequacy,
            usage_n=usage_n,
            note=note,
        )
        return self.repo.link_alternative(link)

    def unlink_alternative(self, outcome_id: str, alternative_id: str) -> None:
        if not self.repo.unlink_alternative(outcome_id, alternative_id):
            raise ValidationError(
                f"no link between outcome {outcome_id!r} and alternative {alternative_id!r}"
            )

    def outcome_alternatives(self, outcome_id: str) -> list[tuple[Alternative, AlternativeLink]]:
        """The alternatives recorded for one outcome, each with its adequacy link."""
        if self.repo.get_outcome(outcome_id) is None:
            raise OutcomeNotFoundError(outcome_id)
        result: list[tuple[Alternative, AlternativeLink]] = []
        for link in self.repo.list_alternative_links(outcome_id=outcome_id):
            alternative = self.repo.get_alternative(link.alternative_id)
            if alternative is not None:
                result.append((alternative, link))
        return result

    def has_existing_solution(
        self, outcome_id: str
    ) -> Literal["yes", "no_linked_nothing", "no_link_at_all"]:
        """Whether an existing solution is recorded for an outcome (M2-07).

        A two-valued question with three honest answers, so a caller can tell
        "we asked and there is nothing" (``no_linked_nothing``) from "we have not
        asked" (``no_link_at_all``). Only ``yes`` means a solution is recorded;
        an empty inventory is never evidence that no solution exists.
        """
        return _solution_state(self.outcome_alternatives(outcome_id))

    def job_outcome_alternatives(
        self, job_id: str
    ) -> list[tuple[str, Alternative, AlternativeLink]]:
        """Every recorded alternative for one Job, each with its outcome and link.

        A bulk read of the inventory so the landscape facet can compute a
        solution state and a kind filter per outcome without a request per row.
        It reuses :func:`_solution_state`, so the facet, the detail row and the
        brief cannot disagree. An unknown job is refused rather than reported as
        an empty inventory.
        """
        if self.repo.get_job(job_id) is None:
            raise JobNotFoundError(job_id)
        result: list[tuple[str, Alternative, AlternativeLink]] = []
        for link in self.repo.list_alternative_links(job_id=job_id):
            alternative = self.repo.get_alternative(link.alternative_id)
            if alternative is not None:
                result.append((link.outcome_id, alternative, link))
        return result

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
