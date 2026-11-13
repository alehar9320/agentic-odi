"""Tests for the staleness rule on derived artifacts."""

from __future__ import annotations

from agentic_odi_core.freshness import is_stale
from agentic_odi_core.models import Segment


def _segment(computed_at: int | None) -> Segment:
    return Segment(
        id="seg-1",
        outcome_ids=["O-1", "O-2"],
        name="Platform engineers",
        people="Platform engineers",
        job_statement="Rotate a leaked secret",
        rationale="Two outcomes on the gather step.",
        confidence=0.75,
        computed_at_event_id=computed_at,
    )


def test_an_artifact_derived_at_the_current_revision_is_current() -> None:
    assert is_stale(_segment(5), 5) is False


def test_an_artifact_derived_before_the_current_revision_is_stale() -> None:
    assert is_stale(_segment(4), 5) is True


def test_an_unstamped_artifact_is_stale_not_current() -> None:
    """Unknown is not fresh: the store cannot vouch for an artifact with no stamp."""
    assert is_stale(_segment(None), 5) is True
