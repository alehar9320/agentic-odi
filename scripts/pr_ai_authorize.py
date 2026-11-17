"""Compute whether a pull request carries the ``ai-merge-authorized`` label.

The label marks a pull request as authorized for AI-agent auto-merge. It is
purely AND-gated: every condition below must hold, and any failure removes the
label.

Gates
-----
1. Trust label        — the PR carries ``ai-merge-safe``.
2. CI green           -- the head commit's check suite is complete and green.
3. No merge conflicts — the PR carries ``ready-for-merge``.
4. Hygiene            — open pull request, targets ``main``, not a draft.

Gate 2 is judged from the check runs GitHub Actions reports on the head commit.
It is deliberately *not* the legacy combined commit status: that endpoint only
carries the statuses third-party apps post (in this repository, Chromatic), so
it reads ``success`` while every Actions job is still queued. Reading it as "CI
green" armed auto-merge on #1100 about a minute after a push, before CI had run
(ADR 0009).

Every function here is pure: give it facts about a pull request, get the label
back (or an empty set). The workflow gathers the facts with ``gh``; this module
never touches the network, so its behaviour can be pinned by tests.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

LABEL = "ai-merge-authorized"

# Labels the PR must carry to be authorized for AI merge.
REQUIRED_LABELS = frozenset({"ai-merge-safe", "ready-for-merge"})

# The only label this system may add or remove. It deliberately excludes the
# risk tiers and the merge-state labels: those are produced by the pr-ai-merge
# and label-merge-conflicts workflows, and removing them here would fight those
# jobs.
MANAGED_LABELS: frozenset[str] = frozenset({LABEL})

# The checks the ``main-requires-ci-green`` ruleset requires by name. A head
# commit is green only when both are present and successful; absent is pending,
# never green.
REQUIRED_CHECKS: tuple[str, ...] = ("CI green", "PR guardrails")

# Checks allowed to be red without blocking a merge. The browser suite is
# advisory until ``AGENTIC_ODI_E2E_BLOCKING`` turns it into a gate -- the same
# repository variable ``.github/workflows/ci.yml`` reads. One switch means the
# merge path and the aggregate cannot disagree about the policy.
ADVISORY_CHECKS: frozenset[str] = frozenset({"End-to-end"})

# Conclusions that mean a check ran and failed. ``cancelled``, ``skipped``,
# ``neutral`` and ``stale`` are not failures: a cancelled run was superseded,
# and a cancelled CI run cannot produce a green ``CI green`` aggregate anyway.
BLOCKING_CONCLUSIONS: frozenset[str] = frozenset(
    {"failure", "timed_out", "action_required", "startup_failure"}
)
NON_BLOCKING_CONCLUSIONS: frozenset[str] = frozenset(
    {"success", "neutral", "skipped", "stale", "cancelled"}
)

# Check runs from other GitHub Apps (CodeRabbit, Cloudflare, Chromatic) are
# reported by the summary but do not gate: they are not required checks, and a
# vendor outage must not stop merges.
ACTIONS_APP = "github-actions"


def advisory_checks() -> frozenset[str]:
    """The advisory set, honouring the repository's e2e policy switch."""
    if os.environ.get("AGENTIC_ODI_E2E_BLOCKING", "").strip().lower() == "true":
        return frozenset()
    return ADVISORY_CHECKS


def _is_actions_check(run: dict) -> bool:
    """True when the run came from GitHub Actions (or names no app at all)."""
    app = run.get("app")
    if isinstance(app, dict) and app.get("slug"):
        return str(app["slug"]) == ACTIONS_APP
    return True


def _run_state(run: dict) -> str:
    """Classify one check run as ``blocking``, ``pending`` or ``ok``.

    An unrecognised conclusion is treated as pending, so a new GitHub verdict
    cannot silently pass the gate.
    """
    if str(run.get("status") or "").strip().lower() != "completed":
        return "pending"
    conclusion = str(run.get("conclusion") or "").strip().lower()
    if conclusion in BLOCKING_CONCLUSIONS:
        return "blocking"
    if conclusion in NON_BLOCKING_CONCLUSIONS:
        return "ok"
    return "pending"


