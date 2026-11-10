"""Pin the drafted brief argument and its mechanical no-fabrication check.

Readiness choices pinned here, per ALH-90 (M3-04):

* The guarantee is mechanical, not a prompt instruction: every numeral in a
  surviving sentence is extracted and asserted to exist in the brief, and to be
  sourced to an outcome the claim links. ``render_narrative`` is the check.
* A failing sentence is **dropped** with a recorded reason. There is no retry,
  so the result is deterministic for a fixed draft — the one-render-versus-drop
  conflict in the ticket is resolved in favour of dropping.
* ``claim_links`` is mandatory and non-empty for ``supported`` and
  ``recommendation``; an unlinked claim is dropped and the brief still renders.
* The narrator is a protocol with a fixture implementation, so the guarantee is
  testable without a model.
* ``--no-narrate`` — the default — renders no drafted block, so the factual
  brief is byte-identical to its pre-narrative golden.
"""

from __future__ import annotations

import re

import pytest
from agentic_odi_core.brief import (
    DRAFTED_LABEL,
    BriefInput,
    BriefOutcome,
    DraftedClaim,
    Narrative,
    NarrativeDraft,
    Narrator,
    NarratorError,
    render_brief,
    render_narrative,
)

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
            sources=("interview-7",),
        ),
        BriefOutcome(
            outcome_id="out-2",
            statement="Minimize the likelihood of a failed install when a customer upgrades",
            score=12.5,
            n=9,
            method="interview",
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
    ),
)


class _FixtureNarrator:
    """A narrator that returns a fixed draft. No model is involved."""

    def __init__(self, draft: NarrativeDraft) -> None:
        self._draft = draft

    def draft(self, brief: BriefInput) -> NarrativeDraft:
        return self._draft


class _FailingNarrator:
    """A narrator that always fails, standing in for a provider outage."""

    def draft(self, brief: BriefInput) -> NarrativeDraft:
        raise NarratorError("connection refused")


