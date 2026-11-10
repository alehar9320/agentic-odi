"""Render the factual review case for a job.

``render_brief`` is a **pure** function of its inputs: no repository access, no
provider call, no fetching, and no writes. Every numeral in the output is
interpolated from an input object, so a number nobody measured cannot appear —
a missing measurement renders an explicit reason, never a zero.

The argumentative sections (``C1.2``) derive from the same input objects, so
they inherit the numeral guarantee with no extra mechanism.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol, runtime_checkable

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
class NarrativeClaim:
    """One drafted sentence and the outcomes it rests on (M3-04/ALH-90).

    ``outcome_ids`` is mandatory and non-empty for a surviving ``supported`` or
    ``recommendation`` claim: a claim with nothing behind it is dropped, not
    printed. ``None`` never appears here — an unlinked claim never becomes one.
    """

    claim: str
    outcome_ids: tuple[str, ...]


@dataclass(frozen=True)
class DraftedClaim:
    """A raw sentence a narrator proposed, with the outcomes it says it rests on."""

    claim: str
    outcome_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class NarrativeDraft:
    """A narrator's raw proposal, before any check (M3-04/ALH-90)."""

    supported: tuple[DraftedClaim, ...] = ()
    recommendation: tuple[DraftedClaim, ...] = ()
    risks: tuple[DraftedClaim, ...] = ()


@dataclass(frozen=True)
class DroppedSentence:
    """A drafted sentence that failed validation, with the reason it was dropped."""

    sentence: str
    reason: str


@dataclass(frozen=True)
class Narrative:
    """The drafted argument, checked against the factual brief (M3-04/ALH-90).

    Every field is prose a model wrote and the checker let through, or is empty.
    The ``dropped`` list travels with it so the brief can state what was removed
    and why: a visible omission, never a silent one. The renderer labels the
    whole block, so no caller can print an unlabelled drafted claim.
    """

    supported: str = ""
    recommendation: str = ""
    risks: str = ""
    claim_links: tuple[NarrativeClaim, ...] = ()
    dropped: tuple[DroppedSentence, ...] = ()

    @property
    def is_empty(self) -> bool:
        """True when nothing survived: there is no drafted text to show."""
        return not (self.supported or self.recommendation or self.risks)


class NarratorError(RuntimeError):
    """Raised by a narrator that cannot produce a draft (timeout, provider error).

    ``render_narrative`` catches it and returns an empty narrative that records
    the failure as a drop reason, so a provider outage degrades to the factual
    brief rather than failing the export.
    """


@runtime_checkable
class Narrator(Protocol):
    """A source of drafted prose. The only seam a model is ever reached through.

    ``render_narrative`` is the sole caller. The protocol keeps the guarantee
    testable without a model: a fixture narrator is a narrator.
    """

    def draft(self, brief: BriefInput) -> NarrativeDraft: ...


#: The one label that marks machine-drafted text. It lives in the core renderer,
#: never in a client, so no caller can print an unlabelled drafted claim.
DRAFTED_LABEL = "Drafted — numbers from the table above"

#: A numeral, an optional sign, optional thousands separators, optional decimals
#: and an optional percent. The lookbehind stops ``out-1`` matching ``-1``.
_NUMERAL_RE = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?%?")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}")


def _normalize_numeral(raw: str) -> str:
    """Canonicalise a numeral so ``15``, ``15.0`` and ``1,500`` compare equal.

    Sign, thousands separators and a trailing percent are stripped; an integral
    value loses its ``.0``. A token that is not a number is returned as-is.
    """
    text = raw.strip().rstrip("%").replace(",", "")
    if text.startswith("+"):
        text = text[1:]
    try:
        value = float(text)
    except ValueError:
        return text
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def _numerals(text: str) -> set[str]:
    """Every numeral token in ``text``, normalised and date-aware.

    A ``YYYY-MM-DD`` date is kept as one token, so its parts are never confused
    with the numbers around it. A digit that is the tail of a hyphenated
    identifier — the ``1`` in ``out-1`` — is skipped: it labels a record, it is
    not a measurement. Everything else is normalised through
    :func:`_normalize_numeral`.
    """
    dates = [(m.start(), m.end()) for m in _DATE_RE.finditer(text)]
    tokens: set[str] = {m.group(0) for m in _DATE_RE.finditer(text)}

    def inside_date(index: int) -> bool:
        return any(start <= index < end for start, end in dates)

    def identifier_tail(index: int) -> bool:
        # ``out-1`` / ``job-2``: a hyphen preceded by a letter marks an
        # identifier, so its trailing digits are a label, not a number. A digit
        # before the hyphen (``15-20``) is a range, whose ends are both numbers.
        return index >= 2 and text[index - 1] == "-" and text[index - 2].isalpha()

    for match in _NUMERAL_RE.finditer(text):
        if inside_date(match.start()) or identifier_tail(match.start()):
            continue
        tokens.add(_normalize_numeral(match.group(0)))
    return tokens


