---
name: delegate-ready-for-dev
description: Find open ready-for-dev issues with no claim and delegate 5 to OpenHands plus 5 to kilo-ai, per the repo's claim protocol
---

# Delegate ready-for-dev issues to OpenHands and kilo-ai

Find open GitHub issues labelled `ready-for-dev` that have not been picked up (no `status/in-progress`, no claim/delegation label, no open PR referencing them), and delegate 5 to OpenHands and 5 to kilo-ai using the repository's claim labels, exactly as done in prior batches.

**Why this skill exists:** agent delegation in this repo is a claim label, not a native assignee (`docs/agents.md`). The convention is a claim label plus `status/in-progress`, repeated in an issue comment with the branch name. Without a reusable skill, each delegation round re-derives the filter and risks double-claiming an issue that another agent already took.

## Prerequisites

- `gh` is authenticated to `github.com` as `alehar9320` with `repo` scope (`gh auth status`).
- You are operating against `alehar9320/agentic-odi`.
- You have read `docs/agents.md` — it is the source of truth for who can take an issue, how a claim is recorded, and when a claim expires.

## The claim protocol (from docs/agents.md)

An issue is eligible only if it is:

1. Open, with `ready-for-dev`, **and**
2. No `status/in-progress`, **and**
3. No claim/delegation label (`openhands`, `kilocode-bot`, `qoder/*`, `freebuff/*`, `agent/*`, `claimed/*`, `agent-claim/*`), **and**
4. No open pull request whose body references the issue (`gh pr list --state open --search '<n> in:body'` must be empty).

## Steps

### 1. List candidates

```bash
gh issue list --repo alehar9320/agentic-odi --state open --label ready-for-dev \
  --json number,title,labels
```

### 2. Exclude taken issues

Drop any issue carrying `status/in-progress` or any of `openhands`, `kilocode-bot`, `qoder/`, `freebuff/`, `agent/opencode-`, `claimed/opencode`, `agent-claim/`.

### 3. Exclude issues with an open PR

For each remaining issue number `<n>`:

```bash
gh pr list --repo alehar9320/agentic-odi --state open --search '<n> in:body' \
  --json number,title
```

Drop `<n>` if the result is non-empty.

### 4. Delegate 5 to OpenHands

OpenHands self-starts from the `openhands` label alone (no comment needed).

Per issue:

```bash
gh issue edit <n> --repo alehar9320/agentic-odi \
  --add-label 'openhands' --add-label 'status/in-progress'
```

Branch convention: `openhands/<n>-<slug>`. Add a claim comment (claim ID, branch, UTC start time, intent) only if a previous label has stalled — not on a fresh delegation.

### 5. Delegate 5 to kilo-ai / Kilo

Kilo has **no label trigger**; it starts on a comment mentioning `@kilocode-bot`. The `kilocode-bot` label is the historical reservation marker ("Delegated to @kilocode-bot for implementation").

Per issue:

```bash
gh issue edit <n> --repo alehar9320/agentic-odi \
  --add-label 'kilocode-bot' --add-label 'status/in-progress'
```

Then comment on the issue starting with `@kilocode-bot` to trigger it:

```
@kilocode-bot Kilo claim: kilocode-bot + status/in-progress.
Branch: kilo/<n>-<slug>
Started: <UTC date>
Intent: implement issue #<n> — <title>
```

Branch convention: `kilo/<n>-<slug>`.

### 6. Verify

Re-view each issue's labels:

```bash
gh issue view <n> --repo alehar9320/agentic-odi --json labels
```

Confirm `status/in-progress` plus exactly one of `openhands` / `kilocode-bot`, and that `ready-for-dev` is still present.

### 7. Stale claims

No claim expires automatically. Treat a claim with no push, PR, or claim comment after **24 hours** as stale: remove the claim label and `status/in-progress`, comment on the issue explaining why, and return it to `ready-for-dev` for the next delegation round.

## Labels used

| Label | Meaning |
|---|---|
| `openhands` | Delegated to OpenHands (its GitHub trigger) |
| `kilocode-bot` | Delegated to @kilocode-bot (Kilo reservation marker) |
| `status/in-progress` | An agent is actively implementing this issue |

## Output

A skill run delegates exactly 10 issues (5 OpenHands, 5 kilo-ai), each labelled `status/in-progress` plus its agent label, with no claim comments on fresh delegations. The skill is re-runnable: each run re-lists candidates and skips anything already claimed.
