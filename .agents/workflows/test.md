---
description: how to run the test suite
---

# Test tiers

Pick the smallest tier that matches your time budget. CI owns the full matrix; agents must not be asked to run it all locally.

| Tier | Command | When | Notes |
|---|---|---|---|
| `--changed` (fast gate) | `uv run python scripts/verify.py --changed` | **Bar for opening a PR.** Run before opening or updating a PR. Fits inside a 10–30 minute agent budget. | Ruff check and format on touched paths, version parity, the generated docs blocks, the docs drift check, bandit for touched Python trees, pytest for selected packages, the brand render, Studio lint + typecheck, website pytest. Prints elapsed seconds and the CI-job coverage table. Fails if the diff selects no check. |
| `--default` | `uv run python scripts/verify.py --default` | Before asking for merge review. | Adds repo-wide `mypy`, Studio units + build + bundle budget, and the site build. Still not a substitute for CI. |
| `--full` | `uv run python scripts/verify.py --full` | **CI's job.** Do not run by default in agent runs. | Runs the whole local matrix (Python, website, Studio, docs, bandit, mypy). E2E, Tauri, and the dependency audit stay CI-only; the coverage table says why. Per-job budgets are 5–20 minutes in CI. |

`--full` is CI's responsibility. It budgets 5–20 minutes per job
(`.github/workflows/ci.yml`), so nobody is asked to run it locally before
opening a pull request.

## What `--changed` does not cover

The dependency audit (`pip-audit`, `npm audit`, `cargo audit`) is a CI job, not a
tier. It reads the lockfiles rather than the diff, so its result does not depend
on which files a pull request touched, and `--changed` neither runs it nor skips
it by selection. Run it by hand when a pull request changes a dependency; the
commands and the accepted-advisory ledger are in
[Development](../docs/development.md#linting-formatting--type-checks).

E2E, the contrast gate, and the Tauri jobs stay CI-only for the same kind of
reason: a browser, a built desktop app, and the Linux webview libraries are not
part of a 10–30 minute local budget. Every required CI job is either covered by
a tier or declared in `CI_JOB_COVERAGE` / `CI_ONLY_REASONS` in
`scripts/verify.py`, with the reason it cannot be. The gate prints that table on
every run, and `tests/scripts/test_verify_ci_parity.py` fails when the table and
`ci-green.needs` disagree.

## PR requirement (honest verification)

A pull request **must** list the tiers it ran and the tiers it skipped in the PR body (in the repo's spirit of no-silent-fabrication). For example:

```markdown
**Verification**
- Ran: `--changed`
- Skipped: `--default` (reason), `--full` (CI)
- Not verified: coverage, e2e, website, desktop (as applicable)
```

This is the repo's no-silent-fabrication rule applied to verification: a PR
that ran only the fast tier must not read as if it ran the default tier, and
a PR that ran nothing must say so instead of leaving the checkboxes blank.

## Running a tier by hand (for reference)

The script wraps these commands. Run them directly when you want to check one
slice yourself.

### Fast tier

`uv run python scripts/verify.py --changed` runs, in order:

```bash
uv run ruff check <touched .py files>
uv run ruff format --check <touched .py files>
uv run python scripts/check_version_parity.py
uv run python scripts/docs_index.py --check
uv run python scripts/doc_check.py
uv run bandit -c pyproject.toml -r apps packages   # when app/package Python changed
uv run pytest -q <selected packages>               # plus tests/ for docs or contract changes
npm --prefix apps/studio run lint                  # when the Studio changed
npm --prefix apps/studio run typecheck             # when the Studio changed
uv run --directory website pytest tests/           # when the site changed
```

This is the answer to "did I break the thing I just edit". It is not a
statement that the suite passes — it is a statement about the changed slice.

### Default tier — the bar for merge review

```bash
uv run python scripts/verify.py --default
```

On top of the fast tier this adds repo-wide `mypy`, the Studio unit suite, the
Studio build with its cold-start bundle budget, and the site build. Run it
before you ask for merge review. If it does not pass, the PR is not ready for
review.

The browser-level end-to-end suite and the desktop build are **not** part of
this tier. They need a browser download, a running sidecar, and the Rust
toolchain, and they are CI's job.

## 3. Full tier — CI's job

```bash
npm --prefix apps/studio run build
npm --prefix apps/studio run test:e2e
npm --prefix apps/studio run test:e2e:smoke
```

CI runs this against the real Studio, the real sidecar, and the real MCP
server, in two jobs:

- **`e2e-smoke` is required.** The `@smoke`-tagged handful, `--retries=0`, no
  `continue-on-error`, no repository-variable kill switch. If it is red, the
  merge is blocked, and that is the point.
- **`e2e` is advisory.** The whole suite with `--retries=1`. Set the repository
  variable `AGENTIC_ODI_E2E` to `false` to skip it; a failure is reported in the
  job summary (every failure, with its locator and call site), in a warning
  annotation, and in `CI green`'s table, without turning CI red. Set
  `AGENTIC_ODI_E2E_BLOCKING` to `true` to make the whole lane block.

`npm --prefix apps/studio run test:e2e:visual` is opt-in until the screenshot
baselines are committed; it is not part of either CI job.

A flaky spec is fixed or parked. Parking means a `// quarantined: #<issue>
<YYYY-MM-DD>` line in the spec plus an entry in `apps/studio/e2e/quarantine.ts`;
`apps/studio/src/test/e2eQuarantine.test.ts` fails the entry after thirty days,
and fails a marker with no entry. Do not add a retry loop to hide one.

## Honest PR bodies

A pull request names the tiers it ran and the tiers it did not run. In the
"Diff summary" section of the PR template, say which tier was the highest one
the author executed — and say plainly which tiers were skipped and why.

This is the repo's no-silent-fabrication rule applied to verification: a PR
that ran only the fast tier must not read as if it ran the default tier, and
a PR that ran nothing must say so instead of leaving the checkboxes blank.

## Where the tests live

Tests live next to the package they cover (`packages/*/tests`,
`apps/*/tests`, `website/tests`). Every file is named `test_*.py`.

- **pytest + pytest-asyncio in STRICT mode** — `@pytest.mark.asyncio` is
  required on every async test.
- **In-memory by default** — tests use `InMemoryRepository` and
  `AGENTIC_ODI_DB=:memory:`; no running server is required.
- **The `reset_db` fixture** clears in-memory state before every test — do
  not skip it.
- **End-to-end specs** live in `apps/studio/e2e/` and are named `*.spec.ts`.
  They bind to roles, labels, and visible text — never to a `data-testid`, of
  which the application has none, and never to a CSS class. Every spec imports
  `test`/`expect` from `e2e/fixtures.ts`, whose automatic fixture resets the
  shared studio before each test.
- **Browser mode** needs Chromium locally: `npx --prefix apps/studio playwright
  install chromium`. The unit suite deliberately ignores `*.visual.test.tsx`;
  those run under Chromatic on every branch push.
