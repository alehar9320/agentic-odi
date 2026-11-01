"""`/api/build` tells a support thread which release the hosted Studio runs.

Like `test_worker_error_shape.py`, the Worker has no JS test runner in this
repository, so the contract is pinned by inspecting the source. The route is
the Worker's own answer, not the sidecar's, and it must expose nothing but the
declared version.
"""

from __future__ import annotations

from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "infra" / "cloudflare" / "worker.ts"


def _source() -> str:
    return WORKER.read_text(encoding="utf-8")


def test_the_worker_answers_api_build() -> None:
    source = _source()
    assert '"/api/build"' in source
    # Two deploys of one release must agree, so the only value is the declared
    # var — never a timestamp, never a second key.
    assert 'version: env.RELEASE_VERSION ?? "unknown"' in source
    assert '"Cache-Control": "no-store"' in source


def test_the_build_route_is_answered_before_the_sidecar_proxy() -> None:
    source = _source()
    # A release deployed without a sidecar still has to answer the question.
    build = source.index('"/api/build"')
    proxy = source.index("const sidecar =")
    assert build < proxy


def test_the_build_route_declares_its_var_in_env() -> None:
    # Without the field on `Env`, `env.RELEASE_VERSION` would not typecheck and
    # the var in wrangler.jsonc would be read by nothing.
    assert "RELEASE_VERSION?: string" in _source()


def test_only_get_is_answered() -> None:
    source = _source()
    assert 'if (request.method !== "GET")' in source
    assert "status: 405" in source
    assert 'Allow: "GET"' in source
