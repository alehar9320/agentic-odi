"""Decide whether a pull request was authored by a coding agent or a human.

Authorship is the first thing a reviewer wants from a label, and the obvious
signal — the pull request's ``user`` — is useless in this repository: agents
push on the owner's account, so every PR reports the same ``User`` login. The
signal lives one level down, in the commit identity and the branch name.
"""

from __future__ import annotations

import re

AGENT_LABEL = "🤖 agent"
HUMAN_LABEL = "👤 human"

# Branch prefixes that identify an agent. Derived from the prefixes observed in
# this repository (`slay` and `jules`) plus the common coding tools.
AGENT_BRANCH_PREFIXES: frozenset[str] = frozenset(
    {
        "aider",
        "amp",
        "claude",
        "codex",
        "copilot",
        "cursor",
        "devin",
        "factory",
        "goose",
        "jules",
        "openhands",
        "otto",
        "slay",
        "sweep",
    }
)


# Tool names that identify an agent in a login or a commit identity. Matched on
# word boundaries, so "amp" does not fire inside "example" and "otto" does not
# fire inside "ottomatic".
AGENT_TOKENS: frozenset[str] = frozenset(
    {
        "agent",
        "aider",
        "amp",
        "claude",
        "codex",
        "copilot",
        "cursor",
        "devin",
        "factory",
        "goose",
        "jules",
        "openhands",
        "opencode",
        "otto",
        "slay",
        "sweep",
    }
)

_AGENT_PATTERN = re.compile(
    r"\[bot\]|\b(?:" + "|".join(sorted(AGENT_TOKENS)) + r")\b",
    re.IGNORECASE,
)


def _mentions_an_agent(text: object) -> bool:
    # Entries arrive from a JSON payload, so a malformed one must be ignored
    # rather than crash the run.
    if not isinstance(text, str):
        return False
    return _AGENT_PATTERN.search(text) is not None


def classify(
    pr_user_login: str,
    pr_user_type: str,
    branch: str,
    commit_identities: list[str],
) -> str:
    """Return the provenance label for one pull request.

    ``commit_identities`` holds the ``"Name <email>"`` string of each commit.
    Any single agent signal wins, so a human branch name cannot mask an agent
    commit.
    """
    if pr_user_type == "Bot" or _mentions_an_agent(pr_user_login or ""):
        return AGENT_LABEL

    if (branch or "").split("/", 1)[0].lower() in AGENT_BRANCH_PREFIXES:
        return AGENT_LABEL

    if any(_mentions_an_agent(identity) for identity in commit_identities or []):
        return AGENT_LABEL

    return HUMAN_LABEL
