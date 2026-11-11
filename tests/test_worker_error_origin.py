"""Every Worker-generated failure says so with `origin: "proxy"`.

The Worker has no JS test runner in this repository, so this contract is pinned
by inspecting the source, the same way `test_worker_error_shape.py` pins the
error shape. The marker is what lets the client tell a Worker-originated
transport failure from a sidecar's own structured 502, so a route that builds a
failure body by hand instead of through `sidecarError()` would silently drop it.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "infra" / "cloudflare" / "worker.ts"


def _source() -> str:
    return WORKER.read_text(encoding="utf-8")


def test_the_factory_marks_every_body_as_proxy_origin() -> None:
    source = _source()
    factory = source[source.index("function sidecarError(") : source.index("function localCapabilitiesResponse(")]
    assert 'origin: "proxy"' in factory


def test_the_no_sidecar_502_carries_the_proxy_origin() -> None:
    source = _source()
    # The one route the Worker answers itself without a sidecar is the
    # `mcp_unreachable` 502; it must still route through the factory.
    assert "sidecarError(" in source
    assert 'code: "mcp_unreachable"' in source
    assert "The studio sidecar isn't configured." in source


def test_capabilities_does_not_go_through_the_error_factory() -> None:
    source = _source()
    # `/api/capabilities` is a real answer, not a failure, so it must not carry
    # an error body at all.
    assert "localCapabilitiesResponse(env)" in source
    capabilities = source[
        source.index("function localCapabilitiesResponse(") : source.index("export default {")
    ]
    assert "sidecarError(" not in capabilities


def test_no_failure_body_bypasses_the_factory() -> None:
    source = _source()
    # The factory is the only place a Worker error body is built: every
    # `{"error": ...}` literal lives inside it. A second hand-rolled body would
    # be the one that forgets `origin`.
    assert source.count("error: {") == 1
    # Every failure path returns through the factory, so count the call sites
    # rather than trusting a single grep.
    assert len(re.findall(r"sidecarError\(", source)) >= 4
