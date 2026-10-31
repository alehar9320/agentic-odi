"""Model Router module.

Provides multi-tier routing (Deterministic, Local LLM, Remote LLM) with
automatic fallback and user settings support.

Tier 0 — ``deterministic``: the honest rule-based responder. Always available.
Never fabricates numbers, scores, or customer names.
Tier 1 — ``local``: an OpenAI-compatible client for a locally-run model server.
Available if and only if the endpoint answers (real probe, TTL-cached).
Tier 2 — ``remote``: the configured OpenAI-compatible cloud endpoint.
"""

from __future__ import annotations

import asyncio
import socket
import time
from collections.abc import AsyncIterator, Callable
from enum import Enum
from urllib.parse import urlparse

from agentic_odi_core.steve_jobs import generate_steve_jobs_response


class ModelTier(str, Enum):
    """Model execution tiers."""

    DETERMINISTIC = "deterministic"  # Tier 0: honest rule-based responder, always on
    LOCAL_LLM = "local"  # Tier 1: OpenAI-compatible client for a local model server
    REMOTE_LLM = "remote"  # Tier 2: configured cloud LLM backend


class RoutingMode(str, Enum):
    """Routing modes for model selection."""

    AUTO = "auto"  # Auto-select smartest available tier, transparent fallback
    FORCE_DETERMINISTIC = "deterministic"  # Force Tier 0
    FORCE_LOCAL = "local"  # Force Tier 1
    FORCE_REMOTE = "remote"  # Force Tier 2


class LocalOpenAIEngine:
    """Honest OpenAI-compatible client for a locally-run model server.

    This is a *client*, not a bundled engine: the Studio does not ship a model.
    The engine is available if and only if the configured local endpoint answers.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8001/v1",
        api_key: str = "local",
        model_name: str | None = None,
        timeout: float = 2.0,
        ttl_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        self.ttl_seconds = ttl_seconds
        self._cached_available: bool | None = None
        self._cached_at: float | None = None

    def is_available(self) -> bool:
        """Probe the local endpoint with a short timeout.

        Results are cached with a TTL so the probe is not run on every turn.
        Never returns True by default.
        """
        now = time.monotonic()
        if (
            self._cached_available is not None
            and self._cached_at is not None
            and self.ttl_seconds > 0
            and now - self._cached_at < self.ttl_seconds
        ):
            return self._cached_available
        available = self._probe()
        self._cached_available = available
        self._cached_at = now
        return available

    def _probe(self) -> bool:
        try:
            parsed = urlparse(self.base_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            with socket.create_connection((host, port), timeout=self.timeout):
                return True
        except OSError:
            return False


class ModelRouter:
    """Intelligent router managing multi-tier execution and seamless fallback."""

    def __init__(
        self,
        mode: RoutingMode = RoutingMode.AUTO,
        local_engine: LocalOpenAIEngine | None = None,
        remote_health_checker: Callable[[], tuple[bool, str]] | None = None,
    ) -> None:
        self.mode = mode
        self.local_engine = local_engine or LocalOpenAIEngine()
        self.remote_health_checker = remote_health_checker

    def resolve_tier(
        self,
        remote_available: bool = False,
        local_available: bool | None = None,
    ) -> ModelTier:
        """Resolve the appropriate tier based on routing mode and availability.

        ``local_available`` defaults to probing the local engine. Forced modes
        return the requested tier even when unavailable — the caller is
        responsible for reporting a forced-mode failure rather than silently
        falling back.
        """
        if local_available is None:
            local_available = self.local_engine.is_available()

        if self.mode == RoutingMode.FORCE_DETERMINISTIC:
            return ModelTier.DETERMINISTIC
        if self.mode == RoutingMode.FORCE_LOCAL:
            return ModelTier.LOCAL_LLM
        if self.mode == RoutingMode.FORCE_REMOTE:
            return ModelTier.REMOTE_LLM

        # AUTO mode logic: remote > local > deterministic
        if remote_available:
            return ModelTier.REMOTE_LLM
        if local_available:
            return ModelTier.LOCAL_LLM
        return ModelTier.DETERMINISTIC

    async def generate_fallback_stream(self, prompt: str, tier: ModelTier) -> AsyncIterator[str]:
        """Stream response for deterministic or local fallback tiers.

        The deterministic tier is honest: it never fabricates scores or data.
        """
        text = generate_steve_jobs_response(prompt)
        words = text.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else " " + word
            yield chunk
            await asyncio.sleep(0.005)
