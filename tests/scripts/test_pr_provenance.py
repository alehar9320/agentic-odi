from __future__ import annotations

import pytest
from pr_provenance import classify

HUMAN = "👤 human"
AGENT = "🤖 agent"


@pytest.mark.parametrize(
    "login,user_type,branch,commits,expected",
    [
        # The spec's own rule, which marks nothing in this repo.
        ("some-bot[bot]", "Bot", "feat/thing", [], AGENT),
        # What this repo actually looks like: owner's account, agent branch.
        ("alehar9320", "User", "slay/6538dc1a-promote-evidence", [], AGENT),
        ("alehar9320", "User", "jules/fix-the-thing", [], AGENT),
        # Agent identity visible only in the commit, not the branch.
        (
            "alehar9320",
            "User",
            "fix/release",
            ["opencode-agent <opencode-agent@users.noreply.github.com>"],
            AGENT,
        ),
        (
            "alehar9320",
            "User",
            "fix/release",
            ["google-labs-jules[bot] <161369871+google-labs-jules[bot]@users.noreply.github.com>"],
            AGENT,
        ),
        # A genuine human branch with a human commit.
        (
            "alehar9320",
            "User",
            "fix/studio-api-outcomes-errors",
            ["Alexander <alehar9320@users.noreply.github.com>"],
            HUMAN,
        ),
        # Unknown prefix + human commit stays human.
        ("contributor", "User", "patch-1", ["Contributor <c@example.com>"], HUMAN),
    ],
)
def test_classify(login, user_type, branch, commits, expected):
    assert classify(login, user_type, branch, commits) == expected


def test_a_human_branch_never_overrides_a_bot_commit():
    assert classify("alehar9320", "User", "fix/x", ["dependabot[bot] <x@y>"]) == AGENT


def test_the_numeric_suffix_alone_is_not_enough():
    """A 20-digit suffix on an unknown prefix is not a provenance signal."""
    assert classify("contributor", "User", "patch-1-18122562874758321467", []) == HUMAN
