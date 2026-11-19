# 0010 — The pre-PR gate accounts for every required CI job

- **Status:** accepted
- **Date:** 2026-11-18

## Context

`CI green` is the status check the `main-requires-ci-green` ruleset requires,
and it aggregates twelve jobs. `scripts/verify.py --changed` is the documented
bar for opening a pull request, but it was a separate list kept by hand, and it
had fallen behind:

- it never ran `ruff format --check`, `doc_check.py`, `docs_index.py --check`,
  bandit, `check_version_parity.py`, or the brand render, so a pull request
  could pass the documented gate and open red on the required `lint`, `docs`,
  or `security` job;
- for a studio-only diff it ran no command at all, and for a website-only diff
  it ran no command at all, and both printed `PASSED`. A gate that reports on
  work it never looked at is worse than no gate.

Over the two days to 2026-11-18, 46% of `CI` runs on the repository were red.
Part of that was a tree defect no local gate can see: unregistered gitlinks
under `.qoder/` made `actions/checkout` exit 128 before a single test ran. The
rest included failures the pre-PR tier claimed to cover and did not.

## Decision

`scripts/verify.py` builds an explicit plan of `Step`s per tier. The checks
that can drift from any edit and are cheap — version parity, the generated
documentation blocks, and the docs drift check — run on every diff. The rest
are selected by path. A diff that selects no step, and an empty diff against
the base ref, both exit non-zero: selection may narrow what is run, never
whether anything was run.

The gate declares `CI_JOB_COVERAGE`, one entry per job in `ci-green.needs`,
mapping the job to the tiers that cover it, and `CI_ONLY_REASONS` for the jobs
that cannot run on a laptop (the network, Chromium, Rust, a real service boot).
`tests/scripts/test_verify_ci_parity.py` parses `ci.yml` and fails when the
declaration and the workflow disagree in either direction, when a CI-only job
has no reason, or when a covered job names a tier that does not exist. The
same file tests the planner: a studio-only diff selects Studio lint and
typecheck, a website-only diff selects the site suite, and an empty or
zero-step run fails.

## Consequences

- A pull request can trust the fast tier again: what it says it ran is what it
  ran, and the coverage table says what it did not.
- The fast tier is slower for mixed diffs. A `.github/` change already selected
  every Python package; it now also selects Studio lint and typecheck. That is
  the cost of the gate matching the checks the merge waits on.
- Adding a required CI job is a two-file change. The contract test fails until
  `verify.py` says whether a tier covers it or why it cannot. That is the
  point: the decision is recorded where a reviewer reads it.
- The gate still does not reproduce the 3.10/3.12 matrix, coverage, Chromium,
  or Rust. Those stay CI's, and the table says so on every run.

## Alternatives considered

- **Run the whole CI matrix locally.** It needs three Python versions, a
  browser download, the Linux webview libraries, and a Rust build; it does not
  fit the 10–30 minute agent budget and would be skipped in practice.
- **Generate the coverage table from `ci.yml` at runtime.** It would always
  agree, and it would hide the only judgement that matters: whether a job can
  run on a laptop. A human writes the reason; a test keeps it honest.
- **Keep the gate advisory and rely on CI.** This is the status quo the red
  rate measured. A required job that fails an hour after the pull request opens
  costs a review cycle; the same failure in the fast tier costs a minute.
