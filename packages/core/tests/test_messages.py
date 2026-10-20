"""Tests for shared assistant messages and error helpers."""

from __future__ import annotations

from agentic_odi_core import messages


def test_framework_guidelines_are_exposed() -> None:
    assert messages.get_odi_framework_guidelines() == messages.ODI_FRAMEWORK_GUIDELINES
    assert "Opportunity Score" in messages.get_odi_framework_guidelines()


def test_not_found_helpers_include_the_id() -> None:
    assert messages.job_not_found("job-1") == "Job not found: job-1"
    assert messages.customer_outcome_not_found("co-1") == "Customer outcome not found: co-1"
