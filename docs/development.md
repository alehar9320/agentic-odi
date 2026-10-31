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

### Conversational UI coverage

The agent-composed surfaces, first-minute guidance, and the product tour are
covered at these levels. `ChatStage.test.tsx` also covers the latest-message
control while following a streamed turn and returning to the live end:

| File | What it covers |
|---|---|
| `apps/studio/src/ui/protocol.test.ts` | Spec parsing: prop types, enums, ranges, required props, depth/node/size ceilings, unknown types |
| `apps/studio/src/ui/UiRenderer.test.tsx` | Card rendering, computed opportunity scores, action dispatch, per-node failure isolation, catalog/registry parity |
| `apps/studio/src/assistant/convert.test.ts` | Every part mapping in both directions, unknown parts dropped, `content` preserved for history |
| `apps/studio/src/api/studioApi.test.ts` | Chat request serialization: visible-path messages and attachment fields match the sidecar schema |
| `apps/studio/src/diagnostics/` | Recursive secret/URL/path redaction, 256 KiB cap, opt-in memory-only capture, local-only metadata fetch, and accessible diagnostics preview/export |
| `apps/studio-api/tests/test_studio_diagnostics.py` | Metadata-only diagnostics response, safe database basename/counts, integrity state, and absence of row contents/config |
| `apps/studio/src/components/chat/Conversation.test.tsx` | Prose and surfaces interleaved in the agent's order through the real runtime; card actions become messages; named alternative N of M and its switch; reasoning disclosure opens on request; the phase is announced and the reply is busy while streaming; failure retry |
| `apps/studio/src/components/chat/Composer.test.tsx` | Send, stop, the slash palette, keyboard focus, dropped and pasted attachments, refusal of unreadable files, and accessible attachment format/size limits in the runtime-bound composer |
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
| `apps/studio/src/App.test.tsx` | First-minute ordering: no tour or interview over the stage, tour on request, context hint after the first reply, job handoff, chosen surface opens, flag off in shell tests |

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

CI runs the suite on Python **3.10, 3.11, and 3.12** and uploads one combined
`coverage.xml` from the 3.12 job to
[Codecov](https://codecov.io/gh/alehar9320/agentic-odi).

The Codecov upload authenticates with the `CODECOV_TOKEN` repository secret and
is non-blocking (`fail_ci_if_error: false`), so a Codecov outage or a fork PR
without secrets cannot fail the test job. The badge at the top of the README
tracks `main`, which is the baseline every PR is compared against:

- **Project** status requires at least **90%** coverage (`target: 90%`) and
  tolerates a 1% dip from `codecov.yml`.
- **Patch** status is informational for now, so new code can land while the
  suite catches up.

Codecov itself never fails the build (`fail_ci_if_error: false`), so the same
floor is enforced locally: `[tool.coverage.report] fail_under` in
`pyproject.toml` makes any run with `--cov` fail below **89%** — the 90% target
minus codecov's 1% tolerance. The current measurement is ~89.2%, so the gate has
little slack; raise `fail_under` as coverage improves rather than lowering it to
unblock a change.

To reproduce the report locally:

```bash
uv run pytest \
  --cov=agentic_odi_cli \
  --cov=agentic_odi_connectors \
  --cov=agentic_odi_core \
  --cov=agentic_odi_mcp_server \
  --cov=agentic_odi_studio_api \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml
```

> [!NOTE]
> Coverage is only collected for the Python packages. `apps/studio/` and test
> directories are excluded in `codecov.yml`.

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

| Area | What it covers |
|---|---|
| `packages/core/tests/` | Domain models, opportunity scoring, `ODIService`, repository implementations, SQLite persistence, schema, and repository factory |
| `apps/mcp-server/tests/` | Full ODI workflow, entity parity, context tools, Customer Outcomes, evidence, tool errors, and HTTP transport startup |
| `apps/studio-api/tests/` | Health, config, canvas, SSE chat, SPA fallback, MCP hydration, probes, and step/outcome passthrough |
| `apps/cli/tests/` | Backend selection, local/remote CRUD, chat, wizard, onboarding, updates, rendering, connectors, and startup performance |
| `packages/connectors/tests/` | Catalog presets, registry persistence, factory, MCP and REST connectors, evidence mapping, and sink |
| `tests/contract/` | Live MCP tool surface and CLI local-handler parity |
| `tests/scripts/` | `scripts/dev.py` startup, port checks, signals, and shutdown; PR guardrails; documentation drift and roadmap gates |
| `apps/studio/src/**/*.test.ts` | SPA units: ODI math, transport bridge, SSE parser, sidecar client |
| `apps/studio/src/**/*.visual.test.tsx` | Component states captured for Chromatic visual review |
| `apps/studio/e2e/` | Browser journeys against the real stack: the conversation, the first-run starters, capturing an outcome, the opportunity landscape, the workspace views, and the MCP passthrough backend |
| `website/tests/` | Static site integrity, OG art reproducibility, and README sync |

> [!TIP]
> Type `/test` in the AI assistant to have the agent run all tests and report the
> results automatically.

## Agent Session Tracking

Agent sessions are captured with the [Entire](https://docs.entire.io/overview)
CLI. The repository integration lives in `.entire/settings.json`,
`.cursor/hooks.json`, and `.opencode/plugins/entire.ts`. Run `entire status` to
confirm it is enabled and `entire checkpoint list` to inspect captured
checkpoints.
