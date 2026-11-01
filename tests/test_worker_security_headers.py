"""The Cloudflare Worker puts security headers on every Response.

The Worker is TypeScript with no JS test runner in this repository, so this
test pins the contract in the source: the header constants that a preview
deployment is smoke-tested against, and the helper that applies them to the
asset path, the proxy path, and both error paths.
"""

from __future__ import annotations

from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "infra" / "cloudflare" / "worker.ts"

REQUIRED_HEADERS = {
    "Content-Security-Policy",
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Referrer-Policy",
    "Permissions-Policy",
}

REQUIRED_CSP_DIRECTIVES = {
    "default-src 'self'",
    # 'wasm-unsafe-eval' lets the edge model engine compile WebGPU shader
    # modules; script-src stays locked to 'self' otherwise.
    "script-src 'self' 'wasm-unsafe-eval'",
    "connect-src 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
}

# The edge model engine's wasm and quantized-weight fetches must survive the
# hosted CSP, so their origins are curated in the Worker.
REQUIRED_EDGE_MODEL_ORIGINS = {
    "https://huggingface.co",
    "https://raw.githubusercontent.com",
    "https://cdn.jsdelivr.net",
}


def _source() -> str:
    return WORKER.read_text(encoding="utf-8")


def test_every_required_header_is_declared() -> None:
    source = _source()
    for name in REQUIRED_HEADERS:
        assert f'"{name}"' in source, f"{name} is missing from the Worker"


def test_the_declared_values_match_the_policy() -> None:
    source = _source()
    assert '"X-Content-Type-Options": "nosniff"' in source
    assert '"X-Frame-Options": "DENY"' in source
    assert '"Referrer-Policy": "strict-origin-when-cross-origin"' in source
    assert '"Permissions-Policy": "geolocation=(), camera=(), microphone=()"' in source


def test_the_content_security_policy_covers_the_studio() -> None:
    source = _source()
    for directive in REQUIRED_CSP_DIRECTIVES:
        assert directive in source, f"{directive} is missing from the CSP"


def test_the_csp_lets_the_edge_model_fetch_its_weights() -> None:
    source = _source()
    for origin in REQUIRED_EDGE_MODEL_ORIGINS:
        assert origin in source, f"{origin} is missing from connect-src"


def test_every_response_path_applies_the_headers() -> None:
    source = _source()
    # Assets, local capabilities, the configured-sidecar error, the proxy, and
    # the unreachable error.
    assert source.count("return secure(") == 5
    assert source.count("secure(\n        await fetch(") == 1
    assert "new Response(response.body, {" in source, (
        "the header helper must reuse the body stream so SSE keeps streaming"
    )
