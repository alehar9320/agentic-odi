"""Shared fixtures and helpers for the website contract tests.

The tests verify what the *sources* produce by building fresh into a temp
dir. Nothing reads a checked-in build output.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
ROOT = SITE.parents[0]
TOOLS = SITE / "tools"
# The tool modules live in website/tools, which pytest does not put on the path.
sys.path.insert(0, str(TOOLS))

STUDIO_THEME = ROOT / "apps" / "studio" / "src" / "styles" / "theme.css"
MCP_SERVER_PY = ROOT / "apps" / "mcp-server" / "src" / "agentic_odi_mcp_server" / "mcp_server.py"
CONTRACT_PY = ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "contract.py"
CATALOG_PY = ROOT / "packages" / "connectors" / "src" / "agentic_odi_connectors" / "catalog.py"
CLI_PY = ROOT / "apps" / "cli" / "src" / "agentic_odi_cli" / "cli.py"
CATALOG_TS = ROOT / "apps" / "studio" / "src" / "ui" / "catalog.ts"
ROADMAP_MD = ROOT / "docs" / "roadmap.md"
SCHEMA_PY = ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "schema.py"
CORE_MODELS_PY = ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "models.py"

_BUILT: Path | None = None
_TMP: tempfile.TemporaryDirectory | None = None


def _build_the_site() -> Path:
    """Build the site once, at import, so collection can list the pages.

    The build happens at import rather than in a fixture because the tests
    are parametrised over the pages that exist, and parametrisation is
    resolved during collection — before any fixture runs.
    """
    global _BUILT, _TMP
    if _BUILT is not None:
        return _BUILT
    import build_site

    _TMP = tempfile.TemporaryDirectory()
    _BUILT = Path(_TMP.name)
    build_site.build(_BUILT)
    return _BUILT


_build_the_site()


def read_page(page: str) -> str:
    """The rendered text of a built page, relative to the built site root."""
    assert _BUILT is not None, "the site was not built"
    return (_BUILT / page).read_text(encoding="utf-8")


# Pages that are deliberately self-contained: inlined CSS, no client bundle, no
# shared shell. The 404 page and the sample workspace must render with no
# network at all, so they are served as-is and are not subject to the site
# shell's contract (the theme toggle, the shared assets). Their own contract is
# the opposite, and it is asserted directly.
STANDALONE_PAGES = {"404.html", "sample/index.html"}


def all_pages() -> list[str]:
    """Every built HTML page that uses the shared shell, relative to the site root."""
    assert _BUILT is not None, "the site was not built"
    return sorted(
        p.relative_to(_BUILT).as_posix()
        for p in _BUILT.rglob("*.html")
        if p.relative_to(_BUILT).as_posix() not in STANDALONE_PAGES
    )


def h1_text(html: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    assert match is not None, "no <h1> found"
    return re.sub(r"<[^>]+>", "", match.group(1)).strip()


def _built_root(page: str) -> Path:
    """The absolute path of a page inside the fresh build."""
    assert _BUILT is not None, "the site was not built"
    return _BUILT / page
