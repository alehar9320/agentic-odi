---
name: fix-up-pr
description: Use when a pull request has merge conflicts, CI that isn't green, or a spec that isn't properly fulfilled, and needs to be made merge-ready
---

# Fix up a pull request

## Overview

A fix-up skill for pull reports: find what's wrong with a PR (merge conflicts, red CI, unmet spec), make the relevant improvements, and verify it's merge-ready — one PR at a time.

**Core principle:** Never manufacture green. A PR is fixed when it merges cleanly, CI passes without removed gates, and it actually fulfills its linked spec. Conflicts, red CI, and spec drift are separate problems; fix each in order, never by deleting tests or bypassing gates.

**Violating the letter of the rules is violating the spirit of the rules.**

## When to Use

Use when:
- A PR has merge conflicts with its base branch
- CI is red / not green for a PR
- A PR's diff doesn't match its linked spec or acceptance criteria
- An agent or orchestrator is processing PRs one at a time (recurring per-PR goal or a specific PR handed off)

Tools: whatever reaches GitHub — `gh` CLI, GitHub MCP (`get_pull_request`, `get_pull_request_reviews`, `list_commits`), or the repo's own checkout. The skill is platform-agnostic; PRs here live on GitHub.

Not for: creating a PR from scratch, reviewing code quality of a green PR, or closing a PR that shouldn't exist.

## The Fix-Up Cycle

Work one PR at a time, in this order:

```
1. FIND   → 2. DIAGNOSE → 3. IMPROVE → 4. VERIFY → 5. LABEL & HANDOFF
```

### 1. FIND — Pull the PR and its context

- Get the PR: number, title, head branch, base branch, author, linked issue/spec.
- Read the PR template fields that were filled in (diff summary, `AGENT_METADATA`, acceptance criteria).
- List the commits and changed files. Identify which files conflict with base.
- Check CI: which workflows ran, which jobs failed, which gates are `needed` by `ci-green`.
- Read the linked spec / acceptance criteria (roadmap entry, PR template, or linked doc).

### 2. DIAGNOSE — Name each problem separately

Classify into exactly these buckets, one at a time:

| Bucket | Signal |
|---|---|
| **Merge conflict** | `git merge-base` shows divergence; `git merge --no-commit --no-ff` leaves conflict markers |
| **Red CI** | A `needed` job is `failure`/`cancelled`; CI step exits non-zero |
| **Unmet spec** | Diff doesn't implement linked acceptance criteria; roadmap cites wrong PR number; documented route isn't served |

Do not collapse "CI red because tests were deleted" into "CI is fine once green." Deleted gates are a separate diagnosis.

### 3. IMPROVE — Fix each bucket, in order

**Merge conflicts first.** A branch that won't merge can't have meaningful CI or spec evaluation.
- Do a real three-way merge. Read each conflict marker, compare main's version (since merge-base) against the PR's version, hand-resolve.
- Never blindly take "theirs" or "ours." Main may hold bug fixes the PR would revert.
- Re-confirm: `git merge-base --is-ancestor PR main` (fast-forwardable) or a clean merge commit with no conflict markers.
- Fix any obvious citation drift (e.g., roadmap entry citing `[PR #494]` when this PR is `#446`).

**Red CI second.** Fix what the PR itself broke; do not remove gates.
- Reproduce the failure locally with the exact command CI runs. Confirm it's deterministic, not flaky.
- If the PR introduced a broken CI step (e.g., `doc_check.py --base --changed-files` when the tool accepts no args), either drop the unsupported args or implement the feature — minimal fix, not scope creep.
- **Restore** any gates/tests the PR deleted (contrast job, `a11y.spec.ts`, `knownPairs.ts`, `test_boot_integrity.py`). Deleting tests to manufacture green is prohibited.
- Investigate *why* a gate was red before restoring; don't assume "restore = fixed."
- Run the project's test command (`uv run pytest`, `npm test`, etc.) and relevant lint/typecheck/e2e locally.

