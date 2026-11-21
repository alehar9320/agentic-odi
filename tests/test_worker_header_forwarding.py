"""The Worker forwards an explicit allowlist of headers to the sidecar.

The Worker is TypeScript with no JS test runner in this repository, so this
test pins the contract in the source: the allowlist the proxy branch builds
from the client request, the absence of the old copy-and-delete behaviour
that forwarded everything except host and cf-connecting-ip, and the
exclusion of `accept-encoding` (the Worker's own fetch negotiates encoding).
"""

from __future__ import annotations

from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "infra" / "cloudflare" / "worker.ts"

# Headers the sidecar asks for. The order is not asserted: the loop builds a
# fresh Headers, so the order in the source is a comment, not a contract.
FORWARDED_HEADERS = [
    "authorization",
    "content-type",
    "accept",
    "accept-language",
    "x-request-id",
]

# Headers a browser sends that must never cross the tunnel, because they are
# useless to the sidecar and logged by anything that logs headers.
PROHIBITED_HEADERS = [
    "cookie",
    "origin",
    "referer",
    "accept-encoding",
]


def _source() -> str:
    return WORKER.read_text(encoding="utf-8")


def test_the_allowlist_is_explicit_and_matches_the_policy() -> None:
    source = _source()
    for name in FORWARDED_HEADERS:
        assert f'"{name}"' in source, f"{name} is missing from the forwarded allowlist"
    assert "FORWARDED_HEADERS" in source, "the proxy branch must declare an allowlist"


def test_prohibited_headers_are_neither_copied_nor_deleted() -> None:
    source = _source()
    for name in PROHIBITED_HEADERS:
        assert f'"{name}"' not in source, (
            f"{name} must not appear in the Worker: the allowlist forwards "
            f"nothing by default, so deleting it would be a no-op that reads "
            f"as if the header crossed the tunnel"
        )


def test_the_old_copy_and_delete_behaviour_is_gone() -> None:
    source = _source()
    assert "new Headers(request.headers)" not in source, (
        "the proxy branch must not copy the client's headers wholesale"
    )
    assert 'headers.delete("host")' not in source, (
        "the proxy branch must not delete host: the allowlist builds a fresh "
        "Headers, so host is never present"
    )
    assert 'headers.delete("cf-connecting-ip")' not in source, (
        "the proxy branch must not delete cf-connecting-ip: the allowlist "
        "builds a fresh Headers, so cf-connecting-ip is never present"
    )


def test_missing_allowlisted_headers_are_skipped_not_required() -> None:
    source = _source()
    assert "request.headers.get(name)" in source, (
        "the loop must read each allowlisted header from the client request"
    )
    assert "value !== null" in source, (
        "the loop must skip headers the client did not send, so a request "
        "without Accept-Language still reaches the sidecar"
    )


def test_accept_encoding_is_excluded_from_the_allowlist() -> None:
    source = _source()
    assert '"accept-encoding"' not in source, (
        "accept-encoding must not be forwarded: the Worker's own fetch "
        "negotiates encoding, and forwarding it can produce a double-encoded "
        "stream"
    )
