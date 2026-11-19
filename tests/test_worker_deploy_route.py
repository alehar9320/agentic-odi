"""`/api/deploy` tells a probe which commit and which bundle this artifact is.

Like `test_worker_build_route.py`, the Worker has no JS test runner in this
repository, so the contract is pinned by reading the source. The distinction that
matters is the one between the two routes: `GET /api/build` answers with the
release tag and deliberately never with a deploy timestamp (`docs/deployment.md`),
which is exactly why it cannot answer the question #612 asks — did the merge reach
the branch that deploys? So `/api/deploy` carries the commit, the build id, and the
bundle the Worker's own asset shelf serves, and it answers before the sidecar
proxy because a deploy without a sidecar still has to be identifiable.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "infra" / "cloudflare" / "worker.ts"
WRANGLER = ROOT / "wrangler.jsonc"


def _source() -> str:
    return WORKER.read_text(encoding="utf-8")


def _deploy_branch() -> str:
    """The `if (url.pathname === "/api/deploy")` block, up to the sidecar proxy."""
    source = _source()
    start = source.index('url.pathname === "/api/deploy"')
    return source[start : source.index("const sidecar =")]


def test_the_worker_answers_api_deploy() -> None:
    source = _source()
    assert 'url.pathname === "/api/deploy"' in source
    assert 'commit: env.COMMIT_SHA ?? "unknown"' in source
    assert 'build_id: env.BUILD_ID ?? "unknown"' in source
    assert '"Cache-Control": "no-store"' in source


def test_the_deploy_route_is_answered_before_the_sidecar_proxy() -> None:
    source = _source()
    # A deploy with no sidecar configured still has to say what it is.
    assert source.index('"/api/deploy"') < source.index("const sidecar =")


def test_the_deploy_route_declares_its_vars_in_env() -> None:
    # Without the fields on `Env` the reads would not typecheck and the vars in
    # wrangler.jsonc would be read by nothing.
    source = _source()
    assert "COMMIT_SHA?: string" in source
    assert "BUILD_ID?: string" in source


def test_the_deploy_route_names_the_bundle_the_asset_shelf_serves() -> None:
    #: "Worker new, page stale" is only detectable if the Worker reports the bundle it
    #: would serve, read from its own assets binding rather than echoed from a var.
    branch = _deploy_branch()
    assert "env.ASSETS.fetch" in branch
    assert ".match(" in branch
    assert "index-" in branch
    assert "entry" in branch


def test_only_get_is_answered() -> None:
    branch = _deploy_branch()
    assert 'request.method !== "GET"' in branch
    assert "status: 405" in branch
    assert 'Allow: "GET"' in branch


def test_the_deploy_vars_are_declared_as_public_and_default_to_unknown() -> None:
    config = WRANGLER.read_text(encoding="utf-8")
    vars_block = config[config.index('"vars"') : config.index("}", config.index('"vars"'))]
    assert '"COMMIT_SHA": "unknown"' in vars_block
    assert '"BUILD_ID": "unknown"' in vars_block
    #: The route is public by design, so nothing that looks like a credential may
    #: ride in the vars it reads.
    for forbidden in ("secret", "SIDECAR_URL", "KEY"):
        assert forbidden not in vars_block
