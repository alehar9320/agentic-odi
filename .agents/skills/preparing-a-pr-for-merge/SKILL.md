---
name: preparing-a-pr-for-merge
description: Use when one open pull request is not yet mergeable — red checks, merge conflicts, a stale base, or a diff that has drifted from its spec — and it must be brought to human-review-ready state
---

# Preparing a PR for merge

**Core principle:** readiness is three independent facts about the branch head,
not a feeling about the diff. Verify each, fix the cause, hand the PR back — and
never wait on CI inside this skill.

One PR per invocation. For several PRs, use `draining-the-pr-queue`.

## The three facts

| Fact | Verified by | Fixed by |
|---|---|---|
| CI green on the head commit | `gh pr checks <n>` | reproduce the failing job locally, fix the cause, push |
| Mergeable: `mergeable: true`, `mergeStateStatus` clean (or blocked only by a missing review), base no more than 50 commits behind | `gh pr view <n> --json mergeable,mergeStateStatus,baseRefName` | rebase onto `origin/<base>`, resolve, `--force-with-lease` |
| The diff does what the linked spec says | spec and `gh api …/pulls/<n>/files` read side by side | add the missing behaviour, test, or doc |

`BLOCKED` because a required review is missing is not a defect — record it and
move on. `DIRTY`, a red check, and a spec gap are.

## Step 1 — read the contract before touching the branch

```bash
gh pr view <n> --json number,title,isDraft,mergeStateStatus,mergeable,baseRefName,headRefName,body,labels,additions,deletions,changedFiles
gh pr view <n> --comments
gh api "repos/{owner}/{repo}/pulls/<n>/files?per_page=100" --paginate --jq '.[].filename'
```

Find the spec: the issue linked in the body, a `docs/superpowers/plans/` or
`specs/` entry, or the `docs/roadmap.md` *In flight* line. No spec anywhere is
itself the first defect — state that in the body instead of inventing one.

Review comments are claims to verify, not gates to clear: turn each into a
defect — file, line, expected, actual — fix the still-valid ones, and account
for every one as fixed in this commit or deferred with a reason.

## Step 2 — make it mergeable

Never work on the PR author's checkout:

```bash
git fetch origin
git worktree add ".worktrees/pr-<n>" "<headRefName>"
cd ".worktrees/pr-<n>" && git rebase "origin/<base>"
uv sync --all-packages --locked
```

Resolve a conflict by understanding both intents. A conflict you cannot resolve
from the surrounding code and the spec is a question for a human, not a coin
flip. Then `git push --force-with-lease`.

The stale-base threshold is real: `.github/pr-guardrails/config.yml` fails a PR
more than 50 commits behind its base.

## Step 3 — prove the diff against the spec

For every behaviour the spec claims, name the file and the test that deliver it.
Then check the gates a spec in this repo usually implies:

- **Contract sync** — a new or changed MCP tool needs `ToolName` / `TOOL_SPECS`
  in `packages/core/src/agentic_odi_core/contract.py` and the `get_capabilities`
  text, in the same PR.
- **Docs** — `README.md` and `docs/` reflect the change, and `docs/roadmap.md`
  gains a *Shipped* or *In flight* line for the capability.
- **Tests** — `uv run pytest` in the owning workspace; `npm --prefix apps/studio test -- --run`
  for the frontend.
- **Reuse** — a PR that adds a source file carries the `Reuses:` block from
  `.agents/skills/reuse-first/SKILL.md`; `scripts/pr_guards.py body-truth` reads it.

Missing behaviour is written here, test-first (`test-driven-development`), not
deferred to a follow-up PR that never comes.

## Step 4 — turn checks green by reproducing, not guessing

Run the failing job's own command from `.github/workflows/ci.yml`:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy apps brand packages
uv run python scripts/doc_check.py
uv run bandit -c pyproject.toml -r apps packages
uv run pytest --cov   # --cov applies the 89% floor in pyproject.toml
npm --prefix apps/studio run lint
npm --prefix apps/studio run typecheck
```

A red job you cannot reproduce locally is an environment difference: name it in
the body and the run link. Do not re-push hoping. Never weaken a check, skip a
test, or add a suppression to make the board green.

## Step 5 — the body is part of readiness

`pr-body` fails an empty body, and `body-truth` and `fabrication` read it. Rewrite
it to state what changed, how it was verified (commands and their result), and
what is still open. No claim the diff does not support.

## Step 6 — hand off, do not wait

Leave the PR non-draft, make labels match reality (`merge-conflict` cleared,
`ready-for-merge` only when all three facts hold), and post this record:

```text
PR #<n> — <title>
Mergeable: <clean | blocked by review | dirty, resolved in <sha>>
Checks: <green | red: <job>, fixed in <sha> | pending — verify with `gh pr checks <n> --watch`>
Spec: <link> — <met | gap: <what> fixed | gap: <what> left, reason>
Touched: <areas>, +<additions>/-<deletions>
Open question for a human: <or "none">
```

Post the same record as a PR comment when the PR's state changed materially, so
the reviewer sees what to look at. Then stop.

## Red flags

| Thought | Reality |
|---|---|
| "CI was green before my push" | Green applies to a commit, not a branch. Re-check after every push. |
| "The body says it, so the diff does it" | A body is a claim. Read the diff. |
| "The conflict is trivial — take theirs" | A conflict is two intents. Resolve the intent or ask. |
| "I'll wait for the checks, then decide" | This skill hands off. Queue-level waiting is `draining-the-pr-queue`. |
| "`--force` is the same as `--force-with-lease`" | It is not. The lease is what protects a concurrent push. |
| "Skipping one test is faster than fixing it" | It makes the PR look ready, not be ready. |
| "It's green, I'll merge it" | Humans merge. This skill ends at review-ready. |

## Common mistakes

- Rebasing someone else's actively reviewed PR without saying so — comment with
  the new head commit.
- Editing the spec to match the code — fix the code or record the deviation as an
  open question.
- Applying `ready-for-merge` while checks are still pending; that label is what
  the queue uses to decide a PR is done.
- Leaving the worktree behind after pushing — `git worktree remove .worktrees/pr-<n>`.
