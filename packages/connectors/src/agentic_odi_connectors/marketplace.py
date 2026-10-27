"""Marketplace discovery for external MCP servers.

The Living Studio's Customize page needs a shelf of connectors that is not
frozen at build time. Two public, unauthenticated sources back it:

* the **official MCP Registry** (``registry.modelcontextprotocol.io``) is the
  install source. Its ``remotes`` entries are real streamable-HTTP endpoints,
  which is exactly what :class:`MCPClientConnector` can talk to.
* **Docker's reviewed MCP registry** (``hub.docker.com/u/mcp``) is the trust
  signal. Every entry there passed a review, so a listing that appears in both
  is marked ``verified`` and carries a pull count as a popularity hint.

Nothing here installs or runs anything: a listing is only ever a config row.
The transport is injectable so tests never touch the network.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from agentic_odi_connectors.catalog import AREA_LABELS, PRESETS, ConnectorPreset
from agentic_odi_connectors.models import ConnectorConfig

OFFICIAL_REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0/servers"
DOCKER_HUB_NAMESPACE_URL = "https://hub.docker.com/v2/repositories/mcp/"
MARKETPLACE_CACHE_TTL_SECONDS = 15 * 60.0
DEFAULT_LIMIT = 50
MAX_LIMIT = 100

FetchResult = tuple[int, bytes]
Fetcher = Callable[[str, float], FetchResult]

# Docker's catalog keys are slugs ("github", "aws-s3"); registry names are
# reverse-DNS paths ("com.acme/thing") or plain slugs. Comparing the last path
# segment, lowercased and stripped of punctuation, matches the common cases
# without pretending to be an exact identity.
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _slug(value: str) -> str:
    return _SLUG_STRIP.sub("", value.lower())


class MarketplaceListing(BaseModel):
    """One discoverable connector, normalized across every source."""

    id: str
    name: str
    title: str | None = None
    summary: str = ""
    version: str = ""
    url: str | None = None
    source: str = "official"
    area: str | None = None
    repository: str | None = None
    docs: str | None = None
    env_vars: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    auth: str = "none"
    installable: bool = False
    verified: bool = False
    pull_count: int = 0
    is_recommended: bool = False
    # Why a listing cannot be installed, shown verbatim in the UI.
    unavailable_reason: str | None = None

    @property
    def display_name(self) -> str:
        return self.title or self.name.rsplit("/", 1)[-1]

    @property
    def connector_name(self) -> str:
        """The registry name an install of this listing produces."""
        return _connector_name(self)


class MarketplaceProvider(Protocol):
    """A source of marketplace listings."""

    def search(self, query: str = "", limit: int = DEFAULT_LIMIT) -> list[MarketplaceListing]: ...

    def get(self, listing_id: str) -> MarketplaceListing | None: ...


def _default_fetcher(url: str, timeout: float) -> FetchResult:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - network path
        return exc.code, exc.read()
    except OSError as exc:  # pragma: no cover - network path
        raise MarketplaceUnavailable(str(exc)) from exc


class MarketplaceUnavailable(RuntimeError):
    """Raised when a marketplace source cannot be reached."""


def _remote_is_http(remote: dict[str, Any]) -> bool:
    return str(remote.get("type", "")) in {"streamable-http", "sse"} and bool(remote.get("url"))


def _headers_from_remote(remote: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    """Turn a remote's header declarations into connector settings.

    A declared secret header becomes a ``${VAR}`` placeholder so no token is
    ever stored in ``connectors.json``; the variable name is what the health
    check reports as missing.
    """
    headers: dict[str, str] = {}
    env_vars: list[str] = []
    for header in remote.get("headers", []) or []:
        name = str(header.get("name", "")).strip()
        if not name:
            continue
        template = str(header.get("value", "")).strip()
        if header.get("isSecret") or "{" in template:
            var = f"MCP_{_SLUG_STRIP.sub('_', name.lower()).strip('_').upper() or 'TOKEN'}"
            headers[name] = f"${{{var}}}"
            env_vars.append(var)
        elif template:
            headers[name] = template
    return headers, env_vars


def _env_vars_from_packages(packages: list[dict[str, Any]]) -> list[str]:
    """Required environment variables declared on stdio packages."""
    names: list[str] = []
    for package in packages or []:
        for env in package.get("environmentVariables", []) or []:
            if env.get("isRequired") and env.get("name"):
                names.append(str(env["name"]))
    return names


def listing_from_registry_record(record: dict[str, Any]) -> MarketplaceListing | None:
    """Normalize one official-registry record, or ``None`` when it has no HTTP remote."""
    server = record.get("server") or {}
    name = str(server.get("name") or "").strip()
    if not name:
        return None
    remotes = [remote for remote in server.get("remotes", []) or [] if _remote_is_http(remote)]
    packages = server.get("packages", []) or []
    env_vars = _env_vars_from_packages(packages)
    if remotes:
        remote = remotes[0]
        headers, header_vars = _headers_from_remote(remote)
        env_vars = header_vars or env_vars
        return MarketplaceListing(
            id=f"official:{name}",
            name=name,
            title=server.get("title"),
            summary=str(server.get("description") or "").strip(),
            version=str(server.get("version") or ""),
            url=str(remote.get("url") or ""),
            source="official",
            repository=(server.get("repository") or {}).get("url"),
            docs=server.get("websiteUrl"),
            env_vars=env_vars,
            headers=headers,
            installable=True,
        )
    # A stdio-only server needs a local process we do not launch; it stays
    # visible in search so the user can see it exists, but it is not installable.
    return MarketplaceListing(
        id=f"official:{name}",
        name=name,
        title=server.get("title"),
        summary=str(server.get("description") or "").strip(),
        version=str(server.get("version") or ""),
        source="official",
        repository=(server.get("repository") or {}).get("url"),
        docs=server.get("websiteUrl"),
        env_vars=env_vars,
        installable=False,
        unavailable_reason="Runs as a local package, not a hosted endpoint.",
    )


class OfficialRegistryProvider:
    """Searches the official MCP Registry."""

    def __init__(
        self,
        *,
        base_url: str = OFFICIAL_REGISTRY_URL,
        timeout: float = 10.0,
        fetcher: Fetcher | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._fetch = fetcher or _default_fetcher
        self._cache: dict[str, MarketplaceListing] = {}

    def _request(self, query: str, limit: int) -> list[MarketplaceListing]:
        params = {"version": "latest", "limit": str(min(max(limit, 1), MAX_LIMIT))}
        if query:
            params["search"] = query
        url = f"{self._base_url}?{urllib.parse.urlencode(params)}"
        status, body = self._fetch(url, self._timeout)
        if status != 200:
            raise MarketplaceUnavailable(f"registry returned {status}")
        payload = json.loads(body.decode("utf-8"))
        listings: list[MarketplaceListing] = []
        for record in payload.get("servers", []):
            listing = listing_from_registry_record(record)
            if listing is not None:
                self._cache[listing.id] = listing
                listings.append(listing)
        return listings

    def search(self, query: str = "", limit: int = DEFAULT_LIMIT) -> list[MarketplaceListing]:
        return self._request(query, limit)

    def get(self, listing_id: str) -> MarketplaceListing | None:
        cached = self._cache.get(listing_id)
        if cached is not None:
            return cached
        # The registry has no id lookup, so search by the name's last segment
        # and keep the exact match.
        needle = listing_id.split(":", 1)[-1]
        for listing in self._request(needle.rsplit("/", 1)[-1], MAX_LIMIT):
            if listing.id == listing_id:
                return listing
        return None


class DockerTrustIndex:
    """Docker's reviewed-catalog membership and popularity, keyed by slug."""

    def __init__(
        self,
        *,
        base_url: str = DOCKER_HUB_NAMESPACE_URL,
        timeout: float = 10.0,
        fetcher: Fetcher | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._fetch = fetcher or _default_fetcher
        self._by_slug: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def load(self) -> dict[str, dict[str, Any]]:
        if self._loaded:
            return self._by_slug
        params = urllib.parse.urlencode({"page_size": MAX_LIMIT})
        status, body = self._fetch(f"{self._base_url}?{params}", self._timeout)
        if status != 200:
            raise MarketplaceUnavailable(f"docker hub returned {status}")
        payload = json.loads(body.decode("utf-8"))
        for repo in payload.get("results", []):
            name = str(repo.get("name") or "")
            if name:
                self._by_slug[_slug(name)] = repo
        self._loaded = True
        return self._by_slug

    def lookup(self, listing_name: str) -> dict[str, Any] | None:
        try:
            index = self.load()
        except Exception:  # noqa: BLE001 - a trust lookup must never break search
            return None
        return index.get(_slug(listing_name.rsplit("/", 1)[-1]))


def listing_from_preset(preset: ConnectorPreset) -> MarketplaceListing:
    """An Editor's pick, expressed as a listing so one component renders both."""
    return MarketplaceListing(
        id=f"preset:{preset.id}",
        name=preset.id,
        title=preset.label,
        summary=preset.summary,
        url=preset.url,
        source="preset",
        area=preset.area,
        docs=preset.docs,
        env_vars=list(preset.env_vars),
        headers=dict(preset.headers),
        auth=preset.auth,
        installable=True,
        verified=True,
        is_recommended=preset.is_recommended,
    )


class MarketplaceCache:
    """A TTL cache of the last successful search, on disk."""

    def __init__(self, path: Path, ttl: float = MARKETPLACE_CACHE_TTL_SECONDS) -> None:
        self.path = path
        self.ttl = ttl

    def read(self) -> list[MarketplaceListing] | None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        if time.time() - float(payload.get("fetched_at", 0)) > self.ttl:
            return None
        listings = payload.get("listings")
        if not isinstance(listings, list):
            return None
        try:
            return [MarketplaceListing.model_validate(item) for item in listings]
        except ValueError:
            return None

    def write(self, listings: list[MarketplaceListing]) -> None:
        payload = {
            "fetched_at": time.time(),
            "listings": [item.model_dump(mode="json") for item in listings],
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        except OSError:  # pragma: no cover - a full disk must not break search
            pass


class MarketplaceService:
    """The Customize page's data source: search, featured, and install resolution.

    A network failure degrades in three steps — live, then the on-disk cache,
    then the built-in preset catalog — so the shelf is never empty because a
    third party is down.
    """

    def __init__(
        self,
        *,
        provider: MarketplaceProvider | None = None,
        trust: DockerTrustIndex | None = None,
        cache: MarketplaceCache | None = None,
    ) -> None:
        self._provider = provider or OfficialRegistryProvider()
        self._trust = trust or DockerTrustIndex()
        self._cache = cache

    def _decorate(self, listings: list[MarketplaceListing]) -> list[MarketplaceListing]:
        for listing in listings:
            match = self._trust.lookup(listing.name)
            if match:
                listing.verified = True
                listing.pull_count = int(match.get("pull_count") or 0)
        return listings

    def search(
        self, query: str = "", limit: int = DEFAULT_LIMIT
    ) -> tuple[list[MarketplaceListing], bool]:
        """Return ``(listings, from_cache)``."""
        try:
            listings = self._provider.search(query, limit)
        except (MarketplaceUnavailable, OSError, ValueError):
            cached = self._cache.read() if self._cache else None
            if cached is not None:
                return self._filter(cached, query, limit), True
            return self.featured(limit)[0], True
        listings = self._decorate(listings)
        if self._cache is not None and not query:
            self._cache.write(listings)
        return listings, False

    def _filter(
        self, listings: list[MarketplaceListing], query: str, limit: int
    ) -> list[MarketplaceListing]:
        if not query:
            return listings[:limit]
        needle = query.lower()
        return [
            listing
            for listing in listings
            if needle in listing.name.lower()
            or needle in (listing.title or "").lower()
            or needle in listing.summary.lower()
        ][:limit]

    def featured(self, limit: int = 6) -> tuple[list[MarketplaceListing], bool]:
        """Editor's picks: the curated presets, ranked recommended-first."""
        listings = [listing_from_preset(preset) for preset in PRESETS]
        listings.sort(key=lambda item: (not item.is_recommended, item.name))
        return self._decorate(listings)[:limit], False

    def resolve(self, listing_id: str) -> MarketplaceListing | None:
        """Find one listing by id, for an install request."""
        if listing_id.startswith("preset:"):
            preset_id = listing_id.split(":", 1)[1]
            for preset in PRESETS:
                if preset.id == preset_id:
                    return listing_from_preset(preset)
            return None
        return self._provider.get(listing_id)


def connector_config_from_listing(
    listing: MarketplaceListing,
    *,
    name: str | None = None,
) -> ConnectorConfig:
    """Build a registry entry from a marketplace listing."""
    if not listing.installable or not listing.url:
        raise ValueError(
            listing.unavailable_reason or f"{listing.display_name} has no hosted endpoint"
        )
    settings: dict[str, Any] = {
        "url": listing.url,
        "auth": listing.auth,
        "headers": dict(listing.headers),
        "env_vars": list(listing.env_vars),
        "tools": [],
    }
    return ConnectorConfig(
        name=name or _connector_name(listing),
        kind="mcp",
        enabled=True,
        settings=settings,
    )


def _connector_name(listing: MarketplaceListing) -> str:
    """A short, filesystem-safe registry name derived from the listing."""
    tail = listing.name.rsplit("/", 1)[-1]
    slug = _SLUG_STRIP.sub("-", tail.lower()).strip("-")
    return slug or "connector"


def env_vars_in_listing(listing: MarketplaceListing) -> list[str]:
    """Variables the listing interpolates, whether declared or implied."""
    found: set[str] = set(listing.env_vars)
    for value in [listing.url or "", *listing.headers.values()]:
        found.update(_ENV_VAR_PATTERN.findall(value))
    return sorted(found)


__all__ = [
    "AREA_LABELS",
    "DEFAULT_LIMIT",
    "DOCKER_HUB_NAMESPACE_URL",
    "DockerTrustIndex",
    "MARKETPLACE_CACHE_TTL_SECONDS",
    "MarketplaceCache",
    "MarketplaceListing",
    "MarketplaceProvider",
    "MarketplaceService",
    "MarketplaceUnavailable",
    "OFFICIAL_REGISTRY_URL",
    "OfficialRegistryProvider",
    "connector_config_from_listing",
    "env_vars_in_listing",
    "listing_from_preset",
    "listing_from_registry_record",
]
