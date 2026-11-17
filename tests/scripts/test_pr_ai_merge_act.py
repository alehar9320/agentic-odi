"""Test the AI merge act workflow (``.github/workflows/pr-ai-merge-act.yml``).

Each assertion is a way the previous version merged a pull request it had no
authorization for: a trigger that took any label event, a CI gate that read
Chromatic's commit status, and no way to disarm (ADR 0009).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "pr-ai-merge-act.yml"
AUTHORIZE = ROOT / ".github" / "workflows" / "pr-ai-authorize.yml"


def test_trigger_is_labeled_and_unlabeled():
    text = WORKFLOW.read_text(encoding="utf-8")
    trigger = text.split("\nconcurrency:", 1)[0]
    assert "pull_request:" in trigger
    assert "types: [labeled, unlabeled]" in trigger
    assert "branches:" not in trigger


def test_unrelated_label_events_do_not_wake_the_job():
    """#1100 was armed nine seconds after a label the bot never acts on."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '"ai-merge-authorized","do-not-merge","needs human review"' in text
    assert "github.event.label.name" in text


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


def test_the_authorization_label_is_reverified_before_arming():
    """A label event is not authorization; the chain is re-read from the PR."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'has "ai-merge-authorized"' in text
    assert 'has "ai-merge-safe"' in text
    assert 'has "ready-for-merge"' in text


def test_the_gate_is_the_tested_python_entrypoint():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pr_ai_authorize.py" in text
    assert "--ci-state" in text
    assert "python3 -c" not in text


def test_the_legacy_combined_status_is_not_the_gate():
    """`/commits/{sha}/status` carries only third-party statuses (#1100)."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "commits/$HEAD_SHA/status" not in text
    assert "/check-runs" in text


def test_auto_merge_is_disarmed_when_a_gate_stops_holding():
    """`--auto` survives later pushes; a withdrawal has to be acted on."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "--disable-auto" in text
    assert "autoMergeRequest" in text


def test_both_merge_workflows_share_one_gate():
    """Fixing one half and forgetting the other is how the signals drifted."""
    for workflow in (WORKFLOW, AUTHORIZE):
        assert "pr_ai_authorize.py" in workflow.read_text(encoding="utf-8")


def test_no_failure_is_swallowed_on_merge_path():
    text = WORKFLOW.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "--auto" in line and "merge" in line:
            assert "|| true" not in line, f"swallowed merge failure: {line.strip()}"
