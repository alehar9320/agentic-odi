"""The merge-conflict labeler, pinned against the failures that silenced it.

It previously tried to create its labels without a checkout or ``--repo``, so
every ``gh label create`` died with "fatal: not a git repository" and the
labels were never created. It also targeted ``merge-ready``, a near-duplicate
of the ``ready-for-merge`` label the repository already has.
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


def test_the_readme_documents_the_labeler():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "agent-pr" in readme or "Label" in readme
    assert "AGENT_METADATA" in readme
