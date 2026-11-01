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

### The sample workspace

The site's primary call to action on the landing page points at
**`website/sample/index.html`**, a read-only sample workspace served at
`/sample/`. It is generated from `website/content/sample-study.json` by
`website/tools/build_sample.py` and committed, so it is part of the deployed
artifact and keeps working when the API is down.

- Regenerate it after editing the fixture or the template:
  `uv run python website/tools/build_sample.py`.
- `uv run python website/tools/build_sample.py --check` fails when the committed
  page disagrees with a fresh render; `test_content_sync.py` runs the same
  comparison, so the page cannot drift from the fixture.
- The page is self-contained: no external font, script, image, or stylesheet.
  `test_content_sync.py` greps the committed file for an external reference, so
  the no-network rule is enforced rather than promised.
- Every row carries a sample marker, and every numeral on the page is read from
  the fixture — the build refuses to publish a number the fixture does not
  contain.

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

### Running the MCP server locally

`python -m agentic_odi_mcp_server` listens on port 8000. Override it with
`--port` or `AGENTIC_ODI_MCP_PORT` (the flag wins), so a second instance can run
beside `scripts/dev.py` without a port clash:

```bash
AGENTIC_ODI_MCP_PORT=8010 python -m agentic_odi_mcp_server
python -m agentic_odi_mcp_server --port 8020
```

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

### Which release is live

`GET /api/build` answers `{"version": "<tag>"}`, read from `vars.RELEASE_VERSION`
in `wrangler.jsonc`. The Worker replies before the sidecar proxy, so a deployment
without a tunnel still identifies itself, and any other method gets a 405 with
`Allow: GET`. The body carries nothing but the version: no environment values,
and never a deploy timestamp, so two deploys of one tag report the same string.

`RELEASE_VERSION` is not a release-please `extra-files` entry, so cutting a release
means editing it in the same commit as the tag. `scripts/check_version_parity.py`
covers the miss and names `wrangler.jsonc` when the declared value drifts from
`.release-please-manifest.json`.

```bash
curl -s https://agentic-odi.alehar.workers.dev/api/build
uv run python scripts/check_version_parity.py
```

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

## Desktop updater signing keys

The updater key pair authenticates release artifacts so an installed app can
verify that an auto-update genuinely came from you. The **public** key is
embedded in `apps/studio/src-tauri/tauri.conf.json` (`plugins.updater.pubkey`) and is
safe to commit. The **private** key must never be committed, logged, printed in
CI, or attached to a build artifact.

1. **Generate a key pair** (only if you need a new one). Leave `-p ""` for a
   passwordless key, or pass a password and remember it:

   ```bash
   npm --prefix apps/studio run tauri signer generate -- -w ./living-studio.key -p "" -f
   ```

   This writes `living-studio.key` (private, `0600`) and `living-studio.key.pub`
   (public).

2. **Paste the public key** into `apps/studio/src-tauri/tauri.conf.json`:

   ```jsonc
   {
     "plugins": {
       "updater": {
         "endpoints": ["https://github.com/alehar9320/agentic-odi/releases/latest/download/latest.json"],
         "pubkey": "<contents of living-studio.key.pub>"
       }
     }
   }
   ```

3. **Store the private key outside the repository** (the repo root is
   git-tracked; a sibling directory is not), with restricted permissions:

   ```bash
   mkdir -p ~/repos/agentic-odi-keys && chmod 700 ~/repos/agentic-odi-keys
   mv living-studio.key ~/repos/agentic-odi-keys/
   chmod 600 ~/repos/agentic-odi-keys/living-studio.key
   ```

   Move it to a long-term secret store (password manager, 1Password/Bitwarden/
   Vault, or a private encrypted backup) when you decide where that lives.
   Losing it means future releases can no longer be signed for existing
   installs.

4. **Add the private key as a GitHub Actions secret** (Settings → Secrets and
   variables → Actions → New repository secret), or via the CLI:

   ```bash
   gh secret set TAURI_SIGNING_PRIVATE_KEY < ~/repos/agentic-odi-keys/living-studio.key
   gh secret set TAURI_SIGNING_PRIVATE_KEY_PASSWORD --body ""   # only if you set a password
   ```

5. **Verify** the secrets exist (values are never displayed):

   ```bash
   gh secret list
   ```

6. **Rotate** by repeating steps 1–4, then publishing a release signed with the
   new key. Existing installs still verify against the public key compiled into
   their binary, so keep the old private key usable and publish the new public
   key ahead of the cut-over.

> [!CAUTION]
> If the private key leaks, treat auto-updates as compromised: generate a new
> pair, rotate the Actions secret, and publish a freshly signed release.
