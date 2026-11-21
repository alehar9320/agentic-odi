"""The committed Studio contract is generated, and its holes only close.

Three properties, checked here so a green build means them:

1. ``apps/studio/openapi.json`` equals what the live app serves. It is the
   source the SPA's TypeScript types are generated from, so a hand-edited or
   stale copy is a contract the client compiles against and the server does not
   honour. ``agentic_odi_studio_api.openapi`` regenerates it; this test is the
   reason nobody has to remember to run it.
2. The contract is the deterministic API surface, not the SPA fallback: the
   fallback is registered only when a built Studio is on disk, so including it
   would make the file depend on whether someone ran ``npm run build``.
3. The number of operations that answer with an open object does not grow. A
   route with no ``response_model`` exports ``additionalProperties: true``, so
   the generated TypeScript types it as an open object and a renamed field
   becomes ``undefined`` at runtime instead of a compile error. The count is a
   ratchet, not a licence: it may only go down, and typing a route lowers
   ``OPEN_RESPONSE_MODEL_CEILING`` in the same change.
"""

from __future__ import annotations

import json

from agentic_odi_studio_api.openapi import CONTRACT, build_contract, normalise

# 77 of the 97 operations still answer with an open object — the two SSE routes
# (`/api/chat`, `/api/llm/chat`) are among them, because a stream has no JSON
# model. It was 60 of 80 when this check landed; `main` has since added 17
# operations (alternatives, outcome delta/history/inputs/interval,
# existing-solution, data status, the model-key settings pair), none of which
# declares a `response_model`. The baseline is re-measured against the merged
# route surface. From here it may only go down: typing a route lowers this
# number in the same change. See issue #1088.
OPEN_RESPONSE_MODEL_CEILING = 77

_SUCCESS_CODES = ("200", "201", "202", "204")
_METHODS = ("get", "post", "patch", "put", "delete")


def _success_schema(operation: dict) -> dict | None:
    for code in _SUCCESS_CODES:
        response = operation.get("responses", {}).get(code)
        if response is None:
            continue
        if code == "204":
            return {"__empty__": True}
        content = response.get("content", {})
        return content.get("application/json", {}).get("schema")
    return None


def _is_typed(schema: dict | None) -> bool:
    """True when the schema names a shape rather than an open object."""
    if schema is None:
        return False
    if schema.get("__empty__"):
        return True
    if "$ref" in schema or schema.get("properties"):
        return True
    if schema.get("type") in {"string", "integer", "number", "boolean"}:
        return True
    if schema.get("type") == "array":
        return _is_typed(schema.get("items", {}))
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            return all(_is_typed(part) for part in schema[key])
    return False


def _untyped_success_responses(document: dict) -> list[str]:
    return sorted(
        f"{method.upper()} {path}"
        for path, item in document["paths"].items()
        for method, operation in item.items()
        if method in _METHODS and not _is_typed(_success_schema(operation))
    )


def test_committed_contract_matches_the_live_app() -> None:
    committed = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert normalise(committed) == normalise(build_contract()), (
        "apps/studio/openapi.json is stale; regenerate it with "
        "`uv run python -m agentic_odi_studio_api.openapi --write`"
    )


def test_the_contract_is_the_api_surface_only() -> None:
    paths = build_contract()["paths"]
    assert all(path.startswith("/api") or path in {"/health", "/capabilities"} for path in paths)
    assert "/api/canvas" in paths


def test_untyped_success_responses_only_shrink() -> None:
    untyped = _untyped_success_responses(build_contract())
    assert len(untyped) == OPEN_RESPONSE_MODEL_CEILING, (
        f"{len(untyped)} operations answer with an open object, expected "
        f"{OPEN_RESPONSE_MODEL_CEILING}.\n"
        "A new route without a `response_model` widens the contract the SPA "
        "compiles against. Give it a response model, or — if you typed an "
        "existing route — lower OPEN_RESPONSE_MODEL_CEILING in the same change.\n"
        "Untyped operations: " + ", ".join(untyped)
    )
