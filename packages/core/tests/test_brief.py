"""Pin the factual brief renderer (C1) and its deterministic argument (C1.2).

Readiness choices pinned here, per ALH-32 / ALH-157:

* Input fixture/schema: :class:`BriefOutcome` / :class:`BriefInput` in ``brief.py``.
* "Three most underserved": highest ``score`` first, ties keep input order.
  Unscored outcomes are excluded from the selection (unknown, not low).
* Decision-consideration text: supplied by the caller on ``BriefInput``; the
  renderer never infers one.
* ``What we would build`` names the lowest-score measured outcome (the pinned
  direction); ``What the evidence supports`` names the outcome ids it rests on;
  ``Risks and unknowns`` names the supplied holes.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentic_odi_core.brief import BriefInput, BriefOutcome, render_brief, select_underserved

GOLDEN = Path(__file__).parent / "golden" / "brief_fixture_job.md"

_FIXTURE = BriefInput(
    job_id="job-1",
    job_name="Publish a plugin",
    generated_at="2026-10-29T00:00:00Z",
    decision_consideration="Should we invest in onboarding or in publishing speed?",
    evidence_count=4,
    holes=("No interviews with enterprise admins yet",),
    outcomes=(
        BriefOutcome(
            outcome_id="out-1",
            statement="Minimize the time it takes to publish a plugin when a release is ready",
            score=15.0,
            n=12,
            method="survey",
            quote="Publishing is the slowest step in my week",
            sources=("interview-7",),
        ),
        BriefOutcome(
            outcome_id="out-2",
            statement="Minimize the likelihood of a failed install when a customer upgrades",
            score=12.5,
            n=9,
            method="interview",
            quote="Upgrades break <script>alert(1)</script> my setup",
            sources=("interview-3",),
        ),
        BriefOutcome(
            outcome_id="out-3",
            statement="Minimize the cost of supporting a new plugin when it ships",
            score=8.0,
            n=5,
            method="survey",
            sources=("survey-1",),
        ),
        BriefOutcome(
            outcome_id="out-4",
            statement="Minimize the time it takes to document a plugin when it is released",
            score=None,
            n=None,
        ),
    ),
)


def _all_numerals(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", text)


def test_golden_file_matches_exactly():
    assert render_brief(_FIXTURE) == GOLDEN.read_text(encoding="utf-8")


def test_same_input_yields_identical_bytes():
    assert render_brief(_FIXTURE) == render_brief(_FIXTURE)


def test_every_numeral_in_output_exists_in_the_fixture():
    output = render_brief(_FIXTURE)
    allowed: set[str] = set()
    allowed |= set(re.findall(r"\d+(?:\.\d+)?", _FIXTURE.job_id))
    allowed |= set(re.findall(r"\d+(?:\.\d+)?", _FIXTURE.job_name))
    allowed |= set(re.findall(r"\d+(?:\.\d+)?", _FIXTURE.generated_at))
    allowed |= set(re.findall(r"\d+(?:\.\d+)?", _FIXTURE.decision_consideration or ""))
    allowed.add(str(_FIXTURE.evidence_count))
    for outcome in _FIXTURE.outcomes:
        allowed |= set(re.findall(r"\d+(?:\.\d+)?", outcome.statement))
        if outcome.score is not None:
            allowed.add(f"{outcome.score:g}")
        if outcome.n is not None:
            allowed.add(str(outcome.n))
        allowed |= set(re.findall(r"\d+(?:\.\d+)?", outcome.method or ""))
        allowed |= set(re.findall(r"\d+(?:\.\d+)?", outcome.quote or ""))
        for source in outcome.sources:
            allowed |= set(re.findall(r"\d+(?:\.\d+)?", source))
    for hole in _FIXTURE.holes:
        allowed |= set(re.findall(r"\d+(?:\.\d+)?", hole))
    # Section positions (1..n) are structural, not measurements.
    allowed |= {str(i) for i in range(1, len(_FIXTURE.outcomes) + 1)}
    for numeral in _all_numerals(output):
        assert numeral in allowed, f"fabricated numeral {numeral!r} in brief"


def test_numeral_walk_does_not_prove_association_so_assert_it_directly():
    output = render_brief(_FIXTURE)
    # 15 belongs to out-1's statement, 12.5 to out-2's.
    assert "publish a plugin when a release is ready" in output
    assert "Score: 15 (underserved)" in output
    assert "Score: 12.5 (underserved)" in output
    # The 12 sample belongs to out-1, not to the outcome that scored 12.5.
    out1_block = output.split("### 1.")[1].split("### 2.")[0]
    assert "Sample: 12" in out1_block


def test_hostile_quote_is_escaped_not_executed():
    output = render_brief(_FIXTURE)
    assert "<script>" not in output
    assert "&lt;script&gt;" in output


def test_unscored_outcome_is_omitted_with_a_reason():
    output = render_brief(_FIXTURE)
    assert "out-4" not in output
    assert "no score and were excluded" in output


def test_no_scored_outcomes_omits_the_section_and_says_why():
    empty = BriefInput(job_id="j", job_name="Empty", generated_at="2026-10-29T00:00:00Z")
    output = render_brief(empty)
    assert "No scored outcomes yet" in output
    assert "not measured" not in output  # no placeholder rows


def test_select_underserved_excludes_unscored_and_keeps_tie_order():
    outcomes = [
        BriefOutcome(outcome_id="a", statement="s", score=None),
        BriefOutcome(outcome_id="b", statement="s", score=10.0),
        BriefOutcome(outcome_id="c", statement="s", score=10.0),
        BriefOutcome(outcome_id="d", statement="s", score=20.0),
    ]
    selected = select_underserved(outcomes)
    assert [o.outcome_id for o in selected] == ["d", "b", "c"]


def test_select_underserved_honours_the_limit():
    outcomes = [
        BriefOutcome(outcome_id=str(i), statement="s", score=float(20 - i)) for i in range(5)
    ]
    assert [o.outcome_id for o in select_underserved(outcomes, limit=3)] == ["0", "1", "2"]


def test_permuting_input_keeps_the_approved_order():
    # A permutation that changes insertion order but not scores must not change
    # which outcomes are selected; ties follow the new input order.
    reordered = tuple(reversed(_FIXTURE.outcomes))
    selected = select_underserved(reordered)
    assert [o.outcome_id for o in selected] == ["out-1", "out-2", "out-3"]


def test_generated_at_is_rendered_from_the_supplied_value():
    a = BriefInput(job_id="j", job_name="J", generated_at="2020-01-01T00:00:00Z")
    b = BriefInput(job_id="j", job_name="J", generated_at="2099-12-31T00:00:00Z")
    assert "2020-01-01T00:00:00Z" in render_brief(a)
    assert "2099-12-31T00:00:00Z" in render_brief(b)
    assert render_brief(a) != render_brief(b)


# ------------------------------------------------------------------ C1.2 argument


def test_argument_sections_are_present():
    output = render_brief(_FIXTURE)
    assert "## What the evidence supports" in output
    assert "## What we would build" in output
    assert "## Risks and unknowns" in output


def test_each_supported_claim_names_an_outcome_id_in_the_input():
    output = render_brief(_FIXTURE)
    section = output.split("## What the evidence supports")[1].split("## What we would build")[0]
    input_ids = {o.outcome_id for o in _FIXTURE.outcomes}
    named = set(re.findall(r"`(out-\d+)`", section))
    assert named, "no outcome ids named in the supported section"
    assert named <= input_ids


def test_build_section_names_the_lowest_score():
    output = render_brief(_FIXTURE)
    section = output.split("## What we would build")[1].split("## Risks and unknowns")[0]
    # Scores are 15, 12.5, 8 -> lowest is out-3.
    assert "out-3" in section


def test_single_measured_outcome_renders_singular_and_names_the_missing_comparison():
    single = BriefInput(
        job_id="j",
        job_name="J",
        generated_at="2026-10-29T00:00:00Z",
        outcomes=(
            BriefOutcome(outcome_id="out-1", statement="Minimize the time when x", score=9.0),
        ),
    )
    output = render_brief(single)
    assert "no comparison drove this choice" in output


def test_no_recorded_holes_says_so_in_one_line():
    no_holes = BriefInput(job_id="j", job_name="J", generated_at="2026-10-29T00:00:00Z")
    output = render_brief(no_holes)
    assert "## Risks and unknowns" in output
    assert "No recorded holes" in output
    assert "not proof that no risk remains" in output


def test_argument_sections_keep_the_numeral_guarantee():
    output = render_brief(_FIXTURE)
    # The only new numerals the argument sections may introduce are scores and
    # ids that already exist in the input.
    argument = output.split("## What the evidence supports")[1]
    allowed = {f"{o.score:g}" for o in _FIXTURE.outcomes if o.score is not None}
    for numeral in _all_numerals(argument):
        assert numeral in allowed or numeral.isdigit(), numeral


def test_argument_sections_are_byte_identical_for_the_same_input():
    assert render_brief(_FIXTURE) == render_brief(_FIXTURE)


# ---------------------------------------------------------------- W1 worth (ALH-64)


def test_no_value_estimate_omits_the_section_and_says_why():
    output = render_brief(_FIXTURE)
    # The fixture records no value estimates, so the section is absent and the
    # gap is named in one line — never a zero.
    assert "## What it is worth" not in output
    assert "worth is unknown, not zero" in output


def test_a_sized_value_renders_with_unit_and_basis():
    sized = BriefInput(
        job_id="j",
        job_name="J",
        generated_at="2026-10-29T00:00:00Z",
        outcomes=(
            BriefOutcome(
                outcome_id="out-1",
                statement="Minimize the time it takes to publish a plugin when a release is ready",
                score=15.0,
                value_estimate=250_000.0,
                value_unit="currency",
                value_basis="market",
                value_source="Gartner 2025 plugin market report",
            ),
        ),
    )
    output = render_brief(sized)
    assert "## What it is worth" in output
    assert "250000 currency (market, sized)" in output
    assert "Gartner 2025 plugin market report" in output


def test_a_thin_value_is_labelled_thin_not_sized():
    thin = BriefInput(
        job_id="j",
        job_name="J",
        generated_at="2026-10-29T00:00:00Z",
        outcomes=(
            BriefOutcome(
                outcome_id="out-1",
                statement="Minimize the time it takes to publish a plugin when a release is ready",
                score=15.0,
                value_estimate=100.0,
                value_unit="users",
                value_n=1,
            ),
        ),
    )
    output = render_brief(thin)
    assert "(estimate, thin)" in output


def test_a_real_zero_value_is_shown_as_zero_not_omitted():
    zero = BriefInput(
        job_id="j",
        job_name="J",
        generated_at="2026-10-29T00:00:00Z",
        outcomes=(
            BriefOutcome(
                outcome_id="out-1",
                statement="Minimize the time it takes to publish a plugin when a release is ready",
                score=15.0,
                value_estimate=0.0,
                value_unit="currency",
                value_basis="market",
                value_source="No buyers in the segment",
            ),
        ),
    )
    output = render_brief(zero)
    assert "0 currency (market, sized)" in output


def test_the_value_section_introduces_no_numeral_outside_the_input():
    sized = BriefInput(
        job_id="j",
        job_name="J",
        generated_at="2026-10-29T00:00:00Z",
        outcomes=(
            BriefOutcome(
                outcome_id="out-1",
                statement="Minimize the time it takes to publish a plugin when a release is ready",
                score=15.0,
                value_estimate=250_000.0,
                value_unit="currency",
                value_basis="pilot",
                value_source="beta with 6 admins",
                value_n=6,
            ),
        ),
    )
    output = render_brief(sized)
    section = output.split("## What it is worth")[1].split("## Risks and unknowns")[0]
    # "1" is the outcome id numeral, not a measurement.
    allowed = {"15", "250000", "6", "1"}
    for numeral in _all_numerals(section):
        assert numeral in allowed, f"fabricated numeral {numeral!r} in value section"


def test_unsized_selected_outcomes_are_counted_when_some_are_sized():
    mixed = BriefInput(
        job_id="j",
        job_name="J",
        generated_at="2026-10-29T00:00:00Z",
        outcomes=(
            BriefOutcome(
                outcome_id="out-1",
                statement="Minimize the time it takes to publish a plugin when a release is ready",
                score=15.0,
                value_estimate=100.0,
                value_unit="users",
                value_n=3,
            ),
            BriefOutcome(
                outcome_id="out-2",
                statement="Minimize the cost of supporting a plugin when it ships",
                score=12.0,
            ),
        ),
    )
    output = render_brief(mixed)
    assert "## What it is worth" in output
    assert "have no value estimate and were omitted" in output
    assert "unsized outcome is unknown, not zero" in output


def test_a_hostile_value_source_is_escaped():
    hostile = BriefInput(
        job_id="j",
        job_name="J",
        generated_at="2026-10-29T00:00:00Z",
        outcomes=(
            BriefOutcome(
                outcome_id="out-1",
                statement="Minimize the time it takes to publish a plugin when a release is ready",
                score=15.0,
                value_estimate=1.0,
                value_unit="currency",
                value_basis="market",
                value_source="<script>alert(1)</script>",
            ),
        ),
    )
    output = render_brief(hostile)
    assert "<script>" not in output
    assert "&lt;script&gt;" in output
