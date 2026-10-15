---
description: how to run the test suite
---

// turbo-all
1. Run all tests from the project root:

```bash
uv run --directory core pytest
uv run --directory mcp_server pytest
uv run --directory local_server pytest
uv run --directory client pytest
uv run --directory cli pytest
```

2. Confirm all tests pass (exit code 0) and report a summary of the test results to the user.

   - If any test fails, read the failure output, investigate the affected source file(s), fix the issue, and re-run step 1.
   - Tests live under each project's `tests/` directory (`core/tests/`, `mcp_server/tests/`, `local_server/tests/`, `client/tests/`, `cli/tests/`). Every file must be named `test_*.py`.
   - Tests use `pytest` + `pytest-asyncio` in **STRICT** mode (`@pytest.mark.asyncio` required on every async test).
   - The mcp_server's shared `reset_db` fixture clears in-memory state before every test — do not skip it.
