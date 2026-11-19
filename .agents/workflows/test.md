---
description: how to run the test suite
---

# Test tiers

Pick the smallest tier that matches your time budget. CI owns the full matrix; agents must not be asked to run it all locally.

| Tier | Command | When | Notes |
|---|---|---|---|
| `--changed` (fast gate) | `uv run python scripts/verify.py --changed` | **Bar for opening a PR.** Run before opening or updating a PR. Fits inside a 10–30 minute agent budget. | Ruff on touched paths, pytest for selected packages. Prints elapsed seconds per step and what was skipped. Fails loudly if a touched file maps to no test target. |
| `--default` | `uv run python scripts/verify.py --default` | Before asking for merge review. | Adds `mypy` for touched packages and `vitest` for touched studio files. Still not a substitute for CI. |
| `--full` | `uv run python scripts/verify.py --full` | **CI's job.** Do not run by default in agent runs. | Runs today's full matrix (Python, website pytest, studio vitest, `npm run build`, Playwright e2e). Per-job budgets are 5–20 minutes in CI. |

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

```bash
uv run pytest packages/<changed>     # pytest on the packages the diff touches
uv run ruff check .                  # lint (the fast tier stops at lint, not format)
```

This is the answer to "did I break the thing I just edit". It is not a
statement that the suite passes — it is a statement about the changed slice.

## 2. Default tier — the bar for opening a PR

```bash
uv run pytest                # all Python tests
uv run --directory website pytest tests/
npm --prefix apps/studio test -- --run          # studio units (jsdom)
npm --prefix apps/studio run lint               # ESLint
npm --prefix apps/studio run typecheck          # tsc --noEmit
```

Run this before you open a pull request. If it does not pass, the PR is not
ready for review.

The browser-level end-to-end suite and the production build are **not** part
of this tier. They live in the full tier on purpose: they need a browser
download and a running sidecar, and they are CI's job.

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
