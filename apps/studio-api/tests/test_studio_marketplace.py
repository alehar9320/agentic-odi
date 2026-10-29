"""Marketplace routes and marketplace-backed installs.

The provider is faked, so these tests never touch the network.
"""

from __future__ import annotations

import pytest
from agentic_odi_connectors.marketplace import (
    MarketplaceListing,
    MarketplaceService,
    MarketplaceUnavailable,
)
from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio.connectors import ConnectorService
from agentic_odi_studio_api.studio.marketplace import StudioMarketplace
from fastapi.testclient import TestClient

HTTP_RECORD = {
    "server": {
        "name": "com.acme/thing",
        "title": "Acme Thing",
        "description": "Does a thing.",
        "version": "1.2.3",
        "remotes": [{"type": "streamable-http", "url": "https://mcp.acme.example/mcp"}],
    }
}

STDIO_RECORD = {
    "server": {
        "name": "io.example/local",
        "description": "Runs locally.",
        "version": "0.2.0",
        "packages": [{"registryType": "npm", "identifier": "local-mcp"}],
    }
}


class FakeProvider:
    """An in-memory stand-in for the official registry."""

    def __init__(self, records: list[dict]) -> None:
        self.records = records

    def search(self, query: str = "", limit: int = 50) -> list[MarketplaceListing]:
        from agentic_odi_connectors.marketplace import listing_from_registry_record

        found = [listing_from_registry_record(record) for record in self.records]
        return [item for item in found if item is not None][:limit]

    def get(self, listing_id: str) -> MarketplaceListing | None:
        for listing in self.search("", 50):
            if listing.id == listing_id:
                return listing
        return None


def _client(tmp_path, provider=None) -> TestClient:
    marketplace = StudioMarketplace(
        service=MarketplaceService(
            provider=provider or FakeProvider([HTTP_RECORD]),
            trust=_NoTrust(),  # type: ignore[arg-type]
        )
    )
    connectors = ConnectorService(tmp_path / "connectors.json", marketplace=marketplace)
    return TestClient(
        create_app(InMemoryRepository(), connectors=connectors, marketplace=marketplace)
    )


class _NoTrust:
    def lookup(self, listing_name: str):
        return None


def test_search_returns_listings_and_connection_types(tmp_path) -> None:
    response = _client(tmp_path).get("/api/marketplace/servers")

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data["listings"]] == ["official:com.acme/thing"]
    types = {item["id"]: item for item in data["types"]}
    assert types["mcp"]["available"] is True
    assert types["a2a"]["available"] is False
    assert types["a2a"]["note"] == "Coming soon"


def test_search_includes_capability_areas(tmp_path) -> None:
    data = _client(tmp_path).get("/api/marketplace/servers").json()

    assert "voice-of-customer" in data["areas"]
    assert data["areas"]["voice-of-customer"]


def test_search_area_filter_excludes_non_matching(tmp_path) -> None:
    client = _client(tmp_path)

    data = client.get("/api/marketplace/servers", params={"area": "strategy-alignment"}).json()

    # Registry listings carry no area, so a strict area filter yields nothing.
    assert data["listings"] == []


def test_featured_returns_editor_picks(tmp_path) -> None:
    response = _client(tmp_path).get("/api/marketplace/featured")

    assert response.status_code == 200
    listings = response.json()["listings"]
    assert listings
    assert all(item["source"] == "preset" for item in listings)
    assert any(item["is_recommended"] for item in listings)


def test_search_degrades_to_presets_when_the_provider_fails(tmp_path) -> None:
    client = _client(tmp_path, provider=_FailingProvider())

    response = client.get("/api/marketplace/servers")

    assert response.status_code == 200
    data = response.json()
    assert data["cached"] is True
    assert data["listings"]


class _FailingProvider:
    def search(self, query: str = "", limit: int = 50):
        raise MarketplaceUnavailable("registry down")

    def get(self, listing_id: str):
        raise MarketplaceUnavailable("registry down")


def test_install_from_marketplace_id_persists(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/connectors", json={"marketplace_id": "official:com.acme/thing"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "name": "thing"}
    listed = client.get("/api/connectors").json()
    assert listed == [{"name": "thing", "kind": "mcp", "enabled": True}]


def test_installed_marketplace_connector_keeps_url_and_no_secrets(tmp_path) -> None:
    client = _client(tmp_path)
    client.post("/api/connectors", json={"marketplace_id": "official:com.acme/thing"})

    import json

    saved = json.loads((tmp_path / "connectors.json").read_text(encoding="utf-8"))

    settings = saved["connectors"][0]["settings"]
    assert settings["url"] == "https://mcp.acme.example/mcp"
    assert "token" not in json.dumps(settings).lower()


def test_install_from_preset_listing_id(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/connectors", json={"marketplace_id": "preset:notion"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "name": "notion"}


def test_install_unknown_listing_id_is_a_validation_error(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/connectors", json={"marketplace_id": "official:nope/missing"})

    assert response.status_code == 400
    assert "Unknown marketplace listing" in response.json()["error"]["message"]


def test_install_browse_only_listing_is_a_validation_error(tmp_path) -> None:
    client = _client(tmp_path, provider=FakeProvider([STDIO_RECORD]))

    response = client.post("/api/connectors", json={"marketplace_id": "official:io.example/local"})

    assert response.status_code == 400
    assert "local package" in response.json()["error"]["message"]


def test_marketplace_id_conflict_reports_409(tmp_path) -> None:
    client = _client(tmp_path)
    client.post("/api/connectors", json={"marketplace_id": "official:com.acme/thing"})

    response = client.post("/api/connectors", json={"marketplace_id": "official:com.acme/thing"})

    assert response.status_code == 409


def test_marketplace_routes_appear_in_the_openapi_contract(tmp_path) -> None:
    paths = _client(tmp_path).get("/api/openapi.json").json()["paths"]

    assert "/api/marketplace/servers" in paths
    assert "/api/marketplace/featured" in paths


@pytest.mark.parametrize("limit", [0, 500])
def test_search_rejects_out_of_range_limits(tmp_path, limit: int) -> None:
    response = _client(tmp_path).get("/api/marketplace/servers", params={"limit": limit})

    assert response.status_code == 422
