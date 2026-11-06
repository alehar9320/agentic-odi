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

## PR requirement (honest verification)

A pull request **must** list the tiers it ran and the tiers it skipped in the PR body (in the repo's spirit of no-silent-fabrication). For example:

```markdown
**Verification**
- Ran: `--changed`
- Skipped: `--default` (reason), `--full` (CI)
- Not verified: coverage, e2e, website, desktop (as applicable)
```

## Legacy notes (for reference)

If you need to run things manually:

1. Run all Python tests from the project root (workspace-aware):

```bash
uv run pytest
```

2. Run website tests separately:

```bash
uv run --directory website pytest tests/
```

3. Run the studio's frontend units:

```bash
npm --prefix apps/studio test -- --run
```

4. Run the browser-level end-to-end suite (build the SPA first — the sidecar serves `apps/studio/dist`):

```bash
npm --prefix apps/studio run build
npm --prefix apps/studio run test:e2e
```

   The first run needs the browser: `npx --prefix apps/studio playwright install chromium`.

5. Confirm all tests pass (exit code 0) and report a summary of the test results to the user.

   - If any test fails, read the failure output, investigate the affected source file(s), fix the issue, and re-run step 1.
   - Tests live under each project's `tests/` directory (`packages/core/tests/`, `apps/mcp-server/tests/`, `apps/cli/tests/`, `apps/studio-api/tests/`, `packages/connectors/tests/`, `website/tests/`). Every file must be named `test_*.py`.
   - Tests use `pytest` + `pytest-asyncio` in **STRICT** mode (`@pytest.mark.asyncio` required on every async test).
   - The mcp_server's shared `reset_db` fixture clears in-memory state before every test — do not skip it.
   - End-to-end specs live in `apps/studio/e2e/` and are named `*.spec.ts`. They bind to roles, labels, and visible text — never to a `data-testid`, of which the application has none.
