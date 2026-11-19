"""Compute whether a pull request carries the ``ai-merge-authorized`` label.

The label marks a pull request as authorized for AI-agent auto-merge. It is
purely AND-gated: every condition below must hold, and any failure removes the
label.

Gates
-----
1. Trust label        — the PR carries ``ai-merge-safe``.
2. CI green           -- the combined status of the head commit is ``success``.
3. No merge conflicts — the PR carries ``ready-for-merge``.
4. Hygiene            — open pull request, targets ``main``, not a draft.

Every function here is pure: give it facts about a pull request, get the label
back (or an empty set). The workflow gathers the facts with ``gh``; this module
never touches the network, so its behaviour can be pinned by tests.
"""

from __future__ import annotations

import argparse
import json
import sys

LABEL = "ai-merge-authorized"

# Labels the PR must carry to be authorized for AI merge.
REQUIRED_LABELS = frozenset({"ai-merge-safe", "ready-for-merge"})

# The only label this system may add or remove. It deliberately excludes the
# risk tiers and the merge-state labels: those are produced by the pr-ai-merge
# and label-merge-conflicts workflows, and removing them here would fight those
# jobs.
MANAGED_LABELS: frozenset[str] = frozenset({LABEL})


def compute_ai_merge_authorized(facts: dict) -> set[str]:
    """Return ``{ai-merge-authorized}`` iff every gate passes, else ``set()``."""
    labels = set(facts.get("labels") or [])

    # Gate 1: trust label.
    if "ai-merge-safe" not in labels:
        return set()
    # Gate 2: CI green — combined status of the head commit.
    if str(facts.get("status") or "").lower() != "success":
        return set()
    # Gate 3: no merge conflicts.
    if "ready-for-merge" not in labels:
        return set()
    # Gate 4: hygiene — open, targets main, not a draft.
    if str(facts.get("state") or "").lower() != "open":
        return set()
    if facts.get("draft") is True:
        return set()
    base = facts.get("base")
    if isinstance(base, dict):
        base = base.get("ref")
    if base is None or base != "main":
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

    result = compute_ai_merge_authorized(facts)
    for label in sorted(result):
        print(label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
