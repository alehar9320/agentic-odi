# Landscape bulk organisation — implementation plan

> **For agentic workers:** steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** let a person select outcomes in the Opportunity Landscape, preview the exact bulk
change table, apply it, read per-row skips, and undo — over two new Studio API routes that
wrap the ALH-196 service.

**Architecture:** `POST /api/outcomes/bulk` and `POST /api/outcomes/bulk/undo` are thin
adapters in `apps/studio-api/.../studio/router.py` over `ODIService.bulk_update_outcomes`
and `ODIService.undo_bulk`, following the file's existing `_uses_mcp` → `call_mcp_tool`
else `_service(request)` shape. The browser holds no rules: it renders the `BulkReport`
dictionary. Selection is a `Set` in `OpportunityLandscape`; the wider "all matching" run is
expanded by the route through `search_outcomes`, never by the UI.

**Tech stack:** FastAPI + pydantic (studio-api), React 19 + TypeScript + vitest (studio),
pytest `TestClient`.

**Spec:** `docs/superpowers/specs/2026-11-03-landscape-bulk-organisation-design.md`

## Global constraints

* No new core validators, no new event types, no change to `TOOL_SPECS` — the tool surface
  stays `outcome_ids`-only (`tests/contract/test_bulk_contract.py` pins it).
* Every route keeps the shared error envelope: raise `_as_http_error(exc)`; the body is
  `{error: {code, message, detail, suggestion, retryable, request_id}}`.
* Frontend copy is plain language, `type="button"` on every button, counts in a
  `role="status"` element, checkboxes carry an accessible name.
* `apps/studio/openapi.json` and `apps/studio/src/api/schema.d.ts` are committed artifacts:
  regenerate both in the task that adds a route, or CI's `npm run gen:api-types` +
  `git diff --exit-code` fails.
* Run `uv run pytest` from the repo root; `ruff check`, `ruff format --check`,
  `uv run mypy apps brand packages`, `uv run python scripts/doc_check.py` stay clean.

## Review Focus

* A preview that writes — the dry run must leave the event log untouched; nothing in the UI
  distinguishes them except the report.
* A partial run described as a success — skipped rows have to be visible next to the count.
* An undo that would overwrite someone's newer edit — the service skips that row; the bar
  must show the reason rather than the local copy it wanted to restore.
* An expired or already-used token — an error sentence, no optimistic restore, canvas
  refreshed from the store.
* An empty selection and a contradictory change (same theme added and removed) — refused
  before any write, by the route and by the service respectively.

---

### Task 1: `POST /api/outcomes/bulk`

**Files:**
- Modify: `apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` (after `UpdateOutcomeRequest`)
- Modify: `apps/studio-api/src/agentic_odi_studio_api/studio/router.py` (after the `search_outcomes` route, ~line 585)
- Test: `apps/studio-api/tests/test_studio_bulk.py` (new)

