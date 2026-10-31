# Development

Everything below mirrors what CI runs. Install the workspace first:

```bash
uv sync --all-packages
```

## Linting, Formatting & Type Checks

Shared tooling lives in the root `pyproject.toml`, so one command covers every
Python project:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy apps packages
uv run --directory website mypy .

# Security scanning
uv run bandit -c pyproject.toml -r apps packages website/
```

## Documentation Checks

`scripts/doc_check.py` keeps the living docs honest against the code. In a pull
request it also refuses a new public capability with no roadmap entry:

```bash
uv run python scripts/doc_check.py
uv run python scripts/doc_check.py --changed-files $(git diff --name-only main...HEAD)
```

It checks that documented CLI commands exist in the Typer tree, documented paths
exist on disk, documented `/api` routes are served by the Studio router,
documented `AGENTIC_ODI_*` variables are read somewhere, and the README's Code
Overview paths exist. It is conservative on purpose: a code span is only a path
when it starts with a known top-level directory, and a command only counts when
it starts with a known entry point. `docs/superpowers/` is excluded — those
plans and specs are a frozen record, not living documentation.

## Frontend & Desktop Checks (studio)

The SPA and Tauri shell mirror their CI jobs locally:

```bash
npm --prefix apps/studio run lint        # ESLint
npm --prefix apps/studio run typecheck   # tsc --noEmit
npm --prefix apps/studio test -- --run   # Vitest on jsdom (run once)
npm --prefix apps/studio run test:visual # Vitest Browser Mode → Chromatic archives
npm --prefix apps/studio run build       # production build → apps/studio/dist
cd apps/studio/src-tauri && cargo fmt --check && cargo clippy -- -D warnings && cargo check
```

### Visual tests

`npm test` runs the jsdom suite and deliberately ignores `*.visual.test.tsx`.
Those files render one component state in Chromium under
`vitest.visual.config.ts`, and the `Chromatic` workflow publishes them on every
branch push so a reviewer can compare pixels component by component. Each test costs one billed snapshot per
build on the free 5,000/month allowance, which is why the two suites are split by
filename instead of running every test in a browser. Browser mode needs Chromium
locally: `npx playwright install chromium`. See
[Deployment](deployment.md) for the project setup and budget rules.

### Copied components (`src/vendor`)

Tailwind v4 styles `src/vendor/**` and nothing else (issue #385). The stylesheet
imports the theme and utility layers with `source(none)` and then rescans that
directory alone, so no product class is ever generated and Tailwind's
document-wide reset stays out of the bundle. The product keeps rendering from
`src/styles/theme.css`, which `src/main.tsx` imports first; vendor utilities land
in `@layer utilities`, and an unlayered product rule always outranks a layered
utility, so the two can never fight over the same element.

`components.json` points the shadcn CLI at that stylesheet and at the `@/` alias,
which resolves to `src/vendor/` in the Vite config and in both tsconfigs. A copied
file therefore keeps the import paths it shipped with:

```bash
npx --yes shadcn@latest add button   # → apps/studio/src/vendor/components/ui/button.tsx
```

Every copied file carries a header naming the registry and any edit made after the
copy; refresh with the CLI instead of editing the markup by hand. Today that is one
line: the registry items import their class merger from the `cn` package, and the
vendor tree standardises on `src/vendor/lib/utils.ts`, so `npm rm cn` and point the
import back at `@/lib/utils` after each add.
`npm --prefix apps/studio test -- --run src/vendor` proves the scope by reading the
compiled stylesheet.

### Conversational UI coverage

The agent-composed surfaces, first-minute guidance, and the product tour are
covered at these levels. `ChatStage.test.tsx` also covers the latest-message
control while following a streamed turn and returning to the live end:

| File | What it covers |
|---|---|
| `apps/studio/src/ui/protocol.test.ts` | Spec parsing: prop types, enums, ranges, required props, depth/node/size ceilings, unknown types |
| `apps/studio/src/vendor/vendor.test.tsx` | Tailwind scope: a vendor utility is compiled, a product-only utility is not, no preflight reset, the copied button renders |
| `apps/studio/src/ui/UiRenderer.test.tsx` | Card rendering, computed opportunity scores, action dispatch, per-node failure isolation, catalog/registry parity |
| `apps/studio/src/assistant/convert.test.ts` | Every part mapping in both directions, unknown parts dropped, `content` preserved for history |
| `apps/studio/src/api/studioApi.test.ts` | Chat request serialization: visible-path messages and attachment fields match the sidecar schema |
| `apps/studio/src/diagnostics/` | Recursive secret/URL/path redaction, 256 KiB cap, opt-in memory-only capture, local-only metadata fetch, and accessible diagnostics preview/export |
| `apps/studio-api/tests/test_studio_diagnostics.py` | Metadata-only diagnostics response, safe database basename/counts, integrity state, and absence of row contents/config |
| `apps/studio/src/components/chat/Conversation.test.tsx` | Prose and surfaces interleaved in the agent's order through the real runtime; card actions become messages; named alternative N of M and its switch; reasoning disclosure opens on request; the phase is announced and the reply is busy while streaming; failure retry |
| `apps/studio/src/components/chat/Composer.test.tsx` | Send, stop, the slash palette, keyboard focus, dropped and pasted attachments, refusal of unreadable files, and accessible attachment format/size limits in the runtime-bound composer |
| `apps/studio/src/assistant/dictation.test.ts`, `src/components/chat/Dictation.test.tsx` | The speech-recognition support gate, the microphone starting a session, and the absence of the control where the API is missing |
| `apps/studio/src/components/chat/ModelPicker.test.tsx` | Listing and marking the configured model, selection writes through `saveSettings`, arrow/Enter/Escape operation, an unreachable backend explained with a Settings path, one probe per backend |
| `apps/studio/src/assistant/attachments.test.ts` | Acceptance by extension and type, the 5 MB image ceiling, and human-readable sizes |
| `apps/studio/src/assistant/starterCopy.test.ts` | The first-run starter lint: situation-first titles, material-first prompts, a promised artifact, no quality adjectives, no claim literal, and the untouched returning-user swaps |
| `apps/studio/src/components/chat/SuggestionPills.test.tsx` | A starter click sends its exported prompt verbatim, and the starters stay disabled while a reply streams |
| `apps/studio-api/tests/test_studio_models.py` | Model listing sorted and deduplicated, offline without connecting, failed probe returned as a message, `/api/models` response shape |
| `apps/studio/src/state/StudioContext.test.tsx` | New, regenerate, and edit turns against a stubbed stream, branch switching, approval answers |
| `apps/studio-api/tests/test_studio_ui_spec.py` | Catalog validation and `render_ui` tool-schema generation |
| `apps/studio-api/tests/test_studio_chat_ui.py` | `render_ui` interception, `ui` SSE events, and the correction fed back to the model |
| `apps/studio-api/tests/test_studio_chat_stream.py` | Reasoning and source events, attachment prompt assembly, terminal-event invariants |
| `apps/studio-api/tests/test_studio_chat_branches.py` | Turn ids and sibling branches: edit and regenerate produce a tree, not a rewrite |
| `apps/studio-api/tests/test_studio_conversations.py` | Branch tree endpoint, `head_id` patch, legacy linear fallback, citation round-trip, idempotent retry, count-mismatch drop |
| `apps/studio-api/tests/test_studio_claims.py` | Claim parser: markers outside code, hypothesis tags, unknown ids downgraded, headings/questions/instructions exempt, list items, decimals, the three-record cap |
| `apps/studio/src/assistant/claims.test.ts` | Marker hiding while a reply streams (including a split marker and literal code), block splitting, claim-to-sentence mapping, seeded counts |
| `apps/studio/src/assistant/parts.test.tsx` | Claim chips open the record, hypothesis tag, uncited underline, missing record, sample chips, the no-citation banner, Escape |
| `apps/studio-api/tests/test_studio_approvals.py` | Gate lifecycle: resolve, timeout, double resolve, unknown id |
| `apps/studio/src/features/flags.test.ts` | Flag precedence (query → storage → env → default), value parsing, local overrides |
| `apps/studio/src/onboarding/machine.test.ts` | Tour transitions, no forward motion without a goal, versioned storage, malformed records |
| `apps/studio/src/onboarding/FirstRunWizard.test.tsx` | Never auto-opens, explicit open, full flow to a destination, skip/Escape, focus trap, resume, replay, inline model repair, flag off |
| `apps/studio/src/test/a11y.test.tsx` | axe-core WCAG 2.1 A/AA sweep over every shipping surface with zero violations; contrast is scoped to the token audit and documented there |
| `apps/studio/src/test/keyboard.test.tsx` | Shell landmarks and skip link, the tab path order (skip link → top bar → rail → transcript), and a project-wide AST scan for click handlers on non-controls |
| `apps/studio/src/styles/theme.test.ts` | Palette contrast in both themes (4.5:1 text, 3:1 focus ring) and no custom property referenced without a definition |
| `apps/studio/src/lib/guidance.test.ts` | One hint at a time, context before evidence, silence before the first exchange, permanent dismissal, defensive storage |
| `apps/studio/src/App.test.tsx` | First-minute ordering: no tour or interview over the stage, tour on request, context hint after the first reply, job handoff, chosen surface opens, flag off in shell tests, and a complete introduction that saves the brief |
| `apps/studio/src/lib/intro.test.ts` | Introduction turns, parsing under empty, very long, and multi-fact replies, the proposed defaults, draft storage, and one-shot migration |
| `apps/studio/src/components/setup/IntroConversation.test.tsx` | Five turns, skip, Escape, in-place summary edits, and the accepted brief with role, team, and evidence |
| `apps/studio/src/components/setup/IntroConversation.visual.test.tsx` | The summary card as one Chromatic snapshot |

## Website Checks (GitHub Pages)

The `website/` static site is part of the main CI workflow. Its tests assert the
committed OG art is reproducible and that the publish pipeline
(`website/tests/test_pages_deploy.py`) still exists:

```bash
uv run --directory website pytest tests/
```

The site is generated at CI time and never committed. CI runs `build_site.py` to
produce `_site` and uploads it as the `website-site` artifact for review.

Publishing happens in `.github/workflows/pages.yml`: it runs those tests,
builds `_site` from `website/`, and deploys the artifact with
`actions/deploy-pages` on every push to `main`. There is no `gh-pages` branch,
so that workflow is the only thing that keeps
<https://alehar9320.github.io/agentic-odi/> online.

## Formatting workflow

- **When editing Python files**, either rely on the **pre-commit hooks** below
  (recommended) or run Ruff formatting directly before pushing:

  ```bash
  uv run ruff format .
  ```

- **CI behavior**:
  - CI runs `uv run ruff check .` to lint without modifying files.
  - CI runs `uv run ruff format --check .` to *verify* formatting only.
  - If CI fails on formatting, run `uv run ruff format .` locally, commit the
    changes, and push again.

## Pre-commit hooks

To run the checks automatically before each commit:

```bash
uv tool install pre-commit
pre-commit install
```

After this, `ruff` and `ruff-format` run on staged files whenever you commit.
You can also trigger them manually:

```bash
pre-commit run --all-files
```

## PR Risk Classification

Every pull request is automatically classified by the
[PR Risk Classification](../.github/workflows/pr-risk.yml) workflow, which runs
on `ubuntu-latest` at $0 cost with zero external dependencies. It scores the diff
(0–100) across three factors and applies a single, mutually exclusive label:

| Label | Meaning | Score |
|---|---|---|
| `safe to merge` | Low risk — small diff, docs-only, or tested source code | ≤ 20 |
| `needs a look` | Medium risk — standard feature work or missing test updates | 21–50 |
| `danger zone` | High risk — critical path (auth, migrations, billing, infra, workflows) or protected-file deletion | ≥ 51 |

Scoring factors:

- **File & line churn** — files changed and lines added/deleted (0–30 points).
- **Critical path override** — touching `auth/`, `migrations/`, `billing/`,
  `infra/`, `.github/workflows/`, or deleting a file in
  `.ci/protected-files.txt` forces the danger zone.
- **Test delta** — source code changed without a corresponding
  `*.test.*`/`*.spec.*`/`tests/**` file adds 20 points.

### PR labels

The same workflow also labels every pull request so a reviewer can read its
shape at a glance, without opening the diff. Labelling is deterministic — no
LLM calls, no network beyond the GitHub API — so it cannot invent a label.

| Axis | Labels | What it tells a reviewer |
|---|---|---|
| Provenance | `🤖 agent`, `👤 human` | Whether a coding agent or a human wrote it. Detected from the PR author, the branch prefix, and the commit identities, because agents in this repository push on the owner's account. |
| Size | `size/XS` … `size/XL` | How much there is to read: <50, 50–249, 250–799, 800–1999, 2000+ lines changed. |
| Domain | `area/studio`, `area/cli`, `area/core`, `area/infra`, `area/docs`, … | Which components the diff touches. A PR can carry several. |
| Supply chain | `dependencies` | A manifest or lockfile changed (`package-lock.json`, `pyproject.toml`, `Cargo.lock`, `go.sum`, …). Worth a careful read even when the diff is one line. |
| Agent telemetry | `breaking change`, `needs deep dive`, `telemetry invalid` | What the agent declared about its own work. |

#### Agent telemetry

Coding agents declare what they know in the pull request body. Add this block to
the description; the [pull request
template](../.github/pull_request_template.md) already includes it:

```html
<!-- AGENT_METADATA {"has_breaking_changes": true, "agent_confidence": "low"} -->
```

- `has_breaking_changes: true` applies `breaking change`.
- `agent_confidence: "low"` applies `needs deep dive`.
- A block that cannot be parsed applies `telemetry invalid`. The workflow keeps
  going either way and never fails the check suite on a malformed block.

Human authors can leave the block alone: the shipped defaults claim nothing.

Labels are managed idempotently. Each run adds the labels it computed and
removes the ones it previously added that no longer apply, so re-pushing a
branch corrects the size label instead of stacking a second one. The set of
labels this system owns is defined once, in `scripts/pr_labels.py`:

```bash
python3 scripts/pr_labels.py --managed          # list every managed label
echo '{"author":{"login":"x","type":"User"},"files":[]}' | python3 scripts/pr_labels.py
```

The risk tier labels (`safe to merge`, `needs a look`, `danger zone`) and the
merge-state labels (`ready-for-merge`, `merge-conflict`) are owned by other
workflows and are deliberately left alone. The workflow is silent: it updates
labels only and never posts PR comments.

## Testing

Tests use **pytest** with **pytest-asyncio** (strict mode) and run entirely
in-memory — no running server required. Tests live next to the package they
cover, and every test runs from the repository root:

```bash
uv run pytest                        # everything
uv run pytest apps/cli               # one app
uv run pytest packages/core          # one package
uv run pytest tests/contract         # cross-package contracts
uv run pytest tests/scripts          # dev launcher
```

The MCP server contract test compares the live FastMCP registry with
`packages/core/src/agentic_odi_core/contract.py`, so add or change a tool in
both places. The CLI local-backend contract test keeps `_LOCAL_HANDLERS` aligned
with the same tool names.

### End-to-end testing

The browser-level suite lives in `apps/studio/e2e/` and runs with
[Playwright](https://playwright.dev). It drives the real Studio against the
real sidecar and MCP server, with no mocked network calls, so it covers the
seams the other tiers cannot: the SPA's assumptions about the sidecar's
response shapes, the sidecar's hydration of the canvas, and the first-run
wizard's ordering relative to the rest of the app.

```bash
npm --prefix apps/studio run build      # the sidecar serves apps/studio/dist
npm --prefix apps/studio run test:e2e
npm --prefix apps/studio run test:e2e:ui   # the Playwright UI
```

The first run needs the browser once:

```bash
npx --prefix apps/studio playwright install chromium
```

Playwright's `webServer` array starts the MCP server, the Studio sidecar, and
a second sidecar on the MCP passthrough backend. Two projects run against
them: `chromium` for the local backend (the product default) and
`mcp-backend` for the passthrough.

Locators bind to what a user perceives — a role, a label, or visible text —
never to a `data-testid`, of which the application has none. When a test
needs data behind it, it seeds through the API rather than through the UI, so
the test stays about the view it is actually checking.

CI runs the suite in the `e2e` job. It is deliberately non-blocking: set the
repository variable `AGENTIC_ODI_E2E` to `false` to skip it, and the
`continue-on-error` on the job keeps a failure from turning CI red.

## Test Coverage

The `test` job is the authoritative Python gate. Pytest runs on Python
**3.10, 3.11, and 3.12** with `--cov-fail-under=89`, so it fails the job on its
own — no token, and therefore no fork PR that skips the check. The current
measurement is **89.75%** (7,720 statements, 791 missed).

The floor is a ratchet. On every pull request, `scripts/coverage_floor.py`
compares `[tool.coverage.report] fail_under` in `pyproject.toml` with the base
branch and fails when the head value is lower. Raise `fail_under` as coverage
improves; never lower it to unblock a change.

The 3.12 job also writes a per-distribution table to the job summary. At the
time of writing:

| Distribution | Coverage |
|---|---|
| `agentic_odi_cli` | 90.57% |
| `agentic_odi_connectors` | 91.05% |
| `agentic_odi_core` | 92.11% |
| `agentic_odi_mcp_server` | 81.92% |
| `agentic_odi_studio_api` | 88.13% |

[Codecov](https://codecov.io/gh/alehar9320/agentic-odi) stays a reporting
layer, not the gate. The 3.12 job uploads `coverage.xml` with the
`CODECOV_TOKEN` secret and `fail_ci_if_error: false`, so an outage or a fork
without secrets cannot turn the job red. `codecov.yml` keeps a **90%** project
target with a 1% dip — the same **89%** minimum pytest enforces — and patch
status is informational while new code lands. The upload carries the `python`
flag, and the README badge tracks that flag on `main`; the project status is
scoped to it so the Studio's lower number cannot turn it red.

The Studio is gated separately. `npm run test:coverage` runs Vitest with the V8
provider, writes `apps/studio/coverage/lcov.info`, and fails the studio job
below statements **74%**, branches **65%**, functions **75%**, and lines
**74%**. The measured values are 74.18%, 65.38%, 75.49%, and 74.33%, so the
thresholds have little slack; raise them as the suite grows. The lcov file is
uploaded to Codecov under the `studio` flag, also non-blocking — the Vitest
thresholds are what gate the merge.

Reproduce both reports locally:

```bash
# Python
uv run pytest \
  --cov=agentic_odi_cli \
  --cov=agentic_odi_connectors \
  --cov=agentic_odi_core \
  --cov=agentic_odi_mcp_server \
  --cov=agentic_odi_studio_api \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml

# Studio
npm --prefix apps/studio run test:coverage
```

The known gaps behind these numbers — recorded from issue #88 rather than fixed
by it — are listed in
[`docs/architecture/testing.md`](architecture/testing.md#known-coverage-gaps).

### Conventions

- Test files live under each project's `tests/` directory and are named
  `test_*.py`.
- Root `tests/` is reserved for cross-package checks (`contract/` and
  `scripts/`).
- Every async test is decorated with `@pytest.mark.asyncio`.
- Use `Client(mcp)` directly (no HTTP server needed) for fast, isolated tests.
- The MCP server's `reset_db` autouse fixture clears in-memory state before
  each test.

### Test Coverage Map

Generated from the test tree by `scripts/coverage_map.py`: every test file and
the source files it imports or shares a name with. CI fails when this table and
the code disagree, so do not edit it by hand — run
`uv run python scripts/coverage_map.py --write`.

<!-- coverage-map:start -->
| Test file | Exercises |
|---|---|
| `apps/cli/tests/test_backend.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`packages/core/src/agentic_odi_core/remote.py` |
| `apps/cli/tests/test_backend_edges.py` | `apps/cli/src/agentic_odi_cli/backend.py` |
| `apps/cli/tests/test_backend_selection.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/cli/tests/test_build_info.py` | `apps/cli/src/agentic_odi_cli/_build_info.py`<br>`apps/cli/src/agentic_odi_cli/version.py` |
| `apps/cli/tests/test_chat_cli.py` | `apps/cli/src/agentic_odi_cli/chat.py`<br>`apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_chat_runtime.py` | `apps/cli/src/agentic_odi_cli/chat.py` |
| `apps/cli/tests/test_chat_wizard.py` | `apps/cli/src/agentic_odi_cli/chat.py`<br>`apps/cli/src/agentic_odi_cli/wizard.py` |
| `apps/cli/tests/test_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/version.py` |
| `apps/cli/tests/test_cli_edges.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_connectors_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/rest/connector.py` |
| `apps/cli/tests/test_connectors_edges.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/connectors.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/paths.py` |
| `apps/cli/tests/test_context.py` | `apps/cli/src/agentic_odi_cli/context.py` |
| `apps/cli/tests/test_customer_outcomes_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/cli/tests/test_data_export.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/cli/tests/test_desired_outcomes_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/desired_outcomes.py` |
| `apps/cli/tests/test_evidence_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_insight_commands.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_jobs_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_mascot.py` | `apps/cli/src/agentic_odi_cli/mascot.py` |
| `apps/cli/tests/test_onboard.py` | `apps/cli/src/agentic_odi_cli/onboard.py`<br>`apps/cli/src/agentic_odi_cli/profile.py` |
| `apps/cli/tests/test_paths.py` | `apps/cli/src/agentic_odi_cli/paths.py` |
| `apps/cli/tests/test_persistence.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/cli/tests/test_profile.py` | `apps/cli/src/agentic_odi_cli/chat.py`<br>`apps/cli/src/agentic_odi_cli/profile.py` |
| `apps/cli/tests/test_profile_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_render.py` | `apps/cli/src/agentic_odi_cli/render.py` |
| `apps/cli/tests/test_schedule_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_settings_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_signals_cli.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_startup_perf.py` | — no direct source pair |
| `apps/cli/tests/test_steps_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_summary_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_update.py` | `apps/cli/src/agentic_odi_cli/update.py` |
| `apps/cli/tests/test_update_check.py` | `apps/cli/src/agentic_odi_cli/update.py` |
| `apps/cli/tests/test_update_command.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/update.py`<br>`apps/cli/src/agentic_odi_cli/version.py` |
| `apps/cli/tests/test_update_edges.py` | `apps/cli/src/agentic_odi_cli/update.py` |
| `apps/cli/tests/test_version_flag.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/version.py` |
| `apps/cli/tests/test_wizard_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/mcp-server/tests/test_context_tools.py` | — no direct source pair |
| `apps/mcp-server/tests/test_customer_outcomes.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_graceful_shutdown.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/mcp-server/tests/test_health.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_odi.py` | — no direct source pair |
| `apps/mcp-server/tests/test_parity.py` | — no direct source pair |
| `apps/mcp-server/tests/test_port_config.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_server_tools.py` | — no direct source pair |
| `apps/mcp-server/tests/test_signals.py` | — no direct source pair |
| `apps/mcp-server/tests/test_tool_branches.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_tool_progress.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_tool_spec_validation.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`<br>`packages/core/src/agentic_odi_core/contract.py` |
| `apps/mcp-server/tests/test_tools.py` | — no direct source pair |
| `apps/studio/e2e/capture.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/chat.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/landscape.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/mcp-backend.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/starters.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/workspace.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/src/App.test.tsx` | `apps/studio/src/App.tsx`<br>`apps/studio/src/api/studioApi.ts` |
| `apps/studio/src/api/sse.test.ts` | `apps/studio/src/api/sse.ts` |
| `apps/studio/src/api/studioApi.local.test.ts` | `apps/studio/src/api/studioApi.ts` |
| `apps/studio/src/api/studioApi.test.ts` | `apps/studio/src/api/studioApi.ts` |
| `apps/studio/src/assistant/attachments.test.ts` | `apps/studio/src/assistant/attachments.ts` |
| `apps/studio/src/assistant/claims.test.ts` | `apps/studio/src/assistant/claims.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/assistant/convert.test.ts` | `apps/studio/src/assistant/convert.ts`<br>`apps/studio/src/types.ts`<br>`apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts` |
| `apps/studio/src/assistant/parts.test.tsx` | `apps/studio/src/assistant/parts.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/assistant/starterCopy.test.ts` | `apps/studio/src/assistant/StudioRuntime.tsx` |
| `apps/studio/src/banners/BannerBridge.test.tsx` | `apps/studio/src/banners/BannerBridge.tsx`<br>`apps/studio/src/banners/BannerProvider.tsx`<br>`apps/studio/src/banners/BannerStack.tsx` |
| `apps/studio/src/banners/BannerProvider.test.tsx` | `apps/studio/src/banners/BannerProvider.tsx` |
| `apps/studio/src/banners/BannerStack.test.tsx` | `apps/studio/src/banners/BannerProvider.tsx`<br>`apps/studio/src/banners/BannerStack.tsx`<br>`apps/studio/src/banners/types.ts` |
| `apps/studio/src/banners/BannerStack.visual.test.tsx` | `apps/studio/src/banners/BannerStack.tsx`<br>`apps/studio/src/banners/catalog.ts`<br>`apps/studio/src/banners/types.ts` |
| `apps/studio/src/banners/BannerToasts.test.tsx` | `apps/studio/src/banners/BannerProvider.tsx`<br>`apps/studio/src/banners/BannerStack.tsx`<br>`apps/studio/src/banners/BannerToasts.tsx` |
| `apps/studio/src/banners/catalog.test.ts` | `apps/studio/src/banners/catalog.ts`<br>`apps/studio/src/banners/types.ts` |
| `apps/studio/src/banners/store.test.ts` | `apps/studio/src/banners/store.ts` |
| `apps/studio/src/bff/capabilities/registry.test.ts` | `apps/studio/src/bff/capabilities/registry.ts` |
| `apps/studio/src/bff/chat/orchestrator.test.ts` | `apps/studio/src/api/sse.ts`<br>`apps/studio/src/bff/chat/orchestrator.ts`<br>`apps/studio/src/bff/data/localDataService.ts`<br>`apps/studio/src/bff/memory/localMemoryService.ts`<br>`apps/studio/src/bff/store/memoryStore.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/bff/data/localDataService.test.ts` | `apps/studio/src/bff/data/localDataService.ts`<br>`apps/studio/src/bff/store/memoryStore.ts` |
| `apps/studio/src/bff/index.test.ts` | `apps/studio/src/bff/index.ts`<br>`apps/studio/src/bff/store/memoryStore.ts` |
| `apps/studio/src/bff/memory/localMemoryService.test.ts` | `apps/studio/src/bff/memory/localMemoryService.ts`<br>`apps/studio/src/bff/store/memoryStore.ts` |
| `apps/studio/src/bff/store/indexedDbStore.test.ts` | `apps/studio/src/bff/store/indexedDbStore.ts` |
| `apps/studio/src/bridge/desktopBridge.test.ts` | `apps/studio/src/bridge/desktopBridge.ts` |
| `apps/studio/src/components/ChangelogModal.test.tsx` | `apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/ChangelogModal.tsx`<br>`apps/studio/src/lib/changelogRead.ts` |
| `apps/studio/src/components/FailurePanel.visual.test.tsx` | `apps/studio/src/components/FailurePanel.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/OdiMascot.test.tsx` | `apps/studio/src/components/OdiMascot.tsx` |
| `apps/studio/src/components/SettingsPanel.test.tsx` | `apps/studio/src/components/SettingsPanel.tsx`<br>`apps/studio/src/onboarding/OnboardingProvider.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/components/canvas/DirectCapture.test.tsx` | `apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/canvas/DirectCapture.tsx` |
| `apps/studio/src/components/canvas/EvidenceStream.test.tsx` | `apps/studio/src/components/canvas/EvidenceStream.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/JobMap.test.tsx` | `apps/studio/src/components/canvas/JobMap.tsx`<br>`apps/studio/src/domain/jobStages.ts` |
| `apps/studio/src/components/canvas/MemoryPanel.test.tsx` | `apps/studio/src/components/canvas/MemoryPanel.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/OpportunityLandscape.test.tsx` | `apps/studio/src/components/canvas/OpportunityLandscape.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/OutcomeCard.test.tsx` | `apps/studio/src/components/canvas/OutcomeCard.tsx` |
| `apps/studio/src/components/canvas/OutcomeCardSample.test.tsx` | `apps/studio/src/components/canvas/OutcomeCard.tsx` |
| `apps/studio/src/components/canvas/SchedulePanel.test.tsx` | `apps/studio/src/components/canvas/SchedulePanel.tsx` |
| `apps/studio/src/components/canvas/ThesisAction.test.tsx` | `apps/studio/src/components/canvas/OutcomeCard.tsx` |
| `apps/studio/src/components/chat/ChatStage.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/ChatStage.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/chat/CommandPalette.test.tsx` | `apps/studio/src/components/chat/Composer.tsx`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/components/chat/Composer.test.tsx` | `apps/studio/src/components/chat/Composer.tsx`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/components/chat/Conversation.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/Conversation.tsx`<br>`apps/studio/src/types.ts`<br>`apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts` |
| `apps/studio/src/components/chat/ModelPicker.test.tsx` | `apps/studio/src/components/chat/ModelPicker.tsx` |
| `apps/studio/src/components/chat/SuggestionPills.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/composerParts.tsx`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/components/customize/ConnectorSuggestionModal.test.tsx` | `apps/studio/src/components/customize/ConnectorSuggestionModal.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/customize/CustomizePage.test.tsx` | `apps/studio/src/components/customize/CustomizePage.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/layout/StudioBar.test.tsx` | `apps/studio/src/components/layout/StudioBar.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/components/notifications/CatchUpFeed.test.tsx` | `apps/studio/src/App.tsx`<br>`apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/notifications/CatchUpFeed.tsx`<br>`apps/studio/src/components/notifications/__fixtures__/signals.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/notifications/noFabricatedSignals.test.ts` | — no direct source pair |
| `apps/studio/src/components/workspace/WorkbenchRail.test.tsx` | `apps/studio/src/components/workspace/WorkbenchRail.tsx` |
| `apps/studio/src/components/workspace/WorkspacePanel.test.tsx` | `apps/studio/src/components/workspace/WorkspacePanel.tsx` |
| `apps/studio/src/diagnostics/DiagnosticsModal.test.tsx` | `apps/studio/src/components/SettingsPanel.tsx`<br>`apps/studio/src/diagnostics/DiagnosticsModal.tsx`<br>`apps/studio/src/onboarding/OnboardingProvider.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/diagnostics/bundle.test.ts` | `apps/studio/src/diagnostics/bundle.ts` |
| `apps/studio/src/diagnostics/redact.test.ts` | `apps/studio/src/diagnostics/redact.ts` |
| `apps/studio/src/features/flags.test.ts` | `apps/studio/src/features/flags.ts` |
| `apps/studio/src/lib/canvasProvenance.test.ts` | `apps/studio/src/lib/canvasProvenance.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/changelogRead.test.ts` | `apps/studio/src/lib/changelogRead.ts` |
| `apps/studio/src/lib/commands.test.ts` | `apps/studio/src/lib/commands.ts` |
| `apps/studio/src/lib/export.test.ts` | `apps/studio/src/lib/export.ts`<br>`apps/studio/src/types.ts`<br>`apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts` |
| `apps/studio/src/lib/greeting.test.ts` | `apps/studio/src/lib/greeting.ts` |
| `apps/studio/src/lib/guidance.test.ts` | `apps/studio/src/lib/guidance.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/markdown.test.ts` | `apps/studio/src/lib/markdown.ts` |
| `apps/studio/src/lib/odi.test.ts` | `apps/studio/src/lib/odi.ts` |
| `apps/studio/src/lib/setup.test.ts` | `apps/studio/src/lib/setup.ts` |
| `apps/studio/src/onboarding/FirstRunWizard.test.tsx` | `apps/studio/src/onboarding/FirstRunWizard.tsx`<br>`apps/studio/src/onboarding/OnboardingProvider.tsx`<br>`apps/studio/src/onboarding/context.ts`<br>`apps/studio/src/onboarding/storage.ts` |
| `apps/studio/src/onboarding/machine.test.ts` | `apps/studio/src/onboarding/machine.ts`<br>`apps/studio/src/onboarding/storage.ts` |
| `apps/studio/src/state/StudioContext.test.tsx` | `apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/styles/print.test.ts` | — no direct source pair |
| `apps/studio/src/styles/theme.test.ts` | — no direct source pair |
| `apps/studio/src/test/a11y.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/ChangelogModal.tsx`<br>`apps/studio/src/components/SettingsPanel.tsx`<br>`apps/studio/src/components/canvas/JobMap.tsx`<br>`apps/studio/src/components/canvas/OpportunityLandscape.tsx`<br>`apps/studio/src/components/chat/ChatStage.tsx`<br>`apps/studio/src/components/chat/Composer.tsx`<br>`apps/studio/src/components/notifications/CatchUpFeed.tsx`<br>`apps/studio/src/onboarding/FirstRunWizard.tsx`<br>`apps/studio/src/onboarding/OnboardingProvider.tsx`<br>`apps/studio/src/onboarding/context.ts`<br>`apps/studio/src/test/axe.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/test/keyboard.test.tsx` | `apps/studio/src/App.tsx`<br>`apps/studio/src/lib/useFocusTrap.ts` |
| `apps/studio/src/ui/UiRenderer.test.tsx` | `apps/studio/src/ui/UiRenderer.tsx`<br>`apps/studio/src/ui/actions.ts`<br>`apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts`<br>`apps/studio/src/ui/registry.ts` |
| `apps/studio/src/ui/protocol.test.ts` | `apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts` |
| `apps/studio/src/updater/UpdateBanner.test.tsx` | `apps/studio/src/updater/UpdateBanner.tsx`<br>`apps/studio/src/updater/UpdateProvider.tsx`<br>`apps/studio/src/updater/service.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/updater/UpdateSettings.test.tsx` | `apps/studio/src/updater/UpdateProvider.tsx`<br>`apps/studio/src/updater/UpdateSettings.tsx`<br>`apps/studio/src/updater/service.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/updater/machine.test.ts` | `apps/studio/src/updater/machine.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/updater/service.test.ts` | `apps/studio/src/updater/service.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/updater/transport.test.ts` | `apps/studio/src/updater/transport.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio-api/tests/test_api.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/studio-api/tests/test_app_spa.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/main.py`<br>`packages/core/src/agentic_odi_core/messages.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/studio-api/tests/test_studio_api.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/chat.py` |
| `apps/studio-api/tests/test_studio_approvals.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/approvals.py` |
| `apps/studio-api/tests/test_studio_brief.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` |
| `apps/studio-api/tests/test_studio_capabilities.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_chat_branches.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/connectors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` |
| `apps/studio-api/tests/test_studio_chat_stream.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/approvals.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` |
| `apps/studio-api/tests/test_studio_chat_ui.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` |
| `apps/studio-api/tests/test_studio_claims.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/claims.py` |
| `apps/studio-api/tests/test_studio_connectors.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/connectors.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/registry.py` |
| `apps/studio-api/tests/test_studio_connectors_router.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/connectors.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py` |
| `apps/studio-api/tests/test_studio_conversations.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/claims.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py` |
| `apps/studio-api/tests/test_studio_diagnostics.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/studio-api/tests/test_studio_errors.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`packages/core/src/agentic_odi_core/remote.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/studio-api/tests/test_studio_evidence.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_llm_proxy.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_manual_crud.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_marketplace.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/connectors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/marketplace.py`<br>`packages/connectors/src/agentic_odi_connectors/marketplace.py` |
| `apps/studio-api/tests/test_studio_mcp_data.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/mcp_data.py` |
| `apps/studio-api/tests/test_studio_memory.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/memory.py` |
| `apps/studio-api/tests/test_studio_model_router.py` | — no direct source pair |
| `apps/studio-api/tests/test_studio_models.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/probes.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py` |
| `apps/studio-api/tests/test_studio_observability.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/observability.py` |
| `apps/studio-api/tests/test_studio_outcome_evidence_crud.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_probes.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/probes.py` |
| `apps/studio-api/tests/test_studio_router.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py`<br>`packages/core/src/agentic_odi_core/remote.py` |
| `apps/studio-api/tests/test_studio_signals.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py`<br>`packages/core/src/agentic_odi_core/remote.py` |
| `apps/studio-api/tests/test_studio_ui_spec.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/ui_spec.py` |
| `brand/tests/test_brand_assets.py` | — no direct source pair |
| `brand/tests/test_generated_sources.py` | — no direct source pair |
| `packages/connectors/tests/test_catalog.py` | `packages/connectors/src/agentic_odi_connectors/catalog.py`<br>`packages/connectors/src/agentic_odi_connectors/registry.py` |
| `packages/connectors/tests/test_config_path.py` | `packages/connectors/src/agentic_odi_connectors/paths.py` |
| `packages/connectors/tests/test_config_validation.py` | — no direct source pair |
| `packages/connectors/tests/test_factory.py` | `packages/connectors/src/agentic_odi_connectors/factory.py`<br>`packages/connectors/src/agentic_odi_connectors/mcp/connector.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/protocol.py`<br>`packages/connectors/src/agentic_odi_connectors/registry.py`<br>`packages/connectors/src/agentic_odi_connectors/rest/connector.py` |
| `packages/connectors/tests/test_http_client.py` | — no direct source pair |
| `packages/connectors/tests/test_mapping.py` | `packages/connectors/src/agentic_odi_connectors/mapping.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py` |
| `packages/connectors/tests/test_marketplace.py` | `packages/connectors/src/agentic_odi_connectors/catalog.py`<br>`packages/connectors/src/agentic_odi_connectors/marketplace.py` |
| `packages/connectors/tests/test_mcp_connector.py` | `packages/connectors/src/agentic_odi_connectors/mcp/connector.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py` |
| `packages/connectors/tests/test_registry.py` | `packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/registry.py` |
| `packages/connectors/tests/test_rest_connector.py` | `packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/rest/connector.py` |
| `packages/connectors/tests/test_sink.py` | `packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/sink.py` |
| `packages/core/tests/test_capability_manifest.py` | `packages/core/src/agentic_odi_core/contract.py` |
| `packages/core/tests/test_connection.py` | `packages/core/src/agentic_odi_core/connection.py` |
| `packages/core/tests/test_consent_pause.py` | `packages/core/src/agentic_odi_core/consent.py`<br>`packages/core/src/agentic_odi_core/contract.py`<br>`packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `packages/core/tests/test_errors.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_evaluation.py` | `packages/core/src/agentic_odi_core/evaluation.py` |
| `packages/core/tests/test_events.py` | `packages/core/src/agentic_odi_core/intent_store.py` |
| `packages/core/tests/test_evidence_not_found.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_intent_store.py` | `packages/core/src/agentic_odi_core/intent_store.py` |
| `packages/core/tests/test_job_validation.py` | `packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_messages.py` | `packages/core/src/agentic_odi_core/messages.py` |
| `packages/core/tests/test_models.py` | `packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_opportunity_ranking.py` | `packages/core/src/agentic_odi_core/evaluation.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_outcome_validation.py` | `packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_pagination.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_remote.py` | `packages/core/src/agentic_odi_core/remote.py` |
| `packages/core/tests/test_repository.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `packages/core/tests/test_repository_factory.py` | `packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_repository_health.py` | `packages/core/src/agentic_odi_core/factory.py` |
| `packages/core/tests/test_router.py` | `packages/core/src/agentic_odi_core/router.py`<br>`packages/core/src/agentic_odi_core/steve_jobs.py` |
| `packages/core/tests/test_scheduled_work.py` | — no direct source pair |
| `packages/core/tests/test_schema.py` | `packages/core/src/agentic_odi_core/schema.py` |
| `packages/core/tests/test_service.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_signal_inbox.py` | — no direct source pair |
| `packages/core/tests/test_sqlite_repository.py` | `packages/core/src/agentic_odi_core/intent_store.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `tests/contract/test_cli_contract.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`packages/core/src/agentic_odi_core/contract.py` |
| `tests/contract/test_mcp_contract.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`<br>`packages/core/src/agentic_odi_core/contract.py` |
| `tests/contract/test_protected_files.py` | — no direct source pair |
| `tests/scripts/test_ci_release.py` | `scripts/ci_release.py` |
| `tests/scripts/test_cli_docs.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `tests/scripts/test_coverage_floor.py` | `scripts/coverage_floor.py` |
| `tests/scripts/test_coverage_map.py` | `scripts/coverage_map.py` |
| `tests/scripts/test_dev.py` | `scripts/dev.py` |
| `tests/scripts/test_dev_main.py` | — no direct source pair |
| `tests/scripts/test_doc_check.py` | `scripts/doc_check.py` |
| `tests/scripts/test_gen_job_stages.py` | `scripts/gen_job_stages.py` |
| `tests/scripts/test_label_merge_conflicts.py` | `scripts/pr_labels.py` |
| `tests/scripts/test_pr_body_gate.py` | — no direct source pair |
| `tests/scripts/test_pr_guards.py` | `scripts/pr_guards.py` |
| `tests/scripts/test_pr_labeler_workflow.py` | — no direct source pair |
| `tests/scripts/test_pr_labels.py` | `scripts/pr_labels.py`<br>`scripts/pr_provenance.py` |
| `tests/scripts/test_pr_provenance.py` | `scripts/pr_provenance.py` |
| `tests/scripts/test_release_assets.py` | `scripts/release_assets.py` |
| `tests/scripts/test_release_instructions.py` | `scripts/release_instructions.py` |
| `tests/scripts/test_release_version_gate.py` | — no direct source pair |
| `tests/scripts/test_release_workflow.py` | — no direct source pair |
| `tests/scripts/test_roadmap_check.py` | `scripts/doc_check.py` |
| `tests/scripts/test_version_sync.py` | `apps/cli/src/agentic_odi_cli/_build_info.py`<br>`scripts/check_version_parity.py` |
| `tests/scripts/test_workflow_triggers.py` | — no direct source pair |
| `tests/test_dev_entrypoint.py` | — no direct source pair |
| `tests/test_docs_code_overview.py` | — no direct source pair |
| `tests/test_worker_error_shape.py` | — no direct source pair |
| `tests/test_worker_security_headers.py` | — no direct source pair |
| `website/tests/site_support.py` | `website/tools/build_site.py` |
| `website/tests/test_content_sync.py` | `website/tools/extract.py` |
| `website/tests/test_design_system.py` | `website/tools/extract.py` |
| `website/tests/test_docs_render.py` | `website/tools/markdown_render.py` |
| `website/tests/test_generated.py` | `website/tools/build_site.py`<br>`website/tools/extract.py` |
| `website/tests/test_make_og.py` | `website/tools/make_og.py` |
| `website/tests/test_pages_deploy.py` | — no direct source pair |
| `website/tests/test_site.py` | `website/tools/extract.py` |
| `website/tests/test_theme.py` | — no direct source pair |
<!-- coverage-map:end -->

> [!TIP]
> Type `/test` in the AI assistant to have the agent run all tests and report the
> results automatically.

## Agent Session Tracking

Agent sessions are captured with the [Entire](https://docs.entire.io/overview)
CLI. The repository integration lives in `.entire/settings.json`,
`.cursor/hooks.json`, and `.opencode/plugins/entire.ts`. Run `entire status` to
confirm it is enabled and `entire checkpoint list` to inspect captured
checkpoints.
