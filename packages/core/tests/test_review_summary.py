"""The review summary names every state it saw, and the render keeps them apart.

Five states exist because the acceptance criteria name them: improved,
degraded, no change, no evidence and orphaned. The summary counts each, and the
render gives a missing measurement its reason instead of a zero, so the two
readings of one review cannot disagree.
"""

from __future__ import annotations

from agentic_odi_core.review import (
    NO_CHANGE,
    NO_EVIDENCE,
    ORPHANED,
    DecisionReview,
    OutcomeReview,
    render_review,
)


def _review(*outcomes: OutcomeReview, days_elapsed: int = 30) -> DecisionReview:
    return DecisionReview(
        decision_id="dec-1",
        job_id="job-1",
        decided_at="2026-10-01T09:00:00+00:00",
        days_elapsed=days_elapsed,
        outcomes=outcomes,
    )


def test_the_summary_counts_every_state_it_saw() -> None:
    review = _review(
        OutcomeReview("out-1", "First", "improved", satisfaction_change=2.0),
        OutcomeReview("out-2", "Second", "degraded", satisfaction_change=-1.0),
        OutcomeReview("out-3", "Third", NO_CHANGE, satisfaction_change=0.0),
        OutcomeReview("out-4", "Fourth", NO_EVIDENCE),
        OutcomeReview("out-5", "Fifth", ORPHANED),
    )

    summary = review.summary()

    assert "1 improved" in summary
    assert "1 degraded" in summary
    assert "1 with no change" in summary
    assert "1 with no evidence" in summary
    assert "1 orphaned" in summary
    assert review.moved_count == 2
    assert review.stale is False


def test_a_decision_with_no_chosen_outcomes_says_so() -> None:
    assert _review().summary() == "This decision chose no outcomes."


def test_an_old_decision_is_stale_and_the_render_names_the_missing_states() -> None:
    review = _review(
        OutcomeReview("out-1", "First", "improved", satisfaction_change=2.0),
        OutcomeReview("out-2", None, NO_EVIDENCE),
        OutcomeReview("out-3", "Third", ORPHANED),
        OutcomeReview("out-4", "Fourth", "improved"),
        days_elapsed=120,
    )

    assert review.stale is True

    rendered = render_review(review)
    assert "# Decision review — `dec-1`" in rendered
    assert "**out-2** — no evidence" in rendered
    assert "Third** — orphaned" in rendered
    assert "Fourth** — improved (satisfaction not measured)" in rendered
