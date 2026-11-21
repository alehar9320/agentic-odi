"""The Studio API contract, generated from the running app (#1088).

``apps/studio/openapi.json`` is the contract the SPA's generated TypeScript
types come from (``apps/studio/src/api/schema.d.ts`` via ``openapi-typescript``).
It used to be maintained by hand, so it drifted from the routes the sidecar
actually serves. This module regenerates it from the live FastAPI app and fails
when the committed copy is stale::

    uv run python -m agentic_odi_studio_api.openapi --check   # fail on drift
    uv run python -m agentic_odi_studio_api.openapi --write   # refresh the file

The SPA fallback (``/{full_path:path}``) is registered only when the built
Studio is on disk, so it is dropped from the generated contract by name:
otherwise the same checkout would produce a different file on a machine that had
run ``npm run build``. Every other route is kept, so a new route the API does not
intend to publish still shows up as drift. The contract is the deterministic API
surface.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CONTRACT = ROOT / "apps" / "studio" / "openapi.json"

#: The catch-all that serves the built SPA; it is a deployment detail, not a route
#: the client compiles against.
SPA_FALLBACK_PATH = "/{full_path:path}"


def build_contract() -> dict:
    """The OpenAPI document the running app serves, without the SPA fallback."""
    from agentic_odi_core.repository import InMemoryRepository

    from agentic_odi_studio_api.app import create_app

    document = create_app(InMemoryRepository()).openapi()
    document["paths"] = {
        path: item for path, item in document.get("paths", {}).items() if path != SPA_FALLBACK_PATH
    }
    return document


def normalise(document: dict) -> str:
    return json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _committed() -> dict | None:
    if not CONTRACT.is_file():
        return None
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _path_drift(live: dict, committed: dict) -> tuple[list[str], list[str]]:
    live_paths = set(live.get("paths", {}))
    committed_paths = set(committed.get("paths", {}))
    return sorted(live_paths - committed_paths), sorted(committed_paths - live_paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="fail if the committed file is stale")
    group.add_argument("--write", action="store_true", help="overwrite the committed file")
    args = parser.parse_args(argv)

    live = build_contract()
    rendered = normalise(live)
    relative = CONTRACT.relative_to(ROOT)

    if args.write:
        CONTRACT.write_text(rendered, encoding="utf-8")
        print(f"wrote {relative} ({len(live.get('paths', {}))} paths)")
        return 0

    committed = _committed()
    if committed is None:
        print(f"missing contract: {relative}", file=sys.stderr)
        return 1

    if normalise(committed) == rendered:
        print(f"OK: {relative} matches the app ({len(live.get('paths', {}))} paths)")
        return 0

    only_in_app, only_in_file = _path_drift(live, committed)
    print(f"the committed contract is stale: {relative}", file=sys.stderr)
    for path in only_in_app:
        print(f"  only in app:  {path}", file=sys.stderr)
    for path in only_in_file:
        print(f"  only in file: {path}", file=sys.stderr)
    print("run `uv run python -m agentic_odi_studio_api.openapi --write`", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
