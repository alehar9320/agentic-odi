"""Assemble the decision memo from what is already recorded (M3-11/ALH-97).

One page a product leader can sign: the decision, why now, the evidence with its
citations, the options we rejected and why, what the chosen outcome is worth,
how we will know it worked, and what we still do not know — every number copied
from a record, never derived.

Readiness choices pinned here (recorded in ``test_memo.py``):

* **Assembly is deterministic and reads nothing.** ``build_memo`` takes the
  records; it does not open a store, invoke a provider, or read a clock. "Why
  now" is derived from the decision's own ``decided_at``, so it is reproducible.
* **A missing section is omitted with a one-line reason**, the rule ``C1``
  established. *What it is worth* says "no value estimate recorded" and renders
  no zero; *How we will know* says which success-condition input is missing.
* **The memo is generated on read and never stored.** A stale stored memo would
  be worse than none, so there is no memo entity and no memo event.
* **An unknown decision raises**, so "no such decision" is never confused with
  an empty memo.
* **The framing sentence is not this increment's job.** ``M3-04`` narrates; the
  memo is the deterministic facts a narrator may later frame.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from agentic_odi_core.brief import (
    NOT_MEASURED,
    BriefInput,
    BriefOutcome,
    Narrative,
    render_narrative_block,
)
from agentic_odi_core.errors import NotFoundError, ValidationError
from agentic_odi_core.evaluation import classify_opportunity, classify_value
from agentic_odi_core.models import Bet, Decision, Evidence, Outcome

#: The one-line reason a section is omitted, matching ``C1``'s rule: never
#: placeholder prose, never a zero.
NO_VALUE_NOTE = "_No value estimate recorded for the chosen outcome — worth is unknown, not zero._"
NO_CRITERIA_NOTE = "_No success criteria recorded — we have not said how we will know it worked._"
NO_HOLES_NOTE = "_No recorded holes — this is not proof that no risk remains._"


@runtime_checkable
class MemoCriterion(Protocol):
    """The success-criterion attributes the memo reads, and nothing else.

    Success criteria are a later enrichment (``M2-08``); until they have a model,
    the memo reads only the one attribute it needs so any record with a
    ``statement`` can supply them.
    """

    statement: str


@dataclass(frozen=True)
class MemoClaim:
    """A chosen outcome and the measurements the memo attributes to it.

    ``sources`` are the evidence records linked to *this* outcome, so a claim's
    citation travels with the claim instead of appearing in a detached list.
    """

    outcome_id: str
    statement: str | None
    score: float | None
    band: str | None
    n: int | None
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoRejection:
    """A rejected option: its statement when it still resolves, and the reason."""

    outcome_id: str
    statement: str | None
    reason: str


@dataclass(frozen=True)
class MemoBet:
    """The bet that answers "how we will know": its hypothesis, target and date."""

    hypothesis: str
    target: float
    measure_by: str


@dataclass(frozen=True)
class Memo:
    """The assembled memo. Every field is copied from a record, or is empty."""

    decision_id: str
    job_id: str
    decided_at: str
    decided_by: str
    rationale: str
    confidence: str
    superseded_by: str | None
    superseded_at: str | None
    why_now: str
    chosen: tuple[MemoClaim, ...] = ()
    rejected: tuple[MemoRejection, ...] = ()
    sources: tuple[str, ...] = ()
    value_outcome_id: str | None = None
    value_estimate: float | None = None
    value_unit: str | None = None
    value_basis: str = "estimate"
    value_n: int | None = None
    value_source: str | None = None
    criteria: tuple[str, ...] = ()
    bet: MemoBet | None = None
    holes: tuple[str, ...] = field(default_factory=tuple)


class MemoDecisionNotFoundError(NotFoundError):
    """The requested decision does not exist. Never confused with an empty memo.

    A :class:`NotFoundError` so the CLI, MCP and Studio all map it to a 404,
    rather than letting a lookup failure surface as a server error.
    """

    def __init__(self, decision_id: str) -> None:
        self.decision_id = decision_id
        super().__init__(decision_id, "Decision")


#: The hard word budgets for the stakeholder message (M3-12/ALH-98). A message
#: is read on a phone; the memo stays the record.
SLACK_WORD_BUDGET = 120
EMAIL_WORD_BUDGET = 200
CHANNEL_BUDGETS: dict[str, int] = {"slack": SLACK_WORD_BUDGET, "email": EMAIL_WORD_BUDGET}

#: Sentence kinds in the order they are *written*, and the order they are
#: *included* under budget pressure. ``unknown`` and a supplied ``link`` are
#: mandatory — they are included first and a message that cannot fit them fails
#: loudly rather than silently dropping the caveat. The optional sentences are
#: dropped lowest-priority first: action, then finding, then value (a value with
#: its basis is the number a stakeholder is most likely to act on).
_MESSAGE_WRITE_ORDER = ("finding", "action", "value", "unknown", "link")
_MESSAGE_INCLUDE_ORDER = ("link", "unknown", "value", "finding", "action")
_MANDATORY_SENTENCES = frozenset({"unknown", "link"})


class MessageBudgetError(ValidationError):
    """A mandatory sentence does not fit the channel's word budget.

    Raised instead of truncating a source, dropping the caveat, or pretending a
    too-long message is fine. The caller shortens the input or uses the memo.
    """

    def __init__(self, channel: str, budget: int, required: int) -> None:
        self.channel = channel
        self.budget = budget
        self.required = required
        super().__init__(
            f"The {channel} message needs {required} words for its caveat and link, "
            f"over the {budget}-word budget. Shorten the input or send the memo."
        )


@dataclass(frozen=True)
class StakeholderMessage:
    """A short, pasteable message: the same facts as the memo, cut to a budget.

    ``subject`` is set only for ``email``. ``dropped`` names the sentence kinds
    removed to fit the budget, so a caller can report them under ``--verbose``;
    they never appear in the pasteable body.
    """

    channel: str
    body: str
    word_count: int
    subject: str | None = None
    dropped: tuple[str, ...] = ()
    link: str | None = None


def _message_subject(memo: Memo) -> str:
    """The email subject: what was decided, then the promise of evidence.

    Derived from the decision's own chosen statement, never invented; with no
    statement it falls back to a fixed phrase rather than a fabricated headline.
    """
    what = next(
        (claim.statement for claim in memo.chosen if claim.statement),
        "a recorded choice",
    )
    return f"Decision: {_escape(what)} — here is the evidence"


def _message_sentences(memo: Memo, *, link: str | None) -> dict[str, str]:
    """One sentence per kind, from the memo. A kind with nothing to say is absent."""
    sentences: dict[str, str] = {}

    finding = next((claim for claim in memo.chosen if claim.statement), None)
    if finding is not None and finding.statement is not None:
        score = (
            f"opportunity {_fmt(finding.score)} ({finding.band or NOT_MEASURED}"
            f"{', n=' + str(finding.n) if finding.n is not None else ''})"
            if finding.score is not None
            else f"score {NOT_MEASURED}"
        )
        sentences["finding"] = f"We found an unmet need: {_escape(finding.statement)} ({score})."

    if memo.chosen:
        names = [claim.statement for claim in memo.chosen if claim.statement]
        chosen = "; ".join(_escape(name) for name in names) if names else "the recorded outcome"
        sentences["action"] = f"We are choosing: {chosen} because {_escape(memo.rationale)}"

    if memo.value_estimate is not None:
        unit = memo.value_unit or NOT_MEASURED
        value = (
            f"It is worth {_fmt(memo.value_estimate)} {unit} ({memo.value_basis}"
            f"{', source: ' + _escape(memo.value_source) if memo.value_source else ''})."
        )
    else:
        value = "Worth is not yet estimated."
    sentences["value"] = value

    if memo.holes:
        sentences["unknown"] = f"What we still do not know: {_escape(memo.holes[0])}."
    else:
        sentences["unknown"] = "We have not recorded what we still do not know."

    if link:
        sentences["link"] = f"Full memo: {link}"
    return sentences


def render_stakeholder_message(
    memo: Memo,
    *,
    channel: str = "slack",
    link: str | None = None,
) -> StakeholderMessage:
    """Cut the memo to a pasteable message within the channel's word budget.

    Deterministic assembly, no model: the same memo and link yield the same
    message. Sentences are included highest-priority first — the largest unknown
    and the memo link are mandatory, so a too-long message fails loudly instead
    of silently dropping its caveat. The lowest-priority sentences (action, then
    finding, then value) are dropped to fit and reported in ``dropped``.
    """
    if channel not in CHANNEL_BUDGETS:
        raise ValidationError(
            f"Unknown channel: {channel!r}. Use one of {sorted(CHANNEL_BUDGETS)}."
        )
    budget = CHANNEL_BUDGETS[channel]
    sentences = _message_sentences(memo, link=link)
    subject = _message_subject(memo) if channel == "email" else None

    def total(words: list[str]) -> int:
        count = sum(len(sentence.split()) for sentence in words)
        return count + (len(subject.split()) if subject else 0)

    included: list[str] = []
    included_kinds: list[str] = []
    dropped: list[str] = []
    for kind in _MESSAGE_INCLUDE_ORDER:
        sentence = sentences.get(kind)
        if sentence is None:
            continue
        if total([*included, sentence]) <= budget:
            included.append(sentence)
            included_kinds.append(kind)
        else:
            dropped.append(kind)

    provided_mandatory = _MANDATORY_SENTENCES & set(sentences)
    blocking = provided_mandatory & set(dropped)
    if blocking:
        raise MessageBudgetError(channel, budget, total([sentences[k] for k in blocking]))

    body = " ".join(sentences[kind] for kind in _MESSAGE_WRITE_ORDER if kind in included_kinds)
    return StakeholderMessage(
        channel=channel,
        body=body,
        word_count=total(included),
        subject=subject,
        dropped=tuple(dropped),
        link=link,
    )


def _escape(text: str) -> str:
    """Escape HTML-significant characters in recorded text.

    A rationale, a statement or a source label is text, not markup: a
    ``<script>`` inside one must render as characters, not execute.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt(value: float | None) -> str:
    """Render a measurement compactly; ``None`` is ``not measured``, never ``0``."""
    if value is None:
        return NOT_MEASURED
    return f"{value:g}"


