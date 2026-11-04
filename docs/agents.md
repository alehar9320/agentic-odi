# Agent Assignment

Who can take a GitHub issue in this repository, how an agent records that it has
taken one, and when that claim stops being true. This is the reference for
humans and for an orchestrator that wants to delegate work in parallel instead
of running one task at a time.

Checked against this repository and its GitHub settings on **2026-10-31**. The
agent landscape moves quickly; re-check the linked vendor docs and the repository
labels before relying on a row marked *unverified here*.

## The short version

- **No AI agent is a native GitHub assignee here.** The assignable accounts are
  `alehar9320` and `sanhenn`. An agent claims an issue with a **label**, not with
  the assignee field.
- The working convention is a claim label `<agent>/<YYYY-MM-DD>-<issue>` plus
  `status/in-progress`, repeated in an issue comment with the branch name.
- **Three agents can start from GitHub itself:** OpenHands (label `openhands`
  or a comment starting `@openhands`), Kiro (label `kiro` or `/kiro`), and Kilo
  (`@kilocode-bot`). Only OpenHands has actually run in this repository.
- **Qoder, Freebuff (Buffy), and OpenCode are driven from a local session.** Their
  claim labels order the work, but nothing on GitHub starts them.
- **Jules is retired.** The label and branches remain as history; Google
  announced the wind-down on 2026-10-29. Do not route new work there.
- **No claim expires automatically.** Treat a claim with no push or PR after
  24 hours as stale and release it.

## What "assigned" means here

There are two mechanisms, and they answer different questions:

| Mechanism | Who can hold it | What it tells a reader | Where it lives |
|---|---|---|---|
| Native assignee | Accounts in the repository's assignee list — today only `alehar9320` and `sanhenn` | Who is accountable for the issue | Issue sidebar, `assignees` API |
| Claim label | Any agent whose app or local session can write labels | Which agent is working on it, and when it started | Labels, issue list, search |

The assignee field is the authoritative answer for humans. The claim label is
the authoritative answer for agents. Neither one grants an agent permission to
push: that comes from the installed GitHub App (OpenHands, Kilo) or from the
credentials of the human running a local agent (Qoder, Freebuff, OpenCode).

This repository already has a busy label vocabulary, so the claim label is not a
proposal — it is what agents and the repository owner already do. This page
names the convention and makes it predictable.

## Who can take an issue