def _numerals(text: str) -> set[str]:
    """Every numeral in ``text``, the same way the guarantee counts them."""
    return set(re.findall(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?%?", text))


def test_fixture_narrator_satisfies_the_protocol() -> None:
    assert isinstance(_FixtureNarrator(NarrativeDraft()), Narrator)


def test_a_number_absent_from_the_brief_drops_the_sentence() -> None:
    narrator = _FixtureNarrator(
        NarrativeDraft(
            supported=(DraftedClaim("The market is worth 999 million.", ("out-1",)),),
        )
    )
    narrative = render_narrative(_FIXTURE, narrator)

    assert narrative.supported == ""
    assert narrative.is_empty
    assert any("999" in drop.reason for drop in narrative.dropped)


def test_an_unlinked_claim_is_dropped_and_the_brief_still_renders() -> None:
    narrator = _FixtureNarrator(
        NarrativeDraft(
            supported=(DraftedClaim("We should invest in publishing.", ()),),
        )
    )
    narrative = render_narrative(_FIXTURE, narrator)

    assert narrative.supported == ""
    assert any("not linked" in drop.reason for drop in narrative.dropped)
    # The factual brief still renders, unchanged.
    assert render_brief(_FIXTURE) == render_brief(_FIXTURE)


def test_a_valid_narrative_keeps_every_numeral_in_the_input() -> None:
    narrator = _FixtureNarrator(
        NarrativeDraft(
            supported=(DraftedClaim("out-1 scores 15 with 12 responses.", ("out-1",)),),
            recommendation=(DraftedClaim("Build toward out-1.", ("out-1",)),),
        )
    )
    narrative = render_narrative(_FIXTURE, narrator)

    assert "15" in narrative.supported
    assert narrative.recommendation == "Build toward out-1."
    assert narrative.claim_links
    # Every numeral in the surviving prose exists in the factual brief.
    factual = render_brief(_FIXTURE)
    for token in _numerals(narrative.supported + " " + narrative.recommendation):
        assert token.replace(",", "") in factual.replace(",", "")


def test_a_numeral_belonging_to_another_outcome_is_dropped() -> None:
    """The source-association check, which a token-set check would miss.

    ``12.5`` is in the brief — it is out-2's score — so a token-set check would
    pass it. Linked to out-1, it is the wrong number and the sentence is dropped.
    """
    narrator = _FixtureNarrator(
        NarrativeDraft(
            supported=(DraftedClaim("out-1 is actually the 12.5 opportunity.", ("out-1",)),),
        )
    )
    narrative = render_narrative(_FIXTURE, narrator)

    assert narrative.supported == ""
    assert any("not sourced to the linked outcome" in drop.reason for drop in narrative.dropped)


def test_an_unknown_outcome_link_is_dropped() -> None:
    narrator = _FixtureNarrator(
        NarrativeDraft(
            recommendation=(DraftedClaim("Build toward out-99.", ("out-99",)),),
        )
    )
    narrative = render_narrative(_FIXTURE, narrator)

    assert narrative.recommendation == ""
    assert any("out-99" in drop.reason for drop in narrative.dropped)


def test_signs_decimals_percentages_and_dates_do_not_conflate() -> None:
    """Tokens the ticket names explicitly: signs, decimals, percentages, dates."""
    brief = BriefInput(
        job_id="job-2",
        job_name="Publish a plugin",
        generated_at="2026-10-29T00:00:00Z",
        evidence_count=1,
        outcomes=(
            BriefOutcome(
                outcome_id="out-1",
                statement="Minimize the time to publish when ready by 2026-04-01 by 25%",
                score=-2.5,
                n=10,
            ),
        ),
    )
    narrator = _FixtureNarrator(
        NarrativeDraft(
            supported=(DraftedClaim("out-1 scores -2.5, a 25% gap.", ("out-1",)),),
            risks=(DraftedClaim("The target date 2026-04-01 is fixed.", ()),),
        )
    )
    narrative = render_narrative(brief, narrator)

    assert "-2.5" in narrative.supported
    assert "25%" in narrative.supported
    assert "2026-04-01" in narrative.risks


def test_a_failing_narrator_yields_an_empty_narrative_with_a_reason() -> None:
    narrative = render_narrative(_FIXTURE, _FailingNarrator())

    assert narrative.is_empty
    assert narrative.dropped
    assert "narrator failed" in narrative.dropped[0].reason


def test_dropping_is_deterministic_for_a_fixed_draft() -> None:
    narrator = _FixtureNarrator(
        NarrativeDraft(
            supported=(
                DraftedClaim("out-1 scores 15.", ("out-1",)),
                DraftedClaim("An invented 42.", ("out-1",)),
            ),
        )
    )
    assert render_narrative(_FIXTURE, narrator) == render_narrative(_FIXTURE, narrator)


def test_no_narrative_renders_no_drafted_block() -> None:
    text = render_brief(_FIXTURE)
    assert DRAFTED_LABEL not in text
    assert "Drafted" not in text


def test_the_factual_sections_are_byte_identical_with_and_without_a_narrative() -> None:
    """The default path must not change one byte for existing callers.

    Removing the drafted block from a narrated brief leaves the factual brief
    byte-for-byte, so an existing caller and its golden are unaffected.
    """
    narrator = _FixtureNarrator(
        NarrativeDraft(supported=(DraftedClaim("out-1 scores 15.", ("out-1",)),)),
    )
    narrative = render_narrative(_FIXTURE, narrator)
    with_narrative = render_brief(BriefInput(**{**_FIXTURE.__dict__, "narrative": narrative}))  # type: ignore[arg-type]

    start = with_narrative.index(f"## {DRAFTED_LABEL}")
    end = with_narrative.index("## Risks and unknowns")
    assert with_narrative[:start] + with_narrative[end:] == render_brief(_FIXTURE)


def test_the_drafted_block_is_labelled_and_linked() -> None:
    narrator = _FixtureNarrator(
        NarrativeDraft(
            supported=(DraftedClaim("out-1 scores 15.", ("out-1",)),),
        )
    )
    narrative = render_narrative(_FIXTURE, narrator)
    text = render_brief(
        BriefInput(**{**_FIXTURE.__dict__, "narrative": narrative})  # type: ignore[arg-type]
    )

    assert f"## {DRAFTED_LABEL}" in text
    assert "→ out-1" in text


def test_an_empty_narrative_renders_no_block() -> None:
    """An empty narrative that dropped nothing adds no block at all."""
    text = render_brief(BriefInput(**{**_FIXTURE.__dict__, "narrative": Narrative()}))  # type: ignore[arg-type]
    assert DRAFTED_LABEL not in text


def test_a_narrative_that_survives_nothing_still_shows_why() -> None:
    """A visible omission, never a silent one: drops are rendered, not hidden."""
    narrator = _FixtureNarrator(
        NarrativeDraft(supported=(DraftedClaim("An invented 999.", ("out-1",)),)),
    )
    narrative = render_narrative(_FIXTURE, narrator)
    text = render_brief(BriefInput(**{**_FIXTURE.__dict__, "narrative": narrative}))  # type: ignore[arg-type]

    assert f"## {DRAFTED_LABEL}" in text
    assert "_Dropped, with the reason:_" in text
    assert "999" in text


@pytest.mark.parametrize("value", ["15", "15.0"])
def test_integral_and_decimal_forms_of_one_number_are_the_same_token(value: str) -> None:
    narrator = _FixtureNarrator(
        NarrativeDraft(supported=(DraftedClaim(f"out-1 scores {value}.", ("out-1",)),)),
    )
    narrative = render_narrative(_FIXTURE, narrator)
    assert narrative.supported != ""