def _as_text(value: object) -> str:
    """Render an enum by its value, a string as itself, anything else as text."""
    return str(getattr(value, "value", value))


def _why_now(decided_at: str) -> str:
    """The "why now" line, derived from the decision's own timestamp.

    No clock is read: the sentence restates when the decision was made, which is
    a fact the record already carries. ``decided_at`` may be a date or a
    timestamp; the date part is what a reader needs.
    """
    day = decided_at.split("T", 1)[0].split(" ", 1)[0]
    return f"This decision was recorded on {day}."


def _claim(outcome: Outcome, sources: tuple[str, ...]) -> MemoClaim:
    counts = [
        count for count in (outcome.importance_n, outcome.satisfaction_n) if count is not None
    ]
    return MemoClaim(
        outcome_id=outcome.id,
        statement=outcome.statement or None,
        score=outcome.opportunity_score,
        band=classify_opportunity(outcome.opportunity_score),
        n=max(counts) if counts else None,
        sources=sources,
    )


def build_memo(
    decision: Decision,
    *,
    outcomes: Sequence[Outcome],
    evidence: Sequence[Evidence],
    criteria: Sequence[MemoCriterion] = (),
    bets: Sequence[Bet] = (),
    holes: Sequence[str] = (),
    chosen_outcome_id: str | None = None,
) -> Memo:
    """Assemble the memo from the records. No store, no clock, no model.

    ``chosen_outcome_id`` pins which chosen outcome the value and criteria
    sections describe; when omitted the decision's first chosen outcome is used.
    """
    by_id = {outcome.id: outcome for outcome in outcomes}
    per_outcome_sources: dict[str, list[str]] = {}
    job_sources: list[str] = []
    for record in evidence:
        if record.name not in job_sources:
            job_sources.append(record.name)
        if record.outcome_id is not None:
            linked = per_outcome_sources.setdefault(record.outcome_id, [])
            if record.name not in linked:
                linked.append(record.name)

    chosen_ids = [str(outcome_id) for outcome_id in decision.chosen_outcome_ids]
    chosen = tuple(
        _claim(by_id[outcome_id], tuple(per_outcome_sources.get(outcome_id, ())))
        if outcome_id in by_id
        else MemoClaim(outcome_id=outcome_id, statement=None, score=None, band="unscored", n=None)
        for outcome_id in chosen_ids
    )

    value_outcome_id = chosen_outcome_id or (chosen_ids[0] if chosen_ids else None)
    value_outcome = by_id.get(value_outcome_id) if value_outcome_id else None

    bet = None
    for bet_record in bets:
        if bet_record.outcome_id == value_outcome_id:
            bet = MemoBet(
                hypothesis=bet_record.hypothesis,
                target=float(bet_record.target),
                measure_by=bet_record.measure_by,
            )
            break

    return Memo(
        decision_id=decision.id,
        job_id=decision.job_id,
        decided_at=decision.decided_at,
        decided_by=decision.decided_by,
        rationale=decision.rationale,
        confidence=_as_text(decision.confidence),
        superseded_by=decision.superseded_by,
        superseded_at=decision.superseded_at,
        why_now=_why_now(decision.decided_at),
        chosen=chosen,
        rejected=tuple(
            MemoRejection(
                outcome_id=record.outcome_id,
                statement=by_id[record.outcome_id].statement
                if record.outcome_id in by_id
                else None,
                reason=record.reason,
            )
            for record in decision.rejected
        ),
        sources=tuple(job_sources),
        value_outcome_id=value_outcome_id if value_outcome is not None else None,
        value_estimate=value_outcome.value_estimate if value_outcome else None,
        value_unit=value_outcome.value_unit if value_outcome else None,
        value_basis=_as_text(value_outcome.value_basis) if value_outcome else "estimate",
        value_n=value_outcome.value_n if value_outcome else None,
        value_source=value_outcome.value_source if value_outcome else None,
        criteria=tuple(criterion.statement for criterion in criteria),
        bet=bet,
        holes=tuple(str(hole) for hole in holes),
    )


