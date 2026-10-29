---
description: how to run the test suite
---

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
