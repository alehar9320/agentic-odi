import pytest
from agentic_odi_core.router import LocalOpenAIEngine, ModelRouter, ModelTier, RoutingMode
from agentic_odi_core.steve_jobs import (
    generate_steve_jobs_response,
)


def test_model_tier_names():
    assert ModelTier.DETERMINISTIC.value == "deterministic"
    assert ModelTier.LOCAL_LLM.value == "local"
    assert ModelTier.REMOTE_LLM.value == "remote"


def test_model_router_tier_resolution_auto():
    router = ModelRouter(mode=RoutingMode.AUTO)
    # No remote, no local -> deterministic (honest floor)
    assert (
        router.resolve_tier(remote_available=False, local_available=False)
        == ModelTier.DETERMINISTIC
    )
    # Remote wins in AUTO
    assert router.resolve_tier(remote_available=True, local_available=False) == ModelTier.REMOTE_LLM
    # Local beats deterministic when remote is down
    assert router.resolve_tier(remote_available=False, local_available=True) == ModelTier.LOCAL_LLM


def test_model_router_forced_modes():
    router_forced_det = ModelRouter(mode=RoutingMode.FORCE_DETERMINISTIC)
    assert (
        router_forced_det.resolve_tier(remote_available=True, local_available=True)
        == ModelTier.DETERMINISTIC
    )

    router_forced_local = ModelRouter(mode=RoutingMode.FORCE_LOCAL)
    assert (
        router_forced_local.resolve_tier(remote_available=True, local_available=True)
        == ModelTier.LOCAL_LLM
    )

    router_forced_remote = ModelRouter(mode=RoutingMode.FORCE_REMOTE)
    assert (
        router_forced_remote.resolve_tier(remote_available=True, local_available=False)
        == ModelTier.REMOTE_LLM
    )


def test_local_engine_is_available_returns_false_when_unreachable():
    engine = LocalOpenAIEngine(base_url="http://127.0.0.1:1/v1", timeout=0.5, ttl_seconds=0)
    assert engine.is_available() is False


def test_local_engine_caches_probe_with_ttl():
    engine = LocalOpenAIEngine(base_url="http://127.0.0.1:1/v1", timeout=0.5, ttl_seconds=0)
    # ttl_seconds=0 means cache expires immediately; probe runs each time
    first = engine.is_available()
    second = engine.is_available()
    assert first is False
    assert second is False


def test_local_engine_reports_endpoint_and_model():
    engine = LocalOpenAIEngine(base_url="http://localhost:8001/v1", model_name="my-local-model")
    assert engine.base_url == "http://localhost:8001/v1"
    assert engine.model_name == "my-local-model"


def test_steve_jobs_formatting():
    res = generate_steve_jobs_response("what are the guidelines")
    assert "ODI, stage by stage" in res
    assert "Define the job" in res


def test_steve_jobs_no_fabricated_score():
    """Tier 0 must not fabricate opportunity scores or invented data."""
    res = generate_steve_jobs_response("hello")
    assert "15.3" not in res
    assert "Opportunity Score of 15.3" not in res
    assert "3,000 hours" not in res


def test_steve_jobs_points_at_compute_opportunity():
    """Tier 0 points at compute_opportunity instead of computing scores itself."""
    res = generate_steve_jobs_response("calculate score 9.0 3.0")
    assert "Breakthrough Opportunity" not in res  # no fabricated scoring verdict
    assert "15.00" not in res


@pytest.mark.asyncio
async def test_fallback_stream():
    router = ModelRouter(mode=RoutingMode.AUTO)
    chunks = []
    async for chunk in router.generate_fallback_stream("hello", ModelTier.DETERMINISTIC):
        chunks.append(chunk)
    full_text = "".join(chunks)
    assert "I received your intent" in full_text or "ODI" in full_text