def _render_claims(memo: Memo) -> list[str]:
    """*What the evidence says* — a claim per chosen outcome, each citing its sources."""
    lines = ["## What the evidence says", ""]
    if not memo.chosen:
        lines.append("_No chosen outcome recorded — the decision names nothing to justify._")
        lines.append("")
        return lines
    for claim in memo.chosen:
        label = f" — {_escape(claim.statement)}" if claim.statement else ""
        if claim.score is None:
            lines.append(f"- `{claim.outcome_id}`{label}: score {NOT_MEASURED}")
        else:
            band = claim.band or NOT_MEASURED
            lines.append(
                f"- `{claim.outcome_id}`{label}: score {_fmt(claim.score)} ({band}), "
                f"n={claim.n if claim.n is not None else NOT_MEASURED}"
            )
        if claim.sources:
            lines.append(f"  - Cited: {', '.join(_escape(source) for source in claim.sources)}")
        else:
            lines.append("  - Cited: _no evidence linked to this outcome yet_")
    lines.append("")
    return lines


def _render_value(memo: Memo) -> list[str]:
    """*What it is worth* — the recorded estimate, or the one-line reason it is absent."""
    lines = ["## What it is worth", ""]
    if memo.value_estimate is None:
        lines.append(NO_VALUE_NOTE)
        lines.append("")
        return lines
    unit = memo.value_unit or NOT_MEASURED
    size = classify_value(memo)
    detail = (
        f"- `{memo.value_outcome_id}`: {_fmt(memo.value_estimate)} {unit} "
        f"({memo.value_basis}, {size})"
    )
    if memo.value_source:
        detail += f" — source: {_escape(memo.value_source)}"
    if memo.value_n is not None:
        detail += f" — n={memo.value_n}"
    lines.append(detail)
    lines.append("")
    return lines


