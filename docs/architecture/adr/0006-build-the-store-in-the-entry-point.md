# 0006 — Build the store in the entry point, not at import

- **Status:** accepted
- **Date:** 2026-11-03

## Context

`apps/mcp-server` constructed its repository in the module body: `build_repository()`
and the `ODIService` over it sat at import scope, along with eight store handles
re-exported from the package. `build_repository()` (`packages/core/src/agentic_odi_core/factory.py`)
reads `AGENTIC_ODI_DB`, defaults to `~/.agentic-odi/odi.db`, and creates the parent
directory before opening SQLite. So importing the module wrote to whoever's home
folder it was, and asking for `--help` opened a database. Three callers paid for it:
the test suite had to set `AGENTIC_ODI_DB` before the first import, any tool that
wanted the store reached a process-wide global, and the answer to "when is the store
opened?" lived in `docs/architecture/data-flow.md` instead of next to the code.

The sidecar already answers that question. `create_app(repo=None)`
(`apps/studio-api/src/agentic_odi_studio_api/app.py`) takes an optional repository,
builds one when it is not given, defines its own lifespan, and returns the app;
`main.py` serves it as a factory. Same question, same shape — the MCP server was the
exception.

What made this look unlandable was a wrong assumption about FastMCP: that a factory
which serves a fresh instance must move all fifty `@mcp.tool` bodies into a function
scope, re-indenting most of a thousand-line module. `FastMCP` accepts `providers`,
and every instance exposes its `local_provider`, so one store-less instance can
declare the surface and another instance can serve it.

## Decision

Every runnable server builds its store in its entry point, through a factory. A
module import is inert.

- `create_server(repository=None)` owns construction: it takes the caller's
  repository or builds one through `build_repository()`, wraps both in a `_Store`
  that knows how to close itself, and returns a `FastMCP` built for that store.
- `main()` calls `create_server()` after argument parsing, so `--help` and
  import-time introspection construct nothing.
- `mcp_server.mcp` survives as a **declaration carrier**: it holds the `@mcp.tool`
  and `@mcp.prompt` functions and nothing else — no store, no lifespan, never served.
  Tool bodies reach the store through one process-level holder (`_service()`), which
  is the "small holder the tools capture" rather than a container.
- Importing the module opens nothing, and `apps/mcp-server/tests/test_server_import.py`
  proves it in a subprocess.

## Consequences

**Easier**

- Tests import the server without a filesystem and get their own store by
  construction; the conftest no longer clears eight collections to fake isolation.
- `AGENTIC_ODI_DB` is read when the process starts, so it can be set after import.
- Both entry points now answer the same question in the same place, which makes the
  next server added to this repo have a shape to copy.
- The tool surface stays one readable list at module scope, which is what
  `website/tools/extract.py` reads and what the contract test enumerates.

**Harder**

- **One store per process.** Each `create_server()` call returns its own server over
  its own store, but the tool bodies resolve that store through the holder, so two
  simultaneously live stores in one process are not supported. Sequential servers are
  fine — each closes its own. Serving two tenants from one process would need the tool
  bodies to close over their store, which is the re-indent this ADR exists to avoid.
- The carrier is a second `FastMCP` object that no one serves. It reads as a mistake
  until the comment says what it is for.

**Now we maintain**

- The holder invariant: a tool called before `create_server()` raises rather than
  silently building a store. `test_graceful_shutdown.py` holds it, as does the
  no-op-before-construction behaviour of `shutdown_store()`.

## Alternatives considered

**Move every tool body into the factory.** It would give genuinely per-server state,
but it re-indents roughly 750 lines — over the deletion budget that
`.github/pr-guardrails/config.yml` blocks on — and would take the `@mcp.tool` markers
out of the module scope `website/tools/extract.py` scans. Rejected; revisit if a real
multi-tenant process is needed.

**A `Context` parameter on every tool.** FastMCP's idiomatic per-call state, and it
would work. Rejected here because it changes every tool's signature, which #461 puts
out of scope, and it is a bigger diff than the problem.

**`uvicorn.run("...:create_server", factory=True)`, to match the sidecar exactly.**
`factory=True` is `uvicorn.run()`'s keyword; `FastMCP.run()` is an instance method.
Hand-rolling the ASGI path would discard FastMCP's banner, host-origin protection and
path defaults to imitate a line the sidecar can write directly. Rejected — the
*decision* transfers, the *keyword* does not.

**Keep the globals and defer only the repository.** Cheaper, and it would leave a
service object pointing at a store no one chose yet. Rejected as the half-measure the
#461 claim release refused to land.
