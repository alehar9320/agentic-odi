# Design: Hold the line — a coverage floor that fails the build (#88)

**Source issue:** https://github.com/alehar9320/agentic-odi/issues/88  
**Date:** 2026-10-31  
**Status:** groomed, ready to implement — **FLAG: carries label `claimed/GH-Impl-2` ("In progress by agent GH-Impl-2")**  
**Labels carried over:** `spec`, `opportunity`, `priority/medium`, `area/ci`, `jules`

> **Before touching this issue:** verify whether `GH-Impl-2` still has it in progress. The label means another agent claimed it. If work exists (a branch or open PR), coordinate rather than duplicate. If the claim is stale, proceed.

---

## 1. Value score: 3 / 5

Engineering hygiene, not a direct user-facing feature. But it gates quality: a PR that drops coverage below 90% fails CI in a secret-free job before Codecov is ever involved. It also prevents the failure mode where machine-generated branches delete test files while claiming to add tests.

**One value increment:** A pull request that drops combined Python coverage below 90% fails the CI test job with the exact files that lost coverage; the front end has its own coverage gate set to current actuals; the coverage map is generated and CI-verified, not hand-maintained.

---

## 2. Preconditions / external dependencies

None within this batch. The `test` job must currently pass on `main` before the floor is added (you must run the suite first and confirm main passes the new gate — no threshold may fail on current `main`).

---

## 3. Atomic implementation steps

### Step 1 — Local coverage floor in `pyproject.toml`

Add to `pyproject.toml`:

```toml
[tool.coverage.report]
fail_under = 90
show_missing = true
skip_covered = true
```

This makes `uv run pytest --cov=…` fail locally when coverage drops below 90%. There is currently **no** `[tool.coverage.report]` and no `fail_under` anywhere in the repo (`git grep fail_under` returns nothing across `*.toml`, `*.yml`, `*.cfg`).

**Test:** run `uv run pytest --cov-fail-under=99 --cov=agentic_odi_core` locally and confirm it fails (proves the flag works).

**Definition of done:** `[tool.coverage.report] fail_under = 90` present; local pytest fails below 90%.

---

### Step 2 — Enforce the floor in the CI test job

In `.github/workflows/ci.yml`, the `test` job runs `uv run pytest --cov=… --cov-report=term-missing --cov-report=xml:coverage.xml`. Add `--cov-fail-under=90` to the pytest invocation so the `test` job itself goes red on sub-floor coverage. This does not depend on `CODECOV_TOKEN` and fires on a fork's pull request.

The floor measures the **combined** Python coverage exactly as CI measures it (single `pytest` over `testpaths = ["apps", "packages", "tests", "website"]` with a combined `--cov` over all five distributions). Do not measure per-package and average.

**Test:** CI `test` job goes red when coverage is artificially dropped below 90% (a CI smoke step, not a pytest).

**Definition of done:** `test` job passes `--cov-fail-under=90`; fails below 90%; no secret required.

---

### Step 3 — Secret-free fork-safe gate + Codecov comment

- `CODECOV_TOKEN` stays for the upload only; the floor is enforced by pytest's exit code, so forks are gated too.
- `codecov.yml` keeps `project.default.target: 90%` and `threshold: 1%` so the badge/PR comment reflect the same bar, but the authoritative gate is now the `test` job. Update the top-of-file comment to state that.
- Remove `apps/studio/**` from the `ignore` list **once** front-end coverage is uploaded (Step 6).

**Definition of done:** `codecov.yml` comment states the authoritative gate is the `test` job; floor works on forks.

---

### Step 4 — Current `main` must pass the new gate (no threshold introduced that fails today)

Run the suite first:
```bash
uv run pytest --cov=agentic_odi_cli --cov=agentic_odi_connectors --cov=agentic_odi_core --cov=agentic_odi_mcp-server --cov=agentic_odi_studio-api --cov-report=term-missing
```
Record the combined number. If it's below 90%, do **not** add the floor yet — raise coverage first (out of scope for this issue). The floor is set at 90 only if current `main` clears it.

**Definition of done:** Combined coverage on `main` ≥ 90%, confirmed by running the suite.

---

### Step 5 — A ratchet: the floor may never be lowered

Add a CI step (three lines) that reads the current coverage floor and compares it to the floor on the base branch; if the committed floor is **lower** than the floor on `main`, the job fails with *"the coverage floor may not be lowered"*. Copy the pattern from the existing "Verify generated API types are up to date" step in `ci.yml`.

**Test:** CI smoke step — verify the "floor may not be lowered" check fails when the floor is reduced.

**Definition of done:** CI step enforces the floor never decreases.

---

### Step 6 — Per-package coverage breakdown in the job summary

Add a CI step that runs coverage per distribution and appends a table to `$GITHUB_STEP_SUMMARY`. The aggregate gates; the table informs (prevents a collapsed package hiding inside the combined number).

**Definition of done:** Per-package breakdown published in the CI job summary.

---

### Step 7 — Front-end coverage floor

`apps/studio` has Vitest and no floor at all (`codecov.yml` ignores `apps/studio/**`).

- Add `@vitest/coverage-v8` as a dev dependency.
- `apps/studio/package.json` — add `"test:coverage": "vitest run --coverage"`.
- `apps/studio/vite.config.ts` — the `test` block sets:
  ```ts
  coverage: {
    provider: "v8",
    reporter: ["text", "lcov"],
    thresholds: { lines: 80, functions: 80, branches: 70, statements: 80 }
  }
  ```