**Interfaces:**
- Consumes: `ODIService.bulk_update_outcomes(outcome_ids, *, add_theme_ids, remove_theme_ids, stage, add_tags, query=None, dry_run=False) -> BulkReport`; `BulkReport.as_dict()` → `{requested, changed, skipped, changes, undo_token}`; `ToolName.BULK_UPDATE_OUTCOMES.value`; `_uses_mcp`, `_require_mcp_url`, `call_mcp_tool`, `_json_or_raw`, `_as_http_error`, `_service`.
- Produces: `BulkQuery` (narrowing mirror of the search route's arguments), `BulkRequest`
  (`mcp_url`, `outcome_ids: list[str]`, `query: BulkQuery | None`, `stage`, `add_theme_ids`,
  `remove_theme_ids`, `add_tags`, `dry_run`), `_bulk_target_ids(request, mcp_url, outcome_ids, query) -> list[str]`,
  and `POST /api/outcomes/bulk` returning the report dict.

- [x] **Step 1: write the failing router tests** in `test_studio_bulk.py`, using
  `def _client(kind: str) -> TestClient: return TestClient(create_app(InMemoryRepository(), backend=backend))`
  the way `test_studio_router.py:15` does, and seeding through `client.post("/api/jobs")` +
  `client.post("/api/outcomes")`:
  * a dry run returns the change table and `undo_token is None`, and a second read of the
    outcome shows nothing was written;
  * one unknown id among the selection comes back in `skipped` with `"outcome not found"`
    while the good row is in `changed`;
  * `outcome_ids: []` is a 400 whose `error.message` contains `No outcomes selected`;
  * `stage="migrate"` is a 400 with `Unknown stage: migrate`;
  * the same theme in `add_theme_ids` and `remove_theme_ids` is a 400 and writes nothing;
  * `query` widens the run: the report's `requested` is the search total, not the checked
    count, and every id the search names is in `changed`.

- [x] **Step 2: run them, confirm they fail** — `uv run pytest apps/studio-api/tests/test_studio_bulk.py -q`
  (404s / unknown route).
- [x] **Step 3: implement.** Add `BulkQuery`/`BulkRequest` to `schemas.py`; add
  `_bulk_target_ids` (pages `search_outcomes` with `limit=200` until it has `total` ids,
  unioned with the named ids, order-stable) and the route in `router.py`. Pass
  `dry_run` through in both the MCP and local branches.
- [x] **Step 4: run the tests, confirm they pass.**
- [x] **Step 5: commit** `feat(studio-api): POST /api/outcomes/bulk · ALH-197`.

### Task 2: `POST /api/outcomes/bulk/undo`

**Files:** Modify `schemas.py` (`BulkUndoRequest`), `router.py`; extend
`apps/studio-api/tests/test_studio_bulk.py`.

**Interfaces:**
- Consumes: `ODIService.undo_bulk(token: str) -> BulkReport`, `ToolName.UNDO_BULK.value`,
  Task 1's report shape.
- Produces: `POST /api/outcomes/bulk/undo` taking `{mcp_url, token}` and returning the
  restored-row report; a token that expired or was already used is a 400 whose message is
  the service's own sentence.

- [x] **Step 1: failing tests** — apply through the route, undo through the route, the
  outcome reads back as it was; undo twice → 400 `already undone`; undo a token from an
  older run after a newer one wrote → 400 naming the newer token; a row edited by hand
  between apply and undo is in the undo report's `skipped`.
- [x] **Step 2: verify they fail**, then **Step 3: implement** the route, **Step 4: verify
  they pass**, **Step 5: commit** `feat(studio-api): undo a bulk run over HTTP · ALH-197`.

### Task 3: the UI preview and the CLI preview are one calculation

**Files:** Test: `tests/contract/test_bulk_contract.py` (extend).

- [x] **Step 1: write the parity test** — build one fixture, run the CLI's
  `LocalBackend.run_tool("bulk_update_outcomes", {..., "dry_run": True})` and the route's
  same call on an `ODIService` over the same store, and assert the two `changes` lists and
  the two `skipped` lists are equal, and that the store's event count is unchanged by the
  pair of previews.
- [x] **Step 2: run it** — `uv run pytest tests/contract/test_bulk_contract.py -q`. Fix
  whatever ordering difference it exposes in the route (it must not re-sort rows the service
  returned).
- [x] **Step 3: commit** `test(contract): the Studio and CLI previews agree row for row`.

### Task 4: regenerate the OpenAPI artifacts

- [x] **Step 1:** dump `create_app(...).openapi()` into `apps/studio/openapi.json` in the
  same 2-space JSON shape that is committed (the file is generated in-process; there is no
  script).
- [x] **Step 2:** `cd apps/studio && npm run gen:api-types`.
- [x] **Step 3:** `git diff --exit-code -- src/api/schema.d.ts` after a second `gen:api-types`
  run proves the committed types are current; commit
  `chore(studio): regenerate OpenAPI for the bulk routes`.

### Task 5: the client half — types and fetchers

**Files:** Modify `apps/studio/src/types.ts`, `apps/studio/src/api/studioApi.ts`;
test `apps/studio/src/api/studioApi.bulk.test.ts` (new).

**Interfaces:**
- Produces for Task 6: `BulkChangeRow {outcome_id, field, from, to}`, `BulkReport
{requested, changed, skipped, changes, undo_token}`, and
  `previewBulkOutcomes(body)` / `applyBulkOutcomes(body)` / `undoBulkOutcomes({mcp_url, token})`,
  all returning `Promise<BulkReport>` and rejecting with `StudioApiError` on a refused run.

- [x] **Step 1: failing fetcher tests** with `vi.stubGlobal("fetch", …)`: the body is posted
  to `/api/outcomes/bulk` with `dry_run: true` for the preview and `false` for the apply; a
  400 envelope rejects with the `StudioError` inside it, keeping the server's message.
- [x] **Step 2: implement**, **Step 3: `npx vitest run src/api` passes**, **Step 4: commit**
  `feat(studio): bulk preview, apply and undo fetchers`.

### Task 6: selection, the change bar, and the change dialog

**Files:** Modify `apps/studio/src/components/canvas/OpportunityLandscape.tsx`,
`apps/studio/src/components/canvas/OutcomeCard.tsx`, `apps/studio/src/styles/theme.css`;
Create `apps/studio/src/components/canvas/BulkChangeBar.tsx`,
`apps/studio/src/components/canvas/BulkChangeDialog.tsx`;
Test `apps/studio/src/components/canvas/OpportunityLandscape.bulk.test.tsx` (new),
extend `apps/studio/src/test/a11y.test.tsx` only if the sweep needs the bar mounted.

**Interfaces:**
- Consumes: Task 5's fetchers; `Narrowing` and the landscape's `result: OutcomeSearch`
  (its `total` is the wider action's number); `JOB_STAGES`; the `themes` list already
  fetched; `useFocusTrap`.
- Produces: `BulkDraft {stage?, addThemeIds, removeThemeIds, addTags}` and
  `BulkChangeBar({selectedCount, matchingTotal, themes, draft, busy, onClear, onDraftChange, onPreviewSelected, onPreviewAll})`,
  `BulkChangeDialog({report, mode, error, themes, steps, busy, onApply, onUndo, onClose})` where `mode` is
  `"preview" | "applied"`; `OutcomeCard` and the table row take an optional
  `checked` / `onToggleChecked` pair, which the landscape supplies only when there is a
  store to write to.

- [x] **Step 1: failing component tests** (same `vi.mock` harness style as
  `OpportunityLandscape.search.test.tsx`):
  * ticking two cards shows the bar naming `2 selected`; with a narrowing whose `total` is
    137, the bar offers `Preview all 137 matching` and the checked-count line separately;
  * with nothing selected the bar is absent and no preview call is made;
  * pressing Preview calls the preview fetcher, renders one table row per
    `changes` entry with its `from` and `to`, and lists a skipped row with its reason;
  * Apply sends the same run without the preview flag, then the dialog reads
    `12 changed · 3 skipped` — the test asserts the skipped number is in the sentence;
  * Undo calls the undo fetcher with the token and the dialog closes on the returned report;
  * a rejected preview keeps the selection and the drafted change (the bar is still there
    with the same numbers) and shows the server's message;
  * an expired-token error is shown with no optimistic restore: the canvas refreshes and the
    rows keep the applied values.
- [x] **Step 2: implement** selection state (`Set<string>`, toggle without touching
  `focusSubject`), a checkbox in `OutcomeCard` and in the table row, the bar, the dialog.
- [x] **Step 3: `npx vitest run src/components/canvas` and `npx tsc -b --noEmit` pass**, then
  **Step 4: the a11y sweep passes** in cards, matrix and table view (`npx vitest run src/test/a11y.test.tsx`).
- [x] **Step 5: commit** `feat(studio): select, preview, apply and undo bulk changes in the landscape`.

### Task 7: document it

**Files:** Modify `docs/living-studio.md` (the "What the canvas is made of" section),
`README.md`.

- [x] **Step 1:** write the selection and undo limitations into `docs/living-studio.md`:
  checked rows are the run; the wider run is a named action whose count came from the same
  search; the matrix view cannot select; a preview is not a promise — the write's own skip
  reasons win; an undo token expires under a newer run and restores only untouched rows.
- [x] **Step 2:** one `README.md` capability sentence for the landscape bulk run.
- [x] **Step 3:** `uv run python scripts/doc_check.py` clean; commit
  `docs(living-studio,README): the landscape's bulk run and its limits`.
- [ ] **Step 4:** full gates — `uv run pytest -q`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy apps brand packages`,
  `cd apps/studio && npx eslint . && npx vitest run` — then push and open the PR stacked on
  `qoder/ALH-196-bulk-outcome-changes`, move ALH-197 to In Review in Linear with the link.