def _outcome_text(outcome: BriefOutcome) -> str:
    """Every numeral-bearing field of one outcome, joined for extraction."""
    parts = [
        outcome.statement,
        outcome.method or "",
        outcome.quote or "",
        outcome.value_source or "",
        *outcome.sources,
    ]
    if outcome.score is not None:
        parts.append(f"{outcome.score:g}")
    if outcome.n is not None:
        parts.append(str(outcome.n))
    if outcome.value_estimate is not None:
        parts.append(f"{outcome.value_estimate:g}")
    if outcome.value_n is not None:
        parts.append(str(outcome.value_n))
    return " ".join(parts)


def _outcome_numerals(outcome: BriefOutcome) -> set[str]:
    """The numerals a claim about this outcome may legitimately use."""
    return _numerals(_outcome_text(outcome))


def _brief_numerals(brief: BriefInput) -> set[str]:
    """Every numeral the brief legitimately carries, computed from its inputs.

    Deliberately built from the input objects rather than the rendered markdown:
    the markdown contains outcome ids like ``out-1``, whose digits are labels,
    not measurements, and must never license a drafted number. This set is the
    membership the no-fabrication guarantee checks against.
    """
    parts = [brief.job_name, brief.decision_consideration or ""]
    parts.extend(brief.holes)
    if brief.strategy is not None:
        parts.extend([brief.strategy.rationale, brief.strategy.expected_effect])
    parts.extend(_outcome_text(outcome) for outcome in brief.outcomes)
    return _numerals(" ".join(parts))


def _validate_claim(
    claim: DraftedClaim,
    *,
    require_link: bool,
    allowed: set[str],
    per_outcome: dict[str, set[str]],
    global_numerals: set[str],
    known_outcomes: set[str],
) -> tuple[NarrativeClaim | None, DroppedSentence | None]:
    """Check one drafted sentence. Return the surviving claim or the drop reason.

    Three checks, in order, each with a named reason:

    1. a ``supported``/``recommendation`` claim links at least one outcome;
    2. every linked outcome exists in this brief;
    3. every numeral is in the brief *and* is sourced to a linked outcome (or a
       brief-level number such as the evidence count).

    The third check is what a token-set check misses: ``12.5`` exists in the
    brief, but if it belongs to another outcome it is the wrong number for the
    claim and the sentence is dropped.
    """
    links = tuple(claim.outcome_ids)
    if require_link and not links:
        return None, DroppedSentence(claim.claim, "claim is not linked to any outcome")
    unknown = [outcome_id for outcome_id in links if outcome_id not in known_outcomes]
    if unknown:
        return None, DroppedSentence(
            claim.claim,
            "claim links an outcome that is not in this brief: " + ", ".join(unknown),
        )
    linked_numerals: set[str] = set()
    for outcome_id in links:
        linked_numerals |= per_outcome.get(outcome_id, set())
    for token in sorted(_numerals(claim.claim)):
        if token not in allowed:
            return None, DroppedSentence(claim.claim, f"numeral {token} is not in the brief")
        if links and token not in linked_numerals and token not in global_numerals:
            return None, DroppedSentence(
                claim.claim,
                f"numeral {token} is not sourced to the linked outcome(s)",
            )
    return NarrativeClaim(claim.claim, links), None