- **The front-end thresholds are set to the current actual coverage and then held.** An 80% line threshold with a ratchet is honest; 90% would fail on day one and train people to ignore the gate. Record the current actual numbers (run `npm --prefix apps/studio test:coverage` first) in `docs/architecture/testing.md`.
- `codecov.yml` — remove `apps/studio/**` from `ignore` once front-end coverage is uploaded; add a Codecov upload step to the `studio` job.

**Test:** run `npm --prefix apps/studio test:coverage` and confirm it passes at current actuals.

**Definition of done:** Front-end has `test:coverage` script, v8 provider, thresholds at current actuals; `studio` job uploads coverage.

---

### Step 8 — Generated coverage map (not hand-maintained)

`README.md` has a hand-maintained **Test Coverage Map** table describing pre-restructure paths (`core/tests/…`, `mcp_server/tests/…`, …) — it's stale.

Create `scripts/coverage_map.py`:
- Walks the test directories, pairs each test file with the source files it exercises (by import path and by name), emits the Markdown table.
- A test asserts the generated table matches the committed `docs/architecture/testing.md` and the README section.
- A CI step regenerates and fails on drift (copy the "Verify generated API types are up to date" pattern).

Update `docs/architecture/testing.md` to hold the coverage map, and regenerate the README section from it. Do not delete the README section (guardrail requires it current); make it generated.

**Test:** `tests/scripts/test_coverage_map.py` — generator is deterministic; committed document matches; a test file with no source pair is reported rather than silently dropped.

**Definition of done:** Coverage map generated; CI drift check fails on stale map; README section generated not hand-written; stale pre-restructure paths gone.

---

### Step 9 — Record the coverage gaps

Issue §11.6 lists coverage holes; **record them, do not fix them here** (fixing is separate focused PRs). Add them to `docs/architecture/testing.md`:

Front end, no test file at all: `StudioContext.tsx` (1,021 lines, SSE dispatcher), `Hero.tsx`, `OfflineNotice.tsx`, `Markdown.tsx`, `SetupConversation.tsx` (509 lines), `DirectCapture.tsx`, `EvidenceStream.tsx`, `OutcomeCard.tsx`, `StudioBar.tsx`, `Toasts.tsx`, `ErrorBoundary.tsx`, `Skeletons.tsx`, `storage.ts`, `steps.tsx`, `content.ts`, `actions.ts`, `props.ts`, `catalog.ts`, `useMediaQuery.ts`, `schema.d.ts` (dead).

Back end uncovered paths: `MAX_TOOL_ROUNDS` exhaustion, MCP unreachable inside `stream_chat`, LLM completion raising, `render_ui` with `catalog is None`, changelog regex parser.

**Definition of done:** Gap list recorded in `docs/architecture/testing.md`.

---

## 4. Non-negotiable constraints

- The floor is enforced by the test job's exit code, not Codecov — works on forks and when upload fails.
- The floor measures combined Python coverage exactly as CI measures it.
- The coverage floor may never be lowered (CI step enforces).
- Front-end thresholds set to current actual coverage and held.
- The coverage map is generated and CI-verified, not hand-maintained.
- No threshold introduced that fails on current `main` (run the suite first).

---

## 5. Out of scope

- Raising the floor above current level (separate PRs).
- Adding tests for the gaps in §11.6 (record them, fix separately).
- Performance or mutation testing.

---

## 6. Verification

```bash
# Combined number CI sees
uv run pytest --cov=agentic_odi_cli --cov=agentic_odi_connectors --cov=agentic_odi_core \
  --cov=agentic_odi_mcp-server --cov=agentic_odi_studio-api --cov-report=term-missing

# Floor fails locally (proves flag works)
uv run pytest --cov=agentic_odi_core --cov-fail-under=99   # must fail

# Map is reproducible
uv run python scripts/coverage_map.py --check
```

Tests to add:
- `tests/scripts/test_coverage_map.py` — deterministic generator; committed document matches; unpaired test file reported.
- CI smoke step (not pytest): "floor may not be lowered" check fails when the floor is reduced.

## Context an implementing agent must read

- `pyproject.toml:37-46` — `[tool.coverage.run]`, `testpaths`, pytest config.
- `codecov.yml` — current target, `ignore` list, `patch.default.informational`.
- `.github/workflows/ci.yml` — `test` job, Codecov upload step (`fail_ci_if_error: false`), `studio` job's `gen:api-types` drift check (pattern to copy).
- `.github/actions/setup/action.yml` — shared setup installs.
- `docs/architecture/testing.md` — where the coverage map belongs.
- `README.md` — Testing → Test Coverage section + hand-maintained Test Coverage Map.
- `packages/core/src/agentic_odi_core/contract.py` + `tests/contract/test_mcp_contract.py` — existing generated, contract-tested artifact pattern to copy.
- `apps/studio/package.json`, `apps/studio/vite.config.ts` — front-end test setup.
- `apps/studio/src/features/flags.test.ts`, `apps/studio/src/ui/UiRenderer.test.tsx` — front-end test style.
- #86 — guardrails that will reject a diff lowering the floor.

## Open question for the human

The `claimed/GH-Impl-2` label: confirm whether to proceed or coordinate with the other agent. Also confirm front-end threshold baseline (run `npm --prefix apps/studio test:coverage` first to get current actuals).
