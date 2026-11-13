"""The Worker and the SPA must share one capability catalog (#801).

The Worker used to carry a hand-written `LOCAL_CAPABILITIES` manifest beside the
SPA's own copy of the same nine ids, labels, and descriptions. The two drifted
silently: an id added to one host left the other answering a different set. The
catalog in `apps/studio/src/bff/capabilities/catalog.ts` is now the single
source, and this test proves the Worker imports it rather than re-typing it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "infra" / "cloudflare" / "worker.ts"
CATALOG = ROOT / "apps" / "studio" / "src" / "bff" / "capabilities" / "catalog.ts"


def _worker_source() -> str:
    return WORKER.read_text(encoding="utf-8")


def _catalog_source() -> str:
    return CATALOG.read_text(encoding="utf-8")


def test_the_worker_imports_the_capability_catalog() -> None:
    source = _worker_source()
    assert "CAPABILITY_CATALOG" in source, "the Worker must import the shared catalog"
    assert "capabilities/catalog" in source, "the import must point at the catalog module"


def test_the_worker_builds_its_manifest_from_the_catalog() -> None:
    source = _worker_source()
    assert "CAPABILITY_CATALOG.map" in source, (
        "the local capabilities manifest must be derived from CAPABILITY_CATALOG"
    )


def test_no_hand_written_capability_manifest_remains() -> None:
    """A literal id inside the Worker means a second source of truth grew back."""
    source = _worker_source()
    for capability_id in (
        "local-data",
        "local-memory",
        "deterministic-assistant",
        "browser-model",
        "endpoint-model",
        "sidecar-llm",
        "sidecar-connectors",
        "sidecar-mcp",
        "sidecar-import",
    ):
        assert f'"{capability_id}"' not in source, (
            f"{capability_id!r} is hand-written in the Worker; take it from the catalog"
        )


def test_the_catalog_stays_data_only() -> None:
    """The catalog must import nothing so Wrangler can bundle it into the Worker."""
    source = _catalog_source()
    assert "import " not in source, "catalog.ts must not import anything"
