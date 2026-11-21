---
title: Development
blurb: Lint, types, frontend checks, and the coverage map.
nav_group: Operate
nav_order: 1
slug: development
---

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

Bandit reads code patterns. It cannot say that a pinned version has a known
advisory, so a separate `dependencies` CI job asks the advisory databases
directly, for the Python runtime export, the Studio's npm packages, and the
Tauri `Cargo.lock`. Run the same three commands locally:

```bash
uv export --all-packages --format requirements-txt --no-hashes --no-dev > /tmp/req.txt
uvx pip-audit==2.7.3 -r /tmp/req.txt --skip-editable
npm --prefix apps/studio audit --omit=dev --audit-level=high
cargo audit --file apps/studio/src-tauri/Cargo.lock
```

An advisory the repository accepts rather than fixes is recorded in
`security/audit-ignore.toml` with a reason and an `expires` date no more than 90
days out; `scripts/audit_ignore.py` reads that ledger, builds the tools' ignore
arguments, filters `npm audit` (which has no ignore flag), and fails the job when
an entry is expired. Validate the ledger and preview the arguments with:

```bash
uv run python scripts/audit_ignore.py --check
uv run python scripts/audit_ignore.py --pip-args
uv run python scripts/audit_ignore.py --cargo-args
```

The audit is not part of `scripts/verify.py --changed`: it needs the lockfiles
rather than the diff, and its result does not depend on which files a pull
request touched. See
[ADR 0008](architecture/adr/0008-dependency-advisories-are-a-gate.md).

## Documentation Checks

`scripts/doc_check.py` keeps the living docs honest against the code:

```bash
uv run python scripts/doc_check.py
```

`docs/roadmap.md` is a pointer page, not a register. It keeps no shipped,
in-flight, or queued lists of its own — those facts live in `CHANGELOG.md` and
Releases, the open-pull-request list, and the `ready-for-dev` issue filter — so
no capability change has to edit a roadmap file to land.

It checks that documented CLI commands exist in the Typer tree, documented paths
exist on disk, documented `/api` routes are served by the Studio router,
documented `AGENTIC_ODI_*` variables are read somewhere, the README's Code
Overview paths exist, and the assistant-ui ledger on its own page is internally honest:
every Adopted row names a file that exists and cites a delivered issue or PR,
the group counts match the tally, and the projection in
[Living Studio](living-studio.md) matches the Adopted and Partial rows in it.

## The assistant-ui ledger

The coverage table has its own page, [The assistant-ui ledger](assistant-ui-ledger.md) — **52** of the library's 129 relevant capabilities deliver something a person can use, **20** more are carried by open issues, **26** wait on a named decision, and **31** are rejected with a reason. It moved off this page so the Development page stays inside its 100 KiB budget; `scripts/doc_check.py` still reads it there, and still fails if the projection in [Living Studio](living-studio.md) drifts from it.

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

The build version is a single source of truth. `__STUDIO_VERSION__` is baked into
the Vite build from `apps/studio/package.json` (`vite.config.ts`) and exposed
through `src/lib/version.ts`; `src/lib/version.test.ts` fails if it drifts from
`package.json` or `.release-please-manifest.json`. `Settings → About` renders it,
and the diagnostics bundle records it together with its source (`build` or
`desktop`).

### Visual tests

`npm test` runs the jsdom suite and deliberately ignores `*.visual.test.tsx`.
Those files render one component state in Chromium under
`vitest.visual.config.ts`, and the `Chromatic` workflow publishes them on every
branch push so a reviewer can compare pixels component by component. Each test costs one billed snapshot per
build on the free 5,000/month allowance, which is why the two suites are split by
filename instead of running every test in a browser. Browser mode needs Chromium
locally: `npx playwright install chromium`. See
[Deployment](deployment.md) for the project setup and budget rules.

### The cold-start bundle budget

The first screen must not wait on everything the app can do, so the Vite build
splits the assistant runtime, the markdown renderer, and the Tauri API out of the
entry chunk with `build.rolldownOptions.output.codeSplitting` groups
(`vite.config.ts`), and emits `dist/.vite/manifest.json` so the budget script can
find the entry by role rather than by a hashed name.

`scripts/check_bundle_budget.mjs` measures the entry chunk and every chunk a cold
load pulls statically, and fails when the entry grows past the recorded baseline
in `scripts/bundle-budget.json` plus a 20% tolerance. CI runs it right after
`npm run build` in the `studio` job. After a deliberate change, re-record the
baseline and say why in the pull request:

```bash
npm --prefix apps/studio run build
node scripts/check_bundle_budget.mjs           # check
node scripts/check_bundle_budget.mjs --update  # re-record the baseline
```

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
covered at these levels. `ChatStage.test.tsx` covers the jump-to-latest control
while following a streamed turn — the arrival count, the polite announcement, the
return to the live end, and the keyboard path — and `arrivalCount.test.ts` holds
the pure count arithmetic. Every test file, with the one line it says about
itself, is in [the test map](reference/test-map.md); it is generated from the
files, so adding a test means writing a docstring, not editing a list here.

## Website Checks (GitHub Pages)

The `website/` static site is part of the main CI workflow. Its tests assert the
committed OG art is reproducible and that the publish pipeline
(`website/tests/test_pages_deploy.py`) still exists:

```bash
uv run --directory website pytest tests/
```

The site is generated at CI time and never committed. CI runs `build_site.py` to
produce `_site` and uploads it as the `website-site` artifact for review.

