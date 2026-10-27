# Deployment

## Project Site (GitHub Pages)

The static site in `website/` is published to
**[https://alehar9320.github.io/agentic-odi/](https://alehar9320.github.io/agentic-odi/)**
by [`.github/workflows/pages.yml`](../.github/workflows/pages.yml).

- A push to `main` runs the website tests, builds `_site` from `website/`, and
  deploys the artifact with `actions/deploy-pages`.
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
