# 0009 — The AI merge gate reads the check suite, not the commit status

- **Status:** accepted
- **Date:** 2026-11-17

## Context

PR [#1100](https://github.com/alehar9320/agentic-odi/pull/1100) merged on
2026-11-17 at 05:37:01Z with a red `End-to-end` check on its head commit, and
without ever carrying `ai-merge-safe` or `ai-merge-authorized`. The issue
timeline has no label event for either one; the labels present were risk, size,
provenance, triage and merge-state labels. Three things in the merge path made
that possible.

1. [`pr-ai-merge-act.yml`](../../.github/workflows/pr-ai-merge-act.yml) woke on
   `pull_request: types: [labeled]` and took the event's PR number at face value.
   It never checked which label was added, and never re-read
   `ai-merge-authorized`. A label the authoring bot added at 05:07:15 armed
   auto-merge at 05:07:24.
2. Both merge workflows defined "CI green" as
   `GET /commits/{sha}/status` → `.state`. That endpoint reports *commit
   statuses*; in this repository the only producer is Chromatic (`Test suite
   publish`, `UI Tests`), and every CI job is a check run. Commit `30033d3` had
   `state: success` at 05:06:17 with `total_count: 2`, while its Actions check
   suite had not reported a single result. The gate read "Chromatic is done",
   not "CI is green".
3. Nothing disarmed auto-merge. Armed at 05:07:24, it survived six pushes and a
   red `End-to-end`, and GitHub's ruleset merged at 05:37:01 because the
   required `CI green` aggregate is green by design when only the advisory
   browser lane fails. A red check and a green required check coexisted, and no
   human was reading.

The intended chain — `ready-for-merge` → `ai-merge-safe` →
`ai-merge-authorized` → arm — was starved rather than absent:
`ready-for-merge` is applied only when `mergeStateStatus` is `clean`, which is
only true after the required checks pass, and any push clears it again. The
broken path armed in seconds; the intended path waited for the six-hourly sweep.
That asymmetry is why the hole went unnoticed.

ADR 0007 explains why the ruleset cannot require a label. This record explains
why the label stopped being the gate: the bot trusted a signal that was not CI,
and acted on an event that was not authorization.

## Decision

1. `scripts/pr_ai_authorize.py` owns "CI green". A pure `compute_ci_state()`
   judges the head commit from its GitHub Actions check runs: `CI green` and
   `PR guardrails` must be present and successful, and every other Actions
   check that failed or timed out blocks unless it is on `ADVISORY_CHECKS`
   (`End-to-end`, the browser suite, which `AGENTIC_ODI_E2E_BLOCKING` promotes
   to a gate). Absent or unfinished is pending, never green. Check runs from
   other apps are reported, not gated: they are not required checks. The legacy
   combined commit status is not consulted.
2. `pr-ai-authorize.yml` and `pr-ai-merge-act.yml` consume that one entrypoint,
   so the label and the arm decision cannot disagree about what green means.
3. The merge act wakes only on the labels that can change its decision
   (`ai-merge-authorized`, `do-not-merge`, `needs human review`), and re-reads
   the whole chain before arming: authorization, trust label, merge state, open
   state, head SHA, check suite.
4. Every run can disarm. If `autoMergeRequest` is set and a gate stops holding —
   label removed, new push, human override, red check — the workflow calls
   `gh pr merge --disable-auto` and comments why. Arming is a request, not a
   decision.
5. `label-merge-conflicts.yml` also runs on `check_suite: completed`, so
   `ready-for-merge` lands when CI finishes instead of up to six hours later.
   Closing the fast path without this would effectively switch auto-merge off.

## Consequences

- Easier: "green" means one thing in the aggregate, the label and the merge act,
  and the comment on the pull request names the head commit that was judged and
  the reason.
- Easier: a new red Actions job blocks without anyone adding it to a list, and a
  new third-party check cannot block a merge.
- Harder: the advisory set is a second place to maintain. It is one constant and
  it reads the same repository variable `ci.yml` reads, so the two policies move
  together.
- Harder: a pull request armed before this change is disarmed at its next label
  or sweep event, so a few queued merges will stop and need a human.
- Maintained: `tests/scripts/test_pr_ai_authorize.py` pins the verdict (red
  required, red non-advisory, red advisory, pending, absent, cancelled,
  third-party) and `tests/scripts/test_pr_ai_merge_act.py` pins the trigger, the
  re-read and the disarm, including that both workflows use the same entrypoint.

## Alternatives considered

- **Keep the combined status and add ruleset checks.** Rejected: that status is
  green before CI runs, so it cannot distinguish "CI passed" from "Chromatic
  posted".
- **Make every check blocking, including the browser suite.** Rejected: the
  suite is flaky by its own admission and the repository already ships a switch
  to make it blocking later. Default-deny over Actions checks with one
  documented exception keeps the queue moving without hiding anything.
- **Merge directly instead of `--auto`.** Rejected: `--auto` is evaluated
  atomically by GitHub against the required checks, which is stronger than a
  read-then-write. The bot's job is to decide whether the pull request is
  authorized, not to re-implement the merge.
- **Arm only from the schedule.** Rejected: up to six hours of latency, and the
  schedule still needs the same disarm path.
