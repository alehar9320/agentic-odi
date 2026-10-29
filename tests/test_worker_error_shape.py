"""The Worker returns the one-error-body shape, even when the sidecar is down.

Like `test_worker_security_headers.py`, the Worker has no JS test runner in
this repository, so the contract is pinned by inspecting the source: a dead
tunnel must read as a recoverable, actionable `{"error": StudioError}`
instead of a legacy `{"detail": ...}` blob.
"""

from __future__ import annotations

from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "infra" / "cloudflare" / "worker.ts"


def _source() -> str:
    return WORKER.read_text(encoding="utf-8")


def test_sidecar_not_configured_emits_the_studio_error_shape() -> None:
    source = _source()
    assert 'code: "mcp_unreachable"' in source
    assert 'message: "The studio sidecar isn\'t configured."' in source
    assert "Set SIDECAR_URL and redeploy." in source
    assert "retryable: false" in source


def test_sidecar_unreachable_emits_a_retryable_suggestion() -> None:
    source = _source()
    assert 'message: "The studio sidecar isn\'t reachable."' in source
    assert "python scripts/dev.py" in source
    assert "retryable: true" in source


def test_worker_error_body_keys_match_the_studio_contract() -> None:
    source = _source()
    # Every Worker-generated error projects these fields so the SPA can render
    # a FailurePanel with suggestion and retry.
    for field in ("code", "message", "suggestion", "retryable", "request_id"):
        assert f"{field}:" in source


def test_a_dead_sidecar_still_returns_502() -> None:
    source = _source()
    # Both Worker-originated failures keep the 502 the SPA already treats as
    # "downstream unreachable".
    assert source.count("{ status: 502 }") == 1
