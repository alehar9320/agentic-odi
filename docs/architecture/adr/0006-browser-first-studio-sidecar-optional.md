# ADR 0006: Browser-first, sidecar-optional Studio

## Status
proposed

## Date
2026-11-14

## Context
The Studio SPA currently requires the sidecar for every /api/* call. Local-first storage (IndexedDB via StudioBff) already exists but is a fallback, not the primary path.

## Decision
The local BFF is the primary data path for reads and writes. The sidecar is optional and provides elevation capabilities only (LLM proxy, connectors, MCP passthrough, desktop shell, updates). The browser app must open and be usable with the sidecar process completely absent.

## Consequences
- tests/test_architecture.py dependency graph must treat studio-api as optional for the SPA.
- data-flow.md read/write paths: BFF primary, sidecar optional sync.
- trust-boundaries.md: bearer token only attached when sidecar reachable.
- No Python changes required; frontend-only.

## Alternatives considered

**Keep sidecar as mandatory.** Rejected: the local-first primitives already exist and several child issues are wiring the app to use them without the sidecar. Making the sidecar mandatory contradicts the local-first direction and blocks offline use.

**Make sidecar a separate optional install.** Rejected: the sidecar is a single binary that provides elevation; distributing it separately adds complexity without benefit. The Tauri shell already bundles it.

**Sidecar as primary, BFF as cache.** Rejected: this is the current state and it makes offline/air-gapped use impossible. The BFF must be primary for true local-first operation.