**Unmet spec third.** Confirm the diff matches acceptance criteria.
- Confront premise mismatches: if the task says "outcome scoring endpoint" but the PR is "conversations listing," flag it to the human partner before fixing — do not silently re-scope.
- Verify each acceptance criterion: route registered and served, pagination shape, newest-first ordering, etc.
- Ensure `doc_check`'s route check passes (documented routes are actually served by the router).
- Roadmap entry cites the correct PR number.

### 4. VERIFY — Merge-ready checklist

Before calling the PR fixed:

- [ ] Premise confirmed with the human partner (right PR, right spec) — not ambiguous
- [ ] Branch merges cleanly into base; no conflict markers remain
- [ ] CI is green **without removing gates**: every `needed` job `success`, `ci-green` reports all needed
- [ ] Any deleted gate/test restored and passing; no test deleted to manufacture green
- [ ] Diff fulfills acceptance criteria; each criterion checked off
- [ ] Roadmap/spec cites the correct PR number
- [ ] `doc_check` route check passes (documented routes served)
- [ ] Any corner cut documented (e.g., "didn't run full e2e suite") so the reviewer knows what's unverified

**Done means merge-ready, not "CI green."** A green CI with deleted gates is not done.

### 5. LABEL & HANDOFF — classify and mark ready

Once VERIFY passes, classify the PR and mark it ready for a human. Labels are additive: create any label that does not exist, then apply it. Never remove labels owned by other workflows (`safe to merge`, `needs a look`, `danger zone`, `ready-for-merge`, `merge-conflict` — see `scripts/pr_labels.py` for the managed set).

#### Scoring dimensions (3 levels by default, 5 when scoring needs it)

Apply one level per dimension. Use the 3-level scale by default; escalate a dimension to 5 levels only when an agent or orchestrator needs finer routing granularity (e.g., routing high-risk PRs to specific reviewers, or size-based batching).

Convention: lowercase, slash-namespaced `<dimension>/<level>`, aligned with the project's existing `status/*` and `area/*` label families.

| Dimension | 3 levels (default) | 5 levels (when scoring needs it) |
|-----------|-------------------|----------------------------------|
| Complexity | `complexity/low`, `complexity/medium`, `complexity/high` | add `complexity/very-low`, `complexity/very-high` |
| Size | `size/small`, `size/medium`, `size/large` | add `size/xsmall`, `size/xlarge` |
| Impact | `impact/low`, `impact/medium`, `impact/high` | add `impact/very-low`, `impact/very-high` |
| Risk | `risk/low`, `risk/medium`, `risk/high` | add `risk/very-low`, `risk/very-high` |

Level guidance (3-level):
- **Complexity** — cognitive load to review: low = single-file, obvious change; medium = cross-file or non-trivial logic; high = architecture-spanning, novel pattern, or subtle semantics.
- **Size** — blast radius of the diff: small = <10 files / <300 lines; medium = 10–30 files or 300–1000 lines; large = >30 files or >1000 lines.
- **Impact** — user/system effect if the PR ships: low = internal or cosmetic; medium = visible behavior change for some users; high = behavior change for all users, data migration, or security-relevant.
- **Risk** — blast radius if merged wrong: low = easily reverted, no data impact; medium = partial user impact, reversible with effort; high = data loss, downtime, or hard-to-revert change.

#### Ready-for-human-review label

Set `ready-for-human-review` **only** when the VERIFY checklist fully passes — branch merges cleanly, CI green without removed gates, spec fulfilled. Set it together with the existing `agent-handoff` label (per `docs/agents.md`, step 5: "Add `agent-handoff` when CI is green and the PR is ready for a human"). `ready-for-human-review` is the canonical "ready for human" marker; `agent-handoff` is the project's existing equivalent and is kept for compatibility.

If VERIFY is not fully green, set neither label.

#### Tooling

Use whatever reaches GitHub — `gh` CLI (`gh label create`, `gh pr edit --add-label`) or GitHub MCP (`addLabel`/`createLabel` equivalents). Create the label if missing, then apply it.

