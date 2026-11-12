"""The AI merge trust labeler, pinned so a silent gate failure cannot ship.

Each gate is AND-gated: any single failure must remove the label.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from pr_ai_merge import (  # noqa: E402
    LABEL,
    MANAGED_LABELS,
    _size_label,
    compute_ai_merge_label,
)

PROTECTED = """# Critical paths that must never be deleted on main.
.github/workflows/pages.yml
.github/workflows/ci.yml
"""


def base_facts(**overrides):
    facts = {
        "author": {"login": "alehar9320", "type": "User"},
        "branch": "fix/a-small-typo",
        "commits": [],
        "body": "",
        "files": [],
        "labels": [],
        "state": "open",
        "draft": False,
        "base": {"ref": "main"},
    }
    facts.update(overrides)
    return facts


def labelled(*labels):
    return base_facts(labels=list(labels))


# ---------------------------------------------------------------------------
# Gate 1 — low disruption ("safe to merge")
# ---------------------------------------------------------------------------


def test_requires_safe_to_merge():
    facts = labelled("ready-for-merge", "size/XS")
    assert compute_ai_merge_label(facts, PROTECTED) == set()


def test_safe_to_merge_satisfies_gate_one():
    facts = labelled("safe to merge", "ready-for-merge", "size/XS")
    assert compute_ai_merge_label(facts, PROTECTED) == {LABEL}


# ---------------------------------------------------------------------------
# Gate 2 — CI green, no conflicts ("ready-for-merge")
# ---------------------------------------------------------------------------


def test_requires_ready_for_merge():
    facts = labelled("safe to merge", "size/XS")
    assert compute_ai_merge_label(facts, PROTECTED) == set()


# ---------------------------------------------------------------------------
# Gate 3 — small enough (size/XS or size/S)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "additions,deletions,expected",
    [
        (0, 0, {LABEL}),  # size/XS
        (49, 0, {LABEL}),  # size/XS
        (50, 0, {LABEL}),  # size/S
        (249, 0, {LABEL}),  # size/S
        (250, 0, set()),  # size/M — too large
        (799, 0, set()),  # size/M — too large
        (2000, 0, set()),  # size/XL — too large
    ],
)
def test_size_boundaries(additions, deletions, expected):
    facts = base_facts(
        files=[{"filename": "a.py", "additions": additions, "deletions": deletions}],
        labels=["safe to merge", "ready-for-merge"],
    )
    assert compute_ai_merge_label(facts, PROTECTED) == expected


def test_size_label_is_xs_or_s():
    assert _size_label([{"additions": 10, "deletions": 0}]) == "size/XS"
    assert _size_label([{"additions": 249, "deletions": 0}]) == "size/S"
    assert _size_label([{"additions": 250, "deletions": 0}]) == "size/M"


# ---------------------------------------------------------------------------
# Gate 4 — clean telemetry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "telemetry",
    [
        ["breaking change"],
        ["needs deep dive"],
        ["telemetry invalid"],
        ["breaking change", "needs deep dive"],
    ],
)
def test_disqualifying_telemetry_removes_label(telemetry):
    facts = labelled("safe to merge", "ready-for-merge", "size/XS", *telemetry)
    assert compute_ai_merge_label(facts, PROTECTED) == set()


def test_no_telemetry_keeps_label():
    facts = labelled("safe to merge", "ready-for-merge", "size/XS")
    assert compute_ai_merge_label(facts, PROTECTED) == {LABEL}


# ---------------------------------------------------------------------------
# Gate 5 — non-sensitive areas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "area",
    ["area/ci", "area/infra", "area/release"],
)
def test_sensitive_area_removes_label(area):
    facts = labelled("safe to merge", "ready-for-merge", "size/XS", area)
    assert compute_ai_merge_label(facts, PROTECTED) == set()


def test_dependency_change_removes_label():
    facts = base_facts(
        files=[{"filename": "pyproject.toml", "additions": 1, "deletions": 0}],
        labels=["safe to merge", "ready-for-merge", "size/XS", "dependencies"],
    )
    assert compute_ai_merge_label(facts, PROTECTED) == set()


def test_touches_ci_workflow_removes_label():
    facts = base_facts(
        files=[{"filename": ".github/workflows/ci.yml", "additions": 1, "deletions": 0}],
        labels=["safe to merge", "ready-for-merge", "size/XS"],
    )
    assert compute_ai_merge_label(facts, PROTECTED) == set()


def test_touches_ci_dir_removes_label():
    facts = base_facts(
        files=[{"filename": ".ci/protected-files.txt", "additions": 1, "deletions": 0}],
        labels=["safe to merge", "ready-for-merge", "size/XS"],
    )
    assert compute_ai_merge_label(facts, PROTECTED) == set()


def test_deleted_protected_file_removes_label():
    facts = base_facts(
        files=[
            {
                "filename": ".github/workflows/pages.yml",
                "additions": 0,
                "deletions": 10,
                "status": "removed",
            }
        ],
        labels=["safe to merge", "ready-for-merge", "size/XS"],
    )
    assert compute_ai_merge_label(facts, PROTECTED) == set()


def test_modified_protected_file_is_not_deleted():
    """Editing a protected file is still flagged by the area gate, but a pure
    modification is not treated as a deletion. The area gate above covers it."""
    facts = base_facts(
        files=[
            {
                "filename": ".github/workflows/ci.yml",
                "additions": 1,
                "deletions": 0,
                "status": "modified",
            }
        ],
        labels=["safe to merge", "ready-for-merge", "size/XS"],
    )
    assert compute_ai_merge_label(facts, PROTECTED) == set()


# ---------------------------------------------------------------------------
# Gate 6 — hygiene
# ---------------------------------------------------------------------------


def test_closed_pr_removes_label():
    facts = labelled("safe to merge", "ready-for-merge", "size/XS")
    facts["state"] = "closed"
    assert compute_ai_merge_label(facts, PROTECTED) == set()


def test_draft_pr_removes_label():
    facts = labelled("safe to merge", "ready-for-merge", "size/XS")
    facts["draft"] = True
    assert compute_ai_merge_label(facts, PROTECTED) == set()


def test_pr_not_targeting_main_removes_label():
    facts = labelled("safe to merge", "ready-for-merge", "size/XS")
    facts["base"] = {"ref": "feature/x"}
    assert compute_ai_merge_label(facts, PROTECTED) == set()


# ---------------------------------------------------------------------------
# All gates pass
# ---------------------------------------------------------------------------


def test_all_gates_pass_applies_label():
    facts = labelled("safe to merge", "ready-for-merge", "size/XS")
    facts["files"] = [{"filename": "README.md", "additions": 3, "deletions": 1}]
    assert compute_ai_merge_label(facts, PROTECTED) == {LABEL}


# ---------------------------------------------------------------------------
# Tolerances
# ---------------------------------------------------------------------------


def test_missing_keys_are_absent_signals_not_errors():
    assert compute_ai_merge_label({}, PROTECTED) == set()


def test_managed_label_owns_only_ai_merge_safe():
    assert MANAGED_LABELS == frozenset({LABEL})


def test_the_cli_prints_nothing_when_no_gate_passes():
    script = Path(__file__).resolve().parents[2] / "scripts" / "pr_ai_merge.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(labelled("size/XS")),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_the_cli_prints_the_label_when_all_gates_pass():
    script = Path(__file__).resolve().parents[2] / "scripts" / "pr_ai_merge.py"
    facts = labelled("safe to merge", "ready-for-merge", "size/XS")
    facts["files"] = [{"filename": "README.md", "additions": 3, "deletions": 1}]
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
    script = Path(__file__).resolve().parents[2] / "scripts" / "pr_ai_merge.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "could not read" in result.stderr


def test_managed_cli_prints_only_ai_merge_safe():
    script = Path(__file__).resolve().parents[2] / "scripts" / "pr_ai_merge.py"
    result = subprocess.run(
        [sys.executable, str(script), "--managed"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == LABEL
