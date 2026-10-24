# Deployment

## Project Site (GitHub Pages)

The static site in `website/` is published to
**[https://alehar9320.github.io/agentic-odi/](https://alehar9320.github.io/agentic-odi/)**
by [`.github/workflows/pages.yml`](../.github/workflows/pages.yml).

- A push to `main` runs the website tests, builds `_site` from `website/`, and
  deploys the artifact with `actions/deploy-pages`.
- No site build output is committed; CI generates `_site` on every push.
- `workflow_dispatch` republishes the site from the Actions tab without a code
  change.
- Pages is configured with the "GitHub Actions" source, so there is no
  `gh-pages` branch. Removing `pages.yml` stops all publishing and the site
  returns 404.
- The `github-pages` environment only allows deployments from `main`.

## Hosted MCP Server

The server is deployed via **[Horizon Prefect](https://www.prefect.io/horizon)**,
Prefect's managed infrastructure for hosting MCP-compatible agents.

## Test Chat (UI)

Interact with the deployed agent directly in your browser:

> **[https://horizon.prefect.io/alhase/servers/agentic-odi/chat](https://horizon.prefect.io/alhase/servers/agentic-odi/chat)**

## MCP Server Endpoint

Integrate via the MCP protocol at:

> **[https://agentic-odi.fastmcp.app/mcp](https://agentic-odi.fastmcp.app/mcp)**

> [!IMPORTANT]
> **Authentication is required** to access the MCP server endpoint. Please reach
> out to the maintainers to obtain the necessary credentials before connecting a
> client.

## Hosted Studio

The Living Studio SPA is deployed to Cloudflare Workers:

| Environment | URL |
|---|---|
| Production (`main`) | **[https://agentic-odi.alehar.workers.dev/](https://agentic-odi.alehar.workers.dev/)** |
| Pull request preview | Posted automatically by Cloudflare Workers Builds as a PR comment |

Production deploys on every push to `main`. The Worker is `agentic-odi`; keep
`name` in `wrangler.jsonc` aligned with the Worker connected in the dashboard.
Preview builds run for non-production branches and are ephemeral: the Cloudflare
PR comment is the source of truth, so do not copy a preview URL into docs. The
hosted UI loads without a backend; canvas data, chat, and mutations need the
sidecar tunnel described below.

## Component Visual Review (Chromatic)

Every `*.visual.test.tsx` file in `apps/studio` renders one component state in a
real Chromium browser. The `Chromatic` workflow
([`.github/workflows/chromatic.yml`](../.github/workflows/chromatic.yml)) runs
those tests on every branch push and publishes the snapshots to
**[Chromatic](https://www.chromatic.com/)**. Reviewers compare the pixels,
approve or reject the change in Chromatic, and the approved build becomes the
baseline for the next comparison.

### Project setup

The project is linked to `alehar9320/agentic-odi` (app id
`6add05ad03e0b1f6aeda07ad`), and the **`CHROMATIC_PROJECT_TOKEN`** repository
secret holds its project token, so the workflow publishes with no manual step.
The first build, published from the CLI, holds the two `FailurePanel`
snapshots:
[build 1](https://www.chromatic.com/build?appId=6add05ad03e0b1f6aeda07ad&number=1).

To rotate the token, generate a new one in **Manage → Project token** and run
`gh secret set CHROMATIC_PROJECT_TOKEN`. No code change is involved.

### What CI does

| Event | Result |
|---|---|
| Push to any branch | Captures the component states, publishes a build, reports its status against that commit |
| Push to `main` | Same, and `chromatic.config.json` auto-accepts, so `main` becomes the baseline |
| Push from Dependabot | Captures snapshots, skips the upload with a notice: Dependabot runs cannot read repository secrets |
| Pull request from a fork | No build; the workflow runs in this repository and never sees a fork branch |
| Missing token in any other run | The job fails rather than passing without publishing |

The workflow triggers on `push` rather than `pull_request`, which is
Chromatic's recommendation: GitHub builds pull_request runs from an ephemeral
merge commit, so the diff would include everything merged into `main` since the
branch point. Chromatic still reports its **UI Tests** status on the pull
request that contains the commit.

To stop a visual change from merging before someone looks at it, add **Visual
tests (Chromatic)** and Chromatic's **UI Tests** to the required status checks
for `main` (Settings → Rules → Rulesets). Unreviewed changes then keep the pull
request red until they are approved in Chromatic.

> [!NOTE]
> `apps/studio/package.json` overrides the transitive `storybook` version that
> `@chromatic-com/vitest` pins, to a release without the dev-server advisory that
> `npm audit` reports as critical. This project never runs a Storybook dev
> server; the override only patches the archive build Chromatic does internally.
> Revisit it when the plugin adopts a newer Storybook.

### Staying inside the free plan

Chromatic bills `tests × builds × browsers × viewports`, and the free plan
includes **5,000 billed snapshots per month** with Chrome only. Three deliberate
choices keep this project far below that ceiling:

| Choice | Where | Why |
|---|---|---|
| Browser mode only picks up `*.visual.test.tsx` | `apps/studio/vitest.visual.config.ts` | The 29 jsdom unit tests never bill a snapshot; adding a component to visual review is one explicit new file. |
| One Chromium instance, one viewport | same file | No browser or viewport matrix multiplying each test. |
| Animations paused at their end frame | same file (`pauseAnimationAtEnd`) | Shimmer and fade-in components do not diff on capture timing. |

Today that is **2 snapshots per build**, one build per branch push, so the
monthly allowance would cover ~2,500 builds. A component added to visual review
costs one snapshot per state per build, so keep new files focused on the states
that matter rather than every prop permutation.

`apps/studio/chromatic.config.json` auto-accepts changes on `main` (so the
default branch updates its baseline without a manual review) and exits zero on
visual changes elsewhere, so the job itself reports success while the review
lands in Chromatic's **UI Tests** check. Rendering errors still fail the job.

### Commands

```bash
# Capture archives; needs Chromium locally (npx playwright install chromium)
npm --prefix apps/studio run test:visual

# Upload the archives captured above
CHROMATIC_PROJECT_TOKEN=... npm --prefix apps/studio run chromatic
```

### Adding a component

1. Create `apps/studio/src/components/<Name>.visual.test.tsx`.
2. Render the state you want reviewed, importing `../styles/theme.css` so the
   snapshot uses the real theme.
3. Call `configure({ title: "<Name>" })` from `@chromatic-com/vitest` if the
   derived name is not the component name.
4. Add one test per state worth reviewing. Automatic snapshots are captured at
   the end of each test; use `takeSnapshot("name")` for a mid-test state.

## Living Studio on a Free Cloudflare Worker

Workers Containers — the only way to run the Python sidecar entirely on
Cloudflare — requires the Workers Paid plan. On the free plan, the Worker serves
the built SPA as Workers Static Assets and proxies `/api/*` to the sidecar
through a free, account-less
[Cloudflare Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

`wrangler.jsonc` publishes `apps/studio/dist` with SPA fallback and runs the Worker
first for `/api/*`; `infra/cloudflare/worker.ts` forwards those calls to the
`SIDECAR_URL` secret. The browser only talks to the Worker origin, so the
sidecar's CORS list is not involved.

```bash
# 1. Build the SPA that the Worker uploads as static assets
npm --prefix apps/studio ci
npm --prefix apps/studio run build

# 2. Terminal A — MCP server (:8000) + sidecar (:8100)
python scripts/dev.py

# 3. Terminal B — free public URL for the sidecar (no account required)
cloudflared tunnel --url http://127.0.0.1:8100
# copy the https://<random>.trycloudflare.com URL it prints

# 4. Store the URL on the Worker, then deploy
npx wrangler secret put SIDECAR_URL   # paste the trycloudflare URL
npx wrangler deploy
```

Workers Builds settings (Workers & Pages → your Worker → Settings → Builds):

| Setting | Value |
|---|---|
| Production branch | `main` |
| Root directory | `/` |
| Build command | `npm --prefix apps/studio ci && npm --prefix apps/studio run build` |
| Deploy command | `npx wrangler deploy` |
| Preview command | `npx wrangler preview` |

A Worker has no run command: the Worker script runs on Cloudflare. Set `name` in
`wrangler.jsonc` to the Worker you created before the first deploy.

### Pull request previews

Workers Builds posts the build status and Preview URL to the pull request
automatically. To enable it:

1. Open the Worker → **Settings** → **Build** → **Branch control**.
2. Keep the production branch set to `main` and enable **Preview Builds**.
3. If Cloudflare shows **Set up Worker Previews**, complete the one-time switch.
   This cannot be reversed.
4. Confirm the Preview command is `npx wrangler preview`.

`wrangler.jsonc` must keep a `previews` block, even an empty one: the
`wrangler preview` command fails the build with "Your Wrangler configuration is
missing a `previews` block" without it. Assets and compatibility settings stay
at the top level, so `"previews": {}` is enough while Previews need no extra
settings. If a future Preview needs vars or bindings, add them under `previews`
with Preview-safe values.

Previews do not inherit production settings. The SPA loads from a Preview, but
`/api/*` returns `502 SIDECAR_URL is not configured` until a preview-specific
`SIDECAR_URL` secret is configured:

```bash
npx wrangler preview secret put SIDECAR_URL --name <branch>
```

When `--name` is omitted it defaults to the current git branch. Previews are
ephemeral, and pull requests from forks may not receive one. If Cloudflare does
not comment, paste the URL into the PR's **Deployment** section.

The `cf` CLI can inspect build triggers and recent builds (`cf builds triggers
list`, `cf builds list`) and create a Preview (`cf previews deploy`), but it does
not post GitHub PR comments. The Workers Builds Git integration owns the PR link;
`cf` is only an optional verification tool and requires `cf auth login`.

> [!NOTE]
> The sidecar runs on your machine, so the Worker only works while
> `python scripts/dev.py` and the Quick Tunnel are running. Quick Tunnel URLs
> change on every restart — update the secret with
> `npx wrangler secret put SIDECAR_URL`. Chat also needs a reachable
> OpenAI-compatible endpoint in the Studio's **Settings**; the canvas, job map,
> and impact simulation work without one.
