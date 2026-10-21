# Deployment

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
| Root directory | `/` |
| Build command | `npm --prefix apps/studio ci && npm --prefix apps/studio run build` |
| Deploy command | `npx wrangler deploy` |

A Worker has no run command: the Worker script runs on Cloudflare. Set `name` in
`wrangler.jsonc` to the Worker you created before the first deploy.

> [!NOTE]
> The sidecar runs on your machine, so the Worker only works while
> `python scripts/dev.py` and the Quick Tunnel are running. Quick Tunnel URLs
> change on every restart — update the secret with
> `npx wrangler secret put SIDECAR_URL`. Chat also needs a reachable
> OpenAI-compatible endpoint in the Studio's **Settings**; the canvas, job map,
> and impact simulation work without one.
