"""Compute the CI-state label a reviewer should see on a pull request.

Every function here is pure: give it facts about a pull request, get labels
back. The workflow gathers the facts with ``gh``; this module never touches the
network, so its behaviour can be pinned by tests.

``ci-pending`` means "a check is still running and nothing else blocks this pull
request" — CI is the only thing between it and a human review.

This module deliberately does **not** manage ``ready-for-merge``. The
[merge-conflict workflow](../.github/workflows/label-merge-conflicts.yml) is
that label's single writer: it derives the label from ``mergeStateStatus`` when
``CI`` completes, and the AI-merge path reads it (ADR 0009). A second writer
computing the same label from different facts would flap a gate a merge depends
on.
"""

from __future__ import annotations

import argparse
import json
import sys

#: The one label this system may add or remove. It deliberately excludes the
#: static axes (size, area, provenance, risk tier) owned by
#: ``scripts/pr_labels.py`` and the merge-state pair owned by
#: ``label-merge-conflicts.yml``.
LABEL = "ci-pending"
MANAGED_LABELS: frozenset[str] = frozenset({LABEL})

#: The only base branch this workflow labels. A pull request aimed anywhere else
#: is not part of the merge queue this label describes.
BASE_REF = "main"

_GREEN = "SUCCESS"
_FAILED = "FAILURE"

# A legacy commit status (``StatusContext`` in ``statusCheckRollup``) reports
# ``state`` rather than ``status``/``conclusion``. Map it onto the check-run
# vocabulary so one old status cannot pin the label forever.
_STATUS_CONTEXT_STATES: dict[str, tuple[str, str | None]] = {
    "SUCCESS": ("COMPLETED", _GREEN),
    "FAILURE": ("COMPLETED", _FAILED),
    "ERROR": ("COMPLETED", _FAILED),
    "PENDING": ("PENDING", None),
    "EXPECTED": ("PENDING", None),
}


def _checks(facts: dict) -> list[dict]:
    """Return the list of check runs, accepting several payload shapes."""
    checks = (
        facts.get("check_runs")
        or facts.get("status_check_rollup")
        or facts.get("statusCheckRollup")
        or []
    )
    return [c for c in checks if isinstance(c, dict)]


def _outcome(check: dict) -> tuple[str | None, str | None]:
    """``(status, conclusion)`` for a check run or a legacy status context.

    A status context carries ``state`` and no ``status``, so it is translated;
    an unknown state is reported verbatim and therefore counts as not completed,
    which is the conservative reading.
    """
    if check.get("status") is None and isinstance(check.get("state"), str):
        state = str(check["state"]).upper()
        return _STATUS_CONTEXT_STATES.get(state, (state, None))
    return check.get("status"), check.get("conclusion")


def compute_ci_labels(facts: dict) -> set[str]:
    """Return the labels implied by one pull request's state.

    ``facts`` may be missing any key; a missing key is an absent signal, never
    an error, because a half-populated payload should still label the PR.
    """
    base_ref = facts.get("base_ref_name")
    if isinstance(base_ref, str) and base_ref and base_ref != BASE_REF:
        return set()

    outcomes = [_outcome(check) for check in _checks(facts)]
    pending = [outcome for outcome in outcomes if outcome[0] != "COMPLETED"]
    conclusions = [outcome[1] for outcome in outcomes if outcome[0] == "COMPLETED"]

    is_draft = bool(facts.get("is_draft"))
    conflicting = facts.get("mergeable") == "CONFLICTING"
    check_failure = any(c in {"FAILURE", "CANCELLED", "TIMED_OUT"} for c in conclusions)
    changes_requested = any(
        review.get("state") == "CHANGES_REQUESTED" for review in (facts.get("reviews") or [])
    )

    # Blocked means something a human must fix before the PR is reviewable: a
    # draft, merge conflicts, a failing/cancelled check, or requested changes.
    # A PR that is merely waiting on CI is not blocked.
    blocked = is_draft or conflicting or check_failure or changes_requested
    if blocked:
        return set()

    # Nothing has created a check run yet: there is no CI state to report.
    if not outcomes:
        return set()

    # ``ci-pending`` is about work still in flight, so it needs a check that is
    # actually unfinished. Checks that are done but not green (skipped, neutral)
    # are not going to change on their own, so they are not "pending".
    if pending:
        return {LABEL}
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
            "read a JSON object with is_draft, mergeable, base_ref_name, "
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
