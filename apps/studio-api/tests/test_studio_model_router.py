"""Tests for the multi-tier model router used by the chat endpoint."""

from __future__ import annotations

from agentic_odi_core import ModelRouter, ModelTier, RoutingMode


def test_router_modes() -> None:
    router_auto = ModelRouter(mode=RoutingMode.AUTO)
    # Remote wins in AUTO
    assert (
        router_auto.resolve_tier(remote_available=True, local_available=False)
        == ModelTier.REMOTE_LLM
    )
    # No remote, no local -> deterministic (honest floor)
    assert (
        router_auto.resolve_tier(remote_available=False, local_available=False)
        == ModelTier.DETERMINISTIC
    )
    # Local beats deterministic when remote is down
    assert (
        router_auto.resolve_tier(remote_available=False, local_available=True)
        == ModelTier.LOCAL_LLM
    )

    router_forced_det = ModelRouter(mode=RoutingMode.FORCE_DETERMINISTIC)
    assert (
        router_forced_det.resolve_tier(remote_available=True, local_available=True)
        == ModelTier.DETERMINISTIC
    )

    router_forced_remote = ModelRouter(mode=RoutingMode.FORCE_REMOTE)
    assert (
        router_forced_remote.resolve_tier(remote_available=True, local_available=False)
        == ModelTier.REMOTE_LLM
    )
