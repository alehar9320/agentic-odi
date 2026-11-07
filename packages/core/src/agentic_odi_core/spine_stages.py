"""Real spine stages, wired to the store.

The seam in :mod:`agentic_odi_core.spine` defines the stage contracts and
honest stubs. This module provides the *real* implementations for the stages
that exist today, so :func:`agentic_odi_core.spine.seam_inventory` can report
them as available and downstream work (the end-to-end proof, the guides, the
Studio) runs against real code rather than doubles.

Two stages are real as of ``A4``/``A5``:

* ``candidate`` — :class:`StoreCandidateExtractor` runs a
  :class:`~agentic_odi_core.extraction.StatementExtractor` over one quote and
  persists the proposals through the repository.
* ``outcome`` — :class:`StoreOutcomeAcceptor` accepts a proposed candidate
  through :func:`~agentic_odi_core.review.accept_candidate`, which goes through
  ``ODIService.add_outcome`` so the format validator still applies.

The remaining five stages stay stubs in :mod:`agentic_odi_core.spine` and still
refuse; nothing here fabricates their result. ``build_spine`` wires what exists
and leaves the rest honest, so a caller never has to know which is which.
"""

from __future__ import annotations

from datetime import datetime, timezone

from agentic_odi_core.errors import NotFoundError
from agentic_odi_core.extraction import (
    FixtureStatementExtractor,
    StatementExtractor,
    extract_candidates,
)
from agentic_odi_core.models import (
    BetRecord,
    DecisionRecord,
    Outcome,
)
from agentic_odi_core.repository import Repository
from agentic_odi_core.review import accept_candidate
from agentic_odi_core.services import ODIService
from agentic_odi_core.spine import (
    Bet,
    BriefDocument,
    BriefFigure,
    CandidateOutcome,
    Decision,
    Measurement,
    ScoreSample,
    Spine,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SpineStageError(NotFoundError):
    """A spine stage was handed an id that does not resolve in the store."""

    def __init__(self, entity_id: str, kind: str) -> None:
        super().__init__(entity_id, kind)


class StoreCandidateExtractor:
    """The real ``candidate`` stage: extract from one quote into the store.

    Wraps a :class:`~agentic_odi_core.extraction.StatementExtractor` (the model
    boundary) and the repository (the store). The extractor proposes; this stage
    validates and persists. It never writes an :class:`Outcome`.
    """

    def __init__(
        self,
        repo: Repository,
        extractor: StatementExtractor | None = None,
    ) -> None:
        self._repo = repo
        self._extractor = extractor or FixtureStatementExtractor()

    def extract(
        self,
        quote: str,
        *,
        quote_id: str,
        job_id: str,
        job_name: str | None = None,
        stage_hint: str | None = None,
        interview_id: str | None = None,
        step_id: str | None = None,
    ) -> list[CandidateOutcome]:
        """Extract and persist candidates for one quote; return the wire shapes.

        This method is synchronous (the repository is synchronous). The
        underlying extractor is awaited here; the seam protocol keeps the async
        boundary at the model, not at the store.
        """
        import asyncio

        candidates = asyncio.run(
            extract_candidates(
                self._repo,
                self._extractor,
                quote_id=quote_id,
                quote=quote,
                job_id=job_id,
                job_name=job_name,
                stage_hint=stage_hint,
                interview_id=interview_id,
                step_id=step_id,
            )
        )
        return [
            CandidateOutcome(
                quote_id=c.quote_id,
                statement=c.statement,
                source_quote=quote,
                confidence=c.confidence,
                candidate_id=c.id,
                status=c.status.value,
                outcome_id=c.outcome_id,
            )
            for c in candidates
        ]


class StoreOutcomeAcceptor:
    """The real ``outcome`` stage: accept a candidate into a real Outcome.

    Delegates to :func:`agentic_odi_core.review.accept_candidate`, which calls
    ``ODIService.add_outcome``. The candidate's ``status`` must be ``proposed``;
    an already-decided candidate is refused rather than re-accepted.
    """

    def __init__(self, repo: Repository, service: ODIService | None = None) -> None:
        self._repo = repo
        self._service = service or ODIService(repo)

    def accept(
        self,
        candidate_id: str,
        *,
        importance: float,
        satisfaction: float,
        statement: str | None = None,
        step_id: str | None = None,
    ) -> Outcome:
        return accept_candidate(
            self._service,
            self._repo,
            candidate_id,
            statement=statement,
            importance=importance,
            satisfaction=satisfaction,
            step_id=step_id,
        )


class StoreScoreSampler:
    """The real ``score`` stage: read an outcome's scores as a sample.

    The sample size is the outcome's own counts if it carries them; otherwise it
    is ``None`` — an unknown sample, not a measured zero. A score is never
    invented: an outcome with no scores yields a sample with no numbers.
    """

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def sample(self, outcome_id: str) -> ScoreSample:
        outcome = self._repo.get_outcome(outcome_id)
        if outcome is None:
            raise SpineStageError(outcome_id, "outcome")
        return ScoreSample(
            outcome_id=outcome.id,
            importance=outcome.importance,
            satisfaction=outcome.satisfaction,
            sample_size=None,
        )


class StoreBriefRenderer:
    """The real ``brief`` stage: render the brief for a subject from the store.

    Every figure carries its basis in words, and the counts are real counts of
    stored rows. An outcome with no scores contributes no opportunity figure
    rather than a fabricated number.
    """

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def render(self, subject_id: str) -> BriefDocument:
        outcome = self._repo.get_outcome(subject_id)
        if outcome is None:
            raise SpineStageError(subject_id, "outcome")
        figures: list[BriefFigure] = []
        if outcome.opportunity_score is not None:
            figures.append(
                BriefFigure(
                    name="opportunity_score",
                    value=outcome.opportunity_score,
                    basis=(
                        f"importance {outcome.importance} + max(importance - "
                        f"satisfaction, 0) at satisfaction {outcome.satisfaction}"
                    ),
                )
            )
        figures.append(
            BriefFigure(
                name="decisions",
                value=float(len(self._repo.list_decisions(subject_id=outcome.id))),
                basis=f"{len(self._repo.list_decisions(subject_id=outcome.id))} decisions recorded",
            )
        )
        return BriefDocument(
            subject_id=outcome.id,
            headline=outcome.statement,
            figures=tuple(figures),
        )


class StoreDecisionRecorder:
    """The real ``decision`` stage: record a decision against its subject.

    Refuses a subject that does not resolve, so a decision can never point at
    nothing.
    """

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def record(self, *, subject_id: str, choice: str, rationale: str) -> Decision:
        if self._repo.get_outcome(subject_id) is None:
            raise SpineStageError(subject_id, "outcome")
        record = DecisionRecord(
            subject_id=subject_id, choice=choice, rationale=rationale, decided_at=_now()
        )
        self._repo.add_decision(record)
        return Decision(
            id=record.id,
            subject_id=record.subject_id,
            choice=record.choice,
            rationale=record.rationale,
            decided_at=record.decided_at,
        )


class StoreBetTracker:
    """The real ``bet`` stage: track a bet under a decision.

    Refuses a decision that does not resolve. The baseline is ``None`` until it
    is measured — an unknown baseline, never an invented zero.
    """

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def track(self, *, decision_id: str, statement: str, metric: str) -> Bet:
        if self._repo.get_decision(decision_id) is None:
            raise SpineStageError(decision_id, "decision")
        record = BetRecord(decision_id=decision_id, statement=statement, metric=metric)
        self._repo.add_bet(record)
        return Bet(
            id=record.id,
            decision_id=record.decision_id,
            statement=record.statement,
            metric=record.metric,
            baseline=record.baseline,
        )


class StoreMeasurementReader:
    """The real ``measure`` stage: read what a bet measured.

    A bet with no measurement yet yields a measurement whose ``value`` is
    ``None`` — "nothing yet" is representable without a fabricated number.
    """

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def measure(self, bet_id: str) -> Measurement:
        bet = self._repo.get_bet(bet_id)
        if bet is None:
            raise SpineStageError(bet_id, "bet")
        records = self._repo.list_measurements(bet_id=bet_id)
        if not records:
            return Measurement(bet_id=bet_id, metric=bet.metric, value=None, observed_at=_now())
        latest = records[-1]
        return Measurement(
            bet_id=latest.bet_id,
            metric=latest.metric,
            value=latest.value,
            observed_at=latest.observed_at,
        )


def build_spine(
    repo: Repository,
    *,
    extractor: StatementExtractor | None = None,
) -> Spine:
    """A spine with the implemented stages real and the rest honest stubs.

    Wires every stage that has a real implementation to the store; a stage
    without one keeps its stub, so the inventory reports exactly what this build
    can and cannot do.
    """
    return Spine(
        extractor=StoreCandidateExtractor(repo, extractor),
        acceptor=StoreOutcomeAcceptor(repo),
        sampler=StoreScoreSampler(repo),
        brief=StoreBriefRenderer(repo),
        decisions=StoreDecisionRecorder(repo),
        bets=StoreBetTracker(repo),
        measurements=StoreMeasurementReader(repo),
    )


__all__ = [
    "SpineStageError",
    "StoreBetTracker",
    "StoreBriefRenderer",
    "StoreCandidateExtractor",
    "StoreDecisionRecorder",
    "StoreMeasurementReader",
    "StoreOutcomeAcceptor",
    "StoreScoreSampler",
    "build_spine",
]
