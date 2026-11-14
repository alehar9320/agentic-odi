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
npm --prefix apps/studio ci                     # install (skips the optional tooling)
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
npm --prefix apps/studio run tooling:install  # Playwright, Chromatic, Tauri CLI
npm --prefix apps/studio run build
npm --prefix apps/studio run test:e2e
```

CI runs this in the `e2e` job against the real Studio, the real sidecar, and
the real MCP server. It is deliberately non-blocking: set the repository
variable `AGENTIC_ODI_E2E` to `false` to skip it, and `continue-on-error`
keeps a failure from turning CI red.

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
  which the application has none.
- **Browser mode** needs Chromium locally: `npx --prefix apps/studio playwright
  install chromium`. The unit suite deliberately ignores `*.visual.test.tsx`;
  those run under Chromatic on every branch push.