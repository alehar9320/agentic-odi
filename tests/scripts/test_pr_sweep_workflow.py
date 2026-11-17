"""The PR sweep weekly workflow, pinned so the schedule and permissions cannot regress.

Every assertion here corresponds to a way the workflow could silently stop running
or fail to post the report: missing schedule, wrong permissions, or a broken
report validation step.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SWEEP = ROOT / ".github" / "workflows" / "pr-sweep.yml"


def test_workflow_has_weekly_schedule() -> None:
    """The sweep must run weekly on a fixed cron, not only on dispatch."""
    text = SWEEP.read_text(encoding="utf-8")
    assert "schedule:" in text
    # Monday 00:00 UTC
    assert "cron: '0 0 * * 1'" in text


def test_workflow_has_dispatch_trigger() -> None:
    """Manual runs must be possible for ad-hoc reporting."""
    text = SWEEP.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text


def test_workflow_has_exact_permissions() -> None:
    """Only the permissions the job actually needs: read queue, write issue comment."""
    text = SWEEP.read_text(encoding="utf-8")
    assert "contents: read" in text
    assert "pull-requests: read" in text
    assert "issues: write" in text
    # No write permission to contents or pull-requests — this is a read-only report
    lines = text.splitlines()
    perm_section = False
    for line in lines:
        if line.strip() == "permissions:":
            perm_section = True
            continue
        if perm_section and line.strip() and not line.startswith(" "):
            perm_section = False
        if perm_section and "write" in line:
            assert "issues: write" in line, f"unexpected write permission: {line.strip()}"


def test_workflow_runs_pr_sweep_script() -> None:
    """The job must call the canonical entry point with --live --json."""
    text = SWEEP.read_text(encoding="utf-8")
    assert "scripts/pr_sweep.py" in text
    assert "--live" in text
    assert "--json" in text


def test_workflow_validates_report_non_empty() -> None:
    """A broken run that produces an empty report must fail the job."""
    text = SWEEP.read_text(encoding="utf-8")
    assert "total_pull_requests" in text
    assert "counts" in text
    # The validation step should exit non-zero on empty report
    assert "sys.exit(1)" in text


def test_workflow_posts_to_tracking_issue() -> None:
    """The report must be posted to a single tracking issue, not a new one each week."""
    text = SWEEP.read_text(encoding="utf-8")
    assert "gh issue comment" in text
    assert "TRACKING_ISSUE" in text


def test_workflow_uses_github_token() -> None:
    """Authentication must use the default GITHUB_TOKEN, no PAT required."""
    text = SWEEP.read_text(encoding="utf-8")
    assert "GITHUB_TOKEN" in text
    assert "secrets.GITHUB_TOKEN" in text


def test_workflow_checks_out_base_branch() -> None:
    """The workflow must check out the base branch (main) to run the script."""
    text = SWEEP.read_text(encoding="utf-8")
    assert "actions/checkout" in text
    assert "ref: main" in text
    assert "persist-credentials: false" in text


def test_workflow_has_concurrency_control() -> None:
    """Only one sweep should run at a time; cancel in-progress on new trigger."""
    text = SWEEP.read_text(encoding="utf-8")
    assert "concurrency:" in text
    assert "cancel-in-progress: true" in text
