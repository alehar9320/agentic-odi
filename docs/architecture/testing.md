# Testing

## Tiers (pre-PR)
See [`.agents/workflows/test.md`](../../.agents/workflows/test.md):
- `--changed` — PR bar (fast gate on touched files)
- `--default` — adds `mypy` and `vitest` for touched areas
- `--full` — CI's responsibility (full matrix)

```bash
uv run python scripts/verify.py --changed
uv run python scripts/verify.py --default
uv run python scripts/verify.py --full
```

The full tier is CI's responsibility and is not asked of anyone before they
open a pull request. The commands below are the manual equivalent of the
default tier.

## Commands (reference)

```bash
uv run pytest                       # all packages + root contract/launcher tests
uv run pytest packages/core         # one package
uv run pytest tests/contract        # MCP contract only
uv run mypy apps brand packages
uv run ruff check .
uv run ruff format --check .
uv run bandit -c pyproject.toml -r apps packages
uv run bandit -c pyproject.toml -r website/
```

The root `pyproject.toml` owns pytest, coverage, ruff, mypy, and bandit configuration. There is no per-package test configuration to keep in sync. Coverage floor is enforced in CI (`fail_under = 89`).

## Layout

Tests live next to their package (`packages/*/tests`, `apps/*/tests`). `testpaths` in the root `pyproject.toml` covers `apps`, `brand`, `packages`, `tests`, and `website`, so one `uv run pytest` collects all of them.

### The per-file map

Every test file and the one line it says about itself lives in
[the test map](../reference/test-map.md). It is generated from the files
themselves by `scripts/docs_index.py`, so a new test file appears there after
`--write` and a file with no description still appears, named, with `—`. The
rules below are what stays prose here.

### `website/tests/` contracts

`test_ci_required.py` is the contract that keeps the site from shipping on faith. It asserts the `website` job in `ci.yml` runs `uv run --directory website pytest tests/`, carries no `continue-on-error`, and is both a `needs:` entry and an enforced result in the `CI green` aggregate — the status check the `main-requires-ci-green` ruleset requires. It also asserts the Pages `deploy` job waits on the tested `build`. The wiring has regressed before: the site's checks once lived in a `feature/gh-pages`-only workflow that never ran for a pull request into `main` (402f0a5).

## Isolation Rules

- Use `InMemoryRepository` in tests. `create_app(InMemoryRepository())` keeps the Studio API off the real `~/.agentic-odi/odi.db`.
- The MCP server uses `build_repository()`; tests set `AGENTIC_ODI_DB=:memory:` before import and call tools through `Client(mcp)` without HTTP.
- Async tests use `@pytest.mark.asyncio` (strict mode).

## Coverage

CI runs the root suite on Python 3.10, 3.11, and 3.12, collects coverage for every `agentic_odi_*` distribution, and uploads `coverage.xml` from the 3.12 job. Codecov requires 90% project coverage; patch coverage is advisory. Python tests and `apps/studio/**` are excluded from the report by `codecov.yml`.

## Frontend

```bash
npm --prefix apps/studio run lint
npm --prefix apps/studio run typecheck
npm --prefix apps/studio test -- --run
npm --prefix apps/studio run build
cd apps/studio/src-tauri && cargo fmt --check && cargo clippy -- -D warnings && cargo check
```

The self-updater lives in `apps/studio/src/updater/` and is covered by vitest:
`machine.test.ts` (state transitions, including the failed-check status line
naming the last *successful* check), `service.test.ts` (scheduling, download,
install, and the bounded in-session action log), `transport.test.ts` (Tauri boundary), and the
`UpdateBanner`/`UpdateSettings` component tests. `StudioBar.test.tsx` and
`SettingsPanel.test.tsx` cover the UI integration points.

The outbox drain guard in `apps/studio/src/bff/outbox.ts` is covered by
`outbox.test.ts`, which races two drains twice: once with a `navigator.locks`
stub and once with `navigator.locks` deleted so the lease row runs. Both assert
exactly one send per record, and the lease path also proves a crashed holder's
lease is reclaimed only after it expires and that a running drain renews it.

The IndexedDB schema and its migrations are covered by two files under
`apps/studio/src/bff/store/`. `migrations.test.ts` asserts the registry has a
step for every version up to `DB_VERSION` and that a gap fails with a message
naming the missing version, so raising the version without a migration fails the
suite instead of throwing `ConstraintError` on an existing database.
`indexedDbStore.test.ts` seeds a v1 database with a row in all seven stores,
opens it with the current code, and asserts every row is unchanged and the
migrated schema equals a fresh database's (store names, key paths,
auto-increment flags, and index names). The same file opens a second connection
at a higher version and asserts the first closes and sets `needsReload` instead
of blocking the upgrade.

