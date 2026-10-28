---
description: how to run the test suite
---

1. Run all checks from the repository root:

```bash
uv run ruff check .
uv run mypy apps packages
uv run pytest
```

2. Confirm all commands exit 0 and report a summary of the test results.

   - If a check fails, read the failure output, investigate the affected source file(s), fix the issue, and re-run step 1.
   - Tests live under each package's `tests/` directory (`apps/*/tests/`, `packages/*/tests/`). Cross-package contract tests live in `tests/contract/`. Every file must be named `test_*.py`.
   - Tests use `pytest` + `pytest-asyncio` in **STRICT** mode (`@pytest.mark.asyncio` required on every async test).
   - The MCP server tests use an in-memory repository fixture; SQLite is the production default.
