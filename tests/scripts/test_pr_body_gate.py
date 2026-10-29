"""The pull request template and its body-truth guardrail."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / ".github" / "pull_request_template.md"
GUARDRAIL_WORKFLOW = ROOT / ".github" / "workflows" / "pr-guardrails.yml"

REQUIRED_SECTIONS = (
    "## Summary",
    "## What a person experiences",
    "## What changed",
    "## How this was verified",
    "## What this does NOT do",
    "## Related issue",
)


def test_the_template_asks_for_the_required_sections() -> None:
    template = TEMPLATE.read_text(encoding="utf-8")

    for section in REQUIRED_SECTIONS:
        assert section in template, f"{section} is missing from the PR template"


def test_guardrail_workflow_checks_pull_request_body_truth() -> None:
    workflow = GUARDRAIL_WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "uv run python scripts/pr_guards.py body-truth" in workflow


def test_the_guardrail_passes_pr_body_and_title_to_the_truth_check() -> None:
    workflow = GUARDRAIL_WORKFLOW.read_text(encoding="utf-8")

    assert "PR_BODY: ${{ github.event.pull_request.body }}" in workflow
    assert "PR_TITLE: ${{ github.event.pull_request.title }}" in workflow
    assert "printf '%s' \"$PR_BODY\"" in workflow
    assert "--body-file \"$RUNNER_TEMP/pr-body.md\"" in workflow
    assert '--title "$PR_TITLE"' in workflow
