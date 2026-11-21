# 0011 — Require current branches and queue merges

- **Status:** accepted
- **Date:** 2026-11-17

## Context

[ADR 0007](0007-branch-protection-enforces-checks-not-labels.md) settled what the
`main-requires-ci-green` ruleset (id `25356329`) can require: two status checks,
`CI green` and `PR guardrails`, and no label. It also recorded, in passing, that
the same ruleset carries `strict_required_status_checks_policy: false` — a green
run describes whatever tree the branch had when the run started, not the tree
`main` would have after the merge.

Two facts make that gap expensive rather than theoretical. Measured on
2026-11-17, `gh pr list --state open` reports 181 open pull requests, so a branch
sitting behind `main` is the normal case, not the exception. And
`.github/pr-guardrails/config.yml` sets `max_behind: 50`, read by `load_config()`
([`scripts/pr_guards.py`](../../../scripts/pr_guards.py)) with the same value as
`GuardConfig`'s default; `check_freshness` returns a *warning* when
`behind > max_behind`, never an error. A branch fifty commits behind or fewer
therefore hears nothing at all — the limit is a silence threshold, not a warning
threshold — and a pull request whose checks passed against a tree that no longer
exists still merges.

The conflict then surfaces at merge time, in front of whoever merges, with no
record of which side won. The guardrail measures the wrong thing: it warns about a
stale base instead of refusing one.

[#956](https://github.com/alehar9320/agentic-odi/issues/956), which this record's
issue supersedes, asked the ruleset to require the `ai-merge-safe` label. ADR 0007
already answered that a ruleset cannot require a label, so the intent behind #956
— "do not let a stale or unreviewed pull request land" — is expressed here through
the settings a ruleset *can* hold: up-to-date branches and the merge queue.

## Decision

1. **Tighten the guardrail's freshness threshold.** `.github/pr-guardrails/config.yml`
   sets `max_behind: 10`, down from `50`. `check_freshness` keeps its existing
   behaviour — a branch is stale when `behind > max_behind` — so the warning now
   fires once a branch is more than ten commits behind `main` (the eleventh commit
   behind and beyond) instead of more than fifty, which is the point at which a
   rebase is still cheap. `GuardConfig`'s dataclass default stays `50`; only the
   committed config file and the test that pins it change, so an unconfigured
   checkout keeps the historical default.
2. **Require up-to-date branches before merge (owner-applied).** Set
   `strict_required_status_checks_policy: true` on the `main-requires-ci-green`
   ruleset. This is a repository setting, not a file: it is applied by the owner
   with `gh api`, and no pull request can carry it. It is recorded here so the
   decision is not lost between the change and the setting.
3. **Queue merges (owner-applied).** Enable the `merge_queue` rule on the same
   ruleset, so a pull request merges against the current `main` and its checks run
   on the queued tree rather than on a snapshot. Also a repository setting, and
   also owner-applied. **Prerequisite:** neither required workflow
   (`.github/workflows/ci.yml`, `.github/workflows/pr-guardrails.yml`) declares the
   `merge_group` trigger today, so a queued commit would report neither `CI green`
   nor `PR guardrails` and could never leave the queue. The owner enables the queue
   only after both workflows run on `merge_group`, and `pr-guardrails.yml` needs its
   own base resolution for that event because it reads `github.base_ref` and
   `github.event.pull_request`; that workflow change is not part of this record.
4. **Record the two settings as owner-applied, not as done.** The documents that
   describe the ruleset state the post-change intent and name these two settings
   as applied by the owner, so a reader can tell what the checkout enforces from
   what only GitHub can.

## Consequences

- Easier: a stale branch is caught by the guardrail once it is more than ten
  commits behind instead of more than fifty, while a rebase is still a rebase
  rather than a merge-resolution exercise.
- Easier: with strict checks and the merge queue on, the checks a merge waits for
  describe the tree that lands, so the "green but stale" merge stops being possible
  rather than being found by whoever merges.
- Harder: merges become slower by design. A branch that falls behind must be
  updated and its checks re-run before it can land, and the merge queue serialises
  what used to be concurrent merges. That cost is the feature.
- Harder: the two settings live outside the checkout. No test can read them, so
  the repository can only record the intent and rely on the owner to apply it; the
  freshness threshold is the half the checkout can enforce, and it is the half
  this change makes.
- Maintained: the fresh half is measured on the commit the guardrail checks out.
  `pr-guardrails.yml` runs on the `pull_request` event, where `actions/checkout`
  checks out GitHub's test merge commit — which already contains the base branch —
  and `_diff_shape` counts `rev-list HEAD..origin/main`. That count reports how far
  `main` moved after the merge commit was built, not how far the contributor's
  branch sits behind, so in CI the warning does not fire on a stale branch. Making
  the CI measurement read the pull-request head (`refs/pull/N/head`) is a workflow
  change and the follow-up this threshold needs before it can bind there.
- Maintained: `tests/scripts/test_pr_guards.py` pins the committed `max_behind` at
  `10`, so a future edit to the threshold must change the test deliberately, and
  `tests/test_adr_index.py` keeps this record's heading, status, date, and sections
  honest.

## Alternatives considered

- **Leave `max_behind` at 50.** Rejected: fifty commits is past the point where a
  rebase is routine, and the warning arrives too late to be cheap. It also leaves
  the guardrail measuring a quantity nobody acts on.
- **Require up-to-date branches without the merge queue.** The two settings do
  different work. Strict checks refuse a stale branch; the queue is what lets a
  correct branch land without a second race against `main`. Requiring up-to-date
  branches alone re-introduces that race — every branch must be re-updated after
  each merge — so the queue is what makes the strictness bearable.
- **Make freshness an error in `scripts/pr_guards.py` instead of tightening the
  config.** Rejected for this change: it moves a warning to a hard failure in the
  guardrail job, which is a larger behavioural change than the threshold, and the
  ruleset settings are where the enforcement belongs. The threshold is the part the
  checkout can own.
- **Re-implement #956 by requiring `ai-merge-safe` in the ruleset.** Not
  expressible; ADR 0007 records why. The label stays a gate of the merge path, and
  #956 is closed with a pointer to this record rather than re-implemented.