After labelling, add a PR comment summarizing what was fixed, which labels were applied, and any corner cuts documented in VERIFY. Then release the claim label per the claim protocol (`docs/agents.md`): remove the claim label and `status/in-progress`; on merge, add `status/done`.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Collapsing all three problems into "make CI green" | Diagnose conflicts, CI, spec separately; fix in order |
| Taking "theirs" to clear conflicts fast | Real three-way merge; review what main changed since base |
| Deleting failing tests or jobs to look green | Restore them; fix the real failure |
| Force-merging / bypassing gates under time pressure | CI green is a hard requirement; no bypass |
| Silently re-scoping when premise mismatches the task | Flag to human partner first |
| Declaring done after `doc_check` exits 0 but gates still missing | `ci-green` must report all needed jobs `success` |

## Red Flags — STOP and Reconsider

- "CI is probably flaky, I'll just force merge."
- "Resolve conflicts by taking theirs — it's faster."
- "The spec is close enough."
- "Skip the spec check; just make tests pass."
- "Delete this failing test so CI goes green."
- "I'll extend the tool to accept those args instead of removing them" (scope creep in a fix-up)
- "Restore = fixed" without investigating why the gate was red
- Declaring done before confirming the premise with the human partner
- "This is different because..." (rationalizing an exception)

**All of these mean: stop, re-diagnose, and apply the cycle properly.**

## Example: Fix up PR #446 (conversations listing)

**Diagnose.**
- Conflict: `studio/router.py`, `studio/memory.py`, `docs/roadmap.md` diverged from main.
- Red CI: `doc_check.py --base origin/main --changed-files docs/roadmap.md` exits 2 — `doc_check` accepts no args; the PR added unsupported flags. Also the `contrast` job, `a11y.spec.ts`/`knownPairs.ts`, and `test_boot_integrity.py` were deleted.
- Unmet spec: task said "outcome scoring endpoint" but PR #446 is "conversations listing"; roadmap entry cites `[PR #494]`, but this PR is `#446`.

**Improve.**
- Flag the premise mismatch to the human partner (conversations vs outcome scoring) before re-scoping.
- Three-way merge `router.py` so `GET /api/conversations` stays registered; fix `roadmap.md` citation `#494 → #446`.
- Fix CI: drop the unsupported `--base`/`--changed-files` args so `doc_check` runs as designed (exit 0). Restore the `contrast` job, a11y tests, and `test_boot_integrity.py`; investigate why contrast was red instead of assuming.
- Verify acceptance criteria: `list_conversations` newest-first with turn counts, `limit`/`offset` pagination, route served by `studio.router`.

**Verify.**
- Branch fast-forwardable into main, no conflict markers.
- `uv run pytest` green for studio-api tests; `ci-green` reports all needed jobs `success`.
- Roadmap cites `#446`; `doc_check` route check passes.
- Corner cut documented: full e2e/Playwright suite not run due to time.

## Quick Reference

| Step | Action | Exit condition |
|---|---|---|
| FIND | Pull PR, commits, files, CI status, linked spec | PR and context in hand |
| DIAGNOSE | Bucket into conflict / red CI / unmet spec | Each problem named separately |
| IMPROVE | Merge conflicts → fix CI (no gate removal) → match spec | All three buckets addressed |
| VERIFY | Merge-clean + green CI + spec fulfilled | All checklist boxes checked |
| LABEL & HANDOFF | Apply complexity/size/impact/risk labels; set `ready-for-human-review` + `agent-handoff` | Labels applied, comment posted, claim released |

## Verification Checklist

Before marking a PR fixed:

- [ ] Premise confirmed with human partner
- [ ] Branch merges cleanly into base; no conflict markers
- [ ] CI green without removed gates (`ci-green` all `success`)
- [ ] Deleted gates/tests restored and passing
- [ ] Every acceptance criterion checked off
- [ ] Roadmap/spec cites correct PR number
- [ ] `doc_check` route check passes
- [ ] Corners cut documented
- [ ] Complexity / size / impact / risk labels applied (created if missing)
- [ ] `ready-for-human-review` and `agent-handoff` labels set (only if VERIFY fully passed)
- [ ] Claim label released per claim protocol

Can't check all boxes? The PR isn't fixed yet.