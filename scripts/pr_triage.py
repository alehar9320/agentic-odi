"""Deterministic Tiered Automated Triage for pull requests.

Implements shift-left filtering so that a human never reads an unvetted AI PR.

A pull request is "vetted" -- eligible for a human to open the diff -- when it
carries the ``ready for human review`` gate label. The gate is applied by the
risk scoring job and means the automated vet is complete:

* Human author        -> vetted immediately (the author is the vetter).
* AI author + low risk    -> vetted after automated risk scoring (fast path).
* AI author + medium risk -> not vetted; needs an assigned reviewer.
* AI author + high risk   -> not vetted; blocking deep-dive review, never
  auto-merged.
* AI author + low risk + XL size -> not fast-tracked; size alone warrants a
  reviewer before a human reads the diff.

Everything here is pure: give it facts about a pull request, get triage
decisions back. No network, no LLM, and no pull request code is ever executed.
"""

from __future__ import annotations

import argparse
import json
import sys

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

# Gate label. When present, a human may open the diff. Absent = unvetted.
GATE_LABEL = "ready for human review"

# Advisory review-routing labels applied to AI PRs that cannot be fast-tracked.
REVIEWER_LABEL = "needs human review"
DEEP_DIVE_LABEL = "deep dive"

AI_LABEL = "🤖 agent"
HUMAN_LABEL = "👤 human"

LOW_TIER = "safe to merge"
MEDIUM_TIER = "needs a look"
HIGH_TIER = "danger zone"

# Size labels, in ascending order.
SIZE_LABELS = ("size/XS", "size/S", "size/M", "size/L", "size/XL")
XL_SIZE = "size/XL"

# AI PRs at this size or larger are never fast-tracked, even at low risk.
NO_FAST_TRACK_SIZE = XL_SIZE


# ---------------------------------------------------------------------------
# Triage decision
# ---------------------------------------------------------------------------


def is_ai_author(author_label: str) -> bool:
    """True when the pull request was authored by a coding agent."""
    return author_label == AI_LABEL


def triage(
    *,
    author_label: str,
    risk_tier: str,
    size_label: str,
) -> dict[str, object]:
    """Return the triage decision for one pull request.

    Returns a dict with:

    * ``gate``: whether ``ready for human review`` should be applied.
    * ``review_label``: advisory review-routing label, or ``None``.
    * ``reason``: human-readable explanation recorded on the PR summary.
    """
    ai = is_ai_author(author_label)

    # Human-authored PRs are vetted by their author; the AI rule does not apply.
    if not ai:
        return {
            "gate": True,
            "review_label": None,
            "reason": "human-authored; the author is the vetter",
        }

    # High risk: blocking deep-dive review. Never auto-merged, never gated.
    if risk_tier == HIGH_TIER:
        return {
            "gate": False,
            "review_label": DEEP_DIVE_LABEL,
            "reason": ("AI-authored high risk; blocking deep-dive review, never auto-merged"),
        }

    # Medium risk: needs an assigned human reviewer before anyone reads the diff.
    if risk_tier == MEDIUM_TIER:
        return {
            "gate": False,
            "review_label": REVIEWER_LABEL,
            "reason": "AI-authored medium risk; needs an assigned reviewer",
        }

    # Low risk. Fast-track only when the diff is not so large that size alone
    # warrants a first human pass.
    if risk_tier == LOW_TIER and size_label == NO_FAST_TRACK_SIZE:
        return {
            "gate": False,
            "review_label": REVIEWER_LABEL,
            "reason": "AI-authored low risk but XL size; needs a reviewer first",
        }

    if risk_tier == LOW_TIER:
        return {
            "gate": True,
            "review_label": None,
            "reason": "AI-authored low risk; automated vet complete",
        }

    # No recognizable risk tier: do not gate. Safer to let a human decide.
    return {
        "gate": False,
        "review_label": REVIEWER_LABEL,
        "reason": "risk tier not yet computed; awaiting automated scoring",
    }


def triage_label_decision(
    *,
    author_label: str,
    risk_tier: str,
    size_label: str,
) -> dict[str, object]:
    """Convenience wrapper returning only the labels to add / remove.

    Keys: ``add`` (labels to apply) and ``remove`` (labels to clear first) for
    the triage-related labels this system owns, plus ``reason`` and ``gate``.
    Removing an absent label is a harmless no-op, so clearing the full owned set
    each run keeps the label state exactly in sync with the decision.
    """
    decision = triage(
        author_label=author_label,
        risk_tier=risk_tier,
        size_label=size_label,
    )

    owned = {GATE_LABEL, REVIEWER_LABEL, DEEP_DIVE_LABEL}
    add: list[str] = []
    if decision["gate"]:
        add.append(GATE_LABEL)
    if decision["review_label"] is not None:
        add.append(decision["review_label"])

    return {
        "add": add,
        "remove": list(owned),
        "reason": decision["reason"],
        "gate": decision["gate"],
    }


def extract_facts(labels: set[str]) -> dict[str, str]:
    """Pull triage-relevant facts out of an existing label set."""
    author_label = HUMAN_LABEL
    if AI_LABEL in labels:
        author_label = AI_LABEL

    risk_tier = ""
    for tier in (LOW_TIER, MEDIUM_TIER, HIGH_TIER):
        if tier in labels:
            risk_tier = tier
            break

    size_label = ""
    for size_candidate in SIZE_LABELS:
        if size_candidate in labels:
            size_label = size_candidate
            break

    return {
        "author_label": author_label,
        "risk_tier": risk_tier,
        "size_label": size_label,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--labels",
        metavar="PATH",
        help="read newline-separated labels and print the triage decision as JSON",
    )
    args = parser.parse_args(argv)

    if args.labels:
        with open(args.labels, encoding="utf-8") as handle:
            labels = {line.strip() for line in handle if line.strip()}
        facts = extract_facts(labels)
        decision = triage_label_decision(
            author_label=facts["author_label"],
            risk_tier=facts["risk_tier"],
            size_label=facts["size_label"],
        )
        print(json.dumps({"facts": facts, "decision": decision}, indent=2))
        return 0

    parser.print_help(sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
