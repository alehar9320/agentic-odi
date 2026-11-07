---
name: fixing-failed-pr
description: Use when a GitHub PR fails review, CI, or merge checks and must be brought to merge-ready state: spec fulfilled, CI green, no merge conflicts.
---

# Fixing a Failed PR

## Overview

You are the PR's last reviewer before human handoff. Your objective: one gate at a time, three gates total — all must pass before re-requesting review.

**The three hard gates:**
1. **Spec fulfilled** — the PR does what its issue/spec says.
2. **CI green** — every check passes locally, then on the PR.
3. **No merge conflicts** — branch applies cleanly to its target.

Core principle: Review is the primary tool. Fixes are small and verified. Never re-request review until all three gates pass.

## When to Use

Use when:
- A PR has resolved review comments but CI still fails
- Comments, CI failures, or merge conflicts block merge
- You need to bring *one* PR to merge readiness

Do NOT use when:
- The spec itself is wrong (stop and re-scope with the author first)
- Writing a new PR from scratch
- The feature shouldn't exist (that's an architecture discussion)

## Core Pattern: Review → Fix → Re-Verify

Run this loop until **all three gates pass**, then stop.

### 1. Establish Intent
- Read the PR description and linked issue
- Define what "done" looks like before touching code
- Capture the **spec** in the Required Review Template

### 2. Review the Delta
- Read every review comment, CI failure log, and merge conflict marker
- Convert each into an actionable defect: file, line, expected, actual
- ❌ NEVER mark a comment "resolved" without the fix being in the next commit

### 3. Fix the Smallest Change
- One fix per defect
- Prefer reverting a bad change over patching around it
- Keep the PR single-purpose — no unrelated cleanup

### 4. Re-Verify Locally (Dummy Verification)
This is mandatory. Run the exact checks that CI runs:
```bash
cd /Users/alexanderhaerenstam/orca/workspaces/agentic-odi/Local-Mac-PRs
uv run pytest                           # unit tests
uv run python -m ruff check             # lint (if configured)
uv run python -m ruff format --check    # format (if configured)
python -c "from fastmcp import Client; print('imports ok')"  # basic import verify
```
- ❌ NEVER skip local verification
- ❌ NEVER believe "CI is green" without reproducing it locally

### 5. Re-Review the Full Diff
- Diff the branch against base as a whole
- Confirm every comment is addressed or explicitly deferred
- Confirm no new conflicts with base

### 6. Merge-Readiness Check
- All three gates pass → re-request review
- Any gate failing → loop back to step 2

## Quick Reference

| Gate | Check | Pass criterion |
|------|-------|----------------|
| Spec fulfilled | PR description vs. diff vs. linked issue | Every spec behavior covered; no scope creep |
| CI green | Local test/lint run + PR check status | All checks green, locally and on CI |
| No merge conflicts | `git merge-base` / manual checkout test | Branch applies cleanly to target |

## Required Review Template (fill per check)

```
## PR Review Checklist

### Gate 1: Spec Fulfilled
- **Spec source:** <link to issue/PR spec>
- **Expected behavior:** <what must happen>
- **Implementation:** <where in code, what does it do>
- **Gap:** <none OR specific missing behavior>

### Gate 2: CI Green
- **Failing check:** <name, if any>
- **Local reproduction:** <command run, result>
- **Fix verified:** <YES/NO>

### Gate 3: No Merge Conflicts
- **Conflict status:** <YES conflicts resolved / NO conflicts>
- **Verified against:** <target branch name>

### Comments Addressed
- **Count total:** <n>
- **Method:** <addressed with commit(s) / deferred with author agreement>
- **Deferred list:** <if any>

### Risk
- **Could still break:** <what>
- **Mitigation:** <testing, guardrails, code review>

### Verdict
- **Status:** READY / NOT READY
- **Blocking gate:** <Gate 1 / Gate 2 / Gate 3 / None>
```

## Common Mistakes (and their fixes)

| Mistake | Fix |
|---------|-----|
| "CI was green on my machine" | Run from a clean checkout of the fixed branch |
| Addressing comments without re-reading full diff | Always re-review the complete diff |
| Folding unrelated cleanup into fixup | Keep fixup PRs single-purpose |
| Re-requesting review without re-running CI | Every change requires full verification |
| Ignoring conflicts because code "looks right" | Manually verify conflict resolution |

## Red Flags — Stop and Re-Verify

- "It's just a one-line change, CI will be fine."
- "I'll fix conflicts after review."
- "I already verified this before my last change."
- "The reviewer is being picky; I'll ignore that comment."

All of these mean: re-run verification, then re-review, before requesting review again.

## This Repo's Verification Steps

1. **Dummy verification (local):** `uv run pytest` from repo root
2. **Real PR test:** apply to https://github.com/alehar9320/agentic-odi/pull/820
3. **After all gates pass:** submit this skill as its own PR

---

## Negative Constraints (what you must never do)

- ❌ Never merge with failing CI, even if "most" checks pass
- ❌ Never skip local verification of any fix
- ❌ Never mark a conflict "resolved" without manually applying the fix to your branch
- ❌ Never combine multiple fixes in one commit without clear separation
- ❌ Never defer a comment unless you have explicit author agreement