def render_memo(memo: Memo) -> str:
    """Render the memo as markdown. Deterministic: the same memo yields the same bytes.

    Every section is present only when it has something to say; a missing one is
    replaced by its one-line reason, never placeholder prose and never a zero.
    """

    lines: list[str] = [f"# Decision memo — `{memo.decision_id}`", ""]
    lines.append("## Decision")
    lines.append("")
    if memo.superseded_by:
        lines.append(
            f"_Superseded by `{memo.superseded_by}` on "
            f"{memo.superseded_at or NOT_MEASURED}. The argument below is the record, "
            "not the current choice._"
        )
        lines.append("")
    if memo.chosen:
        for claim in memo.chosen:
            label = f" — {_escape(claim.statement)}" if claim.statement else ""
            lines.append(f"- Chose `{claim.outcome_id}`{label}")
    else:
        lines.append("_No chosen outcome recorded._")
    lines.append(f"- Rationale: {_escape(memo.rationale)}")
    lines.append(
        f"- Decided by {_escape(memo.decided_by)} on {memo.decided_at} ({memo.confidence})"
    )
    lines.append("")

    lines.append("## Why now")
    lines.append("")
    lines.append(_escape(memo.why_now))
    lines.append("")

    lines.extend(_render_claims(memo))

    lines.append("## What we are not doing")
    lines.append("")
    if memo.rejected:
        for rejection in memo.rejected:
            label = f" — {_escape(rejection.statement)}" if rejection.statement else ""
            lines.append(f"- `{rejection.outcome_id}`{label}: {_escape(rejection.reason)}")
    else:
        lines.append("_No rejected options recorded._")
    lines.append("")

    lines.extend(_render_value(memo))

    lines.append("## How we will know")
    lines.append("")
    if memo.criteria:
        lines.extend(f"- {_escape(criterion)}" for criterion in memo.criteria)
    else:
        lines.append(NO_CRITERIA_NOTE)
    if memo.bet is not None:
        lines.append(
            f"- Bet: {_escape(memo.bet.hypothesis)} — target {_fmt(memo.bet.target)} "
            f"by {memo.bet.measure_by}"
        )
    else:
        lines.append(
            "_No bet recorded — no target or measure-by date, so success has no number yet._"
        )
    lines.append("")

    lines.append("## What we do not know")
    lines.append("")
    if memo.holes:
        lines.extend(f"- {_escape(hole)}" for hole in memo.holes)
    else:
        lines.append(NO_HOLES_NOTE)
    lines.append("")

    lines.append("## Sources")
    lines.append("")
    if memo.sources:
        lines.extend(f"- {_escape(source)}" for source in memo.sources)
    else:
        lines.append("_No sources recorded for this decision yet._")
    lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


