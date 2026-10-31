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


@pytest.mark.parametrize(
    "identity",
    [
        "openhands <openhands@all-hands.dev>",
        "google-labs-jules[bot] <1+x@users.noreply.github.com>",
        "opencode-agent <opencode-agent@users.noreply.github.com>",
        "Claude <noreply@anthropic.com>",
        "dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>",
    ],
)
def test_agent_commit_identities_are_detected(identity):
    """The tool name is the signal; these are the identities this repo sees."""
    assert classify("alehar9320", "User", "fix/thing", [identity]) == AGENT


@pytest.mark.parametrize(
    "identity",
    [
        "Alexander <alehar9320@users.noreply.github.com>",
        "Sam <sam@example.com>",
        "Contributor <c@example.com>",
        "Maria <maria@company.io>",
    ],
)
def test_human_commit_identities_are_not_agents(identity):
    """Word-boundary matching: 'amp' in 'example' must not look like an agent."""
    assert classify("alehar9320", "User", "fix/thing", [identity]) == HUMAN


def test_classify_survives_malformed_commit_entries():
    """A wrong-shaped commits field must not crash the labeler.

    Raw API commit objects can reach the CLI instead of "Name <email>" strings.
    Raising here would fail the workflow, which the spec forbids.
    """
    assert classify("alehar9320", "User", "fix/x", [{"author": {"name": "x"}}]) == HUMAN
    assert classify("alehar9320", "User", "fix/x", [None, 42, "human <h@x>"]) == HUMAN