Copied UI is guarded structurally: `src/vendor/boundary.test.ts` reads every
`.ts` and `.tsx` file under `apps/studio/src/vendor/` and fails on a specifier
that resolves into a product slice (`state`, `api`, `assistant`, `bff`). It is
the second pair of eyes behind the ESLint rule in
`apps/studio/eslint.config.js`, because widening a lint glob silently deletes
the rule. See [Vendor alley](vendor.md).

## Accessibility

Accessibility is tested, not asserted. Four kinds of checks run with the normal
test suites, so a regression turns the build red without a separate command:

- **axe sweep** — `src/test/a11y.test.tsx` renders every shipping surface
  (matrix, job map, catch-up feed, settings, first-run wizard, command palette,
  chat stage, changelog dialog, decision brief) inside a real `<main>` and runs
  [axe-core](https://github.com/dequelabs/axe-core) through `vitest-axe`, with
  zero WCAG 2.1 A/AA violations allowed. The helper lives in `src/test/axe.ts`.
  `vitest-axe@0.1.0` ships an empty `extend-expect` module, so the helper
  asserts on `results.violations` directly instead of the `toHaveNoViolations`
  matcher; the output names the rule, its help text, and the offending
  selector.
  - `color-contrast` is disabled in this sweep: jsdom has no layout, so every
    element computes as transparent-on-white and axe cannot measure real
    colours. Contrast is covered by the next two bullets instead.
- **theme contrast** — `src/styles/theme.test.ts` derives both palettes from
  `theme.css` and asserts every text token (`--text`, `--muted`, `--faint`,
  `--accent`, `--green`, `--amber`) clears 4.5:1 on `--bg` and `--bg-raised`,
  and that the focus ring (`--accent`) clears the 3:1 non-text minimum. The
  same file fails if the stylesheet references a custom property that nothing
  defines, which is how the `--studio-*` aliases silently stopped resolving.
  Measured today: dark text 17.6, muted 8.2, faint 5.1, accent 6.8; light text
  16.6, muted 6.1, faint 4.6, accent 5.0.
- **keyboard and structure** — `src/test/keyboard.test.tsx` asserts the shell
  landmarks, skip link, and `<main>` target, then parses every non-test `.tsx`
  with the TypeScript AST and fails on any intrinsic element that carries
  `onClick` without being a native control or declaring
  `role` + `tabIndex` + `onKeyDown`. Component-level suites cover the rest:
  roving tabindex and arrow keys on the opportunity matrix, `aria-activedescendant`
  in the command palette, focus trapping and focus restore in the mobile lens
  and changelog dialog, and a single polite live region per transcript.

- **artifact structure** — `scripts/artifact_a11y.py` is the one owner of the
  rules an artifact's markup has to satisfy: one `<h1>`, no skipped heading
  level, a named table with scoped headers, a labelled or deliberately hidden
  image, and no id used twice. `tests/scripts/test_artifact_a11y.py` proves each
  rule with a fixture that breaks exactly one of them, `website/tests/test_site.py`
  runs the rule set over every built page, and
  `tests/scripts/test_artifact_inventory.py` scans the artifact roots so a
  renderer nobody registered fails the build by path. The brief is rendered in
  the browser, where Python cannot follow, so `src/components/brief/BriefLens.test.tsx`
  asserts the same four rules against its DOM. Passing these checks is a
  structural statement, not WCAG conformance and not a screen-reader
  certification — that evidence is ALH-252's to collect.

Reduced motion is honoured globally in `theme.css`: `@media
(prefers-reduced-motion: reduce)` collapses the `--motion-*` duration tokens to
`0ms` and turns off `scroll-behavior`, so a new rule inherits it by reading a
token instead of opting in. Motion driven from JavaScript reads
`useReducedMotion()` (`src/lib/useReducedMotion.ts`), which follows a change
without a reload. The budget is asserted in `src/styles/motion.test.ts`: every
duration outside the token block must be a token, exactly one reduced-motion
rule exists, and only the thinking dots and the streaming caret loop.

### Contrast as a build gate

The jsdom sweep above cannot measure contrast, so the browser carries that
half of the gate (issue #543, parent #331). `e2e/a11y.spec.ts` renders the five
core screens — home, the opportunity landscape, the records lens, catch-up, and
settings — in both themes and fails when a screen paints a pair that is not on
the known list, naming the screen, the selector, both colours, and the ratio.
The job is required: `.github/workflows/ci.yml` runs it as `Contrast gate` and
`ci-green` depends on it.

- **the walker** — `src/test/contrast.ts` resolves the effective background by
  walking the ancestors and folding each `background-color` and each gradient
  stop together. axe skips any element over a gradient and returns it as
  `incomplete`, which is exactly the shell, the hero, and the charts, so the
  walker measures them itself and reports a pair it still cannot resolve (an
  image, a filter) as `indeterminate` rather than skipping it. It is
  self-contained: the spec serialises it into the page with
  `Function.prototype.toString`, and `src/test/contrast.test.ts` runs the same
  source in jsdom.
- **the raw-colour gate** — `src/styles/colors.test.ts` fails on a hex or
  `rgb()` literal outside `theme.css`, naming the file and line, so a component
  cannot inline a colour the theme does not own. A handful of files whose
  colours are structural (generated artwork, print media, SVG chart fills) are
  named in `ALLOWED_FILES` with a reason and an issue; the list is capped and
  fails on a stale entry, so it can only shrink.
- **the known pairs** — `e2e/a11y/knownPairs.ts` records the token-level
  failures the walker finds today, each owned by #542 ("fix the tokens that
  fail AA", not yet merged) or #335. It is a ratchet: an unlisted pair fails
  immediately, and an entry that stops failing fails too, so the list can only
  shrink. When #542 lands, the gate reports the stale entries and they are
  deleted.

A deliberately low-contrast pair is injected in the spec's last test, so the
gate is proven to fail rather than assumed to.

## End-to-end

The browser-level suites live in `apps/studio/e2e/` and run with
[Playwright](https://playwright.dev). The sidecar-backed suite drives the real
Studio against the real sidecar and MCP server — no mocked network calls — so
it covers the seams that neither pytest nor vitest can: the SPA's assumptions
about the sidecar's response shapes, the sidecar's hydration of the canvas, and
the first-run wizard's ordering relative to the rest of the app. The
no-sidecar suite uses one 503 stub for `/api/**`, deliberately, so the fallback
path is deterministic rather than dependent on a static server's SPA answer.

```bash
npm --prefix apps/studio run build      # the sidecar serves apps/studio/dist
npm --prefix apps/studio run test:e2e
```

Playwright's `webServer` array starts the MCP server, the Studio sidecar, and
a second sidecar on the MCP passthrough backend. Two projects run against
them: `chromium` for the local backend (the product default) and
`mcp-backend` for the passthrough.

`playwright.no-sidecar.config.ts` is the second, required configuration. It
serves the built SPA from `vite preview` with no sidecar or MCP process and
routes `/api/**` to a 503 HTML answer, then proves the four things the product
promises without one: the stage loads, the assistant answers, a capture lands in
IndexedDB, and a reload still shows it. Run it with
`npm --prefix apps/studio run test:e2e:no-sidecar`.

Locators bind to what a user perceives — a role, a label, or visible text —
never to a `data-testid`, of which the application has none.

`first-paint.spec.ts` is the exception to "drives the real sidecar": it aborts
the module bundle so it can read the pre-JavaScript shell in `index.html`, then
compares the colour it painted against the `--bg` token for each theme.

CI runs the sidecar-backed suite in the `e2e` job. It is deliberately
non-blocking: set the repository variable `AGENTIC_ODI_E2E` to `false` to skip
it, and the `continue-on-error` on the job keeps a failure from turning CI red.
The no-sidecar suite runs in the `e2e-no-sidecar` job, which has no
`continue-on-error` and is part of the `CI green` aggregate: if the browser
fallback regresses, the required check fails.

## Observability

Two record shapes are asserted, and both are asserted on their contents rather
than on a line existing:

- `apps/studio-api/tests/test_studio_observability.py` checks the per-turn JSON
  line carries the token counts and the model, that a backend without usage
  leaves the counts `null` (never estimated), and that no API key, bearer token,
  or authorization header reaches a record.
- `apps/studio-api/tests/test_studio_chat_stream.py` drives a usage chunk and a
  backend that rejects `include_usage`, so the fallback path is exercised.
- `apps/mcp-server/tests/test_tool_timing.py` captures one log record per tool
  call and asserts the tool name, the duration key, and — for a failing tool —
  the envelope code the client already branches on.
- `packages/core/tests/test_logging.py` checks the shared `configure_logging()`
  is idempotent: calling it twice does not duplicate a handler.

See [Observability](observability.md) for the two record shapes.
