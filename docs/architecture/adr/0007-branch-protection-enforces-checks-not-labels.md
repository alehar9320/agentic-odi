# 0007 — Branch protection enforces the checks, not the label

- **Status:** accepted
- **Date:** 2026-11-14

## Context

[ADR 0005](0005-core-layers-and-the-contract-split.md) records the pattern this
record follows: when a proposal meets the repository as it actually is, write down
what the repository can enforce rather than what the proposal asked for.

Phase 2 ([#938](https://github.com/alehar9320/agentic-odi/pull/938)) added
`ai-merge-safe` and `ai-merge-authorized` labeling, and
[the merge act workflow](../../.github/workflows/pr-ai-merge-act.yml) arms
`gh pr merge --auto` on any PR carrying `ai-merge-authorized`. Labels are
advisory: the only thing that reads them is the workflow that acts on them.
[#956](https://github.com/alehar9320/agentic-odi/issues/956) asked to close that
gap by requiring `ai-merge-safe` on the `main-requires-ci-green` ruleset,
alongside the two required status checks.

Reading the live ruleset settled the shape of the question.
`gh api repos/alehar9320/agentic-odi/rulesets/25356329` returns one rule,
`required_status_checks`, with contexts `CI green` and `PR guardrails`. The same
endpoint is where a ruleset's rule types are discovered, and a label is not one
of them: `creation`, `update`, `deletion`, `non_fast_forward`, `pull_request`,
`required_signatures`, `required_linear_history`, `required_status_checks`,
`merge_queue`, `copilot_code_review`. So "require the label in the ruleset" is not
a settings step that was forgotten; it is not expressible. A ruleset can require a
*check*, and only a workflow produces a check.

The live settings also showed the documents had drifted past what the ruleset
does. `docs/architecture/README.md` claimed
`strict_required_status_checks_policy: true` and a `bypass_mode: pull_request`;
neither is in the payload. The field is `current_user_can_bypass`, and it is
`never` on both rulesets. `docs/agents.md` and `docs/development.md` described the
label as a ruleset requirement, which is the claim that would send the next
maintainer to a GitHub setting that does not exist.

## Decision

1. The ruleset's requirement is two status checks. `main-requires-ci-green`
   (id `25356329`, `enforcement: active`, `current_user_can_bypass: never`) targets
   `~DEFAULT_BRANCH` and requires `CI green` and `PR guardrails`. A second
   ruleset, `protect-main` (id `25656413`), adds `deletion`, `non_fast_forward`,
   and `pull_request` — the last with `required_approving_review_count: 0` and
   `require_extra_approval_for_unattributed_changes: true`.
2. `ai-merge-safe` stays a gate of the merge path, not of the ruleset. Gate 1 of
   `scripts/pr_ai_authorize.py` refuses `ai-merge-authorized` without it, and the
   merge act workflow arms auto-merge only on that label. The docs say that, and
   say plainly that a ruleset cannot require a label.
3. The documented set becomes machine-checkable in the one direction the checkout
   can see. `tests/test_adr_index.py` reads the `name:` of job `ci-green`
   ([`ci.yml`](../../.github/workflows/ci.yml)) and job `pr-guardrails`
   ([`pr-guardrails.yml`](../../.github/workflows/pr-guardrails.yml)), and fails
   when the branch-protection table in `docs/development.md` or the ruleset
   paragraph in `docs/architecture/README.md` names a different set. A job rename
   now breaks the pull request that renamed it, instead of leaving `main` waiting
   forever for a check nothing reports.
4. If the label is to be enforced by GitHub itself, the mechanism is a required
   status check that fails without it — a job that reads the PR's labels and exits
   non-zero — not a label rule. Deferred: it puts a job on every pull request, and
   it is a policy call about whether an agent-authored PR should be stopped before
   a human has read it.

## Consequences

- Easier: a maintainer can tell which rule is GitHub's and which is the merge
  path's, and the two cannot drift silently in the direction a test can see.
- Harder: GitHub does not enforce the label. A pull request that satisfies both
  checks can merge without `ai-merge-safe`; what stops it is the merge act
  workflow not arming auto-merge, plus `do-not-merge` and `needs human review`.
  That is process, not settings, and it is now written down as such.
- Harder: rulesets live outside the checkout, so no test can read them. The parity
  test covers the *names* the documents claim; the settings themselves still need
  `gh api` and a maintainer's eyes, which is why
  `docs/architecture/README.md` records the rule ids.
- Maintained: the ADR index is checked too. Every record needs a row, every row
  resolves to a file, the row's status matches the record's own **Status:**, and
  every record carries the six sections this index promises.

## Alternatives considered

- **Require approving reviews instead of the label.** `protect-main` already
  requires a pull request and already requires an extra approval for changes
  attributed to unattributed authors, but `required_approving_review_count` is 0.
  Raising it changes the human review flow and still does not distinguish an
  agent pull request from a human one.
- **Leave the documents as they were.** Rejected: they describe settings that do
  not exist, which is worse than saying nothing, because a maintainer "verifies"
  a rule that was never there.
- **A `label gate` status check now.** The right mechanism, and the one recorded in
  the decision above — but it is a workflow change with its own CI cost and a
  policy question behind it, so it is a trigger rather than part of this record.
- **Classic branch protection
  (`/branches/main/protection`).** Rejected: it answers 403 for this integration,
  and rulesets supersede it, so it is not where the rule can be recorded or read.