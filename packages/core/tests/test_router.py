import pytest
from agentic_odi_core.router import ModelRouter, ModelTier, OnDeviceLLMEngine, RoutingMode
from agentic_odi_core.steve_jobs import (
    format_opportunity_score_insight,
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


@pytest.mark.asyncio
async def test_steve_jobs_full_branches():
    router = ModelRouter(mode=RoutingMode.AUTO)
    # Test formula formatting
    res1 = format_opportunity_score_insight(10.0, 10.0, "Maintain outcome")
    assert "Appropriately Served" in res1
    assert "Maintain outcome" in res1

    res2 = format_opportunity_score_insight(6.0, 9.0)
    assert "Overserved Target" in res2

    # Test Steve Jobs generator keyword paths
    assert "Causal Lineage" in generate_steve_jobs_response("evidence from calls")
    assert "Outcome-Driven Innovation" in generate_steve_jobs_response(
        "how does this stage framework work"
    )
    assert "Impact Simulation" in generate_steve_jobs_response("simulate friction bet")

    # Test OnDeviceLLMEngine stream
    engine = OnDeviceLLMEngine()
    assert engine.is_available() is True
    chunks = []
    async for c in engine.generate_stream("hi"):
        chunks.append(c)
    assert len(chunks) > 0

    # Test fallback stream for ON_DEVICE_LLM tier
    on_device_chunks = []
    async for c in router.generate_fallback_stream("test on device", ModelTier.ON_DEVICE_LLM):
        on_device_chunks.append(c)
    assert len(on_device_chunks) > 0
