"""Sidecar adapter over the shared marketplace service.

Keeps the FastAPI layer thin: the router asks for listings, and the connector
service asks this module to turn a listing id into a registry entry. The
service is constructed lazily so a test can inject a fake provider without
touching the network.
"""

from __future__ import annotations

from agentic_odi_connectors.marketplace import (
    DEFAULT_LIMIT,
    MarketplaceCache,
    MarketplaceListing,
    MarketplaceService,
    connector_config_from_listing,
)
from agentic_odi_connectors.models import ConnectorConfig
from agentic_odi_connectors.paths import marketplace_cache_path


class StudioMarketplace:
    """Marketplace access for the Living Studio, with a per-process memo."""

    def __init__(self, service: MarketplaceService | None = None) -> None:
        self._service = service or MarketplaceService(
            cache=MarketplaceCache(marketplace_cache_path())
        )
        self._last: dict[str, MarketplaceListing] = {}

    def _remember(self, listings: list[MarketplaceListing]) -> list[MarketplaceListing]:
        # Installing resolves a listing the user just saw, often with no query
        # repeated. Keeping the last page avoids a second registry round-trip.
        for listing in listings:
            self._last[listing.id] = listing
        return listings

    def search(
        self, query: str = "", area: str | None = None, limit: int = DEFAULT_LIMIT
    ) -> tuple[list[MarketplaceListing], bool]:
        listings, from_cache = self._service.search(query, limit)
        if area:
            listings = [item for item in listings if item.area == area]
        return self._remember(listings), from_cache

    def featured(self, limit: int = 6) -> list[MarketplaceListing]:
        listings, _ = self._service.featured(limit)
        return self._remember(listings)

    def resolve(self, listing_id: str) -> MarketplaceListing | None:
        listing = self._last.get(listing_id)
        if listing is not None:
            return listing
        return self._service.resolve(listing_id)

    def config_for(self, listing_id: str) -> ConnectorConfig:
        """Turn a listing id into a registry entry, or explain why it cannot be one."""
        listing = self.resolve(listing_id)
        if listing is None:
            raise ValueError(f"Unknown marketplace listing: {listing_id}")
        return connector_config_from_listing(listing)

    def catalog_areas(self) -> dict[str, str]:
        from agentic_odi_connectors.catalog import AREA_LABELS

        return {str(area): label for area, label in AREA_LABELS.items()}


__all__ = ["StudioMarketplace"]
