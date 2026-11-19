---
title: Configuration
blurb: Every environment variable, its default, and the form it accepts.
nav_group: Operate
nav_order: 6
slug: configuration
---

# Configuration

Every `AGENTIC_ODI_*` variable a process reads is declared once, as a field in
`packages/core/src/agentic_odi_core/settings.py`, and read through
`from_env()`. Nothing else reads `os.environ` in `packages/core` or
`apps/*/src`; a direct read elsewhere is drift.

A value that cannot be parsed stops the process with one line naming the
variable, the value, and the form it accepts. It never quietly becomes the
default: `AGENTIC_ODI_MCP_TIMEOUT=30s` used to read as thirty seconds with
nobody told, and now it fails instead. An unset or blank variable is the only
thing that falls back to the default.

## MCP connection

Declared by `MCPConnectionSettings` in `settings.py`; read by the CLI MCP client
through `agentic_odi_core.MCPConnectionConfig.from_env()`.

| Variable | Default | Accepted form | Consumer |
|---|---|---|---|
| `AGENTIC_ODI_MCP_TIMEOUT` | `30.0` | A number of seconds greater than zero | CLI MCP client, per call and handshake |
| `AGENTIC_ODI_MCP_KEEPALIVE` | `15.0` | A number of seconds, or `0` to disable | MCP session keepalive |

Both values are parsed by `agentic_odi_core.MCPConnectionConfig.from_env()`.
The CLI hands the timeout to the FastMCP client for every call, so a frozen
server fails with a clear error instead of hanging. FastMCP has no
keepalive-interval setting yet, so the interval is carried for transports that
support session keepalive.