def compute_ci_state(facts: dict) -> dict:
    """Judge the head commit from its check runs, fail-closed.

    Returns ``state`` (``green``, ``pending`` or ``red``) plus the names behind
    the verdict: ``blocking`` (ran and failed), ``pending`` (not finished),
    ``missing`` (required check never reported) and ``advisory`` (failed but
    allowed). Only ``green`` may authorize a merge.
    """
    checks = [run for run in facts.get("checks") or [] if isinstance(run, dict)]
    required = tuple(facts.get("required") or REQUIRED_CHECKS)
    advisory = advisory_checks()

    runs_by_name: dict[str, list[dict]] = {}
    for run in checks:
        if not _is_actions_check(run):
            continue
        name = str(run.get("name") or "")
        if name:
            runs_by_name.setdefault(name, []).append(run)

    blocking: list[str] = []
    pending: list[str] = []
    missing: list[str] = []
    unconfirmed: list[str] = []
    advisory_failed: list[str] = []

    # The required aggregates first: absent is pending, not green, and a
    # required check that never reported `success` is not green either -- a
    # cancelled `CI green` is not a passing CI.
    for name in required:
        runs = runs_by_name.get(name) or []
        if not runs:
            missing.append(name)
        elif any(_run_state(run) == "blocking" for run in runs):
            blocking.append(name)
        elif any(_run_state(run) == "pending" for run in runs):
            pending.append(name)
        elif not any(str(run.get("conclusion") or "").strip().lower() == "success" for run in runs):
            unconfirmed.append(name)

    # Everything else that Actions reports on the head commit.
    for name, runs in runs_by_name.items():
        if name in required:
            continue
        if any(_run_state(run) == "blocking" for run in runs):
            if name in advisory:
                advisory_failed.append(name)
            else:
                blocking.append(name)
        elif any(_run_state(run) == "pending" for run in runs):
            pending.append(name)

    if blocking:
        state = "red"
        reason = "failing checks: " + ", ".join(sorted(set(blocking)))
    elif missing:
        state = "pending"
        reason = "required checks not reported yet: " + ", ".join(sorted(set(missing)))
    elif unconfirmed:
        state = "pending"
        reason = "required checks never reported success: " + ", ".join(sorted(set(unconfirmed)))
    elif pending:
        state = "pending"
        reason = "checks still running: " + ", ".join(sorted(set(pending)))
    else:
        state = "green"
        reason = "every required check and every non-advisory check run is green"

    return {
        "state": state,
        "reason": reason,
        "blocking": sorted(set(blocking)),
        "pending": sorted(set(pending)),
        "missing": sorted(set(missing)),
        "unconfirmed": sorted(set(unconfirmed)),
        "advisory": sorted(set(advisory_failed)),
    }


def compute_ai_merge_authorized(facts: dict) -> set[str]:
    """Return ``{ai-merge-authorized}`` iff every gate passes, else ``set()``."""
    labels = set(facts.get("labels") or [])

    # Gate 1: trust label.
    if "ai-merge-safe" not in labels:
        return set()
    # Gate 2: CI green — the head commit's check suite, never the legacy
    # combined commit status (see compute_ci_state).
    if compute_ci_state(facts)["state"] != "green":
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
    parser.add_argument(
        "--ci-state",
        action="store_true",
        help=(
            "print the check-suite verdict as JSON instead of the label; the "
            "merge-act workflow reads its state field before arming auto-merge"
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

    if args.ci_state:
        print(json.dumps(compute_ci_state(facts), indent=2, sort_keys=True))
        return 0

    result = compute_ai_merge_authorized(facts)
    for label in sorted(result):
        print(label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
