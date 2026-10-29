# Customize — Connector Management Page — Design

> **Status:** approved-by-default (user opted out of the question loop; decisions below are the agent's calls and are marked as such).

## Intent & Why

The Living Studio can already register external MCP connectors, but only through a small block buried in Settings. Users discover they need connectors either because the studio feels thin without real data, or because the agent suggests one mid-conversation. Today neither path lands anywhere that lets them see what is installed and add more.

This adds a **Customize** page: one place to inspect installed connectors (the truth in `connectors.json`) and add new ones from a curated shelf plus a live marketplace. The shelf must not forward junk, so every listing carries a trust signal from a reviewed source.

## Goals

- A single **Customize** screen with search, connection-type and capability-area filters, an **Installed** section, **Editor's picks**, and a **Marketplace** list.
- Marketplace content is **auto-populated** from a trusted registry, not frozen at build time.
- Installing from the marketplace writes through the existing `ConnectorRegistry` into the shared `connectors.json`, so the CLI sees the same set.
- A **suggestion modal** surfaces a connector when the agent suggests one or when the studio has no connectors, with install / browse-all / dismiss.
- Every listing shows where it came from (Official registry, Editor's pick, Docker-verified).

## Non-goals / anti-goals

- **No permanent left navigation sidebar.** The studio is conversation-first; adding fixed navigation is a larger, unrequested redesign. Customize is a full-stage page you enter and leave.
- **No A2A implementation.** A2A appears as a disabled "Coming soon" connection type only.
- **No container/Docker-run installs.** Our connector speaks streamable HTTP. Docker catalog entries are container images and are therefore used as a *trust signal*, never as an install source.
- **No secret entry in this page.** Credentials stay as `${VAR}` placeholders resolved from the environment, exactly as the CLI and existing presets do. The page may *name* a missing variable; it never stores one.
- **No remote code execution.** Installing only writes a config row. Nothing is fetched or run at install time.

## Anti-goals (would make this a failure even if it works)

- Presenting a listing as installable when our transport cannot reach it.
- Shipping an unauthenticated marketplace feed that any publisher can inject arbitrary junk into without a signal.
- Breaking the conversation-first shell (composer stays on screen) for the normal chat flow.

## Marketplace decision (the agent's call)

Surveyed on 2026-10-26:

| Source | Scale | Auth | Trust signal | Use |
|---|---|---|---|---|
| **Official MCP Registry** (`registry.modelcontextprotocol.io`) | ~600 latest, growing | none | open publishing; `remotes` are real HTTP endpoints | **Install source** |
| **Docker MCP Registry** (`github.com/docker/mcp-registry`; Hub `mcp/*`) | 328 reviewed / 245 on Hub | none | Docker reviews each submission; signed images, SBOMs | **Trust badge + popularity** |
| **Smithery** (`registry.smithery.ai`) | ~20,766 | none for read | `verified` boolean, `useCount` | deferred |
| PulseMCP | — | — | API returns 410 (moved) | out |
| Glama | — | — | 401 | out |

**Chosen: the official MCP Registry is the install source; Docker's reviewed catalog is the trust signal; the existing `PRESETS` are the Editor's picks.**

Rationale: the official registry is the canonical place MCP vendors publish, and its `remotes[].type == "streamable-http"` entries are exactly what `MCPClientConnector` can already talk to. Docker's registry is the strongest "reviewed, no junk" signal available and costs one unauthenticated Hub API call. Only listings that pass the installable filter can be installed; everything else is browse-only and says so.

## Architecture

```
packages/connectors/
  marketplace.py        NEW  MarketplaceListing, MarketplaceProvider protocol,
                             OfficialRegistryProvider, DockerTrustIndex, MarketplaceService
  catalog.py            unchanged presets; becomes the "Editor's picks" source
apps/studio-api/
  studio/marketplace.py NEW  thin sidecar wrapper over MarketplaceService
  studio/router.py           GET /api/marketplace/servers, /api/marketplace/featured,
                             POST /api/connectors accepts `marketplace_id`
  studio/schemas.py          MarketplaceListingOut, MarketplaceSearchResponse
apps/studio/ (frontend)
  src/types.ts               MarketplaceListing, MarketplaceSearch types
  src/api/studioApi.ts       fetchMarketplace, fetchFeatured
  src/state/StudioContext.tsx  marketplace state + actions; customize open/close
  src/components/customize/CustomizePage.tsx      NEW page
  src/components/customize/ConnectorSuggestionModal.tsx  NEW modal
  src/components/layout/StudioBar.tsx             entry point
  src/components/SettingsPanel.tsx                "Manage connectors" link
  src/styles/theme.css                            .customize* styles
```

### Install path

```
Customize page --POST /api/connectors {marketplace_id}>
  -> ConnectorService.add(marketplace_id=...)
  -> MarketplaceService.resolve(marketplace_id)  -> MarketplaceListing
  -> ConnectorConfig(name, kind="mcp", settings=McpConnectorSettings(url, headers, env_vars))
  -> ConnectorRegistry.add -> ~/.config/agentic-odi/connectors.json
```

### Provider contract

```python
class MarketplaceProvider(Protocol):
    def search(self, query: str, limit: int) -> list[MarketplaceListing]: ...
    def get(self, listing_id: str) -> MarketplaceListing | None: ...
```

`OfficialRegistryProvider` maps registry records to `MarketplaceListing`, keeping only
entries with a `streamable-http` remote. `DockerTrustIndex` supplies
`{name -> {verified, pull_count}}`; matching is by normalized server slug.

### Caching

One file-backed cache under `~/.cache/agentic-odi/marketplace.json` with a TTL (default 15 min),
resolved via `paths.cache_path()`'s sibling. Network failures fall back to the cache, then to the
preset catalog alone — the page never shows an empty shelf because a third party is down.

## Contracts

### `MarketplaceListing`

| Field | Type | Notes |
|---|---|---|
| `id` | str | stable key, e.g. `official:com.acme/thing` |
| `name` | str | display name |
| `title` | str \| None | registry `title` when present |
| `summary` | str | description |
| `version` | str | latest version |
| `url` | str | the `streamable-http` remote URL |
| `source` | `"official"` \| `"preset"` | where it came from |
| `area` | str \| None | capability area, when known |
| `repository` | str \| None | source repo |
| `docs` | str \| None | website/docs |
| `env_vars` | list[str] | required variables, from remote headers + env |
| `headers` | dict[str, str] | header template with `${VAR}` placeholders |
| `installable` | bool | false for browse-only |
| `verified` | bool | present in Docker's reviewed catalog |
| `pull_count` | int | Docker Hub pulls, popularity signal |
| `is_recommended` | bool | Editor's pick |

### Sidecar API

| Method | Path | Query/Body | Result |
|---|---|---|---|
| GET | `/api/marketplace/servers` | `q`, `area`, `limit` | `{listings: [...], sources: {...}, cached: bool}` |
| GET | `/api/marketplace/featured` | `limit` | `{listings: [...]}` |
| POST | `/api/connectors` | `{marketplace_id}` or existing `{preset}`/`{name,url}` | `{ok, name}` |

## Frontend

Customize is a **full-stage page**: it replaces the conversation area while open and keeps the
top bar. The composer is not shown on this page — this is a management surface, not a lens on the
thread. `Esc` and a Back control return to the conversation. State lives in `StudioContext`
(`customizeOpen`), so the bar, the Settings link, the suggestion modal, and the chat all route to
the same place.

### Entry points

1. **Bar** — a `Customize` control next to the bell.
2. **Settings** — a "Manage connectors" button replaces the bare preset dropdown as the primary path.
3. **Suggestion modal** — when the agent emits a `connector` suggestion, or on first run with zero
   connectors, a modal offers the recommended connector with **Install**, **Browse all**, **Not now**.
4. **Chat** — a connector suggestion chip links into Customize filtered to that listing.

### Filters

- Connection type: `MCP` (active), `A2A` (disabled, "Coming soon").
- Capability area: the five existing areas from `catalog.AREA_LABELS`, plus `All`.

## Testing

- `packages/connectors/tests/test_marketplace.py` — normalization, installable filter, Docker
  matching, cache TTL, network-failure fallback. All against injected fixtures; **no network**.
- `apps/studio-api/tests/test_studio_marketplace.py` — the two routes and `marketplace_id` install,
  with a fake provider.
- `apps/studio/src/components/customize/CustomizePage.test.tsx` — render, search, install, remove,
  A2A placeholder, empty and error states.
- Existing connector tests must keep passing unchanged.
