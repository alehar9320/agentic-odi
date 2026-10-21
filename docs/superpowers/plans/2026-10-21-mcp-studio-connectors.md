# MCP ↔ Living Studio Connectors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Living Studio register/list/delete/health-check external connectors from conversation (LLM calls a local `add_connector` tool → `connector` SSE event) and from the Settings UI, all persisted to a shared `~/.config/agentic-odi/connectors.json` consumed by the CLI too.

**Architecture:** Backend-first in `packages/connectors` (shared path resolver + catalog `is_recommended` + registry `delete`), then the sidecar (`studio/connectors.py` + router + schemas), then a local tool in `studio/chat.py` + `connector` SSE, then the React settings/chat UI + API layer. Built in an isolated worktree off `fix/error-handling-hardening` so it does not touch the cwd's CGU WIP; the local-tool hook is a clean sibling of CGU's `render_ui`.

**Tech Stack:** Python (pydantic, fastmcp, FastAPI, pytest), TypeScript/React (vitest + @testing-library/react + jsdom).

**Spec:** `docs/superpowers/specs/2026-10-21-mcp-studio-connectors-design.md`

## Global Constraints

- All Python edits pass `uv run ruff check .` and `uv run mypy apps packages` with no NEW errors (37 pre-existing mypy errors are all in test files — out of scope).
- All tests run green: `uv run pytest packages/connectors/tests apps/studio-api/tests -q`; frontend: `apps/studio/src` via `npx vitest run`.
- Shared config path = `AGENTIC_ODI_CONNECTORS_CONFIG` env → else `~/.config/agentic-odi/connectors.json`.
- New code follows existing conventions (pydantic models, FastAPI TestClient, SSE `event:/data:` framing, vitest `mockJson`/`createSseParser`).
- `uv sync --all-packages` (plain `uv sync` skips the virtual workspace members).

## Review Focus

