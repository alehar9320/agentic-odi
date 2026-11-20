"""`/api/capabilities` states its method, like the two routes beside it.

Like `test_worker_build_route.py`, the Worker has no JS test runner in this
repository, so the contract is pinned by inspecting the source. Without a
sidecar the Worker answers the route itself with the local-only manifest; the
point of this test is that it answers only `GET`, and that every other verb gets
the shared 405 with `Allow: GET` rather than a 200 that reads as accepted.
"""

from __future__ import annotations

from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "infra" / "cloudflare" / "worker.ts"


def _source() -> str:
    return WORKER.read_text(encoding="utf-8")


def _capabilities_branch() -> str:
    """The `!sidecar` capabilities branch, up to the sidecar-unreachable error."""
    source = _source()
    start = source.index('url.pathname === "/api/capabilities"')
    return source[start : source.index("console.error", start)]


def test_get_returns_the_local_manifest() -> None:
    branch = _capabilities_branch()
    # The manifest is the Worker's own answer, served for GET on both spellings.
    assert 'url.pathname === "/api/capabilities"' in branch
    assert 'url.pathname === "/api/capabilities/"' in branch
    assert "localCapabilitiesResponse(env)" in branch


def test_post_returns_405_with_allow() -> None:
    branch = _capabilities_branch()
    assert 'request.method !== "GET"' in branch
    # The 405 goes through the shared error body, so `origin: "proxy"` marks it
    # as the Worker's own answer.
    assert "sidecarError(" in branch
    assert "status: 405" in branch
    assert 'Allow: "GET"' in branch
    assert 'code: "method_not_allowed"' in branch
    assert 'origin: "proxy"' in _source()


def test_head_is_rejected_like_post() -> None:
    # A single method test rejects every non-GET verb, HEAD and POST alike.
    branch = _capabilities_branch()
    assert branch.index('request.method !== "GET"') < branch.index("localCapabilitiesResponse(env)")
