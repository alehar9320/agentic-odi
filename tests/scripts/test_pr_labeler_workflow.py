"""The labeler workflows, pinned so the silent failures cannot come back.

Every assertion here corresponds to a way the previous labelers failed while
reporting success: inputs that never reached the action, labels that were never
created, and failures hidden behind ``|| true``.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RISK = ROOT / ".github" / "workflows" / "pr-risk.yml"


def test_inputs_are_passed_with_with_not_env():
    """A uses: step's env does not populate the action's inputs."""
    text = RISK.read_text(encoding="utf-8")
    assert "uses: ./.github/actions/pr-risk" in text
    # Everything from the composite-action step onward is its wiring.
    wiring = text.split("uses: ./.github/actions/pr-risk", 1)[1]
    assert "with:" in wiring
    expected = {
        "BASE_SHA": "${{ github.event.pull_request.base.sha }}",
        "HEAD_SHA": "${{ github.event.pull_request.head.sha }}",
        "PR_NUMBER": "${{ github.event.pull_request.number }}",
        "REPO": "${{ github.repository }}",
        "GITHUB_TOKEN": "${{ secrets.GITHUB_TOKEN }}",
    }
    for key, value in expected.items():
        assert f"{key}: {value}" in wiring, key


def test_the_labels_job_creates_labels_with_an_explicit_repo():
    """gh label create needs --repo outside a checkout."""
    text = RISK.read_text(encoding="utf-8")
    assert "gh label create" in text
    assert "--repo" in text


def test_permissions_include_issues_write():
    """GitHub's label API lives under issues, so issues: write is required."""
    text = RISK.read_text(encoding="utf-8")
    assert "issues: write" in text
    assert "pull-requests: write" in text


def test_no_failure_is_swallowed_on_the_label_path():
    """Removal may be tolerant; adding a label must not be."""
    text = RISK.read_text(encoding="utf-8")
    assert "pr_labels.py" in text
    for line in text.splitlines():
        if "--add-label" in line:
            assert "|| true" not in line, f"swallowed add-label failure: {line.strip()}"


def test_the_workflow_uses_the_managed_label_list_from_the_script():
    """One source of truth: the workflow asks the script, it does not re-list."""
    text = RISK.read_text(encoding="utf-8")
    assert "pr_labels.py --managed" in text


def test_the_workflow_never_checks_out_pr_code():
    """A write-permission workflow must not run PR code."""
    text = RISK.read_text(encoding="utf-8")
    assert "pull_request_target" not in text


def test_paginated_api_calls_use_slurp():
    """Without --slurp, gh emits one array per page and only page 1 is read."""
    text = RISK.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "--paginate" in line:
            assert "--slurp" in line, f"paginate without slurp: {line.strip()}"


def test_label_computation_uses_the_tested_python_entrypoint():
    """No inline JSON assembly in YAML: it cannot be tested or paginated."""
    text = RISK.read_text(encoding="utf-8")
    assert "pr_labels.py --facts" in text
    assert "python3 -c" not in text


def test_both_jobs_skip_fork_pull_requests():
    """pull_request gives forks a read-only token, so labeling cannot succeed.

    The risk job must not go red on an external contribution just because it
    cannot write a label; the labels job already guards this.
    """
    text = RISK.read_text(encoding="utf-8")
    labels_job, risk_job = text.split("\n  pr-risk:\n", 1)
    for name, job in (("labels", labels_job), ("pr-risk", risk_job)):
        assert "head.repo.fork" in job, f"{name} job does not guard fork PRs"


def test_the_risk_job_creates_its_own_tier_labels():
    """The tier labels did not exist, so --add-label 'danger zone' failed.

    Nothing created them: the labels job manages a different set by design.
    """
    text = RISK.read_text(encoding="utf-8")
    risk_job = text.split("\n  pr-risk:\n", 1)[1]
    for tier in ("safe to merge", "needs a look", "danger zone"):
        assert f'gh label create "{tier}"' in risk_job, tier
        assert "--repo" in risk_job
