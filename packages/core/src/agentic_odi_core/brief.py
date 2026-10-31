"""Render the factual review case for a job.

``render_brief`` is a **pure** function of its inputs: no repository access, no
provider call, no fetching, and no writes. Every numeral in the output is
interpolated from an input object, so a number nobody measured cannot appear —
a missing measurement renders an explicit reason, never a zero.

The argumentative sections (``C1.2``) derive from the same input objects, so
they inherit the numeral guarantee with no extra mechanism.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from agentic_odi_core.evaluation import classify_opportunity, classify_value

#: A section with nothing to show is omitted and explained in one line. It is
#: never filled with placeholder prose and never rendered as a zero.
NOT_MEASURED = "not measured"


@dataclass(frozen=True)
class BriefOutcome:
    """One outcome as the brief must show it, with its provenance supplied.

    Every field is an input: the renderer never recomputes a score or invents a
    sample size. ``None`` means the measurement was not supplied and must be
    shown as such.
    """

    outcome_id: str
    statement: str
    score: float | None = None
    n: int | None = None
    method: str | None = None
    quote: str | None = None
    sources: tuple[str, ...] = ()
    #: The recorded value judgement and its basis (W1/ALH-64). ``None`` is an
    #: ``unsized`` outcome: the brief omits the section rather than print a zero.
    value_estimate: float | None = None
    value_unit: str | None = None
    value_basis: str = "estimate"
    value_n: int | None = None
    value_source: str | None = None

    @property
    def band(self) -> str | None:
        """The served/underserved bucket, or ``None`` when unscored."""
        return classify_opportunity(self.score)

    @property
    def value_size(self) -> str:
        """How defensible the value estimate is: ``sized``, ``thin``, ``unsized``."""
        return classify_value(self)


@dataclass(frozen=True)
class BriefStrategy:
    """A recorded strategy, supplied to the brief (D4/ALH-43).

    Every field is an input: the renderer never looks up a strategy, so the
    brief stays a pure function of what the caller hands it. ``kind`` is a
    string rather than the enum so ``brief.py`` keeps no dependency on the
    service layer's model.
    """

    kind: str
    rationale: str
    expected_effect: str
    segment_name: str


@dataclass(frozen=True)
class BriefSegment:
    """A segment as the brief selector needs it (D4/ALH-43).

    Supplied, never looked up: the selector is a pure function of its inputs.
    """

    segment_id: str
    name: str
    outcome_ids: tuple[str, ...]


@dataclass(frozen=True)
class BriefStrategyRecord:
    """One recorded strategy, before selection (D4/ALH-43)."""

    strategy_id: str
    segment_id: str
    chosen_at: str
    kind: str
    rationale: str
    expected_effect: str


def select_brief_strategy(
    chosen_outcome_ids: Sequence[str],
    segments: Sequence[BriefSegment],
    strategies: Sequence[BriefStrategyRecord],
) -> BriefStrategy | None:
    """The one strategy the brief should show, or ``None``.

    The segment a decision is *about* is one whose membership overlaps the
    decision's chosen outcomes; its latest strategy (by ``chosen_at``, then id)
    is the candidate. Across several overlapping segments the latest candidate
    wins, so the choice is deterministic and matches the service's derivation.
    Pure: no repository access, so the CLI and the service cannot drift.
    """
    chosen = set(chosen_outcome_ids)
    latest_by_segment: dict[str, BriefStrategyRecord] = {}
    for record in strategies:
        current = latest_by_segment.get(record.segment_id)
        if current is None or (record.chosen_at, record.strategy_id) > (
            current.chosen_at,
            current.strategy_id,
        ):
            latest_by_segment[record.segment_id] = record

    best: BriefStrategyRecord | None = None
    for segment in segments:
        if not chosen.intersection(segment.outcome_ids):
            continue
        candidate = latest_by_segment.get(segment.segment_id)
        if candidate is None:
            continue
        if best is None or (candidate.chosen_at, candidate.strategy_id) > (
            best.chosen_at,
            best.strategy_id,
        ):
            best = candidate
    if best is None:
        return None
    name = next(
        (segment.name for segment in segments if segment.segment_id == best.segment_id),
        best.segment_id,
    )
    return BriefStrategy(
        kind=best.kind,
        rationale=best.rationale,
        expected_effect=best.expected_effect,
        segment_name=name,
    )


@dataclass(frozen=True)
class BriefInput:
    """Everything the brief renders, supplied by the caller."""

    job_id: str
    job_name: str
    generated_at: str
    outcomes: tuple[BriefOutcome, ...] = ()
    decision_consideration: str | None = None
    evidence_count: int = 0
    holes: tuple[str, ...] = field(default_factory=tuple)
    #: The recorded strategy for the decision's segment, when there is one. The
    #: brief renders it; it never fetches it.
    strategy: BriefStrategy | None = None


def _escape(text: str) -> str:
    """Escape HTML-significant characters in user-supplied text.

    Quotes, statements, and source labels are text, not markup: a ``<script>``
    inside a quote must render as characters, not execute.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_score(score: float | None) -> str:
    """Render a score compactly so ``15.0`` reads as ``15`` and ``12.5`` stays."""
    if score is None:
        return NOT_MEASURED
    return f"{score:g}"


