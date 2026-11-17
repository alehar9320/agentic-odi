"""The merge-conflict labeler, pinned against the failures that silenced it.

It previously tried to create its labels without a checkout or ``--repo``, so
every ``gh label create`` died with "fatal: not a git repository" and the
labels were never created. It also targeted ``merge-ready``, a near-duplicate
of the ``ready-for-merge`` label the repository already has.

It then read ``mergeStateStatus`` exactly once. GitHub computes mergeability
lazily and answers ``UNKNOWN`` for a moment after every push, so the one read
matched no ``case`` branch and no label was ever applied. The polling loop and
the explicit ``UNKNOWN`` branch below are what close that hole.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFLICTS = ROOT / ".github" / "workflows" / "label-merge-conflicts.yml"


def test_conflict_labels_are_created_with_an_explicit_repo():
    text = CONFLICTS.read_text(encoding="utf-8")
    assert "gh label create" in text
    assert "--repo" in text


def test_the_existing_ready_for_merge_label_is_reused():
    text = CONFLICTS.read_text(encoding="utf-8")
    assert "ready-for-merge" in text
    assert "merge-ready" not in text


def test_conflicts_workflow_declares_issues_write():
    text = CONFLICTS.read_text(encoding="utf-8")
    assert "issues: write" in text


def test_the_workflow_checks_out_before_creating_labels():
    """gh label create still needs a repository, so a checkout is present."""
    text = CONFLICTS.read_text(encoding="utf-8")
    assert "actions/checkout" in text


def test_the_workflow_does_not_persist_credentials_into_the_checkout():
    """A labeler never pushes, so the token must not sit in the git config."""
    text = CONFLICTS.read_text(encoding="utf-8")
    assert "persist-credentials: false" in text


def test_merge_state_is_polled_until_it_is_decided():
    """One read of mergeStateStatus returned UNKNOWN and labelled nothing."""
    text = CONFLICTS.read_text(encoding="utf-8")
    assert "for attempt in" in text, "merge state is read once, not polled"
    assert '!= "UNKNOWN"' in text, "the poll never tests for the undecided state"


def test_the_undecided_state_leaves_labels_alone():
    """UNKNOWN is not a conflict and not a clean state; do not guess."""
    text = CONFLICTS.read_text(encoding="utf-8")
    assert "UNKNOWN)" in text, "no explicit UNKNOWN case branch"
    # The UNKNOWN branch must not add or remove a label.
    unknown_branch = text.split("UNKNOWN)", 1)[1].split(";;", 1)[0]
    assert "--add-label" not in unknown_branch
    assert "--remove-label" not in unknown_branch


def test_a_conflict_adds_the_label_and_a_clean_state_clears_it():
    text = CONFLICTS.read_text(encoding="utf-8")
    dirty_branch = text.split("dirty)", 1)[1].split(";;", 1)[0]
    clean_branch = text.split("clean)", 1)[1].split(";;", 1)[0]
    assert "--add-label merge-conflict" in dirty_branch
    assert "--add-label ready-for-merge" in clean_branch
    assert "--remove-label merge-conflict" in clean_branch


TEMPLATE = ROOT / ".github" / "pull_request_template.md"


def test_the_template_ships_a_parseable_metadata_block():
    """The documented example must itself parse, or it teaches agents to fail."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from pr_labels import telemetry_labels

    body = TEMPLATE.read_text(encoding="utf-8")
    assert "AGENT_METADATA" in body
    # An unfilled template must not assert anything false about the PR.
    assert telemetry_labels(body) == set()


def test_the_template_documents_every_supported_metadata_key():
    body = TEMPLATE.read_text(encoding="utf-8")
    assert "has_breaking_changes" in body
    assert "agent_confidence" in body


def test_a_completed_check_suite_keeps_the_ready_label_current():
    """`ready-for-merge` needs a `clean` state, which only exists after the
    checks pass; the six-hourly sweep used to be the only thing looking again."""
    text = CONFLICTS.read_text(encoding="utf-8")
    assert "check_suite:" in text
    assert "github.event.check_suite.head_sha" in text


def test_the_development_guide_documents_the_labeler():
    guide = (ROOT / "docs" / "development.md").read_text(encoding="utf-8")
    assert "PR labels" in guide
    assert "AGENT_METADATA" in guide
