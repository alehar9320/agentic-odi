"""Marketplace normalization, trust matching, caching, and fallback.

Every test injects a fetcher, so the suite never touches the network.
"""

from __future__ import annotations

import json

import pytest
from agentic_odi_connectors.catalog import PRESETS
from agentic_odi_connectors.marketplace import (
    DockerTrustIndex,
    MarketplaceCache,
    MarketplaceService,
    MarketplaceUnavailable,
    OfficialRegistryProvider,
    connector_config_from_listing,
    env_vars_in_listing,
    listing_from_preset,
    listing_from_registry_record,
)

HTTP_RECORD = {
    "server": {
        "name": "com.acme/thing",
        "title": "Acme Thing",
        "description": "Does a thing.",
        "version": "1.2.3",
        "repository": {"url": "https://github.com/acme/thing", "source": "github"},
        "websiteUrl": "https://acme.example/docs",
        "remotes": [{"type": "streamable-http", "url": "https://mcp.acme.example/mcp"}],
    },
    "_meta": {"io.modelcontextprotocol.registry/official": {"isLatest": True}},
}

SECRET_HEADER_RECORD = {
    "server": {
        "name": "com.acme/private",
        "description": "Needs a token.",
        "version": "0.1.0",
        "remotes": [
            {
                "type": "streamable-http",
                "url": "https://mcp.acme.example/private",
                "headers": [
                    {
                        "name": "Authorization",
                        "value": "Bearer {token}",
                        "isSecret": True,
                        "isRequired": True,
                    }
                ],
            }
        ],
    }
}

STDIO_RECORD = {
    "server": {
        "name": "io.example/local",
        "description": "Runs locally.",
        "version": "0.2.0",
        "packages": [
            {
                "registryType": "npm",
                "identifier": "local-mcp",
                "environmentVariables": [
                    {"name": "API_KEY", "isRequired": True},
                    {"name": "OPTIONAL", "isRequired": False},
                ],
            }
        ],
    }
}


def _fetcher(payloads: dict[str, object]):
    """A fetcher that answers by URL substring, recording every call."""

    calls: list[str] = []

    def fetch(url: str, timeout: float):  # noqa: ARG001
        calls.append(url)
        for needle, payload in payloads.items():
            if needle in url:
                body = json.dumps(payload).encode("utf-8")
                return 200, body
        return 404, b"{}"

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


def test_http_record_normalizes_to_installable_listing() -> None:
    listing = listing_from_registry_record(HTTP_RECORD)

    assert listing is not None
    assert listing.id == "official:com.acme/thing"
    assert listing.title == "Acme Thing"
    assert listing.url == "https://mcp.acme.example/mcp"
    assert listing.installable is True
    assert listing.repository == "https://github.com/acme/thing"
    assert listing.docs == "https://acme.example/docs"


def test_stdio_only_record_is_browse_only_with_a_reason() -> None:
    listing = listing_from_registry_record(STDIO_RECORD)

    assert listing is not None
    assert listing.installable is False
    assert listing.unavailable_reason
    assert listing.env_vars == ["API_KEY"]


def test_secret_remote_header_becomes_an_env_placeholder() -> None:
    listing = listing_from_registry_record(SECRET_HEADER_RECORD)

    assert listing is not None
    assert listing.headers["Authorization"].startswith("${")
    assert listing.env_vars == ["MCP_AUTHORIZATION"]
    assert "Bearer " not in listing.headers["Authorization"]


def test_record_without_a_name_is_skipped() -> None:
    assert listing_from_registry_record({"server": {"description": "nameless"}}) is None


def test_provider_search_maps_records_and_remembers_them() -> None:
    fetch = _fetcher({"registry.modelcontextprotocol.io": {"servers": [HTTP_RECORD]}})
    provider = OfficialRegistryProvider(fetcher=fetch)

    listings = provider.search("acme", 10)

    assert [item.name for item in listings] == ["com.acme/thing"]
    assert provider.get("official:com.acme/thing") is not None
    assert "search=acme" in fetch.calls[0]  # type: ignore[attr-defined]
    assert "version=latest" in fetch.calls[0]  # type: ignore[attr-defined]


def test_provider_raises_when_the_registry_errors() -> None:
    provider = OfficialRegistryProvider(fetcher=lambda url, timeout: (503, b"{}"))

    with pytest.raises(MarketplaceUnavailable):
        provider.search("acme", 10)


