# Pillar 5 — Prove & Reach: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the proof that the ODI spine works end to end, the demo that makes it visible, and the reach artifacts (shares, publishes, guides, branding, theming, locale) — without fabricating data, weakening authorization, or shipping a shareable artifact that leaks private bytes.

**Architecture:** ALH-11 is a *coordination* issue, not one implementation prompt. Its 21 active direct children are decomposed across M1–M5. This plan (a) fixes the delivery waves and cross-issue seams, (b) executes the two dependency-free foundation slices that everything else inherits, and (c) names the exact blocker for every remaining slice rather than inventing a stub.

**Tech Stack:** Python 3.10+ (`agentic_odi_core`, `agentic_odi_connectors`, FastMCP, SQLite), FastAPI sidecar (`apps/studio-api`), React/Vite Studio (`apps/studio`), Typer CLI (`apps/cli`), pytest + inline-snapshot.

**Spec:** Linear ALH-11 and its children (ALH-53, ALH-61, ALH-59, ALH-63, ALH-112, ALH-173, ALH-113, ALH-115, ALH-116, ALH-174, ALH-176, ALH-119, ALH-120, ALH-121, ALH-122, ALH-127, ALH-129, ALH-130, ALH-131, ALH-132, ALH-133, ALH-134). Six children were trashed and are out of scope: ALH-54, ALH-55, ALH-56, ALH-57, ALH-60, ALH-62.

## Global Constraints

Copied verbatim from the children; every task implicitly includes them.

- Branch from `origin/main`.
- **New entity? Touch every link in the persistence checklist:** models, repository Protocol + in-memory, SQLite `_apply_event`, remote, schema, service, contract, CLI, studio-api, studio types.
- Docs land in the same PR: `README.md` for a new command or package, `docs/cli.md` for a new flag, `docs/living-studio.md` for a new surface, `docs/roadmap.md` ticked when a milestone item completes.
- No fabricated data. Every surface must be able to say "nothing yet".
- AI output is a proposal; a human accepts it.
- A share token grants read access to exactly one view; tokens are stored hashed, never persisted/logged raw.
- Preview/dry-run never writes or calls transports.
- Provenance is generated, never hand-written; a redaction is always disclosed.
- No raw colour literal in a Studio component (ALH-121); no hardcoded user-facing string (ALH-122).

## Review Focus

1. **Coordination-vs-implementation confusion** — a child marked "Coordination only" must not be re-implemented on the parent; its bounded children own the code.
2. **Authorization on anonymous reads** — `GET /shared/{token}` is the only anonymous route; no mutation route may resolve a token.
3. **Exactly-once claims** — neither Slack webhooks nor Linear/Notion/Confluence APIs promise it; unknown delivery is reported, never silently retried.
4. **Public bytes** — HTML comments, provenance footers, hidden tables and chart alt text are all audience-visible; filter them under the same disclosure policy as visible content.
5. **Honest skips** — a skipped headless print check or unrun screen-reader audit is reported as unverified, never as a pass.

---

## Scope reality: why this is a plan, not a diff

The 21 active children are **not** independently executable today. Eleven of them name a dependency that does not exist in the tree yet (the M1–M3 spine: candidate extraction/acceptance, scoring, `brief.py`, `memo.py`, decision, bet, measure, stakeholder message). The repo today has the *foundation* (models, repository, event store, MCP contract, CLI, Studio) and the M0/M1 CRUD surface, but no `brief.py`, `memo.py`, `handoff.py`, `provenance.py`, `onepager.py`, `templates.py`, `PublishLink`, `SharedView`, or decision/bet/measure modules.

Two children are **dependency-free** and are the explicit first items in ALH-11's delivery order:

- **ALH-53 (F1) — a schema version you can migrate** — foundation for every new entity type the other 19 write.
- **ALH-61 (H1) — pin the contract, fail on drift** — the gate that keeps the 30+ tool surface honest while 50 tickets touch it.

This plan executes those two now (Wave 1) and lays out the remaining waves with their blocking dependency named. It does **not** invent stubs for missing spine stages.

---

## Dependency waves

