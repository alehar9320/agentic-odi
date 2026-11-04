# ALH-163 (M2-01.2) — Theme tree with its rollup: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every theme a read-only rollup — outcomes, measured, top opportunity — that counts a parent and its children as a union of outcome ids, from the terminal, over MCP, and on the board, with the landscape's theme facet filtering by the same subtree rule.

**Architecture:** One new core module (`theme_tree.py`) owns the subtree walk and the count; `ODIService` exposes `theme_rollup`/`list_theme_rollups`; two READ MCP tools and one CLI command call them; `OutcomeQuery.include_children` threads the same rule through search so the card's number and the board's list cannot disagree. Nothing is stored: no event, no table, no field, no `_apply_event` branch.

**Tech Stack:** Python 3.14 (pydantic v2, FastAPI, Typer, MCP), stdlib-only core; React 19 + TypeScript + Vitest in `apps/studio`; uv workspace, ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-11-04-alh-163-theme-rollup-design.md`

## Global Constraints

- `THEME_DEPTH = 2` is the only depth number, used by the write that refuses a third level and the read that stops at the second. No unbounded recursive walker.
- A parent's count is a **union of outcome ids**, never the sum of its children's counts.
- `measured` uses `query.is_scored` and nothing else; `top_opportunity`/`top_statement` are `None` — never `0.0` — when no included outcome is scored.
- No new entity: `ThemeRollup` stays out of `schema._SCHEMA_MODELS`, and `packages/core/tests/test_persistence_parity.py` passes **without being edited**.
- Repeated reads create no events and change no outcome.
- `get_`/`list_` prefixes derive READ: do not state `effect=` for the two new tools, and do not add them to `declared_reads` in `packages/core/tests/test_capability_manifest.py`.
- Docs land in the same PR: `README.md`, `docs/cli.md`, `docs/living-studio.md`, `docs/roadmap.md`.
- Branch from the stack tip (`qoder/ALH-223-xlsx-import`, PR #745); PR base is that branch.

## Review Focus

The five inputs the spec implies and no task's happy-path test would catch:

1. **One outcome filed in the parent and in two children** — must count once, not three (Task 1).
2. **A theme whose outcomes are all unscored** — `outcomes > 0`, `measured = 0`, top absent; no surface invents `0.0` (Task 1, Task 3).
3. **A corrupt parent chain** (A→B→A, reachable because `Theme` only forbids self-parentage) — bounded walk returns, does not spin (Task 1).
4. **Missing theme vs malformed request vs failed read** — 404 / 422 / error, three distinct answers on both doors (Task 4, Task 5).
5. **`include_children` with a theme id that does not exist**, and the same query through the terminal and `GET /api/outcomes/search` — same ids, same total, same refusal (Task 2, Task 5).

---

### Task 1: The rollup, in core

**Files:**
- Create: `packages/core/src/agentic_odi_core/theme_tree.py`
- Modify: `packages/core/src/agentic_odi_core/models.py` (add `THEME_DEPTH = 2` beside `Theme`)
- Modify: `packages/core/src/agentic_odi_core/services.py:1426-1442` (use `THEME_DEPTH` in the refusal), and add `theme_rollup` / `list_theme_rollups` after `list_themes` (1450)
- Modify: `packages/core/src/agentic_odi_core/query.py:86-87` (`_is_scored` → `is_scored`, update its three uses)
- Modify: `packages/core/src/agentic_odi_core/__init__.py` (re-export `ThemeRollup`)
- Test: `packages/core/tests/test_theme_rollup.py`

**Interfaces:**
- Consumes: `Repository.themes: dict[str, Theme]`, `Repository.outcomes: dict[str, Outcome]`, `Theme.parent_id/ordinal/job_id/name`, `rank_outcomes`, `is_scored`.
- Produces:
  - `ThemeRollup(theme_id: str, name: str, parent_id: str | None, outcomes: int, measured: int, top_opportunity: float | None, top_statement: str | None)` with `as_dict()`.
  - `subtree_ids(themes: Mapping[str, Theme], theme_id: str, depth: int = THEME_DEPTH) -> list[str]` — the theme first, then its children, at most `depth − 1` levels down, cycle-safe.
  - `build_rollup(theme: Theme, themes: Mapping[str, Theme], outcomes: Sequence[Outcome]) -> ThemeRollup`.
  - `ODIService.theme_rollup(theme_id: str) -> ThemeRollup` (raises `ThemeNotFoundError`), `ODIService.list_theme_rollups(job_id: str | None = None) -> list[ThemeRollup]` ordered `(job_id or "", ordinal, name)`.

- [x] **Step 1: Write the failing tests** in `test_theme_rollup.py`, each with its own seeded store helper (`_service_with(themes, memberships)` — build on the fixtures already used in `packages/core/tests/test_themes.py`): overlap-counts-once, parent-equals-union-not-sum, `measured` excludes unscored and equals `search_outcomes(theme_ids=subtree).facets.confidence.scored`, tie resolves to `sort_outcomes`'s first scored item, all-unscored → `(top_opportunity, top_statement) == (None, None)` with `measured == 0`, empty theme → `(0, 0, None, None)`, `subtree_ids` stops at depth 2, `subtree_ids` terminates on an A↔B parent cycle built straight through the repository, workspace-theme rollup includes only outcomes of any job it files, `theme_rollup("nope")` raises `ThemeNotFoundError` whose message names the id.
- [x] **Step 2: Run them, watch them fail** — `uv run pytest packages/core/tests/test_theme_rollup.py -q` → `ModuleNotFoundError: agentic_odi_core.theme_tree`.
- [x] **Step 3: Implement** `theme_tree.py` (model + the two functions; the union is a set of `outcome.id`, the top is `rank_outcomes(scored)[0]`), public `is_scored`, `THEME_DEPTH` in `models.py`, the two service methods, and a comment in `_validate_theme_placement` naming `THEME_DEPTH` as the bound that sentence states. Keep the refusal text identical to today's — two tests pin its words.
- [x] **Step 4: Add the no-write proof:** a test that calls `theme_rollup` twice against a SQLite repository and asserts the event count, `repo.outcomes` and every theme are unchanged. Also read `git diff --stat` — `sqlite_repository.py`, `schema.py`, `repository.py` must not appear.
- [x] **Step 5: Gates** `uv run pytest packages/core -q` (includes `test_persistence_parity.py`, unedited), `uv run mypy packages`, `uv run ruff format --check packages/core`, `uv run ruff check packages/core`.
- [x] **Step 6: Commit** `feat(core): roll a theme tree up into counts (ALH-163)`.

### Task 2: The facet's subtree rule, in `OutcomeQuery`

**Files:**
- Modify: `packages/core/src/agentic_odi_core/query.py` (`include_children` field, expansion inside `search_outcomes` after `_validate_query`)
- Test: the existing core search test file (`packages/core/tests/test_outcome_search.py` — find it with `ls packages/core/tests | grep -i search`; add there, not a new file)

**Interfaces:**
- Consumes: `theme_tree.subtree_ids`.
- Produces: `OutcomeQuery(..., include_children: bool = False)`; `search_outcomes` returns the subtree's `items`/`total` when it is true; facet counts unchanged in meaning.

- [ ] **Step 1: Write the failing tests** — selecting a parent with `include_children=False` returns its own memberships only; with `True` it returns parent + children and `total` equals `theme_rollup(parent).outcomes`; a child selected with `True` returns its own items (a leaf has no children); `theme_ids=["ghost"]` with `True` still refuses `Unknown theme: ghost`; the `theme` facet keeps counting direct memberships of each theme while the list is the subtree.
- [ ] **Step 2: Run → fail** (unknown keyword / differing totals).
- [ ] **Step 3: Implement** the field and the expansion — one `if query.include_children and query.theme_ids:` block that rebuilds `theme_ids` from `subtree_ids` over `repo.themes`, deduplicated and order-preserving.
- [ ] **Step 4: Run → pass**, then `uv run pytest packages/core -q`.
- [ ] **Step 5: Commit** `feat(core): a theme query that means its whole subtree (ALH-163)`.

### Task 3: The contract, the server, and the terminal's read path

**Files:**
- Modify: `packages/core/src/agentic_odi_core/contract.py` (`ToolName` members `GET_THEME_ROLLUP`, `LIST_THEME_ROLLUPS`; two `TOOL_SPECS` entries in the theme block; `search_outcomes` spec gains `include_children`)
- Modify: `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` (two `@mcp.tool` handlers beside `list_themes:944`; `search_outcomes` parameter)
- Modify: `apps/cli/src/agentic_odi_cli/backend.py` (`LocalBackend._get_theme_rollup`, `._list_theme_rollups`, `_LOCAL_HANDLERS` entries, `search_outcomes` argument pass-through)
- Test: `apps/mcp-server/tests/test_theme_tools.py`, `packages/core/tests/test_capability_manifest.py` (extend, do not re-create), `tests/contract/test_cli_contract.py` (asserts set equality — no edit should be needed)

**Interfaces:**
- Consumes: `ODIService.theme_rollup` / `list_theme_rollups`, `OutcomeQuery.include_children`.
- Produces: tool names `get_theme_rollup(theme_id)`, `list_theme_rollups(job_id=None)` returning `ThemeRollup.as_dict()` JSON (one object / an array); `search_outcomes(..., include_children: bool = False)`.

- [ ] **Step 1: Write the failing tests** — `get_theme_rollup` answers JSON with the four counts and no `0.0` when nothing is measured; `list_theme_rollups` answers an array ordered like the service; both appear in `TOOL_NAMES`, in `capability_manifest()["tools"]` and in `capability_summary()` (the existing parametrized assertions cover them once the specs exist — add the two sentences to the specs first); `validate_tool_specs(tools=_live_tools()) == []`; the two tools' effect is READ without stating `effect=`; `search_outcomes` with `include_children=true` returns the subtree through the server.
- [ ] **Step 2: Run → fail** (`ToolName member has no TOOL_SPECS entry`, and the CLI contract set-equality failure).
- [ ] **Step 3: Implement** the specs (arguments `["theme_id"]` / `["job_id"]`, required `["theme_id"]` / `[]`, stage `"2"`, `returns` sentences naming the four fields and the absent-top rule), the two handlers in the `list_themes` shape (`json.dumps(...model_dump(mode="json"))`, `_fail(exc)` on error), and the two local backend methods.
- [ ] **Step 4: Run** `uv run pytest apps/mcp-server packages/core/tests/test_capability_manifest.py tests/contract -q` → pass; then `uv run pytest -q` once to catch every enumeration test.
- [ ] **Step 5: Commit** `feat(mcp): read a theme's rollup over the contract (ALH-163)`.

