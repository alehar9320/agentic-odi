"""The hosted probe: what it must answer, and what a failure must look like.

`scripts/verify-hosted-first-run.sh` asks the deployed Worker the questions this
repository answers in its README, and the answers are only trustworthy if the
probe refuses a wrong one loudly. A live run cannot be asserted in CI — production
belongs to whoever deploys it — so these tests point the probe at a stub that
answers exactly like production does, good and bad, and check what it prints and
what it exits.

The promise names below are the contract: the issue asks for one dated line per
named promise, and for the offending response body on a failure rather than a bare
exit code. A check that cannot fail is not a check, so every failing fixture here
is a production response that really occurred.
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify-hosted-first-run.sh"
PRODUCTION_HOST = "agentic-odi.alehar.workers.dev"

Entry = tuple[int, str]
Answer = Entry | Callable[[int], Entry]

_DEPLOY = {"build_id": "b7f3c1", "commit": "deadbeefcafe", "entry": "assets/index-AAA.js"}
_CAPABILITIES = {
    "capabilities": [
        {"id": "local-data", "available": True},
        {"id": "local-memory", "available": True},
        {"id": "deterministic-assistant", "available": True},
        {"id": "browser-model", "available": False},
    ]
}
_SIDECAR_DOWN = {"error": {"code": "sidecar_unavailable", "message": "SIDECAR_URL is not set"}}
_MCP_UNREACHABLE = {
    "error": {
        "code": "mcp_unreachable",
        "message": "The studio sidecar isn't configured.",
        "suggestion": "Set SIDECAR_URL and redeploy.",
    }
}
_INDEX = "<!doctype html><html><body><script src='/assets/index-AAA.js'></script></body></html>"


def _good_routes(
    overrides: dict[tuple[str, str], Answer] | None = None,
) -> dict[tuple[str, str], Answer]:
    routes: dict[tuple[str, str], Answer] = {
        ("GET", "/api/deploy"): (200, json.dumps(_DEPLOY)),
        ("GET", "/api/capabilities"): (200, json.dumps(_CAPABILITIES)),
        ("POST", "/api/jobs"): (502, json.dumps(_SIDECAR_DOWN)),
        ("GET", "/api/canvas"): (502, json.dumps(_SIDECAR_DOWN)),
        ("GET", "/"): (200, _INDEX),
    }
    routes.update(overrides or {})
    return routes


@contextlib.contextmanager
def _stub(routes: dict[tuple[str, str], Answer]):
    """A stand-in for the deployed Worker: answers fixed routes, 404s the rest."""
    counts: dict[tuple[str, str], int] = {}

    class Handler(BaseHTTPRequestHandler):
        def _answer(self) -> None:
            key = (self.command, self.path.split("?")[0])
            counts[key] = counts.get(key, 0) + 1
            if key not in routes:
                self.send_response(404)
                self.end_headers()
                return
            answer = routes[key]
            status, body = answer(counts[key]) if callable(answer) else answer  # type: ignore[operator]
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            self._answer()

        def do_POST(self) -> None:
            self._answer()

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _probe(base_url: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), "--base-url", base_url, "--wait", "2", "--interval", "1", *extra],
        capture_output=True,
        text=True,
        timeout=90,
    )


def test_every_kept_promise_reports_one_dated_pass() -> None:
    with _stub(_good_routes()) as url:
        result = _probe(url, "--commit", _DEPLOY["commit"])

    assert result.returncode == 0, result.stdout + result.stderr
    for promise in (
        "local data is advertised",
        "local memory is advertised",
        "the deterministic assistant is advertised",
        "a job write falls back in a code the browser understands",
        "the canvas falls back in a code the browser understands",
        "the entry page names its bundle",
        "the served bundle belongs to the deploy that claims it",
        "the deploy reports this commit",
    ):
        assert promise in result.stdout, f"{promise!r} was never reported"
    for line in result.stdout.splitlines():
        if "PASS" in line or "FAIL" in line:
            assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z ", line), line


def test_a_write_path_that_answers_mcp_unreachable_fails_and_prints_the_body() -> None:
    #: This is production today: `mcp_unreachable` is the body that stops the browser
    #: serving the local capabilities it advertised a moment earlier.
    broken = _good_routes(
        {
            ("POST", "/api/jobs"): (502, json.dumps(_MCP_UNREACHABLE)),
            ("GET", "/api/canvas"): (502, json.dumps(_MCP_UNREACHABLE)),
        }
    )

    with _stub(broken) as url:
        result = _probe(url, "--commit", _DEPLOY["commit"])

    assert result.returncode != 0
    failing = [line for line in result.stdout.splitlines() if "FAIL" in line]
    assert any("job write" in line for line in failing), result.stdout
    assert any("sidecar_unavailable" in line for line in failing), result.stdout
    assert "mcp_unreachable" in result.stdout


def test_a_capability_that_reports_itself_unavailable_fails_the_probe() -> None:
    unavailable = _good_routes(
        {
            (
                "GET",
                "/api/capabilities",
            ): (
                200,
                json.dumps(
                    {
                        "capabilities": [
                            {"id": "local-data", "available": False},
                            {"id": "local-memory", "available": True},
                            {"id": "deterministic-assistant", "available": True},
                        ]
                    }
                ),
            )
        }
    )

    with _stub(unavailable) as url:
        result = _probe(url, "--commit", _DEPLOY["commit"])

    assert result.returncode != 0
    assert any("local data" in line and "FAIL" in line for line in result.stdout.splitlines()), (
        result.stdout
    )


def test_a_bundle_that_the_deploy_does_not_claim_fails_with_both_names() -> None:
    #: A CDN holding the previous `index.html` while the Worker moved on: the page
    #: serves one bundle, the deploy reports another.
    stale = _good_routes({("GET", "/"): (200, "<script src='/assets/index-OLD9.js'></script>")})

    with _stub(stale) as url:
        result = _probe(url, "--commit", _DEPLOY["commit"])

    assert result.returncode != 0
    failing = [line for line in result.stdout.splitlines() if "FAIL" in line]
    assert any("bundle" in line for line in failing), result.stdout
    assert "index-OLD9.js" in result.stdout and "index-AAA.js" in result.stdout


def test_a_commit_that_is_not_this_one_fails_with_both_values_shown() -> None:
    #: A merged PR that never reached the branch that deploys is exactly what
    #: happened on 2026-11-01, and the state badge said nothing about it.
    with _stub(_good_routes()) as url:
        result = _probe(url, "--commit", "111122223333")

    assert result.returncode != 0
    assert "deadbeefcafe" in result.stdout and "111122223333" in result.stdout
    assert any("commit" in line and "FAIL" in line for line in result.stdout.splitlines()), (
        result.stdout
    )


def test_a_deploy_that_reports_unknown_fails_and_says_the_var_is_unset() -> None:
    unknown = _good_routes(
        {
            (
                "GET",
                "/api/deploy",
            ): (
                200,
                json.dumps(
                    {"build_id": "unknown", "commit": "unknown", "entry": "assets/index-AAA.js"}
                ),
            )
        }
    )

    with _stub(unknown) as url:
        result = _probe(url, "--commit", "deadbeefcafe")

    assert result.returncode != 0
    assert "unknown" in result.stdout
    assert "wrangler deploy" in result.stdout, "the failure must name the wiring that is missing"


def test_an_unreachable_host_fails_instead_of_passing_quietly() -> None:
    #: Nothing answers at all — the probe must say so rather than report a green run
    #: built on empty bodies.
    result = subprocess.run(
        ["bash", str(SCRIPT), "--base-url", "http://127.0.0.1:1", "--wait", "2", "--interval", "1"],
        capture_output=True,
        text=True,
        timeout=90,
    )

    assert result.returncode != 0
    assert "FAIL" in result.stdout or "could not be reached" in result.stdout + result.stderr


def test_a_deploy_that_is_still_coming_up_is_waited_for_not_judged() -> None:
    #: "not deployed yet" must never read as "broken", so the probe polls until the
    #: deploy answers, then asserts once.
    def not_yet(call: int) -> Entry:
        if call < 3:
            return 503, "deploy in progress"
        return 200, json.dumps(_DEPLOY)

    routes = _good_routes({("GET", "/api/deploy"): not_yet})

    with _stub(routes) as url:
        result = _probe(url, "--commit", _DEPLOY["commit"], "--wait", "5")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "waiting" in result.stdout.lower()
    assert "FAIL" not in result.stdout


def test_a_target_that_is_not_production_is_never_counted_as_a_pass() -> None:
    with _stub(_good_routes()) as url:
        result = _probe(url, "--commit", _DEPLOY["commit"])

    assert "NON-PRODUCTION TARGET" in result.stdout
    assert "not a hosted pass" in result.stdout.lower()


def test_the_script_names_only_the_production_host() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert PRODUCTION_HOST in source
    assert re.search(r"\bset -euo pipefail\b", source)
    assert "curl" in source and "jq" in source
    #: A preview URL is ephemeral and `docs/deployment.md` forbids promoting one into
    #: the docs, so the probe must not carry a pattern that could match one either.
    assert not re.search(r"[a-z0-9-]+-agentic-odi\.alehar\.workers\.dev", source)
    assert "docs/deployment.md" not in source


def test_the_script_judges_the_promise_not_merely_the_status() -> None:
    #: A 502 with the wrong code inside is a different product, so a probe that only
    #: compared status codes would call today's production green.
    wrong_code = _good_routes(
        {("POST", "/api/jobs"): (502, json.dumps({"error": {"code": "store_corrupt"}}))}
    )

    with _stub(wrong_code) as url:
        result = _probe(url, "--commit", _DEPLOY["commit"])

    assert result.returncode != 0
    assert "store_corrupt" in result.stdout


def test_a_hand_run_without_a_commit_skips_the_comparison_loudly() -> None:
    #: Step 1 of the issue asks for a run by hand against production to report each
    #: check. Someone typing the URL has no checkout to compare against, so that one
    #: check says it was skipped instead of pretending to have passed.
    with _stub(_good_routes()) as url:
        result = _probe(url)

    assert result.returncode == 0, result.stdout + result.stderr
    assert any("SKIP" in line and "commit" in line for line in result.stdout.splitlines())
    assert "PASS the deploy reports this commit" not in result.stdout


def test_a_deploy_identity_failure_prints_the_deploy_answer_and_not_the_last_page() -> None:
    #: A live run against production printed `index.html` underneath "the deploy reported
    #: no entry asset" — the body of the previous check, which reads as evidence and
    #: proves nothing. A promise about the deploy is evidenced by the deploy's own answer.
    no_entry = _good_routes({("GET", "/api/deploy"): (200, json.dumps({"build_id": "b7f3c1"}))})

    with _stub(no_entry) as url:
        result = _probe(url, "--commit", _DEPLOY["commit"])

    assert result.returncode != 0
    lines = result.stdout.splitlines()
    for needle in ("belongs to the deploy", "the deploy reports this commit"):
        failure = next(line for line in lines if "FAIL" in line and needle in line)
        body = lines[lines.index(failure) + 1]
        assert "body:" in body, f"{needle} failed with no body: {body}"
        assert "build_id" in body, body
        assert "<html" not in body and "doctype" not in body, body


def test_the_deployment_guide_explains_the_probe() -> None:
    #: The runbook is the reason this probe exists: an agent that lands a hosted
    #: change needs to know where to look, and the deploy-command edit that fills the
    #: commit is otherwise invisible.
    guide = (Path(__file__).resolve().parents[2] / "docs" / "deployment.md").read_text(
        encoding="utf-8"
    )

    for promise in (
        "a job write falls back in a code the browser understands",
        "the served bundle belongs to the deploy that claims it",
        "the deploy reports this commit",
    ):
        assert promise in guide, f"docs/deployment.md never names {promise!r}"
    assert "hosted-first-run-log" in guide
    assert "npx wrangler deploy --var COMMIT_SHA:" in guide
    assert "NON-PRODUCTION TARGET" in guide
