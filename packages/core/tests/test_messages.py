"""Tests for shared assistant messages and error helpers."""

from __future__ import annotations

from agentic_odi_core import messages


def test_framework_guidelines_are_exposed() -> None:
    assert messages.get_odi_framework_guidelines() == messages.ODI_FRAMEWORK_GUIDELINES
    assert "Opportunity Score" in messages.get_odi_framework_guidelines()


def test_framework_guidelines_cover_segmentation_and_strategy() -> None:
    """Stages 5 and 6 are in the prompt, not only in the tools."""
    guidelines = messages.get_odi_framework_guidelines()
    assert "### Stage 5: Segment by Underserved Outcomes" in guidelines
    assert "### Stage 6: Formulate the Innovation Strategy" in guidelines
    # The methodology constraint the tools enforce.
    assert "Never** segment by demographics" in guidelines
    # A strategy carries the paths it beat.
    assert "Always state the strategies you rejected and why." in guidelines
    # Every Stage 5/6 tool the model may call is named.
    for tool in ("segment_market", "get_segments", "propose_strategy", "get_strategy"):
        assert tool in guidelines


def test_the_stages_are_stated_in_order() -> None:
    guidelines = messages.get_odi_framework_guidelines()
    headings = [line for line in guidelines.splitlines() if line.startswith("### Stage ")]
    assert [heading.split(":")[0] for heading in headings] == [
        f"### Stage {number}" for number in range(1, 7)
    ]


def test_invalid_strategy_request_uses_the_one_spelling() -> None:
    assert (
        messages.invalid_strategy_request("no path has evidence")
        == "Invalid strategy request: no path has evidence"
    )


def test_not_found_helpers_include_the_id() -> None:
    assert messages.job_not_found("job-1") == "Job not found: job-1"
    assert messages.customer_outcome_not_found("co-1") == "Customer outcome not found: co-1"
