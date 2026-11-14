"""Test the AI merge act workflow (``.github/workflows/pr-ai-merge-act.yml``)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "pr-ai-merge-act.yml"


def test_trigger_is_labeled_only():
    """On pull_request we only react when a label is added (ai-merge-authorized)."""
    text = WORKFLOW.read_text(encoding="utf-8")
    trigger = text.split("on:", 1)[1].split("\nconcurrency:", 1)[0]
    assert "pull_request:" in trigger
    assert "labeled" in trigger
    assert "branches:" not in trigger


def test_schedule_and_dispatch_present():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "schedule:" in text
    assert "workflow_dispatch:" in text


def test_fork_pull_requests_are_skipped_per_job():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target" not in text
    for step in text.split("      - name:"):
        if "if:" in step and "head.repo.fork" in step:
            return
    raise AssertionError("no step guards fork pull requests")


def test_permissions_include_contents_write():
    """gh pr merge --auto needs contents: write."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "contents: write" in text
    assert "pull-requests: write" in text


def test_human_override_is_checked():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "do-not-merge" in text
    assert "needs human review" in text


def test_ci_green_is_reverified_before_merge():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "commits/$HEAD_SHA/status" in text or 'commits/"$HEAD_SHA"/status' in text
    assert "gh pr merge --auto --squash" in text


def test_no_failure_is_swallowed_on_merge_path():
    text = WORKFLOW.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "--auto" in line and "merge" in line:
            assert "|| true" not in line, f"swallowed merge failure: {line.strip()}"
