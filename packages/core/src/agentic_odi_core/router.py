"""On-Device Fallback & Model Router module.

Provides multi-tier routing (Rule-based, On-Device Local LLM, Remote Smart LLM)
with automatic fallback and user settings support.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from enum import Enum

from agentic_odi_core.steve_jobs import generate_steve_jobs_response


class ModelTier(str, Enum):
    """Model execution tiers."""

    RULE_BASED = "rule_based"  # Tier 0: On-device instant rule-based engine (Steve Jobs pass)
    ON_DEVICE_LLM = "on_device_llm"  # Tier 1: On-device / local GGUF / tiny model engine
    REMOTE_LLM = "remote_llm"  # Tier 2: Remote / smart cloud LLM backend


class RoutingMode(str, Enum):
    """Routing modes for model selection."""

    AUTO = "auto"  # Auto-select smartest available tier, transparent fallback
    FORCE_RULE_BASED = "rule_based"  # Force Tier 0
    FORCE_ON_DEVICE = "on_device"  # Force Tier 1
    FORCE_REMOTE = "remote"  # Force Tier 2


class OnDeviceLLMEngine:
    """Minimal lightweight on-device LLM engine wrapper / mock interface."""

    def __init__(self, model_name: str = "on-device-tiny-llm") -> None:
        self.model_name = model_name

    def is_available(self) -> bool:
        """Check if on-device model files/runtime are ready."""
        return True

    async def generate_stream(self, prompt: str) -> AsyncIterator[str]:
        """Generate response chunks from on-device model."""
        response = generate_steve_jobs_response(prompt)
        words = response.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else " " + word
            yield chunk
            await asyncio.sleep(0.01)


class ModelRouter:
    """Intelligent router managing multi-tier execution and seamless fallback."""

    def __init__(
        self,
        mode: RoutingMode = RoutingMode.AUTO,
        on_device_engine: OnDeviceLLMEngine | None = None,
        remote_health_checker: Callable[[], tuple[bool, str]] | None = None,
    ) -> None:
        self.mode = mode
        self.on_device_engine = on_device_engine or OnDeviceLLMEngine()
        self.remote_health_checker = remote_health_checker

    def resolve_tier(self, remote_available: bool = False) -> ModelTier:
        """Resolve the appropriate tier based on routing mode and availability."""
        if self.mode == RoutingMode.FORCE_RULE_BASED:
            return ModelTier.RULE_BASED
        if self.mode == RoutingMode.FORCE_ON_DEVICE:
            return ModelTier.ON_DEVICE_LLM
        if self.mode == RoutingMode.FORCE_REMOTE:
            return ModelTier.REMOTE_LLM

        # AUTO mode logic
        if remote_available:
            return ModelTier.REMOTE_LLM
        if self.on_device_engine.is_available():
            return ModelTier.ON_DEVICE_LLM
        return ModelTier.RULE_BASED

    async def generate_fallback_stream(self, prompt: str, tier: ModelTier) -> AsyncIterator[str]:
        """Stream response for rule-based or on-device fallback tiers."""
        if tier == ModelTier.ON_DEVICE_LLM:
            async for chunk in self.on_device_engine.generate_stream(prompt):
                yield chunk
        else:
            # Rule-based Tier 0
            text = generate_steve_jobs_response(prompt)
            words = text.split(" ")
            for i, word in enumerate(words):
                chunk = word if i == 0 else " " + word
                yield chunk
                await asyncio.sleep(0.005)
