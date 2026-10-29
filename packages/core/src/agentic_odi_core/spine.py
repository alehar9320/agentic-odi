"""The ODI spine seam: the stages, their callable contracts, and honest stubs.

The product *is* the spine: quote → candidate → outcome → score → brief →
decision → bet → measure. Each hop is owned by its own issue (``A4``, ``A5``,
``B1``, ``C1``, ``C6``, ``E1``, ``E2``). Until a hop is implemented, nothing
downstream can produce a real number — and inventing one is worse than
reporting the gap.

This module is the seam that lets the rest of the codebase depend on a stable
shape *now*:

* the ordered stages (:class:`SpineStage`),
* the owner of each stage (:data:`SEAM_OWNERS`), so a gap is reported by
  reference to the issue that closes it,
* the callable contract of each stage (the ``*Protocol`` classes),
* a typed refusal, :class:`StageNotImplemented`, that every stub raises, and
* a capability inventory (:func:`seam_inventory` / :func:`spine_summary`) so any
  surface — CLI, Studio, an agent — can say "nothing yet" honestly.

Nothing here fabricates a result. Every stub raises rather than returning a
placeholder, because a plausible-looking placeholder is indistinguishable from
real data once it reaches a brief.

The transport shapes below (``CandidateOutcome``, ``ScoreSample``, …) are the
seam's *wire* types, not persisted entities: they carry no ``id`` factory, no
repository, schema, or event wiring, and they deliberately do not appear in
:func:`agentic_odi_core.schema.odi_schema`. When a stage lands, its real model
replaces the wire shape and takes on the persistence checklist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import NoReturn, Protocol

from agentic_odi_core.errors import OdiError
from agentic_odi_core.models import Outcome, compute_opportunity_score

# --------------------------------------------------------------------------- #
# Owners
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SeamOwner:
    """The issue that owns a seam, so a gap is reported by reference.

    ``module`` is only set where an issue names the file it will add (for
    example ``C1`` names ``brief.py``); it is ``None`` where the file name is
    not yet decided, rather than guessed.
    """

    id: str
    title: str
    issue: str
    issue_title: str
    module: str | None = None


class SpineStage(str, Enum):
    """The seven stages of the spine, in pipeline order."""

    CANDIDATE = "candidate"
    OUTCOME = "outcome"
    SCORE = "score"
    BRIEF = "brief"
    DECISION = "decision"
    BET = "bet"
    MEASURE = "measure"


SPINE_ORDER: tuple[SpineStage, ...] = (
    SpineStage.CANDIDATE,
    SpineStage.OUTCOME,
    SpineStage.SCORE,
    SpineStage.BRIEF,
    SpineStage.DECISION,
    SpineStage.BET,
    SpineStage.MEASURE,
)

# Seams outside the seven-stage pipeline that other work still depends on.
DEMO_SEAM = "demo"
TEMPLATE_SEAM = "template"

SEAM_OWNERS: dict[str, SeamOwner] = {
    SpineStage.CANDIDATE.value: SeamOwner(
        id=SpineStage.CANDIDATE.value,
        title="Extract candidate outcomes from one quote",
        issue="ALH-17",
        issue_title="A4 · Extract candidate outcomes from one quote",
    ),
    SpineStage.OUTCOME.value: SeamOwner(
        id=SpineStage.OUTCOME.value,
        title="Accept a proposed outcome into the map",
        issue="ALH-18",
        issue_title="A5 · Accept a proposed outcome into the map",
    ),
    SpineStage.SCORE.value: SeamOwner(
        id=SpineStage.SCORE.value,
        title="Every score says how many people it came from",
        issue="ALH-24",
        issue_title="B1 · Every score says how many people it came from",
    ),
    SpineStage.BRIEF.value: SeamOwner(
        id=SpineStage.BRIEF.value,
        title="The case, from the numbers",
        issue="ALH-32",
        issue_title="C1 · The case, from the numbers",
        module="brief.py",
    ),
    SpineStage.DECISION.value: SeamOwner(
        id=SpineStage.DECISION.value,
        title="Record the decision",
        issue="ALH-37",
        issue_title="C6 · Record the decision",
    ),
    SpineStage.BET.value: SeamOwner(
        id=SpineStage.BET.value,
        title="A bet is a thing you can track",
        issue="ALH-46",
        issue_title="E1 · A bet is a thing you can track",
    ),
    SpineStage.MEASURE.value: SeamOwner(
        id=SpineStage.MEASURE.value,
        title="Did it move?",
        issue="ALH-47",
        issue_title="E2 · Did it move?",
    ),
    DEMO_SEAM: SeamOwner(
        id=DEMO_SEAM,
        title="A demo workspace you can load on purpose",
        issue="ALH-58",
        issue_title="M0-13 · Guided · A demo workspace you can load on purpose",
    ),
    TEMPLATE_SEAM: SeamOwner(
        id=TEMPLATE_SEAM,
        title="Workspace templates",
        issue="ALH-119",
        issue_title="M4-13 · Share · Workspace templates",
    ),
}


class StageNotImplemented(OdiError):
    """A spine stage was invoked before its implementation landed.

    Carries the stage and its owner so a caller can render the gap instead of a
    number. Deliberately an :class:`~agentic_odi_core.errors.OdiError` so a
    surface that already catches ODI errors cannot leak a fabricated value past
    an unhandled exception.
    """

    def __init__(self, seam_id: str, owner: SeamOwner | None = None) -> None:
        self.seam_id = seam_id
        self.owner = owner if owner is not None else SEAM_OWNERS.get(seam_id)
        if self.owner is None:
            message = f"The '{seam_id}' stage is not implemented in this build."
        else:
            message = (
                f"The '{seam_id}' stage is not implemented in this build. "
                f"It is owned by {self.owner.issue} ({self.owner.issue_title}); "
                "implement it there rather than fabricating its result."
            )
        super().__init__(message)


# --------------------------------------------------------------------------- #
# Transport shapes (seam wire types — NOT persisted entities)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CandidateOutcome:
    """A proposed outcome extracted from a source quote, awaiting acceptance."""

    quote_id: str
    statement: str
    source_quote: str
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class ScoreSample:
    """A score with its basis: how many responses produced it.

    ``sample_size`` is ``None`` when unknown, which is different from a measured
    zero and must stay distinguishable downstream.
    """

    outcome_id: str
    importance: float | None = None
    satisfaction: float | None = None
    sample_size: int | None = None

    @property
    def opportunity_score(self) -> float | None:
        if self.importance is None or self.satisfaction is None:
            return None
        return compute_opportunity_score(self.importance, self.satisfaction)


@dataclass(frozen=True, slots=True)
class BriefFigure:
    """One number in a brief, with the basis that produced it."""

    name: str
    value: float
    basis: str


@dataclass(frozen=True, slots=True)
class BriefDocument:
    """A rendered brief: its figures, each carrying the basis for its value."""

    subject_id: str
    headline: str
    figures: tuple[BriefFigure, ...] = ()


@dataclass(frozen=True, slots=True)
class Decision:
    """A recorded decision."""

    id: str
    subject_id: str
    choice: str
    rationale: str
    decided_at: str


@dataclass(frozen=True, slots=True)
class Bet:
    """A bet: a decision's claim, with the metric that would move."""

    id: str
    decision_id: str
    statement: str
    metric: str
    baseline: float | None = None


