# ADR 0006: Browser-first, sidecar-optional Studio

- **Status:** proposed
- **Date:** 2026-11-13

## Context

The Studio SPA currently requires the sidecar for every `/api/*` call. Local-first storage (IndexedDB via `StudioBff`) already exists but is a fallback, not the primary path.

## Decision

The local BFF is the primary data path for reads and writes. The sidecar is optional and provides elevation capabilities only (LLM proxy, connectors, MCP passthrough, desktop shell, updates). The browser app must open and be usable with the sidecar process completely absent.

## Consequences

- `tests/test_architecture.py` dependency graph must treat studio-api as optional for the SPA.
- `docs/architecture/data-flow.md` read/write paths: BFF primary, sidecar optional sync.
- `docs/architecture/trust-boundaries.md`: bearer token only attached when sidecar reachable.
- No Python changes required; frontend-only.