### Task 4: `odi themes rollup`

**Files:**
- Modify: `apps/cli/src/agentic_odi_cli/themes.py` (new `rollup` command), `apps/cli/src/agentic_odi_cli/render.py` (`render_theme_rollup`, `render_theme_rollup_list`)
- Modify: `docs/cli.md` (the `## Themes` command list at 364-384, plus the search-semantics section for `--with-children`), `README.md` (the `odi themes …` block near :181 and the capability line near :149)
- Test: `apps/cli/tests/test_themes_cli.py`, `tests/scripts/test_cli_docs.py` (verify granularity before assuming)

**Interfaces:**
- Consumes: `run_tool("get_theme_rollup"/"list_theme_rollups", args)`.
- Produces: `odi themes rollup <theme-id> [--json]` and `odi themes rollup --job <job-id> [--json]`.

- [ ] **Step 1: Write the failing tests** — one theme prints the block (`name`, `4 outcomes · 3 measured`, `top 12.5 — <statement>`); an empty theme prints `no outcomes yet` with no digits invented; an all-unscored theme prints `nothing measured yet`; `--json` carries `top_opportunity: null`; `--job` prints one row per theme, parents before their children; `themes rollup` with neither argument exits 1 with `'rollup wants a theme: name one with THEME_ID or list a scope with --job'`; an unknown id exits 1 and prints the not-found sentence; nothing is written (assert a read-only store's event count via `--dry-run`-free equality, or simply that `run_tool` was called with a `get_`/`list_` tool).
- [ ] **Step 2: Run → fail** (no such command).
- [ ] **Step 3: Implement** the command with `theme_id: str = typer.Argument(None, ...)`, and the two renderers using the existing `_block`/`_table` helpers.
- [ ] **Step 4: Read it by hand:** `uv run odi themes rollup <real-id>`, `uv run odi themes rollup --job <real-job> --json`, `uv run odi themes rollup` (the sentence, exit 1), against a fixture job with an overlapping membership and an unscored theme.
- [ ] **Step 5: Docs**, then `uv run python scripts/doc_check.py` → exit 0 and `uv run pytest tests/scripts -q`.
- [ ] **Step 6: Commit** `feat(cli): odi themes rollup reads the tree with its counts (ALH-163)`.

### Task 5: The board's facet, then the card

**Files:**
- Modify: `apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` (`BulkQuery.include_children`), `.../studio/router.py` (`search_outcomes_api` gains `include_children: bool = Query(False)`, passed into `arguments` only when true)
- Modify: `apps/studio/openapi.json`, `apps/studio/src/api/schema.d.ts` (regenerated)
- Modify: `apps/studio/src/types.ts` (`ThemeRollup`, `OutcomeSearch`/`Narrowing` param), `src/api/studioApi.ts` (append `include_children`), `src/components/canvas/OpportunityLandscape.tsx` (a subtree control on the theme `FacetGroup`, visible only when a selected theme has children; the active chip reads `Billing (incl. subthemes)`), `src/ui/catalog.ts` + `src/ui/registry.ts` + `src/ui/cards.tsx` (`theme_tree` card), `docs/living-studio.md` (the "nine primitives and nine cards" sentence at :560 → ten cards; the facet paragraph at 295-306)
- Test: `apps/studio-api/tests/test_studio_themes.py`, `apps/studio/src/components/canvas/OpportunityLandscape.search.test.tsx`, a new `apps/studio/src/ui/ThemeTreeCard.test.tsx` (or the existing cards test file), `tests/contract/test_outcome_search_parity.py`

**Interfaces:**
- Consumes: `ToolName.SEARCH_OUTCOMES` with `include_children`; the service reads for the card's props (the agent supplies them from `list_theme_rollups`).
- Produces: `GET /api/outcomes/search?include_children=true`; `theme_tree` catalog type with props `{ themes: ThemeRollup[], actions }`.

- [ ] **Step 1: Write the failing studio-api tests** — `include_children=true` narrows to the subtree and the body equals the terminal's for the same query; a missing `theme_id` in the list is a 422/400 envelope and an unknown-but-well-formed theme is the contract's `Unknown theme:` sentence — pin which one and keep missing ≠ malformed; no new route appears in `openapi.json` beyond the parameter.
- [ ] **Step 2: Write the failing parity case** in `tests/contract/test_outcome_search_parity.py`: the same `include_children` query through `LocalBackend` and through the route returns identical ids and `total`.
- [ ] **Step 3: Implement** the route parameter and `BulkQuery` field; regenerate OpenAPI (`create_app(InMemoryRepository(), backend="local").openapi()` → `apps/studio/openapi.json`), run `npm --prefix apps/studio run gen:api-types` twice, prove the second run byte-identical and `git diff --exit-code -- apps/studio/src/api/schema.d.ts` clean.
- [ ] **Step 4: Write the failing Studio tests** — a theme with children offers the subtree control, selecting it sets the flag and refetches, the chip label says *incl. subthemes*, a leaf offers no control; the `theme_tree` card renders a parent row with its rolled-up count, an indented child, `no outcomes yet` for an empty theme, and never `0.0`.
- [ ] **Step 5: Implement** the facet control and the card (catalog entry description > 20 chars, `actions` prop present, registered in `NODE_COMPONENTS`).
- [ ] **Step 6: Gates in `apps/studio`:** `npx tsc -b --noEmit`, `npx eslint .`, `npx vitest run`.
- [ ] **Step 7: Commit** `feat(studio): a theme tree that shows its counts and filters by subtree (ALH-163)`.

### Task 6: The equivalence claim, the roadmap, and the site

**Files:**
- Modify: `docs/roadmap.md` (In-flight line **See the tree with its rollup**, this change)
- Test: whatever `website/` assertion the two new tools move (run the suite and read the reported byte count before touching the ceiling)

- [ ] **Step 1: Add the cross-surface test** — for a seeded job with an overlapping membership: `theme_rollup(parent).outcomes == search_outcomes(theme_ids=[parent], include_children=True)["total"]`, and the Studio card's numbers come from the same `list_theme_rollups` payload the CLI prints. One assertion per pair, named for the drift it prevents.
- [ ] **Step 2: `uv run --directory website pytest tests/ -q`.** If the MCP reference page breaks 110 KB, extend the existing comment with the two one-argument tools and move the ceiling to the measured figure plus headroom — the pattern the comment already records five times. Do not split the page here.
- [ ] **Step 3: Roadmap line**, then `uv run python scripts/doc_check.py` → exit 0.
- [ ] **Step 4: Full gate set from the root:** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy apps brand packages`, `uv run pytest -q`, `uv run python scripts/check_version_parity.py`.
- [ ] **Step 5: Commit** `test(core): the rollup and the facet answer for the same outcomes (ALH-163)`.

## Ship

`git push -u origin qoder/ALH-163-theme-rollup`; PR base `qoder/ALH-223-xlsx-import` (#745), title `feat: read a theme tree's rollup from the terminal, MCP and board`. Body: the issue's own promise (a tree that carries its counts, read-only, no second hierarchy), the design's eight calls with the ones marked *my call* flagged, a `Reuses:` block — rung 1: `rank_outcomes`, `_is_scored`/`is_scored`, `list_themes`'s scope rule, `ThemeNotFoundError`, `_validate_theme_placement`'s depth sentence, `search_outcomes`'s facet machinery, `_block`/`_table` renderers, `FacetGroup`, `catalog.ts`/`NODE_COMPONENTS`, `_LOCAL_HANDLERS`/`run_tool`; rung 2: nothing new installed — no dependency is added by this change — and say which rung each new function failed. Then the Verification numbers. Then ALH-163 → In Review in Linear with the PR link in the same comment. Do not wait for CI; afterwards re-check #745 and #721 for conflicts.

## Verification

Root: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy apps brand packages`, `uv run pytest -q` (2258 at branch start, more at the end), `uv run python scripts/doc_check.py`, `uv run python scripts/check_version_parity.py`, `uv run --directory website pytest tests/ -q`.
`apps/studio`: `npx tsc -b --noEmit`, `npx eslint .`, `npx vitest run` (1073 at branch start).
Issue's own commands, all green: `uv run pytest packages/core -k theme && npm --prefix apps/studio test -- --run -t theme` — note the issue writes `uv run mypy apps packages`; run `apps brand packages` (the superset this repo's CI uses).
Read by hand: `odi themes rollup <id>` for a parent with children, for an empty theme, for an unscored theme, `--job <id>` for the tree, and `odi themes rollup` with no argument (the sentence, exit 1).
