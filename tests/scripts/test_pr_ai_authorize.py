"""Test the AI merge authorization script (``scripts/pr_ai_authorize.py``)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from pr_ai_authorize import (  # noqa: E402
    LABEL,
    MANAGED_LABELS,
    compute_ai_merge_authorized,
)


def base_facts(**overrides):
    facts = {
        "author": {"login": "alehar9320", "type": "User"},
        "branch": "fix/a-small-typo",
        "commits": [],
        "body": "",
        "files": [],
        "labels": ["ai-merge-safe", "ready-for-merge"],
        "state": "open",
        "draft": False,
        "base": {"ref": "main"},
        "status": "success",
    }
    facts.update(overrides)
    return facts


# ---------------------------------------------------------------------------
# Gate 1 — trust label ("ai-merge-safe")
# ---------------------------------------------------------------------------


def test_requires_ai_merge_safe():
    facts = base_facts(labels=["ready-for-merge"], status="success")
    assert compute_ai_merge_authorized(facts) == set()


def test_ai_merge_safe_satisfies_gate_one():
    facts = base_facts(status="success")
    assert compute_ai_merge_authorized(facts) == {LABEL}


# ---------------------------------------------------------------------------
# Gate 2 — CI green (combined status == success)
# ---------------------------------------------------------------------------


def test_requires_ci_green():
    facts = base_facts(status="failure")
    assert compute_ai_merge_authorized(facts) == set()


def test_ci_green_satisfies_gate_two():
    facts = base_facts(status="success")
    assert compute_ai_merge_authorized(facts) == {LABEL}


@pytest.mark.parametrize("status", ["pending", "error", "expected", "failure", ""])
def test_non_success_status_removes_label(status):
    facts = base_facts(status=status)
    assert compute_ai_merge_authorized(facts) == set()


# ---------------------------------------------------------------------------
# Gate 3 — no merge conflicts ("ready-for-merge")
# ---------------------------------------------------------------------------


def test_requires_ready_for_merge():
    facts = base_facts(labels=["ai-merge-safe"], status="success")
    assert compute_ai_merge_authorized(facts) == set()


# ---------------------------------------------------------------------------
# Gate 4 — hygiene
# ---------------------------------------------------------------------------


def test_closed_pr_removes_label():
    facts = base_facts(state="closed", status="success")
    assert compute_ai_merge_authorized(facts) == set()


def test_draft_pr_removes_label():
    facts = base_facts(draft=True, status="success")
    assert compute_ai_merge_authorized(facts) == set()


def test_pr_not_targeting_main_removes_label():
    facts = base_facts(base={"ref": "feature/x"}, status="success")
    assert compute_ai_merge_authorized(facts) == set()


def test_pr_not_targeting_main_removes_label_string_base():
    """The workflow passes ``base`` as a plain string (``baseRefName``)."""
    facts = base_facts(base="feature/x", status="success")
    assert compute_ai_merge_authorized(facts) == set()


def test_missing_status_is_fail_closed():
    """A missing CI status must never allow the label."""
    facts = base_facts(status=None)
    del facts["status"]
    assert compute_ai_merge_authorized(facts) == set()


def test_missing_state_is_fail_closed():
    facts = base_facts(state=None, status="success")
    del facts["state"]
    assert compute_ai_merge_authorized(facts) == set()


def test_missing_base_is_fail_closed():
    facts = base_facts(base=None, status="success")
    del facts["base"]
    assert compute_ai_merge_authorized(facts) == set()


def test_uppercase_success_status_is_accepted():
    facts = base_facts(status="SUCCESS")
    assert compute_ai_merge_authorized(facts) == {LABEL}


# ---------------------------------------------------------------------------
# All gates pass
# ---------------------------------------------------------------------------


def test_all_gates_pass_applies_label():
    facts = base_facts(status="success")
    assert compute_ai_merge_authorized(facts) == {LABEL}


# ---------------------------------------------------------------------------
# Tolerances
# ---------------------------------------------------------------------------


def test_missing_keys_are_fail_closed_not_errors():
    assert compute_ai_merge_authorized({}) == set()


def test_managed_label_owns_only_ai_merge_authorized():
    assert MANAGED_LABELS == frozenset({LABEL})


def test_the_cli_prints_nothing_when_no_gate_passes():
    script = Path(__file__).resolve().parents[2] / "scripts" / "pr_ai_authorize.py"
    facts = base_facts(labels=["ready-for-merge"], status="success")
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(facts),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_the_cli_prints_the_label_when_all_gates_pass():
    script = Path(__file__).resolve().parents[2] / "scripts" / "pr_ai_authorize.py"
    facts = base_facts(status="success")
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(facts),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == LABEL


def test_the_cli_fails_loudly_on_unreadable_input():
    script = Path(__file__).resolve().parents[2] / "scripts" / "pr_ai_authorize.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "could not read" in result.stderr


def test_managed_cli_prints_only_ai_merge_authorized():
    script = Path(__file__).resolve().parents[2] / "scripts" / "pr_ai_authorize.py"
    result = subprocess.run(
        [sys.executable, str(script), "--managed"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == LABEL