| Wave | Issue | Title | Depends on | Status |
|------|-------|-------|-----------|--------|
| 1 | ALH-53 | F1 · A schema version you can migrate | — | **execute now** |
| 1 | ALH-61 | H1 · Pin the contract, fail on drift | — | **execute now** |
| 2 | ALH-63 | H3 · One end-to-end test of the spine | A4, A5, B1, C1, C6, E1, E2 (M1 spine) | blocked |
| 2 | ALH-59 | G2 · Document the spine | G1 = ALH-58 demo loader; spine commands | blocked |
| 3 | ALH-112 | M4-06 · Share · read-only link, revocable token | — (needs approval/disclosure policy) | blocked on policy |
| 3 | ALH-173 | M4-06.2 · snapshot page a stranger can read | ALH-112 | blocked |
| 3 | ALH-176 | M4-09.1 · persist publish identity + reconciliation | connector auth/destination identity decision | blocked on policy |
| 4 | ALH-115 | M4-09 · publish brief to Notion/Confluence | ALH-97 (memo), ALH-176, ALH-198/199 | blocked |
| 4 | ALH-113 | M4-07 · post the brief to Slack | ALH-98 (stakeholder message), ALH-218/235 | blocked |
| 4 | ALH-116 | M4-10 · push a decided outcome to Linear | ALH-176, approval + criterion contracts, ALH-112/173 | blocked |
| 4 | ALH-174 | M4-10.2 · Jira and the approval gate | ALH-116 | blocked |
| 5 | ALH-119 | M4-13 · workspace templates | — (needs guide/screener/view schemas) | partial |
| 5 | ALH-120 | M4-14 · stakeholder one-pager, printed | ALH-97 (memo), ALH-98 | blocked |
| 5 | ALH-130 | M5-10 · readable telemetry for shareable artifacts | — (needs renderer inventory) | partial |
| 5 | ALH-131 | M5-11 · shared artifacts pass a screen reader | — (needs renderer inventory) | partial |
| 5 | ALH-133 | M5-13 · branding on what you share | ALH-201 (contrast seam) | partial |
| 6 | ALH-121 | M5-01 · dark mode + system theme | — (Studio only) | independent |
| 6 | ALH-122 | M5-02 · locale groundwork + translated shell | — (Studio + Python) | independent |
| 6 | ALH-127 | M5-07 · the 90-second tour | ALH-58 (demo), spine UI | blocked |
| 6 | ALH-129 | M5-09 · integration guide for external agents | ALH-61, ALH-53 (versions), ALH-130 | blocked on ALH-61/53 |
| 6 | ALH-132 | M5-12 · social card per docs page | site generator (exists) | independent |
| 6 | ALH-134 | M5-14 · starter kit for a new team | ALH-202/217 (template engine) | blocked |

**Cross-cutting seams that must be agreed before their consumers start** (these are the "readiness blockers" in ALH-11 and must be *decided*, not invented):

- **Per-view disclosure/redaction policy** + existing auth/CSP/cache conventions → blocks ALH-112/173 and the metadata of ALH-130/133.
- **Approval record / permitted override actors & states / destination mapping / generated-field ownership** → blocks ALH-116/174/176.
- **Contract-version source, provenance-format version, logo limits, template component schemas, content-selection rules** → blocks ALH-129/130/133/119/120.

---

## File Structure (Wave 1)

- `packages/core/src/agentic_odi_core/intent_store.py` — add `schema_meta` table, `CURRENT_SCHEMA_VERSION`, `MIGRATIONS`, `ensure_version()`, future-version refusal.
- `packages/core/src/agentic_odi_core/errors.py` — no new class needed; refusal raises `StoreError` with both versions named. (Reuse existing hierarchy.)
- `packages/core/tests/test_schema_version.py` — new; version init, no-op reopen, transactional failure rollback, future refusal, malformed metadata.
- `packages/core/tests/fixtures/` — new; two fixture DBs (`legacy_v0.db`, `future_v99.db`).
- `tests/contract/test_contract_snapshot.py` — new; inline-snapshot of `TOOL_SPECS`, live FastMCP registry input schemas, and `odi_schema()`.
- `tests/contract/test_contract_snapshot_drift.py` — new; negative fixtures proving rename/requiredness/type/missing/extra/entity-field drift each fail.
- `docs/development.md` — the deliberate snapshot-update command.
- `README.md` — only if a new command/package appears (none expected for these two).

---

## Wave 1 · Task 1: Schema version + migration guard (ALH-53)

**Files:** `intent_store.py`, `packages/core/tests/test_schema_version.py`, `packages/core/tests/fixtures/`.

**Interfaces:**
- `CURRENT_SCHEMA_VERSION: int = 1`
- `MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]]` — keyed by *target* version; `MIGRATIONS[n]` upgrades n-1 → n.
- `IntentStore.ensure_version() -> int` — called at the end of `_init_db`; returns the live version.
- Refusal: a DB whose `schema_meta.version > CURRENT_SCHEMA_VERSION` raises `StoreError` naming both versions and the real upgrade command (`odi update`).
- `schema_meta(version INTEGER NOT NULL, updated_at TEXT NOT NULL)` — single row, `CHECK (id = 1)`.

- [ ] Write failing test: a brand-new DB opens and `schema_meta.version == 1`.
- [ ] Run it, confirm failure (`no such table: schema_meta`).
- [ ] Add `CURRENT_SCHEMA_VERSION`, the `schema_meta` table creation, and `ensure_version()`.
- [ ] Run the test, confirm pass.
- [ ] Write failing test: reopening a current-version DB performs no migration and no version write (assert `updated_at` unchanged across two opens).
- [ ] Implement the "current version → return early" branch.
- [ ] Write failing test: a `v99` fixture DB is refused with both `99` and `1` in the message and an existing upgrade command.
- [ ] Implement the future-version refusal branch.
- [ ] Write failing test: a legacy DB (no `schema_meta`) is initialized to v1 exactly once, preserving all existing events.
- [ ] Implement the legacy bootstrap (create table + insert v1).
- [ ] Write failing test: an injected failing migration rolls back data + schema + `schema_meta` together, leaving the original store openable.
- [ ] Implement `MIGRATIONS` application inside a single `with self.conn:` transaction.
- [ ] Write failing test: malformed/duplicate version metadata fails with an actionable message and no partial mutation.
- [ ] Implement the metadata validation branch.
- [ ] Add the two committed fixture DBs under `packages/core/tests/fixtures/`.
- [ ] Run `uv run pytest packages/core -k "version or migrate"`, then ruff + mypy.