@dataclass(frozen=True, slots=True)
class Measurement:
    """What a bet measured, against its baseline."""

    bet_id: str
    metric: str
    value: float | None
    observed_at: str


@dataclass(frozen=True, slots=True)
class DemoWorkspace:
    """A loaded demo workspace. ``labelled`` marks it as sample data."""

    name: str
    job_ids: tuple[str, ...] = ()
    labelled: bool = True


# --------------------------------------------------------------------------- #
# Stage contracts (the interfaces)
# --------------------------------------------------------------------------- #


class CandidateExtractor(Protocol):
    def extract(self, quote: str) -> list[CandidateOutcome]: ...


class OutcomeAcceptor(Protocol):
    def accept(self, candidate: CandidateOutcome, *, job_id: str) -> Outcome: ...


class ScoreSampler(Protocol):
    def sample(self, outcome_id: str) -> ScoreSample: ...


class BriefRenderer(Protocol):
    def render(self, subject_id: str) -> BriefDocument: ...


class DecisionRecorder(Protocol):
    def record(self, *, subject_id: str, choice: str, rationale: str) -> Decision: ...


class BetTracker(Protocol):
    def track(self, *, decision_id: str, statement: str, metric: str) -> Bet: ...


class MeasurementReader(Protocol):
    def measure(self, bet_id: str) -> Measurement: ...


