---
description: how to run the test suite
---

// turbo-all
1. Run all tests from the project root:

```bash
python -m pytest tests/ -v
```

2. Confirm all tests pass (exit code 0) and report a summary of the test results to the user.

   - If any test fails, read the failure output, investigate the affected source file(s), fix the issue, and re-run step 1.
   - Tests live in `tests/`. Every file must be named `test_*.py`.
   - Tests use `pytest` + `pytest-asyncio` in **STRICT** mode (`@pytest.mark.asyncio` required on every async test).
   - The shared `reset_db` fixture in each test file clears in-memory state before every test — do not skip it.
