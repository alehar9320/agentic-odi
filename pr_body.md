## Maintainer TL;DR
> This PR fixes a bug where a corrected API key keeps showing the old key's health verdict for up to 30 seconds. The probe cache is now invalidated when LLM settings are saved, and the cache key includes a truncated hash of the API key so key rotations naturally miss the cache.

## Summary of Changes
- **Core Logic:**
  - Added `_CONFIG_GENERATION` counter and `invalidate_probe_cache()` function to clear the probe cache when settings change
  - Updated cache key from `(endpoint, model)` to `(endpoint, model, key_hash)` where `key_hash` is a truncated SHA256 of the API key
  - Added `POST /api/config` endpoint to persist LLM settings and invalidate the probe cache
- **Targeted Scope:**
  - `apps/studio-api/src/agentic_odi_studio_api/studio/probes.py`
  - `apps/studio-api/src/agentic_odi_studio_api/studio/router.py`
  - `apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py`
  - `apps/studio-api/tests/test_probe_cache.py`

## Linked Issues & Context
- Closes #1136

## Verification & Scoped Tests Executed
- [x] Ran targeted test: `uv run pytest apps/studio-api/tests/test_probe_cache.py -v` (Pass - 7/7 tests)
- [x] Ran full test suite: `uv run pytest apps/studio-api/tests/ -v` (Pass - 497/497 tests)
- [x] Verified zero regressions in immediate module scope
- [x] Ran lint: `uv run ruff check` (Pass)
- [x] Ran typecheck: `uv run mypy` on modified files (Pass - only pre-existing error in unrelated function)

## Safety & Risk Self-Assessment
- **Assigned Risk:** risk:low
- **Breaking Changes:** None