class DemoLoader(Protocol):
    def load(self, *, name: str = "demo") -> DemoWorkspace: ...


class TemplateEngine(Protocol):
    """Applies a named safe template, producing the workspace it defines.

    Declared here rather than in a ``templates`` module so the inventory can name
    the seam without importing a module that does not exist yet.
    """

    def apply(self, template_id: str) -> DemoWorkspace: ...


# --------------------------------------------------------------------------- #
# Stubs — every one refuses rather than fabricating
# --------------------------------------------------------------------------- #


class _Stub:
    """Base for a stub: refuses with the stage's owner named."""

    _seam: str

    def _refuse(self) -> NoReturn:
        raise StageNotImplemented(self._seam, SEAM_OWNERS.get(self._seam))


class UnavailableCandidateExtractor(_Stub):
    _seam = SpineStage.CANDIDATE.value

    def extract(self, quote: str) -> list[CandidateOutcome]:
        self._refuse()


class UnavailableOutcomeAcceptor(_Stub):
    _seam = SpineStage.OUTCOME.value

    def accept(self, candidate: CandidateOutcome, *, job_id: str) -> Outcome:
        self._refuse()


class UnavailableScoreSampler(_Stub):
    _seam = SpineStage.SCORE.value

    def sample(self, outcome_id: str) -> ScoreSample:
        self._refuse()


class UnavailableBriefRenderer(_Stub):
    _seam = SpineStage.BRIEF.value

    def render(self, subject_id: str) -> BriefDocument:
        self._refuse()


class UnavailableDecisionRecorder(_Stub):
    _seam = SpineStage.DECISION.value

    def record(self, *, subject_id: str, choice: str, rationale: str) -> Decision:
        self._refuse()


class UnavailableBetTracker(_Stub):
    _seam = SpineStage.BET.value

    def track(self, *, decision_id: str, statement: str, metric: str) -> Bet:
        self._refuse()


class UnavailableMeasurementReader(_Stub):
    _seam = SpineStage.MEASURE.value

    def measure(self, bet_id: str) -> Measurement:
        self._refuse()


class UnavailableDemoLoader(_Stub):
    _seam = DEMO_SEAM

    def load(self, *, name: str = "demo") -> DemoWorkspace:
        self._refuse()


class UnavailableTemplateEngine(_Stub):
    _seam = TEMPLATE_SEAM

    def apply(self, template_id: str) -> DemoWorkspace:
        self._refuse()


_UNAVAILABLE_TYPES: tuple[type, ...] = (
    UnavailableCandidateExtractor,
    UnavailableOutcomeAcceptor,
    UnavailableScoreSampler,
    UnavailableBriefRenderer,
    UnavailableDecisionRecorder,
    UnavailableBetTracker,
    UnavailableMeasurementReader,
    UnavailableDemoLoader,
    UnavailableTemplateEngine,
)


# --------------------------------------------------------------------------- #
# The wired spine
# --------------------------------------------------------------------------- #


@dataclass
class Spine:
    """The stages of the spine, each either a real implementation or a stub.

    :func:`default_spine` returns every stage stubbed, so the honest default is
    "nothing yet". A caller wires a real implementation by passing it in; the
    inventory then reports that stage as available.
    """

    extractor: CandidateExtractor = field(default_factory=UnavailableCandidateExtractor)
    acceptor: OutcomeAcceptor = field(default_factory=UnavailableOutcomeAcceptor)
    sampler: ScoreSampler = field(default_factory=UnavailableScoreSampler)
    brief: BriefRenderer = field(default_factory=UnavailableBriefRenderer)
    decisions: DecisionRecorder = field(default_factory=UnavailableDecisionRecorder)
    bets: BetTracker = field(default_factory=UnavailableBetTracker)
    measurements: MeasurementReader = field(default_factory=UnavailableMeasurementReader)

    def stage(self, stage: SpineStage) -> object:
        """Return the wired object for a stage."""
        return getattr(self, _SPINE_ATTRS[stage])


