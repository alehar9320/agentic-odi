# 0008 — Require current branches and queue merges

- **Status:** accepted
- **Date:** 2026-11-17

## Context

`main` currently merges a pull request whose green run describes a tree that no
longer exists. `.github/pr-guardrails/config.yml` sets `max_behind: 50`, so a
branch up to 50 commits behind is only *warned* about (`scripts/pr_guards.py:170`
`check_freshness` returns warnings, never errors), and
`strict_required_status_checks_policy` is `false` on the `main-requires-ci-green`
ruleset. The conflict is then found by whoever merges, with no record of which
side won. There are 192 open pull requests at the time of writing.

## Decision

1. Lower the committed guardrail threshold from `max_behind: 50` to `max_behind: 10`
   in `.github/pr-guardrails/config.yml`. `GuardConfig.max_behind`'s dataclass
   default stays at `50`; only the committed config and its pinned test change.
2. Require up-to-date branches on the `main-requires-ci-green` ruleset (id
   `25356329`) by setting `strict_required_status_checks_policy: true`. This is
   an owner-applied repository setting; it is not changed by this pull request.
3. Enable the merge queue on `main`. This is also an owner-applied repository
   setting and is not changed by this pull request.
4. Record all three as the post-change state in `docs/architecture/README.md` and
   `docs/development.md`, keeping `CI green` and `PR guardrails` as the only
   code spans in the development-guide branch-protection table.

## Consequences

- Easier: a stale branch must be updated before it can land, and merges become
  slower by design rather than failing at merge time.
- Harder: merges become slower by design; a stale branch must be updated before
  it can land.
- Maintained: the guardrail's `max_behind` threshold stays pinned by
  `tests/scripts/test_pr_guards.py`, and the branch-protection table stays pinned
  by `tests/test_adr_index.py`.

## Alternatives considered

- **Leave `max_behind` at 50.** Rejected: it leaves `main` merging green-but-stale
  pull requests, which is the problem this record addresses.
- **Require up-to-date branches without the queue.** Rejected: without the queue,
  every stale branch forces a full re-run before merge, which scales poorly with
  192 open pull requests; the queue batches those updates.
