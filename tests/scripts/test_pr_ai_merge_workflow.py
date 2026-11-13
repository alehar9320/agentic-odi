"""The AI merge trust workflow, pinned so the silent failures cannot come back.

Every assertion here corresponds to a way the previous labelers failed while
reporting success: inputs that never reached the action, labels that were never
created, and failures hidden behind ``|| true``.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "pr-ai-merge.yml"


def test_trigger_is_not_restricted_to_main():
    """A stacked pull request targets another feature branch and must still be
    evaluated for the AI merge trust label.

    Scoping ``pull_request`` to ``branches: [main]`` meant stacked PRs never
    ran. Fork PRs are skipped per-job, so widening the trigger cannot fail on
    a read-only token.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    trigger = text.split("on:", 1)[1].split("\nconcurrency:", 1)[0]
    assert "pull_request:" in trigger
    assert "branches:" not in trigger


def test_trigger_includes_labeled_unlabeled_ready_for_review():
    """The ``ready-for-merge`` and ``safe to merge`` labels can land after the
    pull request event, so those label events must re-evaluate the gate."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "labeled" in text
    assert "unlabeled" in text
    assert "ready_for_review" in text


def test_both_schedule_and_dispatch_rescan_open_pull_requests():
    """The label depends on ``ready-for-merge``, which can land after the pull
    request event. A schedule and workflow_dispatch keep labels eventually
    consistent by looping over every open PR."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "schedule:" in text
    assert "workflow_dispatch:" in text
    assert "pr list" in text
    assert "pr-numbers.txt" in text


def test_fork_pull_requests_are_skipped_per_job():
    """pull_request gives forks a read-only token, so labeling cannot succeed."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target" not in text
    for step in text.split("      - name:"):
        if "if:" in step and "head.repo.fork" in step:
            return
    raise AssertionError("no step guards fork pull requests")


def test_the_label_is_created_with_an_explicit_repo():
    """gh label create needs --repo outside a checkout."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'gh label create "ai-merge-safe"' in text
    assert "--repo" in text


def test_permissions_include_issues_write():
    """GitHub's label API lives under issues, so issues: write is required."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "issues: write" in text
    assert "pull-requests: write" in text


def test_no_failure_is_swallowed_on_the_add_label_path():
    """Removal may be tolerant; adding the label must not be."""
    text = WORKFLOW.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "--add-label" in line and "ai-merge-safe" in line:
            assert "|| true" not in line, f"swallowed add-label failure: {line.strip()}"


def test_label_computation_uses_the_tested_python_entrypoint():
    """No inline JSON assembly in YAML: it cannot be tested or paginated."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pr_ai_merge.py --facts" in text
    assert "python3 -c" not in text


def test_paginated_api_calls_use_slurp():
    """Without --slurp, gh emits one array per page and only page 1 is read."""
    text = WORKFLOW.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "--paginate" in line:
            assert "--slurp" in line, f"paginate without slurp: {line.strip()}"


def test_workflow_requests_isDraft_not_draft():
    """``gh pr view`` rejects ``draft`` on non-fork PRs; the supported field is
    ``isDraft``, which the jq assembly maps to ``draft`` for the Python gate."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "isDraft" in text
    assert "draft: $meta[0].isDraft," in text


def test_the_development_guide_documents_the_label():
    guide = (ROOT / "docs" / "development.md").read_text(encoding="utf-8")
    assert "ai-merge-safe" in guide
    assert "AI merge" in guide
