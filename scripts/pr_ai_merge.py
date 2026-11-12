"""Compute whether a pull request carries the ``ai-merge-safe`` trust label.

The label marks a pull request as safe enough for an AI agent to merge without
human review. It is purely AND-gated: every condition below must hold, and any
failure removes the label.

Gates
-----
1. Low disruption      — the PR carries ``safe to merge`` (risk score <= 20).
2. CI green, no conflict — the PR carries ``ready-for-merge``.
3. Small enough        — size is ``size/XS`` or ``size/S`` (< 250 lines).
4. Clean telemetry     — none of ``breaking change``, ``needs deep dive``,
                         ``telemetry invalid``.
5. Non-sensitive areas — the diff touches no CI/infra/release path, no protected
                         file (``.ci/protected-files.txt``) is deleted, and it
                         is not a dependency change.
6. Hygiene             — open pull request, targets ``main``, not a draft.

Every function here is pure: give it facts about a pull request, get the label
back (or an empty set). The workflow gathers the facts with ``gh``; this module
never touches the network, so its behaviour can be pinned by tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pr_labels import is_dependency_change, size_label

LABEL = "ai-merge-safe"

# Area labels whose changes are too sensitive for an unattended AI merge.
SENSITIVE_AREAS = frozenset({"area/ci", "area/infra", "area/release"})

# File prefixes that are always off-limits for AI merge, regardless of area.
SENSITIVE_PREFIXES = (".github/workflows/", ".ci/")

# Telemetry labels that disqualify a PR from AI merge.
DISQUALIFYING_TELEMETRY = frozenset({"breaking change", "needs deep dive", "telemetry invalid"})

# Risk / merge-state labels the PR must carry.
REQUIRED_LABELS = frozenset({"safe to merge", "ready-for-merge"})

# Sizes small enough for an AI agent to merge without a human re-reading the diff.
MERGE_SAFE_SIZES = frozenset({"size/XS", "size/S"})

# The only label this system may add or remove. It deliberately excludes the
# risk tiers and the merge-state labels: those are produced by the pr-risk and
# label-merge-conflicts workflows, and removing them here would fight those jobs.
MANAGED_LABELS: frozenset[str] = frozenset({LABEL})


def _paths(filenames):
    return [f.replace("\\", "/") for f in filenames or []]


def _is_removed(entry) -> bool:
    """A file the pull request deletes (GitHub files API reports ``removed``)."""
    return (entry.get("status") or "").lower() == "removed"


def _load_protected_files() -> str:
    """Read ``.ci/protected-files.txt`` from the repository root.

    The script lives in ``scripts/``, so the repository root is its parent
    directory and the file is found regardless of the working directory.
    """
    candidate = Path(__file__).resolve().parents[1] / ".ci" / "protected-files.txt"
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return ""


def _deleted_protected_file(files, protected_text) -> bool:
    """True when a protected file is deleted by this pull request."""
    protected = {
        line.strip()
        for line in protected_text.splitlines()
        if line.strip() and not line.startswith("#")
    }
    for entry in files or []:
        if not isinstance(entry, dict) or not _is_removed(entry):
            continue
        path = entry.get("filename", "").replace("\\", "/")
        if path in protected:
            return True
    return False


def _touches_sensitive_area(filenames, labels) -> bool:
    """True when the diff reaches CI, infra, release, or a protected path."""
    if labels & SENSITIVE_AREAS:
        return True
    for path in _paths(filenames):
        if path.startswith(SENSITIVE_PREFIXES):
            return True
    return False


def _size_label(files) -> str:
    additions = sum(int(e.get("additions") or 0) for e in files if isinstance(e, dict))
    deletions = sum(int(e.get("deletions") or 0) for e in files if isinstance(e, dict))
    return size_label(additions, deletions)


def _base_branch(facts) -> str | None:
    base = facts.get("base")
    if isinstance(base, dict):
        return base.get("ref")
    return facts.get("base_ref")


def compute_ai_merge_label(facts: dict, protected_files_text: str | None = None) -> set[str]:
    """Return ``{ai-merge-safe}`` iff every gate passes, else ``set()``."""
    if protected_files_text is None:
        protected_files_text = _load_protected_files()

    files = facts.get("files") or []
    filenames = [e.get("filename", "") for e in files if isinstance(e, dict)]
    labels = set(facts.get("labels") or [])

    # Gate 6: hygiene — open, targets main, not a draft.
    if facts.get("state") not in (None, "open"):
        return set()
    if facts.get("draft") is True:
        return set()
    base = _base_branch(facts)
    if base is not None and base != "main":
        return set()

    # Gate 1: low disruption.
    if "safe to merge" not in labels:
        return set()
    # Gate 2: CI green, no merge conflicts.
    if "ready-for-merge" not in labels:
        return set()
    # Gate 3: small enough.
    if _size_label(files) not in MERGE_SAFE_SIZES:
        return set()
    # Gate 4: clean telemetry.
    if labels & DISQUALIFYING_TELEMETRY:
        return set()
    # Gate 5: non-sensitive areas.
    if is_dependency_change(filenames):
        return set()
    if _touches_sensitive_area(filenames, labels):
        return set()
    if _deleted_protected_file(files, protected_files_text):
        return set()

    return {LABEL}


def main(argv: list[str] | None = None) -> int:
    """Print the label for the workflow, or ``--managed`` to list owned labels."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--managed",
        action="store_true",
        help="print every label this system may add or remove, then exit",
    )
    parser.add_argument(
        "--facts",
        metavar="PATH",
        help=(
            "read a JSON object of pull request facts and print the computed "
            "label (or nothing when no gate fails)"
        ),
    )
    args = parser.parse_args(argv)

    if args.managed:
        print(LABEL)
        return 0

    if args.facts:
        try:
            with open(args.facts, encoding="utf-8") as handle:
                facts = json.load(handle)
        except (json.JSONDecodeError, OSError) as error:
            print(f"could not read pull request facts: {error}", file=sys.stderr)
            return 1
    else:
        try:
            facts = json.load(sys.stdin)
        except json.JSONDecodeError as error:
            print(f"could not read pull request facts: {error}", file=sys.stderr)
            return 1

    result = compute_ai_merge_label(facts)
    for label in sorted(result):
        print(label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
