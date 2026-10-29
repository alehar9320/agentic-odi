"""Protected files must never be deleted on main.

A deletion of a protected file breaks GitHub Pages deployment or the site
contract. CI must fail red instead of staying green.

The test reads ``.ci/protected-files.txt`` and compares the current tree
against the base commit (the merge-base with the default branch, or the
previous commit on a direct push to main). If any protected file that
exists on the base is missing now, the test fails.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / ".ci" / "protected-files.txt"


def _protected_paths() -> list[Path]:
    paths: list[Path] = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        paths.append(ROOT / line)
    return paths


def _resolves(ref: str) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def _base_ref() -> str | None:
    """The ref to diff against, or None when this checkout has no history.

    CI checkouts are shallow (fetch-depth 1), so HEAD's ancestors are missing
    and neither origin/main nor HEAD~1 may exist. Unshallow so we can diff the
    PR branch against its merge-base with the default branch. Falls back to
    the previous commit on a direct push to main.
    """
    # Unshallow so we can walk ancestry even on a shallow checkout (e.g. a
    # pull request from a fork). If that fails we fall through to HEAD~1,
    # which will also fail red rather than silently passing.
    try:
        subprocess.check_output(
            ["git", "fetch", "--unshallow", "origin"],
            stderr=subprocess.DEVNULL,
            cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        pass
    for candidate in ("origin/main", "main"):
        try:
            base = subprocess.check_output(
                ["git", "merge-base", candidate, "HEAD"],
                text=True,
                cwd=ROOT,
            ).strip()
            if base:
                return base
        except subprocess.CalledProcessError:
            continue
    # Direct push to main with no fetchable default branch: compare to HEAD~1.
    if _resolves("HEAD~1"):
        return "HEAD~1"
    return None


def _deleted_files(base: str) -> set[str]:
    """Files deleted between ``base`` and HEAD."""
    output = subprocess.check_output(
        ["git", "diff", "--name-status", base, "HEAD"],
        text=True,
        cwd=ROOT,
    )
    deleted: set[str] = set()
    for line in output.splitlines():
        status, _, path = line.partition("\t")
        if status == "D":
            deleted.add(path)
    return deleted


def test_no_protected_file_is_deleted() -> None:
    base = _base_ref()
    if base is None:
        # Red, not skipped: an unchecked tree could be hiding a deletion. Say
        # why, so the fix (check out with the parent commit) is obvious.
        pytest.fail(
            "Cannot check protected files: this checkout has no base commit to diff "
            "against. Check out with history (actions/checkout fetch-depth: 2)."
        )
    deleted = _deleted_files(base)
    violations = []
    for path in _protected_paths():
        rel = str(path.relative_to(ROOT))
        if rel in deleted:
            violations.append(rel)

    assert not violations, (
        "Protected files must not be deleted: "
        + ", ".join(sorted(violations))
        + f"\nBase ref: {base}"
    )