def select_underserved(outcomes: Sequence[BriefOutcome], limit: int = 3) -> list[BriefOutcome]:
    """Return the highest-scoring measured outcomes, most underserved first.

    Only scored outcomes are eligible: an unscored outcome is unknown, not low.
    Ties keep their input order, so a permutation that does not change the
    ranking cannot change the bytes.
    """
    scored = [
        (index, outcome) for index, outcome in enumerate(outcomes) if outcome.score is not None
    ]
    scored.sort(key=lambda pair: (-(pair[1].score or 0.0), pair[0]))
    return [outcome for _, outcome in scored[:limit]]


def _render_outcome(outcome: BriefOutcome, position: int) -> list[str]:
    lines: list[str] = []
    lines.append(f"### {position}. {_escape(outcome.statement)}")
    lines.append("")
    if outcome.score is None:
        lines.append(f"- Score: {NOT_MEASURED}")
    else:
        band = outcome.band or NOT_MEASURED
        lines.append(f"- Score: {_fmt_score(outcome.score)} ({band})")
    lines.append(f"- Sample: {outcome.n if outcome.n is not None else NOT_MEASURED}")
    if outcome.method:
        lines.append(f"- Method: {_escape(outcome.method)}")
    if outcome.quote:
        lines.append(f"- Quote: “{_escape(outcome.quote)}”")
    if outcome.sources:
        lines.append(f"- Sources: {', '.join(_escape(source) for source in outcome.sources)}")
    lines.append("")
    return lines


def _render_supported(selected: list[BriefOutcome]) -> list[str]:
    """*What the evidence supports* — a claim per selected outcome, each naming
    the outcome id it rests on. Derived only from the supplied outcomes."""
    lines = ["## What the evidence supports", ""]
    if not selected:
        lines.append("_No measured outcomes yet — the evidence supports no claim._")
        lines.append("")
        return lines
    for outcome in selected:
        band = outcome.band or NOT_MEASURED
        lines.append(
            f"- `{outcome.outcome_id}` is {band} "
            f"(score {_fmt_score(outcome.score)}) — {_escape(outcome.statement)}"
        )
    lines.append("")
    return lines


def _render_build(selected: list[BriefOutcome]) -> list[str]:
    """*What we would build* — names the outcome with the lowest score.

    Open product decision (ALH-157): the spec says the *lowest* score, which
    may conflict with the highest-underserved ranking the rest of ODI uses.
    This is implemented literally and must not be silently reversed; the
    conflict is recorded rather than resolved here.
    """
    lines = ["## What we would build", ""]
    if not selected:
        lines.append("_No measured outcomes yet — there is nothing to build toward._")
        lines.append("")
        return lines
    if len(selected) == 1:
        only = selected[0]
        lines.append(
            f"- Build toward `{only.outcome_id}` (score {_fmt_score(only.score)}) — "
            f"{_escape(only.statement)}"
        )
        lines.append(
            "_Only one measured outcome is available, so no comparison drove this choice._"
        )
        lines.append("")
        return lines
    # Lowest score, ties by input order (the selection already preserves order).
    lowest = min(selected, key=lambda o: o.score if o.score is not None else float("inf"))
    lines.append(
        f"- Build toward `{lowest.outcome_id}` (lowest score {_fmt_score(lowest.score)}) — "
        f"{_escape(lowest.statement)}"
    )
    lines.append("")
    return lines


def _render_risks(holes: Sequence[str]) -> list[str]:
    """*Risks and unknowns* — names the supplied holes, or says so in one line.

    No recorded holes is **not** proof of no risk, so the empty case states that
    explicitly instead of omitting the section.
    """
    lines = ["## Risks and unknowns", ""]
    if holes:
        lines.extend(f"- {_escape(hole)}" for hole in holes)
    else:
        lines.append("_No recorded holes — this is not proof that no risk remains._")
    lines.append("")
    return lines


