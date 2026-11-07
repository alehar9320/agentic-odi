"""Compute the merge-state labels a reviewer should see on a pull request.

Every function here is pure: give it facts about a pull request, get labels
back. The workflow gathers the facts with ``gh``; this module never touches
the network, so its behaviour can be pinned by tests.

``ci-pending`` means "CI is still running but nothing is blocking" — the PR
is unblocked and ready for a human to review once CI turns green.

``ready-for-merge`` means "CI is green, no merge conflicts, not a draft,
no changes requested" — the label the maintainer's filter keys on.
"""

from __future__ import annotations

import argparse
import json
import sys

# Every label this system may add or remove. It deliberately excludes the
# static axes (size, area, provenance, risk tier): those belong to the PR
# Risk Classification workflow and to scripts/pr_labels.py.
MANAGED_LABELS: frozenset[str] = frozenset({"ci-pending", "ready-for-merge"})


def _checks(facts: dict) -> list[dict]:
    """Return the list of check runs, accepting several payload shapes."""
    checks = (
        facts.get("check_runs")
        or facts.get("status_check_rollup")
        or facts.get("statusCheckRollup")
        or []
    )
    return [c for c in checks if isinstance(c, dict)]


def _conclusion(check: dict) -> str | None:
    return check.get("conclusion")


def _status(check: dict) -> str | None:
    return check.get("status")


def compute_ci_labels(facts: dict) -> set[str]:
    """Return the merge-state labels implied by one pull request's state.

    ``facts`` may be missing any key; a missing key is an absent signal,
    never an error, because a half-populated payload should still label the
    PR.
    """
    checks = _checks(facts)
    completed = [c for c in checks if _status(c) == "COMPLETED"]
    pending = [c for c in checks if _status(c) != "COMPLETED"]

    conclusions = [_conclusion(c) for c in completed]
    ci_green = bool(completed) and all(c == "SUCCESS" for c in conclusions) and not pending

    is_draft = bool(facts.get("is_draft"))
    mergeable = facts.get("mergeable")
    conflicting = mergeable == "CONFLICTING"
    check_failure = any(_conclusion(c) in {"FAILURE", "CANCELLED"} for c in completed)
    changes_requested = any(
        review.get("state") == "CHANGES_REQUESTED" for review in (facts.get("reviews") or [])
    )

    # Blocked means something a human must fix before the PR is reviewable:
    # a draft, merge conflicts, a failing/cancelled check, or requested
    # changes. A PR that is merely waiting on CI is not blocked.
    blocked = is_draft or conflicting or check_failure or changes_requested

    if blocked:
        return set()
    if ci_green:
        return {"ready-for-merge"}
    # Unblocked but CI has not turned green yet: either checks are still
    # running, or they exist but none is green. A PR with no checks at all
    # gets no label until CI creates its first check run.
    if checks:
        return {"ci-pending"}
    return set()


def main(argv: list[str] | None = None) -> int:
    """Print labels for the workflow: computed from stdin, or ``--managed``."""
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
            "read a JSON object with is_draft, mergeable, review_decision, "
            "reviews, and check_runs keys, compute labels, and print them"
        ),
    )
    args = parser.parse_args(argv)

    if args.managed:
        for label in sorted(MANAGED_LABELS):
            print(label)
        return 0

    try:
        if args.facts:
            with open(args.facts, encoding="utf-8") as handle:
                facts = json.load(handle)
        else:
            facts = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, AttributeError) as error:
        print(f"could not read pull request facts: {error}", file=sys.stderr)
        return 1

    if not isinstance(facts, dict):
        print("pull request facts must be a JSON object", file=sys.stderr)
        return 1

    for label in sorted(compute_ci_labels(facts)):
        print(label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
