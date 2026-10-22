"""Shared fixtures and helpers for the website contract tests.

The tests verify what the *sources* produce, so they read a fresh build, not
the committed output. The committed output is a separate concern, covered by
``build_site.py --check`` and by ``test_generated.py``.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
ROOT = SITE.parents[0]
TOOLS = SITE / "tools"
DIST = SITE / "dist"

# The tool modules live in website/tools, which pytest does not put on the path.
sys.path.insert(0, str(TOOLS))

STUDIO_THEME = ROOT / "apps" / "studio" / "src" / "styles" / "theme.css"
MCP_SERVER_PY = ROOT / "apps" / "mcp-server" / "src" / "agentic_odi_mcp_server" / "mcp_server.py"
CONTRACT_PY = ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "contract.py"
CATALOG_PY = ROOT / "packages" / "connectors" / "src" / "agentic_odi_connectors" / "catalog.py"
CLI_PY = ROOT / "apps" / "cli" / "src" / "agentic_odi_cli" / "cli.py"
SCHEMA_PY = ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "schema.py"
CORE_MODELS_PY = ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "models.py"

_BUILT: Path | None = None


@pytest.fixture(scope="session", autouse=True)
def _build_the_site():
    """Build the site once per session; the tests read that build."""
    global _BUILT
    import build_site

    with tempfile.TemporaryDirectory() as tmp:
        _BUILT = Path(tmp)
        build_site.build(_BUILT)
        yield _BUILT


def read_page(page: str) -> str:
    """The rendered text of a built page, relative to the built site root."""
    assert _BUILT is not None, "the site was not built"
    return (_BUILT / page).read_text(encoding="utf-8")


def all_pages() -> list[str]:
    """Every built HTML page, as a path relative to the built site root."""
    assert _BUILT is not None, "the site was not built"
    return sorted(
        str(p.relative_to(_BUILT)) for p in _BUILT.rglob("*.html") if p.name != "404.html"
    )


def h1_text(html: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    assert match is not None, "no <h1> found"
    return re.sub(r"<[^>]+>", "", match.group(1)).strip()


def _built_root(page: str) -> Path:
    """The absolute path of a page inside the fresh build."""
    assert _BUILT is not None, "the site was not built"
    return _BUILT / page