**Acceptance (verbatim):** reopening a current-version DB performs no migration/version write; an empty legacy DB is initialized exactly once; an injected later-migration failure rolls back earlier migration data/schema changes *and* `schema_meta`; missing registry step, malformed/duplicate metadata and a read-only file fail with actionable messages without partial mutation; a future-version refusal leaves file contents unchanged and names an upgrade command that exists; a `v99` DB is refused with both versions; a migration that raises leaves the version unchanged; two fixture DBs prove both paths.

---

## Wave 1 · Task 2: Contract drift snapshot gate (ALH-61)

**Files:** `tests/contract/test_contract_snapshot.py`, `tests/contract/test_contract_snapshot_drift.py`, `docs/development.md`. Add `inline-snapshot` to `[dependency-groups].dev` in the root `pyproject.toml`.

**Interfaces:**
- Snapshot three surfaces together: `contract.TOOL_SPECS` (as a normalized, order-independent structure), the live FastMCP registry's `input_schema` per tool (via `fastmcp.Client(mcp).list_tools()`), and `schema.odi_schema()`.
- Module docstring's first line is the update instruction: `Run `uv run pytest tests/contract/test_contract_snapshot.py --inline-snapshot=fix` to accept a deliberate change, then review the diff.`
- No auto-update in CI; drift fails.

- [ ] Add `inline-snapshot` to the dev dependency group; `uv sync`.
- [ ] Write the snapshot test over the three surfaces with `snapshot(...)`.
- [ ] Generate the initial snapshot (`--inline-snapshot=create`), review it, commit it.
- [ ] Write failing negative fixtures: argument rename, requiredness change, type change, missing live tool, extra live tool, entity-field drift — each must fail with a readable diff.
- [ ] Confirm each negative fixture fails for the right reason (not a collection error).
- [ ] Document the deliberate local update/review command in `docs/development.md`.
- [ ] Run `uv run pytest tests/contract -k snapshot`, then ruff + mypy.

**Acceptance (verbatim):** repeated generation is stable regardless of registry/dict iteration order (normalize ordering, not semantic defaults/required/type); negative fixtures prove rename/requiredness/type/missing-extra-tool/entity-field drift each fail with a readable diff; tests use an in-memory registry with no network/credentials; CI never accepts snapshots automatically and docs show the deliberate local update/review command; green on `main`.

---

## Wave 1 · Verification

```bash
uv run pytest packages/core -k "version or migrate"
uv run pytest tests/contract -k snapshot
uv run ruff check . && uv run ruff format --check .
uv run mypy apps packages
uv run pytest -q
```

---

## Waves 2–6 · Not executed here

Each blocked child starts only when its named dependency exists. The correct
action at that point is to write a fresh bite-sized plan for that child against
the *then-current* code, because every one of them names contracts (brief,
memo, decision, approval, criterion, renderer inventory) that this plan cannot
see yet. Starting them now would mean inventing a stub — explicitly forbidden
by the children ("report a missing stage by reference instead of replacing it
with an invented stub").

Independent M5 craft children (ALH-121 theme, ALH-122 locale, ALH-132 OG cards)
touch only Studio/site and can be scheduled any time; they are deliberately out
of Wave 1 because they are large and unrelated to the foundation guard.

## Wave 1c · ALH-132: a social card for every docs page (delivered)

Executed after Wave 1 because it is dependency-free and bounded (size S): it
extends the existing site generator and needs no spine stage.

- `website/tools/make_og.py` — per-page cards (`page_card`, `render_page`,
  `render_site`). The figure is read back out of the page's own visible text, so
  a number in markup never becomes a claimed figure; a page with no figure draws
  no number rather than a `0`. The generic `render()` defaults are unchanged, so
  the committed `assets/og.png` stays byte-identical.
- `website/tools/build_site.py` — renders one card per published page and fails
  the build if a published page has no card.
- `website/templates/base.html` — each page emits its own `og:image` /
  `twitter:image` plus alt text.
- `website/tests/test_og_pages.py` — 43 assertions covering existence,
  uniqueness, the no-figure fallback, the figure rule, safe unique paths, hard
  titles, and the build gate.

Still blocked, unchanged by this wave: ALH-59, ALH-120, ALH-121, ALH-122, ALH-127,
ALH-129 and the rest of the M4/M5 tree all name spine contracts (memo, brief,
decision, approval, template engine, demo loader) that do not exist in the tree.
Per the children's own rule, the correct action is to report the missing stage by
reference rather than invent a stub.
