---
description: Start the local dev stack and verify the Living Studio
---

# Local Dev & Test Workflow

Use this workflow whenever the user asks to run the app locally or test the
server/Studio stack end to end.

## Steps

1. **Start both Python services** — The launcher starts the MCP server on
   `:8000` and the Studio API sidecar on `:8100`.

```bash
uv run python scripts/dev.py
```

Save the command ID and wait a few seconds for both ports to bind.

2. **Verify the services**

```bash
curl -sf http://127.0.0.1:8100/api/config
curl -sfX POST http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"dev","version":"1"}}}'
```

3. **Open the Studio** — navigate to `http://localhost:8100`.
   For hot reload instead, run `npm --prefix apps/studio run dev` in a second
   terminal; Vite proxies `/api` to the sidecar.

4. **Build the SPA when needed**

```bash
npm --prefix apps/studio run build
```

The sidecar serves `apps/studio/dist` when it exists. Override the location with
`AGENTIC_ODI_STUDIO_DIST`.

5. **Teardown** — stop the launcher; it terminates both child processes.

## Notes

- MCP server: `http://localhost:8000/mcp`
- Studio API and SPA: `http://localhost:8100`
- Vite dev server: `http://localhost:5173`
- Chat requires an OpenAI-compatible endpoint. The default is
  `http://localhost:8001/v1`; configure it in Studio Settings or with
  `AGENTIC_ODI_BASE_URL`.
