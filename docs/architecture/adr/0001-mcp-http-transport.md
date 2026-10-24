# 0001 — Drive MCP over HTTP instead of stdio

- **Status:** accepted
- **Date:** 2026-10-24

## Context

Agentic ODI exposes its domain through an MCP server, and three different kinds
of client call it:

1. the CLI, with `--backend mcp` (and `odi chat`, which runs a tool loop),
2. the Living Studio sidecar, which proxies tool calls for the SPA,
3. external agents (hosted or local) pointed at `AGENTIC_ODI_MCP_URL`.

The MCP specification offers stdio, where the client spawns the server as a
subprocess and speaks JSON-RPC over its pipes, and HTTP, where the server is a
long-running process with a URL.

The project also has a deployment shape that matters here: the free-plan Studio
runs on a Cloudflare Worker that tunnels to the sidecar over HTTP, and no part of
that path can carry a stdio pipe. Users routinely run the server on one machine
and point clients at it from another.

## Decision

The MCP server runs as an HTTP service (`mcp.run(transport="http", port=8000)`)
and every client talks to it over HTTP:

- the CLI calls `AGENTIC_ODI_MCP_URL` (default `http://localhost:8000/mcp`),
- the sidecar calls the same URL through `call_mcp_tool`,
- external agents connect to the same endpoint,
- one server process owns the SQLite repository, so all clients see one store.

`scripts/dev.py` starts the MCP server and the sidecar together so local
development has the same shape as deployment.

## Consequences

**Easier**

- Several clients share one server and one store; a CLI write is visible in the
  Studio immediately, with no file locking between processes.
- The server is reachable across machines and through a tunnel, which is what
  the Cloudflare deployment and "point your agent at my machine" both need.
- Server lifecycle is independent of any one client, so a crashed client does
  not kill the store.

**Harder**

- The server has no authentication in local development. It must not be exposed
  directly to the internet; the Cloudflare setup tunnels the sidecar, not MCP.
- Running the server is a step of its own — a stdio client would have started it
  on demand.
- HTTP adds a network hop and a timeout surface, which the connector and chat
  paths each handle explicitly.

**Now we maintain**

- A port and URL convention (`AGENTIC_ODI_MCP_URL`, port `8000`) in every client.
- Documentation for starting the server before the CLI or Studio can use it.

## Alternatives considered

**stdio.** Simplest for a single local client, and the common default in MCP
examples. Rejected because it cannot serve multiple clients against one store,
cannot be reached over a tunnel, and would need the CLI, the sidecar, and the
Worker each to spawn their own server process — which also means three separate
SQLite writers.

**HTTP with a per-client server.** Keeps isolation but recreates the multi-writer
problem and makes the Studio's view drift from the CLI's. Rejected.

**A bespoke REST API instead of MCP.** Would work for our own clients but would
give up the tool-discovery contract that lets external agents use the same
surface. Rejected; the Studio API is a REST facade *over* MCP for the SPA, not a
replacement for it.
