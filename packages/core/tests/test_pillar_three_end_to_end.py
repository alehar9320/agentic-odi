"""Pillar 3 end-to-end: the five deliverables from one recorded fixture.

The plan's pillar-completion clause requires traceable fixture coverage across
factual case → comparison → recorded decision → derived/rendered roadmap, plus
the value judgement and the bet. This module chains all five on one job so the
hand-offs between them are exercised together, not just each in isolation:

1. the one-page case (:func:`render_brief`) states the sourced numbers;
2. the comparison (:meth:`ODIService.compare_outcomes`) weighs the bets;
3. the recorded decision (:meth:`ODIService.record_decision`) keeps the rejected
   option and the reason, and supersedes rather than overwrites;
4. the roadmap (:meth:`ODIService.build_roadmap` → :func:`render_roadmap`)
   derives from that decision;
5. the bet (:meth:`ODIService.record_bet`) captures its baseline and tracks.

No numeral appears in any rendered output that is not in the recorded input.
"""

from __future__ import annotations

import re
from datetime import date

from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_core.brief import render_brief
from agentic_odi_core.models import Rejection
from agentic_odi_core.roadmap import render_roadmap

_ONBOARDING = "Minimize the time it takes a new admin to onboard when a workspace is created"
_PUBLISHING = "Minimize the time it takes to publish a plugin when a release is ready"
_SUPPORT = "Minimize the cost of supporting a plugin when it ships"


def _fixture() -> tuple[ODIService, str, str, str, str]:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Ship plugins safely")
    onboarding = service.add_outcome(job.id, _ONBOARDING, 9.0, 3.0, at="2026-01-01T00:00:00Z")
    publishing = service.add_outcome(job.id, _PUBLISHING, 8.0, 4.0, at="2026-01-01T00:00:00Z")
    support = service.add_outcome(job.id, _SUPPORT, 6.0, 5.0, at="2026-01-01T00:00:00Z")
    # One sourced value: a market estimate with the report it came from.
    service.set_outcome_value(
        publishing.id,
        250_000.0,
        unit="currency",
        basis="market",
        source="Gartner 2026 plugin market report",
    )
    return service, job.id, onboarding.id, publishing.id, support.id


def test_the_five_deliverables_chain_from_one_fixture():
    service, job_id, onboarding_id, publishing_id, support_id = _fixture()

    # 1. The one-page case states the sourced numbers, including the value.
    brief = render_brief(service.build_brief(job_id, generated_at="2026-01-05T00:00:00Z"))
    assert "## What it is worth" in brief
    assert "250000 currency (market, sized)" in brief
    assert "Gartner 2026 plugin market report" in brief

    # 2. The comparison weighs the two candidate bets side by side, no winner.
    comparison = service.compare_outcomes([onboarding_id, publishing_id])
    assert comparison.columns == (onboarding_id, publishing_id)
    assert len(comparison.rows) > 0

    # 3. The decision keeps the rejected option and the reason.
    decision = service.record_decision(
        job_id,
        [publishing_id],
        rationale="Publishing speed blocks every release; the value estimate is sourced.",
        decided_by="alex",
        decided_at="2026-01-06T00:00:00Z",
        rejected=[
            Rejection(outcome_id=onboarding_id, reason="Onboarding is steady; no acute pain.")
        ],
    )
    assert decision.chosen_outcome_ids == [publishing_id]
    assert decision.rejected[0].outcome_id == onboarding_id

    # A second decision supersedes the first; the predecessor stays readable.
    second = service.record_decision(
        job_id,
        [publishing_id, support_id],
        rationale="Support cost surfaced after the first cut.",
        decided_by="alex",
        decided_at="2026-01-07T00:00:00Z",
        supersedes=decision.id,
    )
    reread = service.repo.get_decision(decision.id)
    assert reread is not None
    assert reread.superseded_by == second.id
    assert reread.superseded_at == "2026-01-07T00:00:00Z"

    # 4. The roadmap derives from the live decision and renders.
    roadmap = service.build_roadmap(job_id, today=date(2026, 1, 8))
    assert {entry.outcome_id for entry in roadmap.entries} == {publishing_id, support_id}
    rendered = render_roadmap(roadmap)
    assert "2026-Q1" in rendered

    # 5. The bet captures its baseline at creation and can be advanced.
    bet = service.record_bet(
        second.id,
        publishing_id,
        "Publishing gets under five minutes",
        target=6.0,
        measure_by="2026-04-01",
    )
    assert bet.baseline == service.get_outcome(publishing_id).opportunity_score
    running = service.advance_bet(bet.id, "running")
    assert running.status.value == "running"

    # No fabricated numeral: every numeral in the rendered case is in the input.
    allowed: set[str] = set()
    for text in (
        job_id,
        "Ship plugins safely",
        "2026-01-05T00:00:00Z",
        _ONBOARDING,
        _PUBLISHING,
        _SUPPORT,
        "Gartner 2026 plugin market report",
        # The record ids the brief names are inputs, not measurements.
        onboarding_id,
        publishing_id,
        support_id,
    ):
        allowed |= set(re.findall(r"\d+(?:\.\d+)?", text))
    # Scores are computed from recorded importance/satisfaction, so they are
    # derived inputs, not fabrications.
    for outcome_id in (onboarding_id, publishing_id, support_id):
        outcome = service.get_outcome(outcome_id)
        assert outcome is not None
        allowed.add(f"{outcome.opportunity_score:g}")
        if outcome.value_estimate is not None:
            allowed.add(f"{outcome.value_estimate:g}")
    # Structural numerals the brief legitimately prints: the evidence count and
    # the one-based position of each rendered outcome.
    allowed.add("0")  # no evidence records were recorded
    allowed |= {str(i) for i in range(1, 4)}
    for numeral in re.findall(r"\d+(?:\.\d+)?", brief):
        assert numeral in allowed, f"fabricated numeral {numeral!r} in the case"


def test_an_unsized_outcome_stays_unsized_in_the_case():
    service = ODIService(InMemoryRepository())
    job = service.add_job("Ship plugins safely")
    service.add_outcome(job.id, _SUPPORT, 6.0, 5.0, at="2026-01-01T00:00:00Z")

    brief = render_brief(service.build_brief(job.id, generated_at="2026-01-05T00:00:00Z"))

    # Nothing was estimated: the section is omitted and says why, never a zero.
    assert "## What it is worth" not in brief
    assert "worth is unknown, not zero" in brief


def test_the_value_is_never_derived_from_the_score():
    service, _, _, publishing_id, _ = _fixture()
    publishing = service.get_outcome(publishing_id)
    assert publishing is not None
    # The score is a separate fact from the recorded value.
    assert publishing.opportunity_score == 12.0
    assert publishing.value_estimate == 250_000.0