| Agent | Starts from GitHub? | Trigger | Claim marker observed here | Status |
|---|---|---|---|---|
| **OpenHands** | Yes | Label `openhands` on an issue, or a comment starting `@openhands`. On pull requests, only `@openhands` comments on PRs to and from repositories added to OpenHands Cloud. | Label `openhands` (description: *Implemented by an OpenHands agent*) plus `openhands/2026-10-31-<issue>`; branch `openhands/<slug>`; bot identity `openhands-ai` | **Working.** Used on issues #322 and #344 and PR #436. |
| **Kiro** | Yes, once the repository is connected to Kiro Web | Label `kiro` on an issue, or a comment mentioning `/kiro`. On a pull request, `/kiro all` addresses all feedback and `/kiro fix` targets one thread. | No claim label used here yet; reserve `kiro/<YYYY-MM-DD>-<issue>` and the `kiro/` branch prefix | **Upstream capability, not yet exercised here.** No `kiro` label or bot comment exists in this repository. Kiro Web needs a Pro, Pro+, Pro Max, or Power subscription. |
| **Kilo** | Yes, through the installed Kilo Code Bot app | Comment mentioning `@kilocode-bot` on an issue, PR, or review comment. There is no label trigger. | Branch `kilo/issue-340-evidence-dedup`; PR author `app/kilo-code-bot`; no claim label | **Installed and used once** (PR #371). Needs a Kilo account with credits. |
| **Qoder** | No, not as configured | Qoder's GitHub Action can answer `@qoder` mentions, but it requires a workflow, the `qoderai` app, and a `QODER_PERSONAL_ACCESS_TOKEN` secret — none of which exist here. QoderWake can react to GitHub events, but it is not installed. | `qoder/2026-10-31-<issue>` claim labels; branches `qoder/<issue>-<slug>` | **Local delegation only.** The branches and labels were created by the repository owner, not by a GitHub listener. |
| **Freebuff (Buffy)** | No | A local Freebuff session started by a human. There is no Freebuff GitHub App. | `freebuff/2026-10-31-<issue>`; branch `freebuff/<date>-<issue>` | **Local.** Used heavily on 2026-10-31 for issues #320–#428. |
| **OpenCode** | No, not as configured | A local OpenCode session. Its GitHub Action is not installed here. | `agent/opencode-<YYYY-MM-DD>[-<issue>]` and `claimed/opencode-<timestamp>` | **Local.** Two label dialects are in use; see *Known gaps*. |
| **GitHub Copilot coding agent** | Not enabled | GitHub's native flow is assigning the issue to Copilot; Copilot then opens a pull request for review. | None | **Unavailable today.** Copilot does not appear in this repository's assignee list, and it needs a paid Copilot plan. Do not plan around it without enabling it first. |
| **Jules (Google)** | Retired | Formerly the `jules` label, `jules/...` branches, and `google-labs-jules[bot]` commits. | `jules` label (no description) on closed issues #105–#123 | **Retired.** Google announced the shutdown on 2026-10-29 and is folding the work into Antigravity. Treat the label as inert. |
| **Dependabot, GitHub Actions** | n/a | Schedules and repository events | `dependabot[bot]`, `github-actions[bot]` | **Automation, not issue workers.** They update dependencies and run CI; do not assign product work to them. |

The PR provenance labeler in `scripts/pr_provenance.py` also recognizes `aider`,
`amp`, `claude`, `codex`, `cursor`, `devin`, `factory`, `goose`, `otto`, `slay`,
and `sweep`. None of them has a branch, label, bot comment, or workflow in this
repository. They are recognized names, not available workers.

## Per-agent notes

### OpenHands

- **Trigger.** Apply the `openhands` label to an issue, or comment with a message
  that starts `@openhands`. On a pull request, `@openhands` works only when the
  PR is both to and from repositories added to OpenHands Cloud.
- **What happens.** OpenHands comments on the issue ("I'm on it!" with a link to
  the cloud conversation), opens a pull request when it believes the issue is
  resolved, and comments with a summary and the PR link.
- **Access.** OpenHands requests short-lived GitHub tokens that expire after
  **8 hours**, with contents, issues, pull requests, workflows, actions, and
  commit-status write access. Repository access is granted per repository in
  OpenHands Cloud and can be revoked there.
- **What we saw here.** Issue #322 was picked up by `openhands-ai`, claimed with
  `openhands/2026-10-31-322`, and delivered as PR #372. A second OpenHands run
  later opened PR #374 for the same issue, discovered #372 had already merged,
  and closed #374 as a duplicate. Check `origin/main`, existing pull requests, and
  the claim label before starting.
- **Expiry.** The token expires in 8 hours; the claim label never expires on its
  own. Sessions live in OpenHands Cloud and are not started by this repository's
  CI.
- **Not merged.** PR #363 ("run an Agent Canvas autopilot against OpenHands
  Cloud") is an open proposal for a local orchestrator. Do not depend on its
  packages or CLI commands until it merges.

### Kiro

- **Trigger.** Add the `kiro` label to an issue, or comment with `/kiro`. When
  Kiro opens a pull request, leave review comments and use `/kiro all` or
  `/kiro fix` to have it respond.
- **Requirements.** Kiro Web must be connected to the repository, and the
  account needs a Kiro Pro, Pro+, Pro Max, or Power subscription. Kiro's
documented project conventions live in `.kiro/steering/` at the repository root;
that directory does not exist here yet, so Kiro-specific steering is not
configured in this repository.
- **What we saw here.** No `kiro` claim label, no `/kiro` comment in the issue
  and PR history we checked, and no Kiro bot identity. A `kiro-superpowers`
  branch added Kiro tool mappings for Superpowers, but that is editor
  integration, not issue pickup.
- **Expiry.** Subscription-dependent; no published session lifetime. A claim
  label, once created, is yours to remove.

### Kilo

- **Trigger.** Mention `@kilocode-bot` on an issue, pull request, or review
  comment. The exact handle matters: `@kilo` is not the bot.
- **Requirements.** The Kilo Code Bot GitHub App is installed (PR #371 was
  authored by `app/kilo-code-bot`), the repository is authorized in Kilo, and the
  account has credits. Credit usage follows the selected model and task
  complexity.
- **What we saw here.** PR #371 says "Implements issue #340" but does not use a
  `Closes` trailer, so GitHub did not link the PR to the issue automatically.
  Always add `Closes #<issue>` to agent PRs.
- **Expiry.** Credit balance and app installation; no published session TTL.
  Kilo has no label trigger and keeps no claim label, so the PR or branch is the
  only durable trace.

### Qoder

- **Not a GitHub listener here.** Qoder's documented GitHub path is Qoder Action:
  a workflow in `.github/workflows/`, the `qoderai` GitHub App, and a
  `QODER_PERSONAL_ACCESS_TOKEN` secret. That workflow does not exist, so an
  `@qoder` comment starts nothing.
- **How work actually happened.** The owner ran Qoder locally and recorded the
  claim with labels such as `qoder/2026-10-31-446` and branches such as
  `qoder/446-list-conversations`. PRs are authored from the owner's account.
- **Expiry.** A local Qoder session ends with the process. The claim label
  persists until someone removes it.

### Freebuff (Buffy)

- **No GitHub listener.** A human starts a Freebuff session in the repository.
  Freebuff claims work by creating a label such as
  `freebuff/2026-10-31-413` and a branch such as `freebuff/2026-10-31-413`.
- **An orchestrator cannot start it from GitHub.** It can see the claim and avoid
  the issue, but dispatch still requires a person to start a session.
- **Expiry.** The session ends when the process ends; the label persists.

### OpenCode

- **Local first.** OpenCode sessions here claim with either
  `agent/opencode-<date>` / `agent/opencode-<date>-<issue>` or
  `claimed/opencode-<timestamp>`. Both appear on the same issues, for example
  issue #413.
- **No workflow.** OpenCode's GitHub Action is not installed; a comment does not
  start a session.
- **Expiry.** Session-bound; labels persist.

### GitHub Copilot coding agent

GitHub's native model is to assign an issue to Copilot, which researches the
repository and opens a pull request for review. That is the closest thing to
"assign an issue to an agent" on GitHub. It is **not enabled here**: Copilot is
not in the assignee list, and a paid Copilot plan is required. If it is enabled
later, it belongs in the native-assignee column, not the claim-label convention.

### Jules

Jules was Google's asynchronous coding agent and it was used on issues #105–#123
in this repository. Google announced on 2026-10-29 that Jules is winding down
and its learnings are moving into Antigravity. The `jules` label still exists;
removing it would destroy history, so it stays. Do not treat it as an available
worker. No replacement integration is configured here.

## The claim protocol

This is the canonical protocol for a new agent claim. It matches what OpenHands,
Qoder, and Freebuff already do, and it is the contract an orchestrator should
enforce.

1. **Pick an eligible issue.** It should carry `ready-for-dev`, and it must not
   carry `status/in-progress`, a claim label, or an open pull request that
   references it.

   ```bash
   gh issue list --repo alehar9320/agentic-odi --state open --label ready-for-dev \
     --json number,title,labels
   gh pr list --repo alehar9320/agentic-odi --state open --search '<issue> in:body'
   ```

2. **Claim it before writing code.** Create the claim label if it is new, apply
   it, and add `status/in-progress`:

   ```bash
   gh label create 'openhands/2026-10-31-344' \
     --repo alehar9320/agentic-odi --force \
     --description 'OpenHands claim on 2026-10-31 for issue 344'
   gh issue edit 344 --repo alehar9320/agentic-odi \
     --add-label 'openhands/2026-10-31-344' --add-label status/in-progress
   ```

3. **Say it in the issue.** Comment with the claim ID or label, the branch name,
   the UTC time, and what the agent intends to do. The OpenHands and Freebuff
   conventions both do this; it is the human-readable half of the lock.

4. **Name the branch `<agent>/<issue>-<slug>`.** Examples in use:
   `qoder/446-list-conversations`, `openhands/alh-125`,
   `freebuff/2026-10-31-413`. The prefix is what the PR provenance classifier
   reads.

5. **Open a pull request, never push to `main`.** Include `Closes #<issue>`, fill
   in the pull request template, and include the `AGENT_METADATA` block. Add
   `agent-handoff` when CI is green and the PR is ready for a human.

6. **Release the claim.** When the PR merges, or when you abandon the work,
   remove the claim label and `status/in-progress`, and comment on the issue to
   say which happened. A merged PR should leave `status/done`; an abandoned one
   should leave the issue ready for the next agent.

Legacy claim markers exist and should not be copied into new work:

| Marker seen | Example | Canonical replacement |
|---|---|---|
| `agent/opencode-<date>[-<issue>]` | `agent/opencode-2026-10-31-413` | `<agent>/<date>-<issue>` |
| `claimed/<agent>-<timestamp>` | `claimed/opencode-20261031-2130` | `<agent>/<date>-<issue>` |
| `agent-claim/<hash>` | `agent-claim/7c4e2b` | `<agent>/<date>-<issue>` |
| `claimed/GH-Impl-2` | old bulk-work labels | `<agent>/<date>-<issue>` |

Do not delete the old labels from closed issues: they are the record of how the
work was done. Apply the canonical form going forward.

## How to see what is taken

```bash
# Every live claim, across agents
gh issue list --repo alehar9320/agentic-odi --state open \
  --label status/in-progress --json number,title,labels

# One agent's claims
gh issue list --repo alehar9320/agentic-odi --state all \
  --search 'label:openhands/2026-10-31-322'

# Agent pull requests waiting for a human
gh pr list --repo alehar9320/agentic-odi --state open --label agent-handoff \
  --json number,title,headRefName

# The issue's own timeline, including claim comments
gh issue view 344 --repo alehar9320/agentic-odi --comments
```

A claim is not a lock in the database sense. GitHub has no compare-and-swap for
labels, so two agents can both read "free" and both apply a label within the same
second. The claim comment is the tie-breaker: the earlier timestamp wins, and the
later agent must release its label and pick another issue. An orchestrator should
re-read the issue after claiming and back off if a different claim appeared.

## Expiry and staleness

| What | Expires? | Rule |
|---|---|---|
| Claim label + `status/in-progress` | No | Stale after **24 hours** with no push, PR, or claim comment. The agent that owns it releases it, or a human removes both labels and comments why. |
| OpenHands GitHub token | **8 hours** | Issued per run; a long-idle session must re-authenticate. |
| OpenHands Cloud conversation | Vendor-managed | No published TTL in the GitHub integration docs; the PR or issue comment is the durable record. |
| Kiro Web session | Vendor-managed | No published TTL; access depends on a Pro/Pro+/Pro Max/Power subscription. |
| Kilo cloud agent | Vendor-managed | Runs on Kilo credits; no published TTL. |
| Qoder / Freebuff / OpenCode session | With the process | The local process ending does not remove the claim label. |
| Copilot session data | 28 days (Actions-based) | Cloud-sandbox sessions are retained for the life of the account. This is data retention, not claim expiry. |
| Jules | Service | Winding down as announced on 2026-10-29; the label is inert. |

Two practical consequences:

- **Credential expiry is not claim expiry.** An OpenHands token dying after eight
  hours says nothing about whether the issue is still owned. Look at the label
  and the last comment.
- **Subscription or credit exhaustion is silent.** A trigger that no longer
  produces a bot comment looks exactly like a trigger that was never received.
  Before re-dispatching, check that the app is still installed and the account
  still has access.

## Constraints every agent inherits

- Read `AGENTS.md` and `.agents/rules/agent_instructions.md` before writing code.
  Kiro additionally reads `.kiro/steering/`; Qoder Action reads `AGENTS.md`.
- Never push to `main` and never merge. Agents open pull requests; a human merges.
  The `main-requires-ci-green` ruleset requires `CI green` and `PR guardrails`.
- Fill in the pull request template truthfully, including the machine-readable
  diff summary and the `AGENT_METADATA` block. The guardrails compare the claims
  with the actual diff.
- Keep `README.md` and `docs/` current in the same change; `scripts/doc_check.py`
  fails on documented paths, commands, routes, and environment variables that do
  not exist.
- Do not remove labels owned by another workflow (`safe to merge`,
  `needs a look`, `danger zone`, `ready-for-merge`, `merge-conflict`). See
  `scripts/pr_labels.py` for the managed set.
- One issue, one claim. Do not start a second agent on an issue that already has
  a live claim, even if the first agent looks idle; ask on the issue first.

## Fan-out rules for an orchestrator

An orchestrator can safely parallelize if it treats the claim label as the lock
and the pull request as the handoff.

1. **Filter.** Candidate work is an open issue with `ready-for-dev`, without
   `status/in-progress`, without any `<agent>/<date>-<issue>` label, and without
   an open PR that references it.
2. **Route by trigger capability, not by preference.** OpenHands and Kiro can be
   dispatched from GitHub with a label. Kilo needs a comment mention. Qoder,
   Freebuff, and OpenCode need a human-started session; an orchestrator can
   reserve the issue but cannot start the work.
3. **Claim, then dispatch.** Apply the claim label and `status/in-progress`
   first. After dispatch, re-read the issue; if another claim appeared first,
   release yours and choose different work.
4. **Keep the fan-out bounded by what you can observe.** Start with one open
   claim per agent and one task per vendor until you have measured how many
   concurrent sessions that vendor actually runs. The vendor docs linked below do
   not publish a safe concurrency number, and guessing one produces duplicate
   work rather than throughput.
5. **Prefer different files.** Two agents editing the same component will collide
   even on different issues. Use the `area/*` labels and the issue's file list to
   keep parallel work disjoint.
6. **Handoff is explicit.** A PR with `agent-handoff` and green CI is waiting for
   a human; it is not done. A claim is done when the PR merges and the claim
   label is removed.
7. **Exclude retired and unavailable workers.** Jules is retired; Copilot is not
   enabled here. Routing to either produces a silent no-op.

The state machine the orchestrator should enforce:

```text
ready-for-dev
  └─ claim: <agent>/<date>-<issue> + status/in-progress + claim comment
       ├─ PR opened: Closes #<issue> + agent-handoff
       │    └─ merged: remove claim + status/in-progress, add status/done
       └─ 24h with no push or PR: release claim, comment, back to ready-for-dev
```

## Known gaps

These are real limits of the current setup, not aspirations:

- **Three claim-label dialects.** `agent/opencode-*`, `claimed/*`, and
  `agent-claim/*` predate the canonical `<agent>/<date>-<issue>` form. Until they
  are migrated, a query for one shape misses claims in another; query
  `status/in-progress` as the lowest common denominator.
- **The provenance labeler under-reports local agents.** The branch prefixes in
  `scripts/pr_provenance.py` do not include `freebuff`, `qoder`, `kilo`, or
  `kiro`, so PRs from those agents are labeled `👤 human` (for example #430 and
  #435). The provenance label answers "was this written by an agent", not "is
  this issue claimed"; do not use it as claim state.
- **No automated expiry.** Nothing removes a stale claim. Issue #303's
  `agent-claim/7c4e2b` and the `claimed/opencode-*` labels on #311 and #312 are
  live examples of claims that outlived the work. A scheduled sweep would need a
  decision about what "stale" means before it could be automated.
- **No machine-readable registry.** This page is prose and tables. An
  orchestrator that needs the agent list in code should read it from a small JSON
  or YAML file next to this document; that file does not exist yet.
- **Only OpenHands has run end-to-end from a GitHub trigger.** Kiro and Kilo are
  documented upstream and installed at the app level, but this repository has no
  Kiro pickup and one Kilo PR (#371). Treat their first real run as a test, not a
  proven path.

## Sources

- [OpenHands GitHub integration](https://docs.openhands.dev/openhands/usage/cloud/github-installation)
  — label and `@openhands` triggers, short-lived tokens, PR behavior.
- [Kiro Web](https://kiro.dev/web/) and [Kiro GitHub setup](https://kiro.dev/docs/web/github/)
  — `kiro` label, `/kiro` comments, `/kiro all` and `/kiro fix`, subscription
  tiers.
- [Kilo for GitHub](https://kilo.ai/docs/code-with-ai/platforms/github) —
  `@kilocode-bot`, app installation, credits.
- [Qoder Action](https://docs.qoder.com/cli/qoder-action) — `@qoder` mentions,
  workflow and secret requirements.
- [QoderWake GitHub delivery loop](https://docs.qoder.com/qoderwake/github-devops)
  — event-driven agent workflow, not installed here.
- [GitHub Copilot on GitHub](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent)
  — native assignment, plans, and session retention.
- [The Verge: Google is sunsetting Jules](https://www.theverge.com/tech/1022729/google-is-sunsetting-its-ai-coding-agent-jules)
  — announcement on 2026-10-29.
- Repository evidence: `gh api repos/alehar9320/agentic-odi/assignees`, issue
  labels, issue comments, and the branch list, all read on 2026-10-31.