- Local tool path must NOT fall back to `mcp_client.call_tool` (regression risk: `add_connector` must be intercepted in-process).
- Connector routes must not depend on backend (works for both `local` and `mcp` modes).
- `connectors.json` must survive round-trips through CLI, sidecar, and service (same resolver).
- A malformed `add_connector` arg set / unknown preset must yield `connector`/`error`, not a 500.
- Frontend must keep rendering during an unknown/late SSE event type (forward-compat with CGU's `render_ui`/`ui:` events).

---

### Task 1: Shared config path resolver + registry delete

**Files:**
- Create: `packages/connectors/src/agentic_odi_connectors/paths.py`
- Modify: `packages/connectors/src/agentic_odi_connectors/__init__.py:32-59` (export `config_path`)
- Modify: `packages/connectors/src/agentic_odi_connectors/registry.py` (add `delete`)
- Test: `packages/connectors/tests/test_paths.py`, extend `packages/connectors/tests/test_registry.py`

**Interfaces:**
- Produces: `agentic_odi_connectors.paths.config_path() -> Path`
- Produces: `ConnectorRegistry.delete(name: str) -> bool`

- [ ] **Step 1: Write failing tests**
  `test_paths.py`: env override returns `Path(env)`; default returns `~/.config/agentic-odi/connectors.json`; parent created.
  `test_registry.py`: `delete("x")` returns True and persists; `delete("missing")` raises `ConnectorNotFoundError`.

- [ ] **Step 2: Verify RED** — `pytest packages/connectors/tests/test_paths.py packages/connectors/tests/test_registry.py -q`

- [ ] **Step 3: Implement** `paths.py` (`os.getenv` + `Path`); `registry.delete` (filter + `_save`, reuse `_known_kinds`? no).

- [ ] **Step 4: Verify GREEN** — same command passes.

- [ ] **Step 5: Commit** — `feat(connectors): add shared config resolver + registry delete`

### Task 2: Catalog recommended presets

**Files:**
- Modify: `packages/connectors/src/agentic_odi_connectors/catalog.py`
- Test: extend `packages/connectors/tests/test_catalog.py`

**Interfaces:**
- Produces: `ConnectorPreset.is_recommended: bool`; `list_presets(area=None, recommended=False)`

- [ ] **Step 1: Write failing tests**: `list_presets(recommended=True)` returns a non-empty subset; every recommended preset is in the full set; `is_recommended` field exists on `get_preset("notion")` (True) and a non-recommended one (False).

- [ ] **Step 2: RED**

- [ ] **Step 3: Implement** `is_recommended: bool = Field(default=False)` on `ConnectorPreset`; mark `notion,posthog,exa,linear,github` as recommended; `list_presets(..., recommended=False)` filter param.

- [ ] **Step 4: GREEN**

- [ ] **Step 5: Commit** — `feat(connectors): mark recommended MCP presets`

### Task 3: Sidecar ConnectorService (catalog/add/delete/health)

**Files:**
- Create: `apps/studio-api/src/agentic_odi_studio_api/studio/connectors.py`
- Modify: `packages/connectors/src/agentic_odi_connectors/__init__.py` (export `config_path`, `ConnectorService`? no — service is studio-api)
- Test: `apps/studio-api/tests/studio/test_connectors.py`

**Interfaces:**
- Produces: `ConnectorService(config_path: Path | None = None)` with `.catalog()`, `.add(name=None, preset_id=None, url=None) -> ConnectorConfig`, `.list() -> list[ConnectorConfig]`, `.delete(name) -> bool`, `.health(name) -> HealthStatus`.

- [ ] **Step 1: Write failing tests** (tmp_path): `add(name="gong", preset_id="gong")` persists + returns config; `add(name="x", url="http://y")` custom; `delete` removes; `catalog()` includes `is_recommended`; `health` on unknown raises `ConnectorNotFoundError`.

- [ ] **Step 2: RED**

- [ ] **Step 3: Implement** `ConnectorService` wrapping `paths.config_path()` + `ConnectorRegistry` + `get_preset`/`connector_config_from_preset`; `health` uses `build_connector(...).health()` with `asyncio.run` (mirror CLI's `_run`).

- [ ] **Step 4: GREEN** — `pytest apps/studio-api/tests/studio/test_connectors.py -q`

- [ ] **Step 5: Commit** — `feat(studio-api): add ConnectorService`

### Task 4: Sidecar REST routes + schemas

**Files:**
- Modify: `apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` (add request/response models)
- Modify: `apps/studio-api/src/agentic_odi_studio_api/studio/router.py` (add routes + `_connectors`)
- Modify: `apps/studio-api/src/agentic_odi_studio_api/app.py` (`app.state.connectors = ConnectorService()`)
- Test: `apps/studio-api/tests/studio/test_connectors_router.py`

**Interfaces:**
- Produces: `AddConnectorRequest`, `ConnectorCatalogItem`, `ConnectorListItem`, `ConnectorHealthResponse`.
- Routes: `GET /api/connectors/catalog`, `GET /api/connectors`, `POST /api/connectors`, `DELETE /api/connectors/{name}`, `POST /api/connectors/{name}/health`.

- [ ] **Step 1: Write failing tests** (TestClient on `create_app(InMemoryRepository())`): catalog list, add from preset, add custom, delete, health 404 on unknown; monkeypatch `build_connector` for health.

- [ ] **Step 2: RED**

- [ ] **Step 3: Implement** schemas + routes + `app.state.connectors`.

- [ ] **Step 4: GREEN**

- [ ] **Step 5: Commit** — `feat(studio-api): expose connector management REST routes`

### Task 5: Chat local `add_connector` tool + `connector` SSE

**Files:**
- Modify: `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`
- Modify: `apps/studio-api/src/agentic_odi_studio_api/studio/router.py` (`post_chat` passes service)
- Test: extend `apps/studio-api/tests/test_studio_chat_branches.py`

**Interfaces:**
- Produces: `ADD_CONNECTOR_TOOL` (openai tool def); `stream_chat(request, service=None)` intercepts `add_connector` locally; yields `connector` SSE event.

- [ ] **Step 1: Write failing tests** (reuse `_FakeOpenAI`/`_Mcp` harness): emit a tool_call `add_connector` with `{"name":"gong","preset":"gong"}` → SSE includes `event: connector` with `{"action":"registered","name":"gong"}`; `add_connector` with unknown preset → `connector` SSE `{"status":"error",...}` and no `mcp_client.call_tool`.

- [ ] **Step 2: RED**

- [ ] **Step 3: Implement** `ADD_CONNECTOR_TOOL`; append to `openai_tools`; branch in tool loop (`if name == "add_connector": events = _apply_add_connector(...)`); `_apply_add_connector(arguments, service)` returns list of SSE dicts.

- [ ] **Step 4: GREEN**

- [ ] **Step 5: Commit** — `feat(studio-api): conversational add_connector via local tool + connector SSE`

### Task 6: Frontend types + API layer

**Files:**
- Modify: `apps/studio/src/types.ts`
- Modify: `apps/studio/src/api/studioApi.ts`
- Test: extend `apps/studio/src/api/studioApi.test.ts` and `apps/studio/src/api/sse.test.ts`

**Interfaces:**
- Produces: TS types `ConnectorPreset`, `ConnectorConfigListItem`, `ConnectorHealth`.
- API fns: `fetchConnectorCatalog()`, `fetchConnectors()`, `addConnector({name,preset?,url?})`, `deleteConnector(name)`, `checkConnectorHealth(name)`.

- [ ] **Step 1: Write failing tests**: `fetchConnectorCatalog()` parses `{defaults}`? no — `/api/connectors/catalog`; `addConnector` POSTs `{name,url}`; `sse.test.ts` parses a `connector` frame.

- [ ] **Step 2: RED** (`npx vitest run src/api`)

- [ ] **Step 3: Implement** types + api fns.

- [ ] **Step 4: GREEN**

- [ ] **Step 5: Commit** — `feat(studio): add connector API + types`

### Task 7: Settings connectors section

**Files:**
- Modify: `apps/studio/src/components/SettingsPanel.tsx`
- Test: `apps/studio/src/components/SettingsPanel.test.tsx` (new, testing-library)

**Interfaces:**
- SettingsPanel reads `useStudio().connectors` + `refreshConnectors`.

- [ ] **Step 1: Write failing test**: renders registered connector names; "Add preset" button calls `addConnector`.

- [ ] **Step 2: RED**

- [ ] **Step 3: Implement** SettingsPanel connectors block.

- [ ] **Step 4: GREEN**

- [ ] **Step 5: Commit** — `feat(studio): add Connectors section to Settings`

### Task 8: ChatCopilot connector suggestion cards

**Files:**
- Modify: `apps/studio/src/components/chat/ChatCopilot.tsx`
- Modify: `apps/studio/src/state/StudioContext.tsx`
- Test: `apps/studio/src/components/chat/ChatCopilot.test.tsx` (new)

**Interfaces:**
- StudioContext handles `connector` SSE → `connectorSuggestions` state + `pushToast`.
- ChatCopilot renders `connectorSuggestion` cards and a click-to-dismiss.

- [ ] **Step 1: Write failing test**: a `connector` `registered` event appears as a suggestion card; clicking dismiss removes it.

- [ ] **Step 2: RED**

- [ ] **Step 3: Implement** SSE case in StudioContext + cards in ChatCopilot.

- [ ] **Step 4: GREEN**

- [ ] **Step 5: Commit** — `feat(studio): render connector registration as suggestion cards`

### Task 9: CLI alignment + final verification

**Files:**
- Modify: `apps/cli/src/agentic_odi_cli/connectors.py` (`_config_path` → `paths.config_path`)
- Test: run existing CLI contract + connectors tests; full suite.

- [ ] **Step 1: Align** `_config_path` to shared resolver; keep `--config` override + env override semantics (`AGENTIC_ODI_CONNECTORS_FILE` still maps to `config_path`? preserve backward compat: env `AGENTIC_ODI_CONNECTORS_FILE` → `AGENTIC_ODI_CONNECTORS_CONFIG`.)

- [ ] **Step 2: Run full backend suite** `uv run pytest packages/connectors/tests apps/studio-api/tests -q` + `uv run ruff check .`

- [ ] **Step 3: Update README** connectors section (paths/config).

- [ ] **Step 4: Commit** — `refactor(cli): align connector config path with sidecar resolver`

### Task 10: Branch, push, PR, green CI

- [ ] `git checkout -b feature/mcp-studio-connectors` (already created as worktree branch off b646384)
- [ ] Commit all task commits on `feature/mcp-studio-connectors`
- [ ] Push branch, create PR against `main`
- [ ] CI green (ruff, mypy, pytest, vitest)
- [ ] Report PR URL
