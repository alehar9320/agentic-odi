"""REST and webhook connector kinds.

Both kinds share one HTTP puller: a REST endpoint returns a JSON document, and a
webhook connector posts a configured request (usually to a webhook inbox or a
subscription endpoint) and normalizes the JSON response. The transport is
injectable so tests never touch the network.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from agentic_odi_connectors.models import (
    HealthStatus,
    IngestBatch,
    IngestRecord,
    RestConnectorSettings,
)
from agentic_odi_connectors.paths import cache_path
from agentic_odi_connectors.protocol import Connector

FetchResult = tuple[int, bytes]
Fetcher = Callable[[str, str, dict[str, str], bytes | None, float], FetchResult]

# Health probes are harmless but not free: the studio polls connectors often,
# and two probes within half a minute would report the same system.
HEALTH_CACHE_TTL_SECONDS = 30.0


def _load_health_cache() -> dict[str, Any]:
    try:
        payload = json.loads(cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_health_cache(cache: dict[str, Any]) -> None:
    path = cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache), encoding="utf-8")
    except OSError:
        # A cache that cannot be written is a missed optimization, not a
        # failed health check.
        return


def clear_health_cache(name: str | None = None) -> None:
    """Forget cached health results, for one connector or all of them."""
    cache = _load_health_cache()
    if name is None:
        cache.clear()
    else:
        cache.pop(name, None)
    _save_health_cache(cache)


def _cached_health(name: str) -> HealthStatus | None:
    entry = _load_health_cache().get(name)
    if not isinstance(entry, dict):
        return None
    checked_at = entry.get("checked_at")
    status = entry.get("status")
    if not isinstance(checked_at, int | float) or not isinstance(status, dict):
        return None
    if time.time() - checked_at > HEALTH_CACHE_TTL_SECONDS:
        return None
    cached = HealthStatus(**status)
    cached.details["cached"] = True
    return cached


def _store_health(name: str, status: HealthStatus) -> None:
    cache = _load_health_cache()
    cache[name] = {"checked_at": time.time(), "status": status.model_dump()}
    _save_health_cache(cache)


# A malformed cursor chain must not become an unbounded crawl.
MAX_PAGES = 100


def _default_fetch(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout: float,
) -> FetchResult:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        return int(response.status), response.read()


def _lookup(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


class RestConnector(Connector):
    """Pulls JSON records from an HTTP endpoint into the ingest sink."""

    kind = "rest"

    def __init__(
        self,
        name: str,
        settings: RestConnectorSettings,
        *,
        kind: str | None = None,
        fetcher: Fetcher | None = None,
    ) -> None:
        self.name = name
        self.settings = settings
        self.kind = kind or type(self).kind
        self._fetch = fetcher or _default_fetch

    def _request(self, url: str | None = None) -> FetchResult:
        body = None
        headers = dict(self.settings.headers)
        if self.settings.json_body is not None:
            body = json.dumps(self.settings.json_body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        return self._fetch(
            self.settings.method,
            url or self.settings.url,
            headers,
            body,
            self.settings.timeout,
        )

    def _next_url(self, payload: Any) -> str | None:
        """Resolve the next page the response points at, when paging is on."""
        if self.settings.pagination is None:
            return None
        value = _lookup(payload, self.settings.pagination.next_path)
        if not isinstance(value, str) or not value:
            return None
        if value.startswith(("http://", "https://")):
            return value
        # A relative cursor (e.g. "/records?page=2") is relative to the
        # request that produced it, not to the process working directory.
        return urllib.parse.urljoin(self.settings.url, value)

    def _items(self, payload: Any) -> list[Any]:
        if self.settings.records_key:
            extracted = _lookup(payload, self.settings.records_key)
            if isinstance(extracted, list):
                return extracted
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("records", "items", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        return [payload]

    def _record(self, item: Any, index: int) -> IngestRecord:
        if isinstance(item, dict):
            name = str(
                item.get("name")
                or item.get("title")
                or item.get("id")
                or f"{self.name}-{index + 1}"
            )
            content = None
            for key in ("content", "text", "description", "body", "summary"):
                if isinstance(item.get(key), str):
                    content = item[key]
                    break
            if content is None:
                content = json.dumps(item, indent=2, default=str)
            raw = item
        elif isinstance(item, str):
            name = f"{self.name}-{index + 1}"
            content = item
            raw = {"value": item}
        else:
            name = f"{self.name}-{index + 1}"
            content = json.dumps(item, default=str)
            raw = {"value": item}
        return IngestRecord(
            source_name=self.name,
            source_kind=self.kind,
            item_type=self.settings.item_type,
            name=name,
            content=content,
            raw=raw,
        )

    async def health(self) -> HealthStatus:
        cached = _cached_health(self.name)
        if cached is not None:
            return cached
        try:
            status, _ = self._request()
        except Exception as exc:  # noqa: BLE001
            result = HealthStatus(ok=False, message=str(exc))
        else:
            ok = 200 <= status < 400
            result = HealthStatus(
                ok=ok,
                message="reachable" if ok else f"HTTP {status}",
                details={"status": status, "url": self.settings.url},
            )
        _store_health(self.name, result)
        return result

    async def ingest(self) -> IngestBatch:
        batch = IngestBatch(connector_name=self.name)
        url: str | None = None
        seen: set[str] = set()
        for _ in range(MAX_PAGES):
            try:
                status, body = self._request(url)
            except Exception as exc:  # noqa: BLE001
                batch.errors.append(str(exc))
                return batch
            if not 200 <= status < 400:
                batch.errors.append(f"HTTP {status} from {url or self.settings.url}")
                return batch
            text = body.decode("utf-8", errors="replace")
            try:
                payload: Any = json.loads(text)
            except json.JSONDecodeError:
                payload = text
            records = self._items(payload)
            for item in records:
                batch.records.append(self._record(item, len(batch.records)))
            next_url = self._next_url(payload)
            if next_url is None or next_url in seen:
                return batch
            seen.add(next_url)
            url = next_url
        batch.errors.append(f"Stopped after {MAX_PAGES} pages; pagination did not terminate.")
        return batch


class WebhookConnector(RestConnector):
    """Posts to a webhook endpoint and ingests the JSON response."""

    kind = "webhook"
