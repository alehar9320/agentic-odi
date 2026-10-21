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

3. Confirm all tests pass (exit code 0) and report a summary of the test results to the user.

   - If any test fails, read the failure output, investigate the affected source file(s), fix the issue, and re-run step 1.
   - Tests live under each project's `tests/` directory (`packages/core/tests/`, `apps/mcp-server/tests/`, `apps/cli/tests/`, `apps/studio-api/tests/`, `packages/connectors/tests/`, `website/tests/`). Every file must be named `test_*.py`.
   - Tests use `pytest` + `pytest-asyncio` in **STRICT** mode (`@pytest.mark.asyncio` required on every async test).
   - The mcp_server's shared `reset_db` fixture clears in-memory state before every test — do not skip it.