# ------------------------------------------------------------ export (M3-11.2)


@dataclass(frozen=True)
class MemoNarrativeInput:
    """The memo's facts, shaped for the narrator's numeral guarantee (M3-11.2).

    The memo is a projection of records, not a :class:`BriefInput`, so a narrator
    that speaks :class:`~agentic_odi_core.brief.Narrator` needs the facts it
    checks numerals against. This is the one adapter between the two: the memo's
    chosen claims become brief outcomes (score, sample and sources travel with
    them), and the decision's rationale is the consideration. Nothing is
    recomputed — a field nobody supplied stays ``None``.
    """

    memo: Memo
    brief: BriefInput


def memo_narrative_input(memo: Memo) -> MemoNarrativeInput:
    """Project a :class:`Memo` into the :class:`BriefInput` a narrator checks against.

    Only the chosen outcomes are exposed: a drafted framing sentence is about the
    decision, so a numeral must trace to a chosen outcome or a memo-level fact
    (the decision id, the evidence count). The rationale is the decision under
    consideration, and the holes are the recorded unknowns.
    """
    outcomes = tuple(
        BriefOutcome(
            outcome_id=claim.outcome_id,
            statement=claim.statement or claim.outcome_id,
            score=claim.score,
            n=claim.n,
            sources=claim.sources,
        )
        for claim in memo.chosen
    )
    brief = BriefInput(
        job_id=memo.job_id,
        job_name=memo.job_id,
        generated_at=memo.decided_at,
        outcomes=outcomes,
        decision_consideration=memo.rationale,
        evidence_count=len(memo.sources),
        holes=memo.holes,
    )
    return MemoNarrativeInput(memo=memo, brief=brief)


