---
title: Observability
blurb: What a turn cost, which tool was slow, and the one logging setup.
nav_group: Build
nav_order: 7
slug: observability
---

# Observability

The product's premise is agentic tool use, so two questions must have answers
after the fact: *what did this turn cost?* and *which tool was slow?* Two record
shapes answer them, and one function makes sure they are emitted at all.

## The shared logging setup

`packages/core/src/agentic_odi_core/logging.py` owns `configure_logging()`.
Every entrypoint calls it once at startup — the CLI's Typer callback, the MCP
server's `main()`, and the Studio sidecar's `main()`. It configures a single
stderr handler on the root logger and reads `AGENTIC_ODI_LOG_LEVEL` (default
`INFO`). It is idempotent: a process that imports more than one entrypoint still
prints each line once.

Without it, whether an application logger's record reached a handler depended on
whatever framework the process ran under. uvicorn installs its own; a bare
`python -m` installs none, so a warning that mattered could vanish silently.

## The turn record

`apps/studio-api/.../studio/observability.py` writes one JSON line per chat turn.
Each line carries the request id, the model, the shape of the turn (`rounds`,
`tool_calls`, `tool_errors`), how long it took, and how it ended:

| Field | Meaning |
|---|---|
| `prompt_tokens` | Tokens the backend billed for the prompt, or `null`. |
| `completion_tokens` | Tokens the backend billed for the completion, or `null`. |
| `total_tokens` | Their sum, or `null`. |
| `model` | The model the turn ran against. |

The counts are read from the backend's final usage chunk. A backend that omits
usage leaves them `null` — the counts are never estimated. The turn asks for
usage with `stream_options={"include_usage": True}`; a backend that rejects the
parameter with a 400 is retried without it, and that base URL is remembered for
the process so the probe is not repeated.

## The MCP tool line

`apps/mcp-server/.../mcp_server.py` installs one middleware that emits a line per
tool call:

```
mcp.tool name=get_health duration_ms=3 outcome=ok
mcp.tool name=get_job duration_ms=1 outcome=error code=not_found
```

The error case reads the same `_fail` envelope a client branches on, so the log
and the wire share one code vocabulary. A slow tool is now distinguishable from a
hung one.

## What is redacted, and what is absent

The turn line never carries an API key, an authorization header, or a
customer's words; the `SENSITIVE_KEYS` list in `observability.py` is the
contract. Redaction walks every nested mapping and list, so a token inside a
request object or a quote inside an evidence entry is replaced too, and a
non-sensitive nested value is still readable. The token *counts* are exempt
from the "token" substring heuristic because they are counts, not secrets.

Deliberately absent: no cost table, no price inference. Tokens are recorded; a
fabricated dollar figure would be worse than none.
