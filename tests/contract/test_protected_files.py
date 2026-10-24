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


def _base_ref() -> str:
    """The ref to diff against.

    On a pull request we diff against the merge-base with the default
    branch so we see what the branch changed. On a direct push to main we
    fall back to the previous commit.
    """
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
    return "HEAD~1"


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


def _git_revision_path(ref: str, path: Path) -> str:
    return str(path.relative_to(ROOT))


def test_no_protected_file_is_deleted() -> None:
    base = _base_ref()
    deleted = _deleted_files(base)
    violations = []
    for path in _protected_paths():
        rel = _git_revision_path(base, path)
        if rel in deleted:
            violations.append(rel)

    assert not violations, (
        "Protected files must not be deleted: "
        + ", ".join(sorted(violations))
        + f"\nBase ref: {base}"
    )
