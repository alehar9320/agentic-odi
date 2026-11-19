# 0006 — Browser-first, sidecar-optional Studio

- **Status:** proposed
- **Date:** 2026-11-14

## Context

The Studio SPA currently requires the sidecar for every `/api/*` call. Local-first storage (IndexedDB via `StudioBff`) already exists but is a fallback, not the primary path.

## Decision

The local BFF is the primary data path for reads and writes. The sidecar is optional and provides elevation capabilities only (LLM proxy, connectors, MCP passthrough, desktop shell, updates). The browser app must open and be usable with the sidecar process completely absent.

## Consequences

- `tests/test_architecture.py` dependency graph must treat studio-api as optional for the SPA.
- `data-flow.md` read/write paths: BFF primary, sidecar optional sync.
- `trust-boundaries.md`: bearer token only attached when sidecar reachable.
- No Python changes required; frontend-only.

## Alternatives considered

**Keep the sidecar as the required primary path (status quo).** Rejected: it leaves the SPA unusable whenever the sidecar is absent, which is exactly the offline and cold-start case local-first storage exists to cover.

**Make IndexedDB a pure read/write fallback only.** Rejected: that keeps the sidecar as the primary data path and does not deliver the browser-first goal; every write still round-trips to the sidecar even when the browser can answer locally.

**Embed a Python sidecar in the SPA (WASM/Pyodide).** Rejected: it is heavy, adds a second runtime to the browser, and reintroduces the very process boundary this record is designed to make optional.