_SPINE_ATTRS: dict[SpineStage, str] = {
    SpineStage.CANDIDATE: "extractor",
    SpineStage.OUTCOME: "acceptor",
    SpineStage.SCORE: "sampler",
    SpineStage.BRIEF: "brief",
    SpineStage.DECISION: "decisions",
    SpineStage.BET: "bets",
    SpineStage.MEASURE: "measurements",
}


def default_spine() -> Spine:
    """A spine whose every stage is an honest stub."""
    return Spine()


# --------------------------------------------------------------------------- #
# Capability inventory — so any surface can say "nothing yet"
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SeamStatus:
    """Whether a seam is implemented, and who owns it until it is."""

    id: str
    owner: SeamOwner
    available: bool


def _is_available(obj: object | None) -> bool:
    """A seam is available when something was wired and it is not a stub."""
    return obj is not None and not isinstance(obj, _UNAVAILABLE_TYPES)


def seam_status(seam_id: str, obj: object | None) -> SeamStatus:
    return SeamStatus(id=seam_id, owner=SEAM_OWNERS[seam_id], available=_is_available(obj))


def seam_inventory(
    spine: Spine | None = None,
    *,
    demo: DemoLoader | None = None,
    templates: TemplateEngine | None = None,
) -> list[SeamStatus]:
    """The status of every seam, pipeline stages first.

    ``demo`` and ``templates`` are optional: a caller that never loads a demo or
    applies a template should not have to construct one, and the honest default
    for an unwired seam is "not available".
    """
    spine = spine or default_spine()
    statuses = [seam_status(stage.value, spine.stage(stage)) for stage in SPINE_ORDER]
    statuses.append(seam_status(DEMO_SEAM, demo))
    statuses.append(seam_status(TEMPLATE_SEAM, templates))
    return statuses


def missing_stages(
    spine: Spine | None = None,
    *,
    demo: DemoLoader | None = None,
    templates: TemplateEngine | None = None,
) -> list[str]:
    """The ids of the seams that are not implemented yet."""
    inventory = seam_inventory(spine, demo=demo, templates=templates)
    return [status.id for status in inventory if not status.available]


def spine_summary(
    spine: Spine | None = None,
    *,
    demo: DemoLoader | None = None,
    templates: TemplateEngine | None = None,
) -> str:
    """An honest, human-readable rendering of what the spine can and cannot do.

    Says "nothing yet" in words and names each gap by its owning issue. It never
    prints a number, because there is no number to print.
    """
    inventory = seam_inventory(spine, demo=demo, templates=templates)
    pipeline = [status for status in inventory if status.id in {s.value for s in SPINE_ORDER}]
    available = [status for status in pipeline if status.available]
    lines = [
        f"The ODI spine has {len(pipeline)} stages. "
        f"{len(available)} of {len(pipeline)} are implemented in this build.",
        "",
    ]
    for status in pipeline:
        if status.available:
            lines.append(f"- {status.id}: available")
        else:
            lines.append(
                f"- {status.id}: not implemented yet — {status.owner.issue} ({status.owner.title})"
            )
    lines.append("")
    lines.append(
        "Nothing has been fabricated to fill a gap; each stage above is "
        "implemented by its named issue."
    )
    return "\n".join(lines)


__all__ = [
    "Bet",
    "BetTracker",
    "BriefDocument",
    "BriefFigure",
    "BriefRenderer",
    "CandidateExtractor",
    "CandidateOutcome",
    "Decision",
    "DecisionRecorder",
    "DemoLoader",
    "DemoWorkspace",
    "DEMO_SEAM",
    "Measurement",
    "MeasurementReader",
    "SEAM_OWNERS",
    "SPINE_ORDER",
    "ScoreSample",
    "ScoreSampler",
    "SeamOwner",
    "SeamStatus",
    "Spine",
    "SpineStage",
    "StageNotImplemented",
    "TEMPLATE_SEAM",
    "TemplateEngine",
    "UnavailableBetTracker",
    "UnavailableBriefRenderer",
    "UnavailableCandidateExtractor",
    "UnavailableDecisionRecorder",
    "UnavailableDemoLoader",
    "UnavailableMeasurementReader",
    "UnavailableOutcomeAcceptor",
    "UnavailableScoreSampler",
    "UnavailableTemplateEngine",
    "default_spine",
    "missing_stages",
    "seam_inventory",
    "seam_status",
    "spine_summary",
]