def _render_value(selected: list[BriefOutcome]) -> list[str]:
    """*What it is worth* — the value estimate with its unit and its basis.

    Only the selected outcomes that have an estimate appear. An outcome with no
    estimate is ``unsized`` and contributes nothing: no zero, no placeholder. When
    no selected outcome is sized the section is **omitted** and replaced by the
    one-line note C1 uses elsewhere, so the brief never implies a worth it cannot
    source.
    """
    sized = [outcome for outcome in selected if outcome.value_estimate is not None]
    if not sized:
        return [
            "_No value estimate recorded for the selected outcomes yet — "
            "worth is unknown, not zero._",
            "",
        ]
    lines = ["## What it is worth", ""]
    for outcome in sized:
        unit = outcome.value_unit or NOT_MEASURED
        basis = outcome.value_basis
        size = outcome.value_size
        detail = f"- `{outcome.outcome_id}`: {_fmt_value(outcome.value_estimate)} {unit} "
        detail += f"({basis}, {size})"
        if outcome.value_source:
            detail += f" — source: {_escape(outcome.value_source)}"
        if outcome.value_n is not None:
            detail += f" — n={outcome.value_n}"
        lines.append(detail)
    unsized = len(selected) - len(sized)
    if unsized:
        lines.append(
            f"_{unsized} selected outcome(s) have no value estimate and were omitted — "
            "an unsized outcome is unknown, not zero._"
        )
    lines.append("")
    return lines


def _fmt_value(value: float | None) -> str:
    if value is None:
        return NOT_MEASURED
    return f"{value:g}"


def _render_strategy(strategy: BriefStrategy | None) -> list[str]:
    """*The strategy* — the recorded choice, its reason, and its expected effect.

    Rendered only when a strategy is supplied. With none, the section is omitted
    (not filled with a placeholder): "no strategy recorded" is the honest state,
    and a slogan is worse than silence.
    """
    if strategy is None:
        return []
    lines = ["## The strategy", ""]
    lines.append(f"- Kind: {_escape(strategy.kind)}")
    lines.append(f"- Segment: {_escape(strategy.segment_name)}")
    lines.append(f"- Why: {_escape(strategy.rationale)}")
    lines.append(f"- Expected effect: {_escape(strategy.expected_effect)}")
    lines.append("")
    return lines


def render_brief(brief: BriefInput) -> str:
    """Render the factual review case as markdown.

    Deterministic: the same input yields identical bytes.
    """
    lines: list[str] = [f"# Brief: {_escape(brief.job_name)}", ""]

    lines.append("## The job")
    lines.append("")
    lines.append(f"- Job ID: {_escape(brief.job_id)}")
    lines.append(f"- Evidence records: {brief.evidence_count}")
    lines.append(f"- Generated: {_escape(brief.generated_at)}")
    lines.append("")

    lines.append("## The decision we are considering")
    lines.append("")
    if brief.decision_consideration:
        lines.append(_escape(brief.decision_consideration))
    else:
        lines.append("_No decision consideration recorded yet._")
    lines.append("")

    lines.append("## Underserved outcomes")
    lines.append("")
    selected = select_underserved(brief.outcomes)
    if selected:
        for position, outcome in enumerate(selected, start=1):
            lines.extend(_render_outcome(outcome, position))
        unscored = len(brief.outcomes) - len([o for o in brief.outcomes if o.score is not None])
        if unscored:
            lines.append(
                f"_{unscored} outcome(s) had no score and were excluded — "
                "an unscored outcome is unknown, not low._"
            )
            lines.append("")
    else:
        lines.append("_No scored outcomes yet — nothing to show here._")
        lines.append("")

    lines.extend(_render_supported(selected))
    lines.extend(_render_build(selected))
    lines.extend(_render_value(selected))
    lines.extend(_render_strategy(brief.strategy))
    lines.extend(_render_risks(brief.holes))

    lines.append("## Sources")
    lines.append("")
    seen: list[str] = []
    for outcome in selected:
        for source in outcome.sources:
            if source not in seen:
                seen.append(source)
    if seen:
        lines.extend(f"- {_escape(source)}" for source in seen)
    else:
        lines.append("_No sources recorded for the selected outcomes yet._")
    lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"
