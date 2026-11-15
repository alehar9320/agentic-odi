---
name: draining-the-pr-queue
description: Use when several open pull requests must each reach review-ready state — the goal is stated as a number of PRs, or waiting on CI between them would idle the session
---

# Draining the PR queue

**Core principle:** the deliverable is N PRs at review-ready, not N merges. Fix,
hand off, start verification by pushing, take the next PR; come back for
verification once at the end.

Announce at start: "Using draining-the-pr-queue to bring <N> PRs to review-ready."

Default `N = 5` when the request names no number. The per-PR work belongs to
`preparing-a-pr-for-merge`; this skill owns the queue, the ordering, the deferral,
and the sweep.

## Step 1 — state the goal, build the queue

```bash
gh pr list --state open --limit 100 \
  --json number,title,isDraft,mergeStateStatus,labels,additions,deletions,headRefName,updatedAt \
  --jq '.[]
        | select((.labels | map(.name) | index("ready-for-merge")) | not)
        | select((.labels | map(.name) | index("agent-handoff")) | not)
        | {number, title, isDraft, mergeStateStatus, additions, deletions, headRefName}'
```

Exclude a PR when:

- it already carries `ready-for-merge` — nothing to do;
- it carries `agent-handoff` — a human asked to hold it;
- its `updatedAt` is minutes old — someone else is iterating on it;
- it carries `danger zone` — unless the human named that PR explicitly.

A draft PR is in scope — "undone" includes draft — and `preparing-a-pr-for-merge`
promotes it to non-draft once the three facts hold.

`UNKNOWN` merge state means GitHub has not computed mergeability for the current
head yet; re-query with `gh pr view <n> --json mergeStateStatus` rather than
reading it as clean.

**Order, cheapest unblock first:** `DIRTY` → red checks → spec gaps →
`BLOCKED`-by-review last; within a class, fewer `additions + deletions` first.
Record the ordered list before starting. Reordering mid-loop needs a stated
reason.

## Step 2 — one iteration per PR

Run `preparing-a-pr-for-merge` for exactly one PR. It returns a handoff record;
append that record to the ledger and start the next PR.

Loop rules:

- The push is what starts CI. That is the verification you are deferring — never
  sit on `gh pr checks --watch` mid-loop.
- One worktree per PR under `.worktrees/pr-<n>`; remove it once pushed.
- A PR that needs a product decision stops at "ready except <question>" and the
  loop continues. The question is an output, not a blocker.
- Stop the loop early, and say why, when: the queue is empty; a fix would
  contradict an already-merged PR; or two queued PRs touch the same code and
  would conflict with each other (do the older one, note the newer).
- Deliver N or fewer, never more than N. A sixth PR is not a bonus.

## Step 3 — the deferred verification sweep

This is the half that makes pipelining honest — without it, "pending" gets
reported as "done".

```bash
for n in <queue>; do echo "== #$n"; gh pr checks "$n"; done
```

For each PR:

- all green → apply `ready-for-merge`, record green in the ledger;
- red → re-enter `preparing-a-pr-for-merge` for that job only, push again, mark
  verification pending once more;
- still pending after a second sweep → hand off to a human with the run link and
  say plainly that verification did not complete.

Close with a per-PR verdict: `ready`, `ready except <question>`, or `not ready —
<reason>`. A partial result stated honestly beats a claimed 5 of 5.

## Ledger

Write it to `.superpowers/pr-queue/<YYYY-MM-DD>.md` — gitignored working state,
not a deliverable:

```markdown
# PR queue — <date> — goal: <N> ready

| PR | State | CI | Mergeable | Spec | Pending |
|----|-------|----|-----------|------|---------|
| #712 | ready | green | clean | met | — |
| #711 | fixed | pending | clean | met | rerun after <sha> |
```

`write_todos` is the live view; the ledger is what survives compaction. Include
the commands you ran, so the sweep is repeatable by whoever picks this up.

## Why a wrapper and not one bigger skill

| Option | Shape | Verdict |
|---|---|---|
| Singular skill parameterized by `N` | one file, `N == 1` branches | Rejected. The one-PR path is the common invocation and would carry queue state, ordering, and sweep logic it never uses; the loop rules read as noise when you asked about a single PR. |
| Wrapper + singular (chosen) | this file owns queue state, ordering, deferral, sweep; `preparing-a-pr-for-merge` owns one PR's three facts | Both are invocable alone. "Fix PR #712" gets the singular skill; "get 5 PRs ready" gets this one. |
| Script-driven loop (`scripts/pr_queue.py`) | deterministic selection and polling | Deferred. Selection and ordering are one `gh` pipeline, and the per-PR work is judgment. Revisit if a workflow needs the same queue query, or the sweep needs to run unattended. |

The seam is the handoff record: the singular skill's output is this skill's
input, so neither knows the other's internals. That is also why the singular
skill never waits — waiting is queue-level, and putting it there would make every
single-PR use pay for it.

## Red flags

| Thought | Reality |
|---|---|
| "Five PRs at once, one worktree" | One PR at a time, one worktree each. Parallel branches collide in the same files. |
| "I'll wait for this run before starting the next" | That is the load the goal explicitly refuses. Push, record pending, move on. |
| "All five look green, done" | Pending is not green. The sweep is the proof the deliverable exists. |
| "It's green, I'll merge" | Humans merge. Ready is the endpoint. |
| "This PR is nearly ready, so I'll also refactor it" | Scope creep turns three ready PRs into five unfinished ones. |
| "The queue was short, so I'll call it 5" | Say which PRs could not be made ready, and why. |