def render_narrative(brief: BriefInput, narrator: Narrator) -> Narrative:
    """Draft the brief's argument, then keep only what the numbers support.

    The guarantee is mechanical, not a prompt instruction: every numeral in a
    surviving sentence is extracted and asserted to exist in the brief, and to
    be sourced to an outcome the claim links. A failing sentence is **dropped**
    with a recorded reason; there is no retry, so the result is deterministic
    for a fixed draft. A narrator that raises :class:`NarratorError` yields an
    empty narrative whose drop list names the failure. Nothing is written and no
    repository is read: ``brief`` is the whole input.
    """
    factual = replace(brief, narrative=None)
    allowed = _brief_numerals(factual)
    per_outcome = {outcome.outcome_id: _outcome_numerals(outcome) for outcome in brief.outcomes}
    known_outcomes = set(per_outcome)
    attributed: set[str] = set()
    for tokens in per_outcome.values():
        attributed |= tokens
    global_numerals = allowed - attributed

    try:
        draft = narrator.draft(brief)
    except NarratorError as error:
        return Narrative(dropped=(DroppedSentence("", f"narrator failed: {error}"),))

    surviving: dict[str, list[NarrativeClaim]] = {
        "supported": [],
        "recommendation": [],
        "risks": [],
    }
    dropped: list[DroppedSentence] = []
    for section, require_link in (
        ("supported", True),
        ("recommendation", True),
        ("risks", False),
    ):
        for claim in getattr(draft, section):
            kept, reason = _validate_claim(
                claim,
                require_link=require_link,
                allowed=allowed,
                per_outcome=per_outcome,
                global_numerals=global_numerals,
                known_outcomes=known_outcomes,
            )
            if kept is not None:
                surviving[section].append(kept)
            elif reason is not None:
                dropped.append(reason)

    claim_links = tuple(
        claim
        for section in ("supported", "recommendation", "risks")
        for claim in surviving[section]
    )
    return Narrative(
        supported=" ".join(claim.claim for claim in surviving["supported"]),
        recommendation=" ".join(claim.claim for claim in surviving["recommendation"]),
        risks=" ".join(claim.claim for claim in surviving["risks"]),
        claim_links=claim_links,
        dropped=tuple(dropped),
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
    #: The drafted, checked argument (M3-04). ``None`` — the default — renders no
    #: drafted block at all, so every existing caller and golden file is
    #: byte-identical. When present the block is labelled by this renderer.
    narrative: Narrative | None = None


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


def _render_narrative(narrative: Narrative | None) -> list[str]:
    """The drafted argument, always labelled and always linked (M3-04/ALH-90).

    Rendered only when a narrative is supplied *and* it has something to say:
    surviving prose, or a dropped sentence to explain. The block is headed by
    :data:`DRAFTED_LABEL`, so a reader always knows which part a model wrote,
    and every drafted line carries the outcome ids it rests on. Dropped
    sentences are listed with their reasons in the same block — so a draft that
    survives nothing still shows *why* it is empty, never a silent omission.
    With no narrative, or one that is empty and dropped nothing, nothing is
    rendered: the factual brief is unchanged.
    """
    if narrative is None or (narrative.is_empty and not narrative.dropped):
        return []
    lines = [f"## {DRAFTED_LABEL}", ""]
    for heading, text in (
        ("What the evidence supports", narrative.supported),
        ("What we should do", narrative.recommendation),
        ("Risks and unknowns", narrative.risks),
    ):
        if not text:
            continue
        lines.append(f"**{heading}**")
        lines.append("")
        lines.append(_escape(text))
        lines.append("")
    if narrative.claim_links:
        lines.append("Claim links:")
        lines.append("")
        for claim in narrative.claim_links:
            lines.append(f"- {_escape(claim.claim)} → {', '.join(claim.outcome_ids)}")
        lines.append("")
    if narrative.dropped:
        lines.append("_Dropped, with the reason:_")
        lines.append("")
        for drop in narrative.dropped:
            sentence = f"“{_escape(drop.sentence)}” — " if drop.sentence else ""
            lines.append(f"- {sentence}{_escape(drop.reason)}")
        lines.append("")
    return lines


def render_narrative_block(narrative: Narrative | None) -> str:
    """The drafted block as a standalone fragment, or ``""`` when there is none.

    The one public seam onto :func:`_render_narrative`, so an exporter that
    composes its own document (the memo export, M3-11.2/ALH-171) cannot print an
    unlabelled drafted claim or invent a second label string. Returns markdown
    ending in a newline, or the empty string when nothing should be shown.
    """
    lines = _render_narrative(narrative)
    if not lines:
        return ""
    return "\n".join(lines).rstrip("\n") + "\n"


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
    lines.extend(_render_narrative(brief.narrative))
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