def test_docker_trust_index_marks_verified_and_counts_pulls() -> None:
    fetch = _fetcher(
        {
            "registry.modelcontextprotocol.io": {"servers": [HTTP_RECORD]},
            "hub.docker.com": {"results": [{"name": "thing", "pull_count": 153521}]},
        }
    )
    service = MarketplaceService(
        provider=OfficialRegistryProvider(fetcher=fetch),
        trust=DockerTrustIndex(fetcher=fetch),
    )

    listings, from_cache = service.search("acme", 10)

    assert from_cache is False
    assert listings[0].verified is True
    assert listings[0].pull_count == 153521


def test_trust_index_failure_degrades_to_unverified() -> None:
    fetch = _fetcher({"registry.modelcontextprotocol.io": {"servers": [HTTP_RECORD]}})
    service = MarketplaceService(
        provider=OfficialRegistryProvider(fetcher=fetch),
        trust=DockerTrustIndex(fetcher=fetch),
    )

    listings, _ = service.search("acme", 10)

    assert listings[0].verified is False
    assert listings[0].installable is True


def test_network_failure_falls_back_to_the_on_disk_cache(tmp_path) -> None:
    cache = MarketplaceCache(tmp_path / "marketplace.json")
    cache.write([listing_from_registry_record(HTTP_RECORD)])  # type: ignore[list-item]
    service = MarketplaceService(
        provider=OfficialRegistryProvider(
            fetcher=lambda url, timeout: (_ for _ in ()).throw(OSError())
        ),
        trust=DockerTrustIndex(fetcher=lambda url, timeout: (500, b"{}")),
        cache=cache,
    )

    listings, from_cache = service.search("", 10)

    assert from_cache is True
    assert [item.name for item in listings] == ["com.acme/thing"]


def test_stale_cache_is_ignored(tmp_path) -> None:
    cache = MarketplaceCache(tmp_path / "marketplace.json", ttl=-1)
    cache.write([listing_from_registry_record(HTTP_RECORD)])  # type: ignore[list-item]

    assert cache.read() is None


def test_no_cache_and_no_network_falls_back_to_presets(tmp_path) -> None:
    service = MarketplaceService(
        provider=OfficialRegistryProvider(fetcher=lambda url, timeout: (500, b"{}")),
        trust=DockerTrustIndex(fetcher=lambda url, timeout: (500, b"{}")),
        cache=MarketplaceCache(tmp_path / "marketplace.json"),
    )

    listings, from_cache = service.search("", 5)

    assert from_cache is True
    assert listings
    assert all(item.source == "preset" for item in listings)


def test_featured_ranks_recommended_presets_first() -> None:
    service = MarketplaceService(trust=DockerTrustIndex(fetcher=lambda url, timeout: (500, b"{}")))

    listings, _ = service.featured(4)

    assert len(listings) == 4
    assert listings[0].is_recommended is True
    assert all(item.source == "preset" for item in listings)


def test_resolve_finds_a_preset_listing() -> None:
    service = MarketplaceService(trust=DockerTrustIndex(fetcher=lambda url, timeout: (500, b"{}")))

    listing = service.resolve("preset:notion")

    assert listing is not None
    assert listing.title == "Notion"


def test_resolve_unknown_preset_returns_none() -> None:
    service = MarketplaceService(trust=DockerTrustIndex(fetcher=lambda url, timeout: (500, b"{}")))

    assert service.resolve("preset:nope") is None


def test_connector_config_from_listing_keeps_credentials_as_placeholders() -> None:
    listing = listing_from_registry_record(SECRET_HEADER_RECORD)

    config = connector_config_from_listing(listing)  # type: ignore[arg-type]

    assert config.kind == "mcp"
    assert config.settings["url"] == "https://mcp.acme.example/private"
    assert config.settings["env_vars"] == ["MCP_AUTHORIZATION"]
    assert "Bearer " not in json.dumps(config.settings)


def test_connector_config_rejects_a_browse_only_listing() -> None:
    listing = listing_from_registry_record(STDIO_RECORD)

    with pytest.raises(ValueError, match="local package"):
        connector_config_from_listing(listing)  # type: ignore[arg-type]


def test_connector_name_is_short_and_filesystem_safe() -> None:
    config = connector_config_from_listing(listing_from_registry_record(HTTP_RECORD))  # type: ignore[arg-type]

    assert config.name == "thing"


def test_env_vars_in_listing_collects_declared_and_interpolated() -> None:
    exa = next(preset for preset in PRESETS if preset.id == "exa")

    assert env_vars_in_listing(listing_from_preset(exa)) == ["EXA_API_KEY"]
