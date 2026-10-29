"""Tests for the multi-tier model router used by the chat endpoint."""

from __future__ import annotations

from agentic_odi_core import ModelRouter, ModelTier, RoutingMode


def test_router_modes() -> None:
    router_auto = ModelRouter(mode=RoutingMode.AUTO)
    assert router_auto.resolve_tier(remote_available=True) == ModelTier.REMOTE_LLM
    assert router_auto.resolve_tier(remote_available=False) == ModelTier.ON_DEVICE_LLM

    router_forced_rule = ModelRouter(mode=RoutingMode.FORCE_RULE_BASED)
    assert router_forced_rule.resolve_tier(remote_available=True) == ModelTier.RULE_BASED

    router_forced_remote = ModelRouter(mode=RoutingMode.FORCE_REMOTE)
    assert router_forced_remote.resolve_tier(remote_available=False) == ModelTier.REMOTE_LLM
