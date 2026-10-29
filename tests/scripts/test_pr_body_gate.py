"""The pull request template and the CI gate that requires a non-empty body."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / ".github" / "pull_request_template.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

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


def test_ci_runs_the_body_gate_only_for_pull_requests() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "\n  pr-body:\n" in workflow
    assert "github.event_name == 'pull_request'" in workflow


def test_the_gate_reads_the_body_through_the_api_and_fails_when_empty() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    gate = workflow.split("\n  pr-body:\n", 1)[1].split("\n  lint:\n", 1)[0]

    assert "gh pr view" in gate
    assert "--json body" in gate
    assert "tr -d '[:space:]'" in gate, "whitespace-only bodies must count as empty"
    assert "exit 1" in gate