def narrate_memo(memo: Memo, narrator: Any) -> Narrative:
    """Draft and check one framing paragraph for the memo (M3-11.2/ALH-171).

    Reuses ``M3-04``'s narrator and its numeral/link guarantee — there is no
    second model policy. The narrator is handed the memo's own facts and its
    draft is validated by :func:`~agentic_odi_core.brief.render_narrative`, so a
    sentence with an absent numeral is dropped with a recorded reason rather than
    printed. The result is a :class:`Narrative` the export renders in one
    labelled block; the factual memo is unchanged whether or not it survives.
    """
    from agentic_odi_core.brief import render_narrative

    return render_narrative(memo_narrative_input(memo).brief, narrator)


def render_memo_markdown(memo: Memo, *, narrative: Narrative | None = None) -> str:
    """The exported markdown: the factual memo, plus one labelled drafted block.

    With no narrative this is byte-identical to :func:`render_memo` — the default
    export stays the deterministic assembly. A narrated export appends the
    labelled block after the memo's own sections, so a reader always knows which
    paragraph a model wrote.
    """
    base = render_memo(memo)
    if narrative is None:
        return base
    block = render_narrative_block(narrative)
    if not block:
        return base
    return base.rstrip("\n") + "\n\n" + block


def render_memo_html(
    memo: Memo,
    *,
    source: str,
    generated_at: str,
    schema_version: int,
    narrative: Narrative | None = None,
) -> str:
    """A standalone, printable HTML memo (M3-11.2/ALH-171).

    Reuses ``C4``'s approach: the markdown is escaped and rendered as pre-wrapped
    text, so a quote that contains markup stays text instead of executing, and
    the document carries no app CSS and no network asset, so it opens offline.
    The banner states the source, the export time and the schema version — the
    metadata the caller supplied, never a research claim.
    """
    import html as _html

    body = _html.escape(render_memo_markdown(memo, narrative=narrative))
    banner = (
        '<p class="memo__banner">'
        "Exported from the recorded data — a snapshot, not a live view. "
        f"Source: {_html.escape(source)}. "
        f"Generated: {_html.escape(generated_at)}. "
        f"Schema version: {schema_version}."
        "</p>"
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        "<title>Decision memo</title>\n"
        f"<style>{_MEMO_PRINT_TOKENS}</style>\n</head>\n<body>\n"
        f"{banner}\n"
        f'<div class="memo__body">{body}</div>\n'
        "</body>\n</html>\n"
    )


#: The paper rules the Studio's print sheet uses, inlined so the exported file is
#: standalone. Kept here so the memo's HTML export needs no app asset.
_MEMO_PRINT_TOKENS = """
  @page { size: A4; margin: 14mm; }
  body {
    margin: 0 auto;
    max-width: 46rem;
    padding: 2rem 1.25rem 4rem;
    background: #fff;
    color: #111;
    font: 16px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  h1 { font-size: 1.6rem; line-height: 1.2; }
  h2 { margin-top: 2rem; font-size: 1.2rem; }
  code { background: #f4f4f5; padding: 0.1em 0.3em; border-radius: 4px; }
  .memo__banner {
    margin: 0 0 2rem;
    padding: 0.6rem 0.8rem;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    font-size: 0.85rem;
    color: #3f3f46;
  }
  .memo__body { white-space: pre-wrap; }
"""
