"""Pin the decision memo assembler (M3-11/ALH-97).

Readiness choices pinned here (the increment's blockers):

* **Assembly is deterministic and reads nothing.** ``build_memo`` takes records;
  the same records yield identical bytes and no store or clock is touched.
* **A missing section is omitted with a one-line reason**, the rule ``C1`` set.
  *What it is worth* says "no value estimate recorded" and renders no zero.
* **The memo is generated on read and never stored.** Building one writes no
  event and no row: the store is byte-identical afterwards.
* **An unknown decision raises**, so "no such decision" is never confused with
  an empty memo.
* **A full fixture produces every section**, pinned by a golden file.
* **No invented numbers.** Every numeral in the output exists in the inputs, and
  a value's unit and source travel with the number.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from agentic_odi_core.memo import (
    NO_CRITERIA_NOTE,
    NO_HOLES_NOTE,
    NO_VALUE_NOTE,
    MemoDecisionNotFoundError,
    build_memo,
    render_memo,
)
from agentic_odi_core.models import Decision, Evidence, Outcome, Rejection
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService

GOLDEN = Path(__file__).parent / "golden" / "memo_fixture_decision.md"

#: Fixed-id records so the golden file is byte-stable across runs.
_FIXTURE_DECISION = Decision(
    id="dec-1",
    job_id="job-1",
    chosen_outcome_ids=["out-1"],
    rejected=[Rejection(outcome_id="out-2", reason="Support cost is already low.")],
    rationale="Publishing speed blocks every release.",
    decided_by="alex",
    decided_at="2026-01-02T00:00:00Z",
)

_FIXTURE_OUTCOMES = (
    Outcome(
        id="out-1",
        job_id="job-1",
        statement="Minimize the time it takes to publish a plugin when a release is ready",
        importance=9.0,
        satisfaction=3.0,
        opportunity_score=15.0,
        value_estimate=250000.0,
        value_unit="currency",
        value_basis="market",
        value_source="Gartner 2026",
    ),
    Outcome(
        id="out-2",
        job_id="job-1",
        statement="Minimize the cost of supporting a plugin when it ships",
        importance=5.0,
        satisfaction=7.0,
    ),
)

#: The same chosen outcome with no value estimate: worth is unknown, not zero.
_UNSIZED_OUTCOMES = (
    Outcome(
        id="out-1",
        job_id="job-1",
        statement="Minimize the time it takes to publish a plugin when a release is ready",
        importance=9.0,
        satisfaction=3.0,
        opportunity_score=15.0,
    ),
    Outcome(
        id="out-2",
        job_id="job-1",
        statement="Minimize the cost of supporting a plugin when it ships",
        importance=5.0,
        satisfaction=7.0,
        opportunity_score=3.0,
    ),
)

_FIXTURE_EVIDENCE = (
    Evidence(
        source_name="Interview 7",
        source_kind="manual",
        name="interview-7",
        content="Publishing is the slowest step in my week",
        job_id="job-1",
        outcome_id="out-1",
    ),
)


class _FixedBet:
    """A bet record with fixed ids, matching the ``MemoBetRecord`` shape."""

    outcome_id = "out-1"
    hypothesis = "Publishing gets under 5 minutes"
    target = 6.0
    measure_by = "2026-04-01"


def _full_memo():
    return build_memo(
        _FIXTURE_DECISION,
        outcomes=_FIXTURE_OUTCOMES,
        evidence=_FIXTURE_EVIDENCE,
        bets=(_FixedBet(),),
    )


def _all_numerals(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", text)


def test_golden_file_matches_exactly() -> None:
    assert render_memo(_full_memo()) == GOLDEN.read_text(encoding="utf-8")


def test_same_records_yield_identical_bytes() -> None:
    assert render_memo(_full_memo()) == render_memo(_full_memo())


def test_a_fully_populated_decision_produces_every_section() -> None:
    text = render_memo(_full_memo())
    for section in (
        "## Decision",
        "## Why now",
        "## What the evidence says",
        "## What we are not doing",
        "## What it is worth",
        "## How we will know",
        "## What we do not know",
        "## Sources",
    ):
        assert section in text


def test_a_decision_with_no_value_estimate_omits_it_with_a_reason() -> None:
    memo = build_memo(
        Decision(
            id="dec-1",
            job_id="job-1",
            chosen_outcome_ids=["out-1"],
            rationale="Publishing speed blocks every release.",
            decided_by="alex",
            decided_at="2026-01-02T00:00:00Z",
        ),
        outcomes=_UNSIZED_OUTCOMES,
        evidence=_FIXTURE_EVIDENCE,
    )
    text = render_memo(memo)
    assert NO_VALUE_NOTE in text
    # No zero is ever rendered in place of an unknown worth.
    assert "0 currency" not in text


def test_a_decision_with_no_bet_says_which_step_is_missing() -> None:
    memo = build_memo(
        _FIXTURE_DECISION,
        outcomes=_FIXTURE_OUTCOMES,
        evidence=_FIXTURE_EVIDENCE,
    )
    text = render_memo(memo)
    assert NO_CRITERIA_NOTE in text
    assert "No bet recorded" in text


def test_no_holes_says_that_absence_is_not_proof() -> None:
    memo = build_memo(
        _FIXTURE_DECISION,
        outcomes=_FIXTURE_OUTCOMES,
        evidence=_FIXTURE_EVIDENCE,
    )
    assert NO_HOLES_NOTE in render_memo(memo)


def test_recorded_holes_are_listed() -> None:
    memo = build_memo(
        _FIXTURE_DECISION,
        outcomes=_FIXTURE_OUTCOMES,
        evidence=_FIXTURE_EVIDENCE,
        holes=("No interviews with enterprise admins yet",),
    )
    assert "- No interviews with enterprise admins yet" in render_memo(memo)


def test_recorded_criteria_are_listed() -> None:
    class _Criterion:
        statement = "Publish time under 5 minutes for 80% of releases"

    memo = build_memo(
        _FIXTURE_DECISION,
        outcomes=_FIXTURE_OUTCOMES,
        evidence=_FIXTURE_EVIDENCE,
        criteria=(_Criterion(),),
    )
    assert "- Publish time under 5 minutes for 80% of releases" in render_memo(memo)


def test_an_unknown_decision_raises_rather_than_rendering_an_empty_memo() -> None:
    service = ODIService(InMemoryRepository())
    with pytest.raises(MemoDecisionNotFoundError):
        service.build_memo("no-such-decision")


def test_a_superseded_decision_is_marked_as_the_record() -> None:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Publish a plugin")
    first = service.add_outcome(
        job.id,
        "Minimize the time it takes to publish a plugin when a release is ready",
        9.0,
        3.0,
        at="2026-01-01T00:00:00Z",
    )
    second = service.add_outcome(
        job.id,
        "Minimize the cost of supporting a plugin when it ships",
        5.0,
        7.0,
        at="2026-01-01T00:00:00Z",
    )
    original = service.record_decision(
        job.id,
        [first.id],
        rationale="Publishing speed blocks every release.",
        decided_by="alex",
        decided_at="2026-01-02T00:00:00Z",
    )
    service.record_decision(
        job.id,
        [second.id],
        rationale="Support cost turned out to matter more.",
        decided_by="alex",
        decided_at="2026-02-02T00:00:00Z",
        supersedes=original.id,
    )
    text = render_memo(service.build_memo(original.id))
    assert "Superseded by" in text
    assert "not the current choice" in text


def test_building_a_memo_writes_nothing() -> None:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(
        job.id,
        "Minimize the time it takes to publish a plugin when a release is ready",
        9.0,
        3.0,
        at="2026-01-01T00:00:00Z",
    )
    decision = service.record_decision(
        job.id,
        [outcome.id],
        rationale="Publishing speed blocks every release.",
        decided_by="alex",
        decided_at="2026-01-02T00:00:00Z",
    )

    def snapshot() -> str:
        repo = service.repo
        parts = {
            "decisions": [d.model_dump(mode="json") for d in repo.decisions.values()],
            "bets": [b.model_dump(mode="json") for b in repo.bets.values()],
            "outcomes": [o.model_dump(mode="json") for o in repo.outcomes.values()],
            "snapshots": [s.model_dump(mode="json") for s in repo.score_snapshots],
        }
        return repr(parts)

    before = snapshot()
    render_memo(service.build_memo(decision.id))
    assert snapshot() == before


def test_every_numeral_in_output_exists_in_the_records() -> None:
    memo = _full_memo()
    text = render_memo(memo)

    allowed: set[str] = set()
    for source in (
        memo.decision_id,
        memo.job_id,
        memo.decided_at,
        memo.rationale,
        memo.decided_by,
        memo.confidence,
        memo.why_now,
    ):
        allowed |= set(_all_numerals(source))
    for claim in memo.chosen:
        allowed |= set(_all_numerals(claim.outcome_id))
        allowed |= set(_all_numerals(claim.statement or ""))
        if claim.score is not None:
            allowed.add(f"{claim.score:g}")
        if claim.n is not None:
            allowed.add(str(claim.n))
    for rejection in memo.rejected:
        allowed |= set(_all_numerals(rejection.outcome_id))
        allowed |= set(_all_numerals(rejection.reason))
        allowed |= set(_all_numerals(rejection.statement or ""))
    for source in memo.sources:
        allowed |= set(_all_numerals(source))
    if memo.value_estimate is not None:
        allowed.add(f"{memo.value_estimate:g}")
    if memo.value_n is not None:
        allowed.add(str(memo.value_n))
    allowed |= set(_all_numerals(memo.value_source or ""))
    if memo.bet is not None:
        allowed.add(f"{memo.bet.target:g}")
        allowed |= set(_all_numerals(memo.bet.measure_by))
        allowed |= set(_all_numerals(memo.bet.hypothesis))
    for hole in memo.holes:
        allowed |= set(_all_numerals(hole))

    for numeral in _all_numerals(text):
        assert numeral in allowed, f"numeral {numeral!r} in memo is not in the records"


def test_a_value_number_travels_with_its_unit_and_source() -> None:
    text = render_memo(_full_memo())
    line = next(line for line in text.splitlines() if "250000" in line)
    assert "currency" in line
    assert "market" in line
    assert "Gartner 2026" in line


def test_recorded_text_is_escaped() -> None:
    decision = Decision(
        id="dec-1",
        job_id="job-1",
        chosen_outcome_ids=["out-1"],
        rationale="Upgrades break <script>alert(1)</script> my setup.",
        decided_by="alex",
        decided_at="2026-01-02T00:00:00Z",
    )
    text = render_memo(build_memo(decision, outcomes=_FIXTURE_OUTCOMES, evidence=()))
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_a_chosen_outcome_that_no_longer_exists_is_still_named() -> None:
    """An orphaned chosen outcome is named, not dropped: the decision is the record."""
    decision = Decision(
        id="dec-1",
        job_id="job-1",
        chosen_outcome_ids=["out-1", "out-gone"],
        rationale="Because.",
        decided_by="alex",
        decided_at="2026-01-02T00:00:00Z",
    )
    memo = build_memo(decision, outcomes=_FIXTURE_OUTCOMES, evidence=())
    text = render_memo(memo)
    assert "`out-gone`" in text
    assert "score not measured" in text