Every page that uses the shared shell gets **its own social card**: `build_site.py`
calls `make_og.render_card()` with the page's own `og:title`, the docs nav group it
sits under, and the one number the page itself renders (the landing page's stat, the
MCP reference's tool count). Nothing is invented - a page with no number of its own
is drawn without one - and a page that ends up with no card fails the build with
`MissingCardError`. The cards land in the build output under `og/`, never in git.
`website/tests/test_og_pages.py` asserts the contract.

The landing page's primary call to action points at the **sample workspace**,
`website/sample/index.html`. Unlike the rest of the site it *is* committed, so
it survives an API outage and can be linked from the README. It is generated
from `website/content/sample-study.json` by `website/tools/build_sample.py`;
regenerate it after editing the fixture or `website/templates/sample.html`:

```bash
uv run python website/tools/build_sample.py          # write the committed page
uv run python website/tools/build_sample.py --check  # fail when it is stale
```

`website/tests/test_content_sync.py` runs the same comparison, so the page
cannot drift from the fixture, and it greps the committed file for an external
reference so the no-network rule is enforced rather than promised.

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

### Merge-state labels

The [merge-conflict workflow](.github/workflows/label-merge-conflicts.yml) owns
the two labels a reviewer reads to know whether a pull request can land:

| Label | Meaning |
|---|---|
| `merge-conflict` | The branch cannot merge into `main` as it stands. |
| `ready-for-merge` | No conflict; the branch merges cleanly. |

GitHub computes mergeability lazily and answers `UNKNOWN` for a moment after
every push, so the workflow polls `mergeStateStatus` (up to ten times, six
seconds apart) before it decides. A state that is still `UNKNOWN` after the
retries leaves both labels untouched rather than guessing; a state that is
neither `clean` nor `dirty` (for example `behind`) clears `merge-conflict`
without claiming the PR is ready.

### Which files actually conflict

`scripts/doc_churn.py` ranks the files and top-level directories that appear in
the most merged pull requests, which is the churn that produces conflicts. It
is offline by default — it reads the saved fixtures payload — and shells out to
`gh` only with `--live`:

```bash
uv run python scripts/doc_churn.py --since 30d            # offline fixtures
uv run python scripts/doc_churn.py --since 30d --live     # the real history
uv run python scripts/doc_churn.py --since 30d --live --json
```

A path repeated inside one pull request counts once: the number is how many
pull requests touched a file, not how many file entries named it.

### Tiered Automated Triage (shift-left filtering)

The same risk workflow runs a third job, **triage**, which decides whether a
human may open the diff. It enforces the project's shift-left rule:

> **Humans should never read an unvetted AI PR.**

A pull request is vetted -- and becomes eligible for a human reviewer -- only
when it carries the `ready for human review` gate label. The triage job applies
it deterministically (no LLM, no PR code executed) from the provenance, risk
tier, and size labels the `labels` and `pr-risk` jobs just computed:

| Author | Risk tier | Gate decision | What a human sees |
|---|---|---|---|
| Human | any | `ready for human review` | The diff is open for review immediately. |
| Agent | `safe to merge` (≤ 20) | `ready for human review` | Automated vet complete; fast path to review. |
| Agent | `safe to merge` + `size/XL` | `needs human review` | Size alone warrants a first reviewer pass. |
| Agent | `needs a look` (21–50) | `needs human review` | Awaits an assigned reviewer before anyone reads the diff. |
| Agent | `danger zone` (≥ 51) | `deep dive` | Blocking deep-dive review; never auto-merged. |

The triage job owns the gate labels (`ready for human review`, `needs human
review`, `deep dive`) and manages them idempotently on every run, so re-pushing
a branch re-triages the pull request. It creates its own labels (the `labels`
job manages a different set), runs only on non-fork pull requests, and never
executes pull request code.

```bash
python3 scripts/pr_triage.py --labels labels.txt   # print the triage decision
```

## AI merge trust and authorization labels

Two labels work together to let an AI agent merge safe pull requests without
human review:

| Label | Meaning | Set by |
|-------|---------|--------|
| `ai-merge-safe` | The PR is non-disruptive and non-sensitive (AND-gated on risk, size, telemetry, sensitive areas, hygiene). | `pr-ai-merge.yml` |
| `ai-merge-authorized` | CI is green and the PR carries `ai-merge-safe` + `ready-for-merge`; an AI agent may auto-merge it. | `pr-ai-authorize.yml` |

### `ai-merge-safe` (labelling only — humans still merge)

The [PR AI merge trust workflow](.github/workflows/pr-ai-merge.yml) applies
`ai-merge-safe` only when every gate passes, and removes it when any gate
fails. Deterministic — no LLM calls, no network beyond the GitHub API, no pull
request code executed. Fork pull requests are skipped per-job.

| Gate | Requirement |
|------|-------------|
| Low disruption | `safe to merge` (risk score ≤ 20) |
| CI green, no conflicts | `ready-for-merge` |
| Small enough | `size/XS` or `size/S` (< 250 lines changed) |
| Clean telemetry | none of `breaking change`, `needs deep dive`, `telemetry invalid` |
| Non-sensitive areas | no CI/infra/release path, no deleted protected file, no dependency change |
| Hygiene | open, non-draft PR targeting `main` |

```bash
python3 scripts/pr_ai_merge.py --facts facts.json   # print the label or nothing
python3 scripts/pr_ai_merge.py --managed            # list owned labels
```

### `ai-merge-authorized` (CI green → AI agent may auto-merge)

The [PR AI merge authorize workflow](.github/workflows/pr-ai-authorize.yml)
applies `ai-merge-authorized` only when the PR carries `ai-merge-safe`, the
head commit's check suite is complete and green, `ready-for-merge` is present
(no merge conflicts), and hygiene passes (open, non-draft, targets `main`). It
is removed when any gate fails.

"Green" is `compute_ci_state()` in `scripts/pr_ai_authorize.py`: `CI green` and
`PR guardrails` must be successful, and every other GitHub Actions check run on
the head commit must be green except the advisory browser suite (`End-to-end`),
which `AGENTIC_ODI_E2E_BLOCKING=true` turns into a gate. The legacy combined
commit status is deliberately not consulted — it carries only third-party
statuses, so it reads `success` while CI is still queued. See
[ADR 0009](architecture/adr/0009-ai-merge-gate-reads-the-check-suite.md).

```bash
python3 scripts/pr_ai_authorize.py --facts facts.json   # print the label or nothing
python3 scripts/pr_ai_authorize.py --managed            # list owned labels
```

### Auto-merge (Phase 2)

The [PR AI merge act workflow](.github/workflows/pr-ai-merge-act.yml) arms
`gh pr merge --auto --squash` only on an open PR that carries
`ai-merge-authorized`, `ai-merge-safe` and `ready-for-merge`, whose head commit
passes the check-suite gate, and whose labels it has just re-read. The trigger
is narrowed to the labels that can change the decision, so an unrelated label
cannot arm a merge.

Arming is a request, not a decision: every run can disarm. If a gate stops
holding — the authorization or trust label is removed, a new push resets the
checks, a human adds `do-not-merge` or `needs human review`, or the suite goes
red — the workflow calls `gh pr merge --disable-auto` and says why in an
idempotent `## AI merge act` comment that names the head commit it judged.

### Branch protection (enforced on `main`)

A label is advisory; a status check is not. The `main-requires-ci-green`
ruleset on `main` requires these checks, and nothing can bypass them:

| Check / requirement | Purpose |
|---------------------|---------|
| `CI green` status check | Full CI matrix passes |
| `PR guardrails` status check | Diff-shape, body-truth, and fabrication gates pass |

The `protect-main` ruleset adds the branch-level rules: no deletion, no
non-fast-forward push, and every change arrives through a pull request.

A ruleset cannot require a *label* — its rule types are checks, reviews, and push
rules, not labels — so `ai-merge-safe` is enforced one step later, by the merge
path: gate 1 of `scripts/pr_ai_authorize.py` refuses `ai-merge-authorized`
without it, and `pr-ai-merge-act.yml` arms auto-merge only on that label. A pull
request can therefore satisfy both checks and still not be auto-merged; what stops
it is the missing label and the `do-not-merge` / `needs human review` labels, not
GitHub settings.

Rulesets are repository settings, not files, so this cannot be enforced from the
checkout. `tests/test_adr_index.py` checks the names the documents claim against
the job names in `.github/workflows/ci.yml` and
`.github/workflows/pr-guardrails.yml`, so a renamed job fails on the pull request
that renamed it. See [ADR 0007](architecture/adr/0007-branch-protection-enforces-checks-not-labels.md)
for the decision and the deferred `label gate` check.

## Testing

See `.agents/workflows/test.md` for the test tiers. **Before opening a PR**, run the pre-PR tier:

```bash
uv run python scripts/verify.py --changed   # required CI checks the diff can drive (PR bar)
uv run python scripts/verify.py --default   # adds repo-wide mypy, studio build, site build
uv run python scripts/verify.py --full      # local matrix; e2e/Tauri/audit stay CI-only
```

Per-command ceiling is 300s; designed for a 10–30 minute agent budget. CI owns
`--full`. The gate prints which tier covers each required CI job and why the
rest are CI-only; `tests/scripts/test_verify_ci_parity.py` keeps that table
equal to `ci-green.needs`. The PR body must list the tiers run and skipped.

Tests use **pytest** with **pytest-asyncio** (strict mode) and run entirely
in-memory — no running server required. Tests live next to the package they
cover.

The MCP server contract test compares the live FastMCP registry with
`packages/core/src/agentic_odi_core/contract.py`, so add or change a tool in
both places. The CLI local-backend contract test keeps `_LOCAL_HANDLERS` aligned
with the same tool names.

### Artifact structure

An artifact is HTML a person reads without the app: a built website page, the
sample workspace, the offline shell, the decision brief. All of them are judged
by one rule set, `scripts/artifact_a11y.py`, which reports six structural defects:

- `single-h1` — the document holds exactly one `<h1>`; none and two are both defects.
- `heading-order` — a heading never skips a level.
- `table-caption` — a data table is named, by a `<caption>` or by an
  `aria-labelledby` that resolves to an `id` the document actually contains.
- `table-header-scope` — every `<th>` declares `scope` of row, col, rowgroup or colgroup.
- `image-label` — an `<img>` carries `alt`, and an `<svg>` is either decoration
  (`aria-hidden="true"`) or a chart with a label a reader can be told.
- `duplicate-id` — no `id` is used twice, so a link or a label cannot point at the
  wrong element.

```bash
uv run pytest tests/scripts/test_artifact_a11y.py           # the rules, on fixtures
uv run pytest website/tests/test_site.py -k artifact_audit   # every built page against them
```

`scripts/artifact_renderers.py` is the inventory: one row per renderer, plus the
artifacts that have none. `tests/scripts/test_artifact_inventory.py` scans the
artifact roots for the markup that gives a renderer away, so a new file writing
`<h1>` or `<table>` under one of those roots fails the suite by name until it is
registered as a `Renderer(...)` row.

Zero violations is a structural check. It is not WCAG conformance and it is not
a screen-reader certification — nobody has read these artifacts with an actual
reader, which is ALH-252's work. The memo, the one-pager and the shared page are
recorded in the inventory as having no renderer at all, so there is nothing here
to audit for them yet.

### End-to-end testing

The browser-level suite lives in `apps/studio/e2e/` and runs with
[Playwright](https://playwright.dev). It drives the real Studio against the
real sidecar and MCP server, with no mocked network calls, so it covers the
seams the other tiers cannot: the SPA's assumptions about the sidecar's
response shapes, the sidecar's hydration of the canvas, and the first-run
wizard's ordering relative to the rest of the app.

```bash
npm --prefix apps/studio run build            # the sidecar serves apps/studio/dist
npm --prefix apps/studio run test:e2e         # the product suite
npm --prefix apps/studio run test:e2e:smoke   # the blocking @smoke subset
npm --prefix apps/studio run test:e2e:visual  # the opt-in screenshot contract
npm --prefix apps/studio run test:e2e:ui      # the Playwright UI
```

The first run needs the browser once:

```bash
npx --prefix apps/studio playwright install chromium
```

Playwright's `webServer` array starts the MCP server, the Studio sidecar, and
a second sidecar on the MCP passthrough backend. `chromium` (the local
backend, the product default) and `mcp-backend` (the passthrough) make up
`test:e2e`; a spec is collected by exactly one of them.

A third project, `screenshots`, is added only when `PR_SCREENSHOTS=1` is set.
It runs `e2e/pr-screenshots.spec.ts`, which writes one PNG per key screen into
the `pr-screenshots` directory under `apps/studio` for human review. The
default `test:e2e` run never sees it. The `pr-screenshots` workflow sets the
variable, captures the screens against a live backend, and posts them as a
single comment on the pull request. The job is advisory — `continue-on-error:
true` and no membership in `ci-green`'s `needs` — so a screenshot failure
cannot block a merge.

Locators bind to what a user perceives — a role, a label, or visible text —
never to a `data-testid`, of which the application has none, and never to a CSS
class. When a test needs data behind it, it seeds through the API rather than
through the UI, so the test stays about the view it is actually checking.

Every spec imports `test` and `expect` from `e2e/fixtures.ts`. Its automatic
fixture resets the shared studio — jobs, conversation memory, unread signals —
before each test, so no spec inherits another's writes and the result does not
depend on the order Playwright chose. A spec that imports from
`@playwright/test` directly gets the shared state back.

CI runs two browser jobs. `e2e-smoke` is **required** and runs the `@smoke`
tagged subset with `--retries=0`. `e2e` runs the whole suite and stays advisory:
set the repository variable `AGENTIC_ODI_E2E` to `false` to skip it, or
`AGENTIC_ODI_E2E_BLOCKING` to `true` to make it block. Its summary lists every
failure with its locator and call site, plus every test that passed only on
retry.

`test:e2e:visual` is opt-in because the repository has committed no screenshot
baselines yet; running it in the product lane made that lane permanently red.

A flaky spec is fixed or parked, never left to retry: `e2e/quarantine.ts` +
`// quarantined: #<issue> <YYYY-MM-DD>` in the spec, with
`src/test/e2eQuarantine.test.ts` failing the entry after thirty days. See
[Testing](architecture/testing.md#a-flaky-spec-is-fixed-or-parked-never-retried-indefinitely).

## Cold-open budget

A study at scale must reach an interactive screen in under a second, or a PM
batches their work instead of checking something. The reference study is 1,500
outcomes over 30 jobs, each with a complete eight-step job map and one customer
quote per outcome (3,270 events). It is generated deterministically by
`agentic_odi_core.corpus.build_corpus`, so the number is comparable between runs
and machines:

```bash
uv run python scripts/gen_corpus.py --out /tmp/corpus.db
```

The number is measured per segment, because the fix differs per segment, and the
regression tests live with the segment they cover:

```bash
uv run pytest packages/core -k perf --no-header -q
npm --prefix apps/studio test -- --run src/components/canvas/opportunityLandscape.perf.test.tsx
```

**Reference environment:** AMD EPYC 9B14, 4 vCPU, 15 GiB RAM, Linux, Python
3.13.15, `uv` 0.13.5, median of seven cold-open runs.

| Segment | Before | After | Fix |
|---|---|---|---|
| Store open (`_load_snapshot` replay) | 32 ms | 27 ms | Unchanged; replay itself was never the bottleneck. |
| Canvas assembly (`fetch_local_canvas`) | 1,146 ms | 23 ms | `_sync` now reads only events appended since the last apply (`get_stream(after_id=…)`) instead of re-parsing the whole log on every read. One assembly read 206,010 rows; it now reads 3,270. |
| First interactive render (SPA matrix) | 590 ms | 162 ms | The landscape plots the 200 highest-opportunity outcomes above the fold and offers "Plot all"; 8,957 DOM nodes became 1,709. |

Cold open, end to end, is store open plus assembly plus first render: **32 + 1,146
+ 590 ≈ 1,768 ms before, 27 + 23 + 162 ≈ 212 ms after.**

The Python bounds in `packages/core/tests/test_perf_cold_open.py` are deliberately
loose (2 s per segment — roughly an order of magnitude over the reference number).
A tight wall-clock bound on a shared runner fails on a busy box and gets deleted
within a month. The deterministic guard is
`test_perf_canvas_assembly_does_not_rescan_the_whole_log`: it counts rows read
rather than seconds, and a return to the full rescan (206,010 rows) fails it on
any machine.

## Render budget

The cold-open number above is one screen appearing. The second cost is a screen
that re-renders while you use it, and that is what the Studio's state splits
(#503, #504, #505) are for. Their precondition is a number, so
`apps/studio/src/test/renderCounts.tsx` counts renders and
`src/state/StudioContext.test.tsx` pins them.

Four surfaces are instrumented — the composer, the opportunity landscape, the
workbench rail, and the banner area — mounted inside the real provider stack.
A counter rendered *beside* a context consumer cannot see that consumer re-render
(React bails out below a provider whose children element is stable), so each
surface is wrapped in a `Profiler` and the number is commits that included it.

| Scenario | composer | landscape | rail | banners |
|---|---|---|---|---|
| Forty streamed deltas | 5 | 2 | 2 | 2 |
| Twenty keystrokes in the composer | 40 | 0 | 0 | 0 |
| One health poll turning unhealthy | 1 | 1 | 1 | 5 |

Baseline recorded on 2026-11-05 at commit `c403ba17`.

```bash
npm --prefix apps/studio test -- --run src/state/StudioContext.test.tsx   # the budget
npm --prefix apps/studio test -- --run src/test/renderCounts.test.tsx     # the harness
```

Two things make these numbers usable. They are **exact, not ceilings**: the split
issues may only lower a row, and a rise — or a drop — fails with the surface
named, so it has to be argued with and re-recorded in the same pull request. And
the scenario starts only once the boot has gone quiet: the harness waits for the
fetches the boot left in flight, because a health answer landing mid-typing
otherwise measures the race instead of the interaction.

The harness is imported by tests alone, and the shipped bundle is byte-identical
to the baseline it was taken against (`index-BLu6eXb1.js`, 1,321.24 kB / 392.52 kB
gzip; `index-BXj2fr1g.css`, 106.89 kB / 20.56 kB gzip). A wall-clock render
budget is deliberately not asserted: it would fail on a busy runner for reasons
unrelated to the code under review.

## Test Coverage

The `test` job is the authoritative Python gate. Pytest runs on Python **3.10,
3.11, and 3.12** with coverage on and `--cov-fail-under=89` — the same floor as
`[tool.coverage.report] fail_under` in `pyproject.toml` — so a pull request that
drops the combined number fails in a job that needs no secret, a fork's pull
request included. Measured on 2026-11-21: **89.52%** (16,467 statements, 1,726
missed), so the gate has little slack.

The floor is a ratchet. On every pull request, `scripts/coverage_floor.py`
compares `fail_under` in `pyproject.toml` with the base branch and fails when the
head value is lower. Raise `fail_under` as coverage improves; never lower it to
unblock a change.

[Codecov](https://codecov.io/gh/alehar9320/agentic-odi) stays the reporting
surface, not the gate. The 3.12 job writes a per-distribution table to the job
summary and uploads `coverage.xml` with the `CODECOV_TOKEN` secret under the
`python` flag. A run without the secret (a fork, or Dependabot) skips the upload
and says so in the log and the job summary instead of passing silently; an
attempted upload that fails does fail the job (`fail_ci_if_error: true`).
`codecov.yml` keeps a **90%** project target with a 1% dip — the same **89%**
minimum pytest enforces — and scopes that status to the `python` flag, so the
Studio's lower number cannot turn it red. Patch status is informational while
new code lands.

The Studio is gated separately. `npm run test:coverage` runs Vitest with the V8
provider, writes `apps/studio/coverage/lcov.info`, and fails the `studio` job
below statements **83%**, branches **75%**, functions **83%**, and lines **83%**.
Measured on 2026-11-21: 83.3%, 75.9%, 83.5%, 83.4%. The lcov file is
uploaded to Codecov under the `studio` flag, also non-blocking — the Vitest
thresholds are what gate the merge.

Reproduce both reports locally:

```bash
# Python: the combined number CI sees
uv run pytest \
  --cov=agentic_odi_cli \
  --cov=agentic_odi_connectors \
  --cov=agentic_odi_core \
  --cov=agentic_odi_mcp_server \
  --cov=agentic_odi_studio_api \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml \
  --cov-fail-under=89

# Studio
npm --prefix apps/studio run test:coverage
```

> [!NOTE]
> Codecov's project status covers the Python packages. `apps/studio/` reports
> under its own flag, and test directories stay excluded in `codecov.yml`.

### Conventions

- Test files live under each project's `tests/` directory and are named
  `test_*.py`.
- Root `tests/` is reserved for cross-package checks (`contract/` and
  `scripts/`).
- Every async test is decorated with `@pytest.mark.asyncio`.
- Use `Client(mcp)` directly (no HTTP server needed) for fast, isolated tests.
- The MCP server's `configured_server` autouse fixture names a fresh
  `InMemoryRepository` before each test.

### Test Coverage Map

Every test file and the source it exercises, generated from the test tree rather
than maintained by hand. `uv run python scripts/coverage_map.py --check` fails CI
when this table drifts from the repository; `--write` regenerates it. A test with
no resolvable pair stays in the table, named, rather than disappearing.

<!-- coverage-map:start -->
| Test file | Exercises |
|---|---|
| `apps/cli/tests/test_alternatives_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/cli/tests/test_backend.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/remote.py` |
| `apps/cli/tests/test_backend_edges.py` | `apps/cli/src/agentic_odi_cli/backend.py` |
| `apps/cli/tests/test_backend_selection.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/cli/tests/test_build_info.py` | `apps/cli/src/agentic_odi_cli/_build_info.py`<br>`apps/cli/src/agentic_odi_cli/version.py` |
| `apps/cli/tests/test_candidates_cli.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`apps/cli/src/agentic_odi_cli/cli.py` |
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
| `apps/cli/tests/test_data_path.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_demo_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_desired_outcomes_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/desired_outcomes.py` |
| `apps/cli/tests/test_doctor.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/doctor.py` |
| `apps/cli/tests/test_evidence_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_insight_commands.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_interviews_cli.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`apps/cli/src/agentic_odi_cli/cli.py`<br>`packages/core/src/agentic_odi_core/contract.py` |
| `apps/cli/tests/test_jobs_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_link_outcome_errors.py` | `apps/cli/src/agentic_odi_cli/backend.py` |
| `apps/cli/tests/test_mascot.py` | `apps/cli/src/agentic_odi_cli/mascot.py` |
| `apps/cli/tests/test_onboard.py` | `apps/cli/src/agentic_odi_cli/onboard.py`<br>`apps/cli/src/agentic_odi_cli/profile.py`<br>`apps/cli/src/agentic_odi_cli/version.py` |
| `apps/cli/tests/test_paths.py` | `apps/cli/src/agentic_odi_cli/paths.py` |
| `apps/cli/tests/test_persistence.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/cli/tests/test_profile.py` | `apps/cli/src/agentic_odi_cli/chat.py`<br>`apps/cli/src/agentic_odi_cli/paths.py`<br>`apps/cli/src/agentic_odi_cli/profile.py` |
| `apps/cli/tests/test_profile_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/profile.py` |
| `apps/cli/tests/test_render.py` | `apps/cli/src/agentic_odi_cli/render.py` |
| `apps/cli/tests/test_schedule_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_segments_cli.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_settings_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_signals_cli.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_startup_perf.py` | — no direct source pair |
| `apps/cli/tests/test_stats_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`packages/core/src/agentic_odi_core/funnel.py`<br>`packages/core/src/agentic_odi_core/intent_store.py` |
| `apps/cli/tests/test_steps_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_studies_cli.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_summary_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_trust_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/cli/tests/test_update.py` | `apps/cli/src/agentic_odi_cli/update.py` |
| `apps/cli/tests/test_update_check.py` | `apps/cli/src/agentic_odi_cli/update.py` |
| `apps/cli/tests/test_update_command.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/update.py`<br>`apps/cli/src/agentic_odi_cli/version.py` |
| `apps/cli/tests/test_update_edges.py` | `apps/cli/src/agentic_odi_cli/update.py` |
| `apps/cli/tests/test_version_flag.py` | `apps/cli/src/agentic_odi_cli/cli.py`<br>`apps/cli/src/agentic_odi_cli/version.py` |
| `apps/cli/tests/test_wizard_cli.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `apps/mcp-server/tests/mcp_failures.py` | `packages/core/src/agentic_odi_core/remote.py` |
| `apps/mcp-server/tests/test_candidates.py` | `packages/core/src/agentic_odi_core/remote.py` |
| `apps/mcp-server/tests/test_context_tools.py` | — no direct source pair |
| `apps/mcp-server/tests/test_customer_outcomes.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_graceful_shutdown.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/mcp-server/tests/test_health.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_import_side_effects.py` | — no direct source pair |
| `apps/mcp-server/tests/test_interviews.py` | — no direct source pair |
| `apps/mcp-server/tests/test_odi.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_parity.py` | — no direct source pair |
| `apps/mcp-server/tests/test_port_config.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_segments.py` | — no direct source pair |
| `apps/mcp-server/tests/test_server_tools.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`<br>`packages/core/src/agentic_odi_core/contract.py` |
| `apps/mcp-server/tests/test_signals.py` | — no direct source pair |
| `apps/mcp-server/tests/test_spine_tools.py` | — no direct source pair |
| `apps/mcp-server/tests/test_tool_branches.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_tool_progress.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` |
| `apps/mcp-server/tests/test_tool_spec_validation.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`<br>`packages/core/src/agentic_odi_core/contract.py` |
| `apps/mcp-server/tests/test_tool_timing.py` | — no direct source pair |
| `apps/mcp-server/tests/test_tools.py` | — no direct source pair |
| `apps/mcp-server/tests/test_traceability_tools.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`<br>`packages/core/src/agentic_odi_core/models.py` |
| `apps/studio/e2e/a11y.spec.ts` | `apps/studio/e2e/a11y/knownPairs.ts`<br>`apps/studio/e2e/fixtures.ts`<br>`apps/studio/e2e/helpers.ts`<br>`apps/studio/src/test/contrast.ts` |
| `apps/studio/e2e/brief.spec.ts` | `apps/studio/e2e/fixtures.ts`<br>`apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/capture.spec.ts` | `apps/studio/e2e/fixtures.ts`<br>`apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/chat.spec.ts` | `apps/studio/e2e/fixtures.ts`<br>`apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/first-paint.spec.ts` | `apps/studio/e2e/fixtures.ts`<br>`apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/first-run.spec.ts` | `apps/studio/e2e/fixtures.ts`<br>`apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/landscape.spec.ts` | `apps/studio/e2e/fixtures.ts`<br>`apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/mcp-backend.spec.ts` | `apps/studio/e2e/fixtures.ts`<br>`apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/motion.spec.ts` | `apps/studio/e2e/fixtures.ts`<br>`apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/no-sidecar/offline.spec.ts` | `apps/studio/e2e/fixtures.ts`<br>`apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/pr-screenshots.spec.ts` | `apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/starters.spec.ts` | `apps/studio/e2e/fixtures.ts`<br>`apps/studio/e2e/helpers.ts` |
| `apps/studio/e2e/visual.spec.ts` | `apps/studio/e2e/fixtures.ts`<br>`apps/studio/e2e/helpers.ts`<br>`apps/studio/e2e/visual/fixtures.ts` |
| `apps/studio/e2e/workspace.spec.ts` | `apps/studio/e2e/fixtures.ts`<br>`apps/studio/e2e/helpers.ts` |
| `apps/studio/src/App.test.tsx` | `apps/studio/src/App.tsx`<br>`apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/state/scheduleProbe.ts` |
| `apps/studio/src/api/sse.test.ts` | `apps/studio/src/api/sse.ts` |
| `apps/studio/src/api/studioApi.local.test.ts` | `apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/bff/store/types.ts` |
| `apps/studio/src/api/studioApi.test.ts` | `apps/studio/src/api/studioApi.ts` |
| `apps/studio/src/assistant/attachments.test.ts` | `apps/studio/src/assistant/attachments.ts` |
| `apps/studio/src/assistant/claims.test.ts` | `apps/studio/src/assistant/claims.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/assistant/consequence.test.ts` | `apps/studio/src/assistant/consequence.ts` |
| `apps/studio/src/assistant/convert.test.ts` | `apps/studio/src/assistant/convert.ts`<br>`apps/studio/src/types.ts`<br>`apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts` |
| `apps/studio/src/assistant/dictation.test.ts` | `apps/studio/src/assistant/dictation.ts` |
| `apps/studio/src/assistant/extract/common.test.ts` | `apps/studio/src/assistant/extract/common.ts` |
| `apps/studio/src/assistant/extract/docx.test.ts` | `apps/studio/src/assistant/extract/common.ts`<br>`apps/studio/src/assistant/extract/docx.ts` |
| `apps/studio/src/assistant/extract/pdf.test.ts` | `apps/studio/src/assistant/extract/common.ts`<br>`apps/studio/src/assistant/extract/pdf.ts` |
| `apps/studio/src/assistant/interview/Interview.test.tsx` | `apps/studio/src/assistant/interview/Interview.tsx`<br>`apps/studio/src/assistant/interview/conductor.ts`<br>`apps/studio/src/bff/store/memoryStore.ts` |
| `apps/studio/src/assistant/interview/conductor.test.ts` | `apps/studio/src/assistant/interview/conductor.ts` |
| `apps/studio/src/assistant/interview/persistence.test.ts` | `apps/studio/src/assistant/interview/persistence.ts`<br>`apps/studio/src/bff/store/memoryStore.ts`<br>`apps/studio/src/bff/store/types.ts` |
| `apps/studio/src/assistant/parts.approval.test.tsx` | `apps/studio/src/assistant/parts.tsx` |
| `apps/studio/src/assistant/parts.test.tsx` | `apps/studio/src/assistant/parts.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/assistant/pending.test.ts` | `apps/studio/src/assistant/pending.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/assistant/plan.test.ts` | `apps/studio/src/assistant/plan.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/assistant/queue.test.ts` | `apps/studio/src/assistant/queue.ts` |
| `apps/studio/src/assistant/quote.test.ts` | `apps/studio/src/assistant/quote.ts` |
| `apps/studio/src/assistant/speech.test.ts` | `apps/studio/src/assistant/speech.ts` |
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
| `apps/studio/src/bff/data/localDataService.test.ts` | `apps/studio/src/bff/data/localDataService.ts`<br>`apps/studio/src/bff/store/memoryStore.ts`<br>`apps/studio/src/lib/odi.ts` |
| `apps/studio/src/bff/index.test.ts` | `apps/studio/src/bff/index.ts`<br>`apps/studio/src/bff/store/memoryStore.ts` |
| `apps/studio/src/bff/memory/localMemoryService.test.ts` | `apps/studio/src/bff/memory/localMemoryService.ts`<br>`apps/studio/src/bff/store/memoryStore.ts` |
| `apps/studio/src/bff/outbox.test.ts` | `apps/studio/src/bff/outbox.ts`<br>`apps/studio/src/bff/store/memoryStore.ts`<br>`apps/studio/src/bff/store/types.ts` |
| `apps/studio/src/bff/storageFacts.test.ts` | `apps/studio/src/bff/storageFacts.ts`<br>`apps/studio/src/bff/store/indexedDbStore.ts`<br>`apps/studio/src/bff/store/memoryStore.ts` |
| `apps/studio/src/bff/store/indexedDbStore.test.ts` | `apps/studio/src/bff/store/indexedDbStore.ts`<br>`apps/studio/src/bff/store/memoryStore.ts`<br>`apps/studio/src/bff/store/migrations.ts`<br>`apps/studio/src/bff/store/types.ts` |
| `apps/studio/src/bff/store/migrations.test.ts` | `apps/studio/src/bff/store/migrations.ts` |
| `apps/studio/src/bridge/desktopBridge.test.ts` | `apps/studio/src/bridge/desktopBridge.ts` |
| `apps/studio/src/bridge/runtime.test.ts` | `apps/studio/src/bridge/runtime.ts` |
| `apps/studio/src/components/BlockedReasonNote.test.tsx` | `apps/studio/src/components/BlockedReasonNote.tsx` |
| `apps/studio/src/components/BootFailurePage.test.tsx` | `apps/studio/src/components/BootFailurePage.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/ChangelogModal.test.tsx` | `apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/ChangelogModal.tsx`<br>`apps/studio/src/lib/changelogRead.ts` |
| `apps/studio/src/components/FailurePanel.visual.test.tsx` | `apps/studio/src/components/FailurePanel.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/OdiMascot.test.tsx` | `apps/studio/src/components/OdiMascot.tsx` |
| `apps/studio/src/components/SettingsPanel.test.tsx` | `apps/studio/src/components/SettingsPanel.tsx`<br>`apps/studio/src/lib/version.ts`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/components/ShareAction.test.tsx` | `apps/studio/src/components/ShareAction.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/ShareSheet.test.tsx` | `apps/studio/src/components/ShareSheet.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/SharedArtifact.test.tsx` | `apps/studio/src/App.tsx`<br>`apps/studio/src/components/SharedArtifact.tsx` |
| `apps/studio/src/components/brief/BriefLens.test.tsx` | `apps/studio/src/components/brief/BriefLens.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/Dashboard.test.tsx` | `apps/studio/src/components/canvas/Dashboard.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/DirectCapture.test.tsx` | `apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/canvas/DirectCapture.tsx` |
| `apps/studio/src/components/canvas/EvidenceStream.test.tsx` | `apps/studio/src/components/canvas/EvidenceStream.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/JobMap.test.tsx` | `apps/studio/src/components/canvas/JobMap.tsx`<br>`apps/studio/src/domain/jobStages.ts` |
| `apps/studio/src/components/canvas/MemoryPanel.test.tsx` | `apps/studio/src/components/canvas/MemoryPanel.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/OpportunityLandscape.test.tsx` | `apps/studio/src/components/canvas/OpportunityLandscape.tsx`<br>`apps/studio/src/lib/odi.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/OpportunityLandscapeFacet.test.tsx` | `apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/canvas/OpportunityLandscape.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/OutcomeCard.test.tsx` | `apps/studio/src/components/canvas/OutcomeCard.tsx` |
| `apps/studio/src/components/canvas/OutcomeCardAlternatives.test.tsx` | `apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/canvas/OutcomeCard.tsx` |
| `apps/studio/src/components/canvas/OutcomeCardBand.test.tsx` | `apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/canvas/OutcomeCard.tsx` |
| `apps/studio/src/components/canvas/OutcomeCardNote.test.tsx` | `apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/canvas/OutcomeCard.tsx` |
| `apps/studio/src/components/canvas/OutcomeCardSample.test.tsx` | `apps/studio/src/components/canvas/OutcomeCard.tsx` |
| `apps/studio/src/components/canvas/SchedulePanel.test.tsx` | `apps/studio/src/components/canvas/SchedulePanel.tsx` |
| `apps/studio/src/components/canvas/ScorePopover.test.tsx` | `apps/studio/src/components/canvas/ScorePopover.tsx`<br>`apps/studio/src/lib/odi.ts` |
| `apps/studio/src/components/canvas/SegmentBoard.test.tsx` | `apps/studio/src/components/canvas/SegmentBoard.tsx`<br>`apps/studio/src/lib/odi.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/canvas/ThesisAction.test.tsx` | `apps/studio/src/components/canvas/OutcomeCard.tsx` |
| `apps/studio/src/components/canvas/opportunityLandscape.perf.test.tsx` | `apps/studio/src/components/canvas/OpportunityLandscape.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/chat/ChatStage.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/ChatStage.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/chat/ClaimCitation.test.tsx` | `apps/studio/src/components/chat/ClaimCitation.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/chat/CommandPalette.test.tsx` | `apps/studio/src/components/chat/Composer.tsx`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/components/chat/Composer.test.tsx` | `apps/studio/src/components/chat/Composer.tsx`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/components/chat/Conversation.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/Conversation.tsx`<br>`apps/studio/src/lib/relativeTime.ts`<br>`apps/studio/src/types.ts`<br>`apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts` |
| `apps/studio/src/components/chat/Dictation.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/ThreadComposer.tsx`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/components/chat/Markdown.test.tsx` | `apps/studio/src/components/chat/Markdown.tsx` |
| `apps/studio/src/components/chat/ModelPicker.test.tsx` | `apps/studio/src/components/chat/ModelPicker.tsx` |
| `apps/studio/src/components/chat/PendingCalls.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/Conversation.tsx`<br>`apps/studio/src/components/chat/PendingCalls.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/chat/PlanPanel.test.tsx` | `apps/studio/src/components/chat/PlanPanel.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/chat/QueueLane.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/assistant/queue.ts`<br>`apps/studio/src/components/chat/QueueLane.tsx`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/components/chat/SelectionToolbar.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/SelectionToolbar.tsx` |
| `apps/studio/src/components/chat/Speech.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/Conversation.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/chat/StallNotice.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/Conversation.tsx`<br>`apps/studio/src/components/chat/StallNotice.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/chat/StarterCards.visual.test.tsx` | — no direct source pair |
| `apps/studio/src/components/chat/SuggestionPills.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/composerParts.tsx`<br>`apps/studio/src/state/StudioContext.tsx` |
| `apps/studio/src/components/chat/ThreadComposer.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/assistant/attachments.ts`<br>`apps/studio/src/components/chat/ThreadComposer.tsx`<br>`apps/studio/src/lib/commands.ts`<br>`apps/studio/src/lib/useFocusTrap.ts`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/chat/WorkBlock.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/chat/Conversation.tsx`<br>`apps/studio/src/components/chat/WorkBlock.tsx`<br>`apps/studio/src/types.ts`<br>`apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts` |
| `apps/studio/src/components/chat/arrivalCount.test.ts` | `apps/studio/src/components/chat/arrivalCount.ts` |
| `apps/studio/src/components/customize/ConnectorSuggestionModal.test.tsx` | `apps/studio/src/components/customize/ConnectorSuggestionModal.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/customize/CustomizePage.test.tsx` | `apps/studio/src/components/customize/CustomizePage.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/interview/InterviewCard.test.tsx` | `apps/studio/src/components/interview/InterviewCard.tsx`<br>`apps/studio/src/components/interview/types.ts`<br>`apps/studio/src/test/axe.ts` |
| `apps/studio/src/components/interview/answered.test.ts` | `apps/studio/src/components/interview/answered.ts` |
| `apps/studio/src/components/layout/StudioBar.test.tsx` | `apps/studio/src/components/layout/StudioBar.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/components/layout/StudioBar.visual.test.tsx` | `apps/studio/src/components/layout/StudioBar.tsx` |
| `apps/studio/src/components/notifications/CatchUpFeed.test.tsx` | `apps/studio/src/App.tsx`<br>`apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/notifications/CatchUpFeed.tsx`<br>`apps/studio/src/components/notifications/__fixtures__/signals.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/notifications/noFabricatedSignals.test.ts` | — no direct source pair |
| `apps/studio/src/components/records/RecordDetail.test.tsx` | `apps/studio/src/components/records/RecordDetail.tsx`<br>`apps/studio/src/components/records/RecordsPanel.tsx`<br>`apps/studio/src/lib/odi.ts`<br>`apps/studio/src/lib/records.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/records/RecordsPanel.test.tsx` | `apps/studio/src/components/records/RecordsPanel.tsx`<br>`apps/studio/src/lib/odi.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/records/RecordsTable.test.tsx` | `apps/studio/src/components/records/RecordsTable.tsx`<br>`apps/studio/src/lib/odi.ts`<br>`apps/studio/src/lib/records.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/settings/AboutSection.test.tsx` | `apps/studio/src/components/settings/sections/AboutSection.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/components/settings/ConnectionsSection.test.tsx` | `apps/studio/src/components/settings/sections/ConnectionsSection.tsx`<br>`apps/studio/src/components/settings/sections/ModelSection.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/settings/ContextSection.test.tsx` | `apps/studio/src/components/settings/sections/ContextSection.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/settings/DataSection.test.tsx` | `apps/studio/src/components/settings/sections/DataSection.tsx` |
| `apps/studio/src/components/settings/InstallSection.test.tsx` | `apps/studio/src/bridge/runtime.ts`<br>`apps/studio/src/components/settings/sections/InstallSection.tsx`<br>`apps/studio/src/install.ts` |
| `apps/studio/src/components/settings/ModelSection.test.tsx` | `apps/studio/src/components/settings/sections/ModelSection.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/components/settings/SettingsLayout.test.tsx` | `apps/studio/src/components/SettingsPanel.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/components/settings/SettingsPanel.perFieldSave.test.tsx` | `apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/components/SettingsPanel.tsx`<br>`apps/studio/src/onboarding/OnboardingProvider.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/components/settings/UpdatesSection.test.tsx` | `apps/studio/src/components/settings/sections/UpdatesSection.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/components/settings/saves.test.ts` | `apps/studio/src/components/settings/saves.ts`<br>`apps/studio/src/components/settings/validation.ts` |
| `apps/studio/src/components/setup/IntroConversation.test.tsx` | `apps/studio/src/components/setup/IntroConversation.tsx`<br>`apps/studio/src/lib/intro.ts` |
| `apps/studio/src/components/setup/IntroConversation.visual.test.tsx` | `apps/studio/src/components/setup/IntroConversation.tsx` |
| `apps/studio/src/components/status/StatusDot.test.tsx` | `apps/studio/src/components/status/StatusDot.tsx` |
| `apps/studio/src/components/status/StatusDot.visual.test.tsx` | `apps/studio/src/components/icons.tsx`<br>`apps/studio/src/components/status/StatusDot.tsx` |
| `apps/studio/src/components/workspace/WorkbenchRail.test.tsx` | `apps/studio/src/components/workspace/WorkbenchRail.tsx` |
| `apps/studio/src/components/workspace/WorkspacePanel.test.tsx` | `apps/studio/src/components/workspace/WorkspacePanel.tsx` |
| `apps/studio/src/components/workspace/panelContext.test.ts` | `apps/studio/src/components/workspace/panelContext.ts`<br>`apps/studio/src/domain/jobStages.ts` |
| `apps/studio/src/components/workspace/panels.test.tsx` | `apps/studio/src/components/workspace/panels.tsx` |
| `apps/studio/src/diagnostics/DiagnosticsModal.test.tsx` | `apps/studio/src/components/SettingsPanel.tsx`<br>`apps/studio/src/diagnostics/DiagnosticsModal.tsx`<br>`apps/studio/src/onboarding/OnboardingProvider.tsx`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/diagnostics/bundle.test.ts` | `apps/studio/src/diagnostics/bundle.ts` |
| `apps/studio/src/diagnostics/redact.test.ts` | `apps/studio/src/diagnostics/redact.ts` |
| `apps/studio/src/features/flags.test.ts` | `apps/studio/src/features/flags.ts` |
| `apps/studio/src/install.test.ts` | `apps/studio/src/install.ts` |
| `apps/studio/src/lib/blockedReason.test.ts` | `apps/studio/src/lib/blockedReason.ts` |
| `apps/studio/src/lib/boot.test.ts` | `apps/studio/src/lib/boot.ts` |
| `apps/studio/src/lib/brandCopy.test.ts` | `apps/studio/src/lib/brand.ts` |
| `apps/studio/src/lib/brief.test.ts` | `apps/studio/src/lib/brief.ts`<br>`apps/studio/src/lib/export.ts`<br>`apps/studio/src/lib/odi.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/canvasProvenance.test.ts` | `apps/studio/src/lib/canvasProvenance.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/changelogRead.test.ts` | `apps/studio/src/lib/changelogRead.ts` |
| `apps/studio/src/lib/commands.test.ts` | `apps/studio/src/lib/commands.ts` |
| `apps/studio/src/lib/dashboard.test.ts` | `apps/studio/src/lib/dashboard.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/download.test.ts` | `apps/studio/src/lib/download.ts` |
| `apps/studio/src/lib/export.test.ts` | `apps/studio/src/lib/brief.ts`<br>`apps/studio/src/lib/export.ts`<br>`apps/studio/src/types.ts`<br>`apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts` |
| `apps/studio/src/lib/focus.test.ts` | `apps/studio/src/lib/focus.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/formula.test.ts` | — no direct source pair |
| `apps/studio/src/lib/greeting.test.ts` | `apps/studio/src/lib/greeting.ts` |
| `apps/studio/src/lib/guidance.test.ts` | `apps/studio/src/lib/guidance.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/intro.test.ts` | `apps/studio/src/lib/intro.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/modelEndpoint.test.ts` | `apps/studio/src/lib/modelEndpoint.ts` |
| `apps/studio/src/lib/odi.test.ts` | `apps/studio/src/lib/odi.ts` |
| `apps/studio/src/lib/offlinePage.test.ts` | — no direct source pair |
| `apps/studio/src/lib/onlineStatus.test.tsx` | `apps/studio/src/lib/onlineStatus.ts` |
| `apps/studio/src/lib/records.test.ts` | `apps/studio/src/lib/odi.ts`<br>`apps/studio/src/lib/records.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/lib/relativeTime.test.ts` | `apps/studio/src/lib/relativeTime.ts` |
| `apps/studio/src/lib/sampleLoop.test.ts` | `apps/studio/src/lib/odi.ts`<br>`apps/studio/src/lib/sampleLoop.ts` |
| `apps/studio/src/lib/scoreVocabulary.test.ts` | `apps/studio/src/lib/odi.ts`<br>`apps/studio/src/lib/records.ts` |
| `apps/studio/src/lib/session.test.ts` | `apps/studio/src/lib/session.ts` |
| `apps/studio/src/lib/setup.test.ts` | `apps/studio/src/lib/setup.ts` |
| `apps/studio/src/lib/share.test.ts` | `apps/studio/src/lib/share.ts` |
| `apps/studio/src/lib/swRouting.test.ts` | `apps/studio/src/lib/swRouting.ts` |
| `apps/studio/src/lib/swUpdate.test.ts` | `apps/studio/src/lib/swUpdate.ts` |
| `apps/studio/src/lib/theme.test.ts` | `apps/studio/src/lib/theme.ts` |
| `apps/studio/src/lib/themeBootstrap.test.ts` | — no direct source pair |
| `apps/studio/src/lib/useReducedMotion.test.tsx` | `apps/studio/src/lib/useReducedMotion.ts` |
| `apps/studio/src/lib/version.test.ts` | `apps/studio/src/lib/version.ts` |
| `apps/studio/src/lib/windowState.test.ts` | — no direct source pair |
| `apps/studio/src/onboarding/FirstRunWizard.test.tsx` | `apps/studio/src/lib/sampleLoop.ts`<br>`apps/studio/src/onboarding/FirstRunWizard.tsx`<br>`apps/studio/src/onboarding/OnboardingProvider.tsx`<br>`apps/studio/src/onboarding/context.ts`<br>`apps/studio/src/onboarding/storage.ts` |
| `apps/studio/src/onboarding/LandScene.test.tsx` | `apps/studio/src/lib/sampleLoop.ts`<br>`apps/studio/src/onboarding/LandScene.tsx` |
| `apps/studio/src/onboarding/machine.test.ts` | `apps/studio/src/onboarding/machine.ts`<br>`apps/studio/src/onboarding/storage.ts` |
| `apps/studio/src/onboarding/sampleCleanup.test.ts` | `apps/studio/src/lib/sampleLoop.ts`<br>`apps/studio/src/onboarding/sampleCleanup.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/state/StudioContext.test.tsx` | `apps/studio/src/assistant/queue.ts`<br>`apps/studio/src/bff/index.ts`<br>`apps/studio/src/lib/session.ts`<br>`apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/state/notices/NoticesContext.tsx`<br>`apps/studio/src/state/scheduleProbe.ts`<br>`apps/studio/src/state/settings/SettingsContext.tsx`<br>`apps/studio/src/test/renderCounts.tsx` |
| `apps/studio/src/state/canvas/CanvasContext.test.tsx` | `apps/studio/src/state/canvas/CanvasContext.tsx`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/state/deviceStatus.test.ts` | `apps/studio/src/bff/capabilities/registry.ts`<br>`apps/studio/src/state/deviceStatus.ts` |
| `apps/studio/src/state/probeBreaker.test.ts` | `apps/studio/src/api/studioApi.ts`<br>`apps/studio/src/state/probeBreaker.ts`<br>`apps/studio/src/types.ts` |
| `apps/studio/src/state/regions.test.ts` | `apps/studio/src/state/regions.ts` |
| `apps/studio/src/state/scheduleProbe.test.ts` | `apps/studio/src/state/scheduleProbe.ts` |
| `apps/studio/src/state/settings/SettingsContext.test.ts` | `apps/studio/src/state/settings/SettingsContext.tsx` |
| `apps/studio/src/styles/bootShell.test.ts` | — no direct source pair |
| `apps/studio/src/styles/brief.test.ts` | — no direct source pair |
| `apps/studio/src/styles/colors.test.ts` | — no direct source pair |
| `apps/studio/src/styles/mainstage.test.ts` | — no direct source pair |
| `apps/studio/src/styles/motion.test.ts` | — no direct source pair |
| `apps/studio/src/styles/print.test.ts` | — no direct source pair |
| `apps/studio/src/styles/theme.test.ts` | — no direct source pair |
| `apps/studio/src/styles/tokens.test.ts` | — no direct source pair |
| `apps/studio/src/test/a11y.test.tsx` | `apps/studio/src/assistant/StudioRuntime.tsx`<br>`apps/studio/src/components/ChangelogModal.tsx`<br>`apps/studio/src/components/SettingsPanel.tsx`<br>`apps/studio/src/components/brief/BriefLens.tsx`<br>`apps/studio/src/components/canvas/JobMap.tsx`<br>`apps/studio/src/components/canvas/OpportunityLandscape.tsx`<br>`apps/studio/src/components/chat/ChatStage.tsx`<br>`apps/studio/src/components/chat/Composer.tsx`<br>`apps/studio/src/components/notifications/CatchUpFeed.tsx`<br>`apps/studio/src/onboarding/FirstRunWizard.tsx`<br>`apps/studio/src/onboarding/OnboardingProvider.tsx`<br>`apps/studio/src/onboarding/context.ts`<br>`apps/studio/src/test/axe.ts`<br>`apps/studio/src/types.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/test/contrast.test.ts` | `apps/studio/src/test/contrast.ts` |
| `apps/studio/src/test/e2eQuarantine.test.ts` | `apps/studio/e2e/quarantine.ts` |
| `apps/studio/src/test/keyboard.test.tsx` | `apps/studio/src/App.tsx`<br>`apps/studio/src/lib/useFocusTrap.ts` |
| `apps/studio/src/test/renderCounts.test.tsx` | `apps/studio/src/state/StudioContext.tsx`<br>`apps/studio/src/state/notices/NoticesContext.tsx`<br>`apps/studio/src/state/settings/SettingsContext.tsx`<br>`apps/studio/src/test/renderCounts.tsx` |
| `apps/studio/src/ui/UiRenderer.test.tsx` | `apps/studio/src/ui/UiRenderer.tsx`<br>`apps/studio/src/ui/actions.ts`<br>`apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts`<br>`apps/studio/src/ui/registry.ts` |
| `apps/studio/src/ui/protocol.test.ts` | `apps/studio/src/ui/catalog.ts`<br>`apps/studio/src/ui/protocol.ts` |
| `apps/studio/src/updater/UpdateBanner.test.tsx` | `apps/studio/src/updater/UpdateBanner.tsx`<br>`apps/studio/src/updater/UpdateProvider.tsx`<br>`apps/studio/src/updater/service.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/updater/UpdateSettings.test.tsx` | `apps/studio/src/updater/UpdateProvider.tsx`<br>`apps/studio/src/updater/UpdateSettings.tsx`<br>`apps/studio/src/updater/service.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/updater/machine.test.ts` | `apps/studio/src/updater/machine.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/updater/service.test.ts` | `apps/studio/src/updater/service.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/updater/transport.test.ts` | `apps/studio/src/updater/transport.ts`<br>`apps/studio/src/updater/types.ts` |
| `apps/studio/src/vendor/boundary.test.ts` | `apps/studio/src/assistant/plan.ts`<br>`apps/studio/src/vendor/boundary.ts`<br>`apps/studio/src/vendor/lib/utils.ts` |
| `apps/studio/src/vendor/components/ui/dialog.test.tsx` | `apps/studio/src/vendor/components/ui/dialog.tsx` |
| `apps/studio/src/vendor/ledger.test.ts` | — no direct source pair |
| `apps/studio/src/vendor/vendor.test.tsx` | — no direct source pair |
| `apps/studio-api/tests/test_api.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/studio-api/tests/test_app_spa.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/main.py`<br>`packages/core/src/agentic_odi_core/messages.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/studio-api/tests/test_boot_integrity.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/intent_store.py` |
| `apps/studio-api/tests/test_capability_routes.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_probe_cache.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/probes.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py` |
| `apps/studio-api/tests/test_studio_alternatives.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_api.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/secrets.py` |
| `apps/studio-api/tests/test_studio_approvals.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/approvals.py` |
| `apps/studio-api/tests/test_studio_auth.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_brief.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` |
| `apps/studio-api/tests/test_studio_capabilities.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_chat_branches.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/connectors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` |
| `apps/studio-api/tests/test_studio_chat_prompt.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py` |
| `apps/studio-api/tests/test_studio_chat_stream.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/approvals.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py`<br>`packages/core/src/agentic_odi_core/contract.py` |
| `apps/studio-api/tests/test_studio_chat_ui.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` |
| `apps/studio-api/tests/test_studio_claims.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/claims.py` |
| `apps/studio-api/tests/test_studio_connectors.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/connectors.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/registry.py` |
| `apps/studio-api/tests/test_studio_connectors_router.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/connectors.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py` |
| `apps/studio-api/tests/test_studio_conversations.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/claims.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py` |
| `apps/studio-api/tests/test_studio_csp.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/studio-api/tests/test_studio_data_status.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/studio-api/tests/test_studio_diagnostics.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/studio-api/tests/test_studio_error_status_map.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`packages/core/src/agentic_odi_core/remote.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/studio-api/tests/test_studio_errors.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`packages/core/src/agentic_odi_core/remote.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `apps/studio-api/tests/test_studio_evidence.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_focus.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/schemas.py` |
| `apps/studio-api/tests/test_studio_funnel.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`<br>`packages/core/src/agentic_odi_core/events.py`<br>`packages/core/src/agentic_odi_core/funnel.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `apps/studio-api/tests/test_studio_llm_proxy.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_manual_crud.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_marketplace.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/connectors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/marketplace.py`<br>`packages/connectors/src/agentic_odi_connectors/marketplace.py` |
| `apps/studio-api/tests/test_studio_mcp_data.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/mcp_data.py` |
| `apps/studio-api/tests/test_studio_memory.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`packages/core/src/agentic_odi_core/migrations.py` |
| `apps/studio-api/tests/test_studio_model_router.py` | — no direct source pair |
| `apps/studio-api/tests/test_studio_models.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/probes.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py` |
| `apps/studio-api/tests/test_studio_observability.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/observability.py` |
| `apps/studio-api/tests/test_studio_outcome_evidence_crud.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_paths.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/paths.py` |
| `apps/studio-api/tests/test_studio_probes.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/probes.py` |
| `apps/studio-api/tests/test_studio_proposals.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_router.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py`<br>`packages/core/src/agentic_odi_core/remote.py` |
| `apps/studio-api/tests/test_studio_secrets.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/secrets.py` |
| `apps/studio-api/tests/test_studio_segments.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py`<br>`packages/core/src/agentic_odi_core/remote.py` |
| `apps/studio-api/tests/test_studio_sharing.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/sharing.py` |
| `apps/studio-api/tests/test_studio_signals.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/errors.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py`<br>`packages/core/src/agentic_odi_core/remote.py` |
| `apps/studio-api/tests/test_studio_studies.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py`<br>`apps/studio-api/src/agentic_odi_studio_api/studio/router.py` |
| `apps/studio-api/tests/test_studio_traceability.py` | `apps/studio-api/src/agentic_odi_studio_api/app.py` |
| `apps/studio-api/tests/test_studio_ui_spec.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/ui_spec.py` |
| `brand/tests/test_brand_assets.py` | — no direct source pair |
| `brand/tests/test_generated_sources.py` | — no direct source pair |
| `packages/connectors/tests/test_catalog.py` | `packages/connectors/src/agentic_odi_connectors/catalog.py`<br>`packages/connectors/src/agentic_odi_connectors/factory.py`<br>`packages/connectors/src/agentic_odi_connectors/protocol.py`<br>`packages/connectors/src/agentic_odi_connectors/registry.py` |
| `packages/connectors/tests/test_config_path.py` | `packages/connectors/src/agentic_odi_connectors/paths.py` |
| `packages/connectors/tests/test_config_validation.py` | — no direct source pair |
| `packages/connectors/tests/test_evidence_equivalence.py` | `packages/connectors/src/agentic_odi_connectors/mapping.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/core/src/agentic_odi_core/models.py` |
| `packages/connectors/tests/test_factory.py` | `packages/connectors/src/agentic_odi_connectors/factory.py`<br>`packages/connectors/src/agentic_odi_connectors/mcp/connector.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/protocol.py`<br>`packages/connectors/src/agentic_odi_connectors/registry.py`<br>`packages/connectors/src/agentic_odi_connectors/rest/connector.py` |
| `packages/connectors/tests/test_http_client.py` | — no direct source pair |
| `packages/connectors/tests/test_http_client_lifecycle.py` | — no direct source pair |
| `packages/connectors/tests/test_mapping.py` | `packages/connectors/src/agentic_odi_connectors/mapping.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py` |
| `packages/connectors/tests/test_marketplace.py` | `packages/connectors/src/agentic_odi_connectors/catalog.py`<br>`packages/connectors/src/agentic_odi_connectors/marketplace.py` |
| `packages/connectors/tests/test_mcp_connector.py` | `packages/connectors/src/agentic_odi_connectors/mcp/connector.py`<br>`packages/connectors/src/agentic_odi_connectors/models.py` |
| `packages/connectors/tests/test_no_prints.py` | `packages/connectors/src/agentic_odi_connectors/paths.py` |
| `packages/connectors/tests/test_rate_limit.py` | `packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/rate_limit.py` |
| `packages/connectors/tests/test_registry.py` | `packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/registry.py` |
| `packages/connectors/tests/test_rest_connector.py` | `packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/protocol.py`<br>`packages/connectors/src/agentic_odi_connectors/rest/connector.py` |
| `packages/connectors/tests/test_sink.py` | `packages/connectors/src/agentic_odi_connectors/models.py`<br>`packages/connectors/src/agentic_odi_connectors/rate_limit.py`<br>`packages/connectors/src/agentic_odi_connectors/sink.py` |
| `packages/core/tests/test_alternatives.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_alternatives_presentation.py` | — no direct source pair |
| `packages/core/tests/test_candidate_decision.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/review.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/spine_extraction.py` |
| `packages/core/tests/test_capability_manifest.py` | `packages/core/src/agentic_odi_core/contract.py` |
| `packages/core/tests/test_claim_check.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_claim_interview.py` | `packages/core/src/agentic_odi_core/evaluation.py`<br>`packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_connection.py` | `packages/core/src/agentic_odi_core/connection.py`<br>`packages/core/src/agentic_odi_core/errors.py` |
| `packages/core/tests/test_consent_pause.py` | `packages/core/src/agentic_odi_core/consent.py`<br>`packages/core/src/agentic_odi_core/contract.py`<br>`packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `packages/core/tests/test_default_db_path.py` | `packages/core/src/agentic_odi_core/paths.py` |
| `packages/core/tests/test_demo.py` | `packages/core/src/agentic_odi_core/demo.py`<br>`packages/core/src/agentic_odi_core/evaluation.py`<br>`packages/core/src/agentic_odi_core/factory.py` |
| `packages/core/tests/test_errors.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_evaluation.py` | `packages/core/src/agentic_odi_core/evaluation.py` |
| `packages/core/tests/test_evaluation_harness.py` | `packages/core/src/agentic_odi_core/evaluation.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_events.py` | `packages/core/src/agentic_odi_core/intent_store.py` |
| `packages/core/tests/test_evidence_not_found.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_extraction.py` | `packages/core/src/agentic_odi_core/extraction.py`<br>`packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_funnel.py` | `packages/core/src/agentic_odi_core/events.py`<br>`packages/core/src/agentic_odi_core/funnel.py`<br>`packages/core/src/agentic_odi_core/intent_store.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_funnel_service.py` | `packages/core/src/agentic_odi_core/funnel.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_intent_store.py` | `packages/core/src/agentic_odi_core/intent_store.py` |
| `packages/core/tests/test_interview.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py`<br>`packages/core/src/agentic_odi_core/transcript.py` |
| `packages/core/tests/test_job_validation.py` | `packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_logging.py` | `packages/core/src/agentic_odi_core/logging.py` |
| `packages/core/tests/test_messages.py` | `packages/core/src/agentic_odi_core/contract.py`<br>`packages/core/src/agentic_odi_core/messages.py` |
| `packages/core/tests/test_migrations.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/intent_store.py`<br>`packages/core/src/agentic_odi_core/migrations.py` |
| `packages/core/tests/test_models.py` | `packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_n_advisory.py` | `packages/core/src/agentic_odi_core/evaluation.py`<br>`packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_opportunity_ranking.py` | `packages/core/src/agentic_odi_core/evaluation.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_opportunity_score.py` | `packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_outcome_mapping.py` | `packages/core/src/agentic_odi_core/evaluation.py`<br>`packages/core/src/agentic_odi_core/mapping.py`<br>`packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_outcome_method.py` | `packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_outcome_trace_write.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/traceability.py` |
| `packages/core/tests/test_outcome_validation.py` | `packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_pagination.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_perf_cold_open.py` | `packages/core/src/agentic_odi_core/corpus.py`<br>`packages/core/src/agentic_odi_core/intent_store.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_persistence_parity.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_promotion_identity.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_proposals.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/factory.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_recovery.py` | `packages/core/src/agentic_odi_core/recovery.py` |
| `packages/core/tests/test_remote.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/remote.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_repository.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py` |
| `packages/core/tests/test_repository_factory.py` | `packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_repository_health.py` | `packages/core/src/agentic_odi_core/factory.py` |
| `packages/core/tests/test_review.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/evaluation.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/review.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/spine_extraction.py` |
| `packages/core/tests/test_router.py` | `packages/core/src/agentic_odi_core/router.py`<br>`packages/core/src/agentic_odi_core/steve_jobs.py` |
| `packages/core/tests/test_schedule.py` | `packages/core/src/agentic_odi_core/schedule.py` |
| `packages/core/tests/test_scheduled_work.py` | — no direct source pair |
| `packages/core/tests/test_schema.py` | `packages/core/src/agentic_odi_core/schema.py` |
| `packages/core/tests/test_schema_version.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/intent_store.py`<br>`packages/core/src/agentic_odi_core/migrations.py` |
| `packages/core/tests/test_score_history.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_segmentation.py` | `packages/core/src/agentic_odi_core/segmentation.py` |
| `packages/core/tests/test_segments_service.py` | `packages/core/src/agentic_odi_core/errors.py` |
| `packages/core/tests/test_segments_staleness.py` | `packages/core/src/agentic_odi_core/freshness.py`<br>`packages/core/src/agentic_odi_core/models.py` |
| `packages/core/tests/test_service.py` | `packages/core/src/agentic_odi_core/evaluation.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_signal_inbox.py` | `packages/core/src/agentic_odi_core/services.py` |
| `packages/core/tests/test_similarity.py` | `packages/core/src/agentic_odi_core/similarity.py` |
| `packages/core/tests/test_spine.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/schema.py`<br>`packages/core/src/agentic_odi_core/spine.py` |
| `packages/core/tests/test_spine_end_to_end.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/spine.py` |
| `packages/core/tests/test_spine_extraction.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/spine_extraction.py` |
| `packages/core/tests/test_spine_similarity.py` | `packages/core/src/agentic_odi_core/spine_similarity.py` |
| `packages/core/tests/test_spine_stages.py` | `packages/core/src/agentic_odi_core/factory.py`<br>`packages/core/src/agentic_odi_core/spine_stages.py` |
| `packages/core/tests/test_sqlite_integrity.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/integrity.py`<br>`packages/core/src/agentic_odi_core/intent_store.py`<br>`packages/core/src/agentic_odi_core/recovery.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_sqlite_repository.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/intent_store.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_stats.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/stats.py` |
| `packages/core/tests/test_steve_jobs.py` | `packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/steve_jobs.py` |
| `packages/core/tests/test_strategy.py` | `packages/core/src/agentic_odi_core/strategy.py` |
| `packages/core/tests/test_study.py` | `packages/core/src/agentic_odi_core/contract.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/schema.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py` |
| `packages/core/tests/test_survey.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/survey.py` |
| `packages/core/tests/test_survey_input_retention.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py`<br>`packages/core/src/agentic_odi_core/stats.py`<br>`packages/core/src/agentic_odi_core/trust.py` |
| `packages/core/tests/test_traceability.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py`<br>`packages/core/src/agentic_odi_core/traceability.py` |
| `packages/core/tests/test_transcript.py` | `packages/core/src/agentic_odi_core/transcript.py` |
| `packages/core/tests/test_trust_pillar.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py`<br>`packages/core/src/agentic_odi_core/stats.py` |
| `packages/core/tests/test_trust_seams.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/models.py`<br>`packages/core/src/agentic_odi_core/trust.py` |
| `packages/core/tests/test_trust_service.py` | `packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `tests/contract/test_cli_contract.py` | `apps/cli/src/agentic_odi_cli/backend.py`<br>`packages/core/src/agentic_odi_core/contract.py` |
| `tests/contract/test_contract_snapshot.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`<br>`packages/core/src/agentic_odi_core/contract.py`<br>`packages/core/src/agentic_odi_core/schema.py` |
| `tests/contract/test_contract_snapshot_drift.py` | `packages/core/src/agentic_odi_core/contract.py`<br>`packages/core/src/agentic_odi_core/schema.py` |
| `tests/contract/test_mcp_contract.py` | `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`<br>`packages/core/src/agentic_odi_core/contract.py`<br>`packages/core/src/agentic_odi_core/errors.py`<br>`packages/core/src/agentic_odi_core/remote.py`<br>`packages/core/src/agentic_odi_core/repository.py`<br>`packages/core/src/agentic_odi_core/services.py` |
| `tests/contract/test_no_unregistered_gitlinks.py` | — no direct source pair |
| `tests/contract/test_protected_files.py` | — no direct source pair |
| `tests/e2e/__init__.py` | — no direct source pair |
| `tests/e2e/test_spine.py` | `packages/core/src/agentic_odi_core/factory.py` |
| `tests/scripts/test_artifact_a11y.py` | `scripts/artifact_a11y.py` |
| `tests/scripts/test_artifact_inventory.py` | `scripts/artifact_renderers.py` |
| `tests/scripts/test_assistant_ui_ledger.py` | `scripts/doc_check.py` |
| `tests/scripts/test_audit_ignore.py` | `scripts/audit_ignore.py` |
| `tests/scripts/test_blind_excepts.py` | — no direct source pair |
| `tests/scripts/test_bundle_budget.py` | — no direct source pair |
| `tests/scripts/test_ci_release.py` | `scripts/ci_release.py` |
| `tests/scripts/test_cli_docs.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `tests/scripts/test_coverage_floor.py` | `scripts/coverage_floor.py` |
| `tests/scripts/test_coverage_map.py` | `scripts/coverage_map.py` |
| `tests/scripts/test_dev.py` | `scripts/dev.py` |
| `tests/scripts/test_dev_main.py` | — no direct source pair |
| `tests/scripts/test_doc_check.py` | `scripts/doc_check.py` |
| `tests/scripts/test_doc_churn.py` | `scripts/doc_churn.py` |
| `tests/scripts/test_docs_index.py` | `scripts/docs_index.py` |
| `tests/scripts/test_gen_corpus.py` | `packages/core/src/agentic_odi_core/corpus.py`<br>`packages/core/src/agentic_odi_core/sqlite_repository.py`<br>`scripts/gen_corpus.py` |
| `tests/scripts/test_gen_job_stages.py` | `scripts/gen_job_stages.py` |
| `tests/scripts/test_hosted_first_run_workflow.py` | — no direct source pair |
| `tests/scripts/test_label_merge_conflicts.py` | `scripts/pr_labels.py` |
| `tests/scripts/test_migrations_registry.py` | `apps/studio-api/src/agentic_odi_studio_api/studio/memory.py`<br>`packages/core/src/agentic_odi_core/migrations.py` |
| `tests/scripts/test_pr_ai_authorize.py` | `scripts/pr_ai_authorize.py` |
| `tests/scripts/test_pr_ai_merge.py` | `scripts/pr_ai_merge.py` |
| `tests/scripts/test_pr_ai_merge_act.py` | — no direct source pair |
| `tests/scripts/test_pr_ai_merge_workflow.py` | — no direct source pair |
| `tests/scripts/test_pr_body_gate.py` | — no direct source pair |
| `tests/scripts/test_pr_guards.py` | `scripts/pr_guards.py` |
| `tests/scripts/test_pr_labeler_workflow.py` | — no direct source pair |
| `tests/scripts/test_pr_labels.py` | `scripts/pr_labels.py`<br>`scripts/pr_provenance.py` |
| `tests/scripts/test_pr_provenance.py` | `scripts/pr_provenance.py` |
| `tests/scripts/test_pr_sweep.py` | `scripts/pr_sweep.py` |
| `tests/scripts/test_pr_sweep_workflow.py` | — no direct source pair |
| `tests/scripts/test_pr_triage.py` | `scripts/pr_triage.py` |
| `tests/scripts/test_release_assets.py` | `scripts/release_assets.py` |
| `tests/scripts/test_release_instructions.py` | `scripts/release_instructions.py` |
| `tests/scripts/test_release_version_gate.py` | — no direct source pair |
| `tests/scripts/test_release_workflow.py` | — no direct source pair |
| `tests/scripts/test_settings_registry.py` | `packages/core/src/agentic_odi_core/settings.py` |
| `tests/scripts/test_updater_proof_gate.py` | — no direct source pair |
| `tests/scripts/test_vendor_policy.py` | `scripts/vendor_policy.py` |
| `tests/scripts/test_verify.py` | `scripts/verify.py` |
| `tests/scripts/test_verify_ci_parity.py` | `scripts/verify.py` |
| `tests/scripts/test_verify_hosted_first_run.py` | — no direct source pair |
| `tests/scripts/test_version_sync.py` | `apps/cli/src/agentic_odi_cli/_build_info.py`<br>`scripts/check_version_parity.py` |
| `tests/scripts/test_workflow_triggers.py` | — no direct source pair |
| `tests/test_adr_index.py` | — no direct source pair |
| `tests/test_architecture.py` | — no direct source pair |
| `tests/test_dev_entrypoint.py` | — no direct source pair |
| `tests/test_docs_code_overview.py` | — no direct source pair |
| `tests/test_docs_method.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `tests/test_guide_commands.py` | `apps/cli/src/agentic_odi_cli/cli.py` |
| `tests/test_integration_example.py` | `packages/core/src/agentic_odi_core/contract.py` |
| `tests/test_score_tolerance_parity.py` | `packages/core/src/agentic_odi_core/models.py` |
| `tests/test_timeout_ceiling.py` | — no direct source pair |
| `tests/test_tour.py` | `scripts/tour.py` |
| `tests/test_underserved_threshold_parity.py` | `packages/core/src/agentic_odi_core/evaluation.py` |
| `tests/test_worker_build_route.py` | — no direct source pair |
| `tests/test_worker_capabilities_route.py` | — no direct source pair |
| `tests/test_worker_csp_rationale.py` | — no direct source pair |
| `tests/test_worker_deploy_route.py` | — no direct source pair |
| `tests/test_worker_error_origin.py` | — no direct source pair |
| `tests/test_worker_error_shape.py` | — no direct source pair |
| `tests/test_worker_header_forwarding.py` | — no direct source pair |
| `tests/test_worker_security_headers.py` | — no direct source pair |
| `website/tests/site_support.py` | `website/tools/build_site.py` |
| `website/tests/test_ci_required.py` | — no direct source pair |
| `website/tests/test_content_sync.py` | `website/tools/build_sample.py`<br>`website/tools/extract.py` |
| `website/tests/test_design_system.py` | `website/tools/extract.py` |
| `website/tests/test_docs_render.py` | `scripts/artifact_a11y.py`<br>`website/tools/build_site.py`<br>`website/tools/markdown_render.py` |
| `website/tests/test_generated.py` | `website/tools/build_site.py`<br>`website/tools/extract.py` |
| `website/tests/test_make_og.py` | `website/tools/make_og.py` |
| `website/tests/test_og_pages.py` | `website/tools/build_site.py`<br>`website/tools/make_og.py` |
| `website/tests/test_pages_deploy.py` | — no direct source pair |
| `website/tests/test_site.py` | `scripts/artifact_a11y.py`<br>`website/tools/extract.py` |
| `website/tests/test_theme.py` | — no direct source pair |
<!-- coverage-map:end -->

> [!TIP]
> Type `/test` in the AI assistant to have the agent run all tests and report the
> results automatically.

## Store schema version

The SQLite event store stamps its own file-format version in a `schema_meta`
table on open. The constants live in
`packages/core/src/agentic_odi_core/intent_store.py`:

- `CURRENT_SCHEMA_VERSION` — the format this build writes. It starts at `1`.
- `MIGRATIONS` — a `dict[int, Callable]` keyed by the version it produces;
  `MIGRATIONS[n]` upgrades a store from `n - 1` to `n`.

`IntentStore.ensure_version()` runs on every open:

- A current-version store is left untouched (no migration, no version write).
- An unstamped (legacy) store is stamped `v1` once, then migrated forward.
- Migrations run **in order inside one transaction**. A step that raises rolls
  back its data *and* schema changes together with the version stamp, so a
  half-migrated event log can never be left behind.
- A store written by a newer build is refused with both versions named and the
  `odi update` upgrade command, and the file is left byte-for-byte unchanged.

Bump `CURRENT_SCHEMA_VERSION` **only** when you register a migration. An
additive field that needs no data change must not bump it.

## Contract drift snapshot

`tests/contract/test_contract_snapshot.py` pins three surfaces together so an
accidental change fails CI instead of a customer: `contract.TOOL_SPECS`, the
live FastMCP registry's input schemas, and `schema.odi_schema()`.

When you make a **deliberate** change to any of those, regenerate the snapshot
locally, then review the diff like code before committing:

```bash
uv run pytest tests/contract/test_contract_snapshot.py --inline-snapshot=fix
```

CI never accepts a snapshot automatically; drift fails the build. A newly
accepted snapshot is not proof of backward compatibility — an intentional
breaking change needs its own compatibility decision.

## The ninety-second tour

`docs/tour/README.md` and `docs/tour/tour.cast` are generated, never hand-edited.
Regenerate them in one command after a change that affects the walkthrough:

```bash
uv run python scripts/tour.py
```

`scripts/tour.py` executes every command in `docs/tour/script.md` against a
disposable store, so a command that no longer runs fails the build rather than
rotting in prose. `tests/test_tour.py` fails if the committed artifacts differ
from a fresh run, if the walkthrough exceeds the ninety-second budget, or if a
documented command cannot be executed.

## Agent Session Tracking

Agent sessions are captured with the [Entire](https://docs.entire.io/overview)
CLI. The repository integration lives in `.entire/settings.json`,
`.cursor/hooks.json`, and `.opencode/plugins/entire.ts`. Run `entire status` to
confirm it is enabled and `entire checkpoint list` to inspect captured
checkpoints.
