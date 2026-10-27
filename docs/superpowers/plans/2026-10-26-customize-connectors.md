# Customize — Connector Management Page — Plan

Design: `docs/superpowers/specs/2026-10-26-customize-connectors-design.md`

## Step 1 — Marketplace package (`packages/connectors`)

- `marketplace.py`:
  - `MarketplaceListing` (pydantic) with the fields in the design.
  - `MarketplaceProvider` protocol: `search(query, limit)`, `get(listing_id)`.
  - `OfficialRegistryProvider`: `urllib` GET against `registry.modelcontextprotocol.io/v0/servers`,
    `version=latest`; map records → listings; keep `streamable-http` remotes; derive `env_vars`
    and `headers` from remote headers + package env vars.
  - `DockerTrustIndex`: `hub.docker.com/v2/repositories/mcp/?page_size=100`; build slug → pulls map.
  - `MarketplaceService(provider=..., trust=..., cache=...)`: `search()`, `featured()`, `resolve(id)`.
  - `MarketplaceCache`: JSON file, TTL, `get`/`set`.
- `paths.py`: add `marketplace_cache_path()`.
- Tests: `packages/connectors/tests/test_marketplace.py`.

## Step 2 — Sidecar

- `studio/marketplace.py`: `MarketplaceService` wiring, lazily constructed, injectable for tests.
- `schemas.py`: `MarketplaceListingOut`, `MarketplaceSearchResponse`; `AddConnectorRequest.marketplace_id`.
- `connectors.py`: `ConnectorService.add(marketplace_id=...)` → resolve → `ConnectorConfig`.
- `router.py`: `GET /api/marketplace/servers`, `GET /api/marketplace/featured`.
- `app.py`: `app.state.marketplace`.
- Tests: `apps/studio-api/tests/test_studio_marketplace.py`.

## Step 3 — Frontend state + API

- `types.ts`: `MarketplaceListing`, `MarketplaceSearch`, `ConnectorType`.
- `studioApi.ts`: `fetchMarketplace`, `fetchFeatured`; `AddConnectorPayload.marketplace_id`.
- `StudioContext.tsx`: `marketplace`, `marketplaceError`, `refreshMarketplace`, `featured`,
  `customizeOpen`, `openCustomize(filter?)`, `closeCustomize`, `installFromMarketplace`.

## Step 4 — Customize page

- `components/customize/CustomizePage.tsx`: header + Back, search, type chips (MCP/A2A-coming-soon),
  area chips, Installed section, Editor's picks, Marketplace list, empty/error/loading states.
- `components/customize/ConnectorSuggestionModal.tsx`: the suggestion modal.
- `App.tsx`: render Customize instead of the thread when `customizeOpen`.
- `StudioBar.tsx`: Customize entry point.
- `SettingsPanel.tsx`: "Manage connectors" link.
- `theme.css`: `.customize*`, `.suggestion-modal*`.

## Step 5 — Docs

- `docs/connectors.md`: marketplace section.
- `docs/living-studio.md`: Customize surface row + entry points.
- `README.md`: mention the Customize page in the studio row/feature list.
- `docs/architecture/README.md` + `data-flow.md`: marketplace module and read path.

## Step 6 — Verify

- `uv run pytest`, `npm --prefix apps/studio test -- --run`, `npm run lint`, `npm run typecheck`,
  `uv run ruff check .`, `uv run mypy apps packages`, regenerate `apps/studio/openapi.json`.
