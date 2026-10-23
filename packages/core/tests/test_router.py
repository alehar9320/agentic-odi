import pytest
from agentic_odi_core.router import ModelRouter, ModelTier, RoutingMode
from agentic_odi_core.steve_jobs import (
    generate_steve_jobs_response,
)


def test_steve_jobs_formatting():
    res = generate_steve_jobs_response("calculate score 9.0 3.0")
    assert "Breakthrough Opportunity" in res
    assert "15.00" in res

    res_guidelines = generate_steve_jobs_response("what are the guidelines")
    assert "Outcome-Driven Innovation (ODI)" in res_guidelines
    assert "Stage 1" in res_guidelines

    res_sim = generate_steve_jobs_response("simulate impact")
    assert "Impact Simulation" in res_sim


def test_model_router_tier_resolution():
    router = ModelRouter(mode=RoutingMode.AUTO)
    assert router.resolve_tier(remote_available=True) == ModelTier.REMOTE_LLM
    assert router.resolve_tier(remote_available=False) == ModelTier.ON_DEVICE_LLM

    router_forced_rule = ModelRouter(mode=RoutingMode.FORCE_RULE_BASED)
    assert router_forced_rule.resolve_tier(remote_available=True) == ModelTier.RULE_BASED

    router_forced_remote = ModelRouter(mode=RoutingMode.FORCE_REMOTE)
    assert router_forced_remote.resolve_tier(remote_available=False) == ModelTier.REMOTE_LLM


@pytest.mark.asyncio
async def test_fallback_stream():
    router = ModelRouter(mode=RoutingMode.AUTO)
    chunks = []
    async for chunk in router.generate_fallback_stream("hello", ModelTier.RULE_BASED):
        chunks.append(chunk)
    full_text = "".join(chunks)
    assert 'I received your intent: **"hello"**.' in full_text
