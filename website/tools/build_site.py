"""Render the Agentic ODI site.

The site is static: this script turns the repository's own sources — the
Studio theme, the MCP tool contract, the connector catalog, the CLI registry,
the ODI schema, and the guides under ``docs/`` — into HTML, CSS, and JS.

Nothing here runs at request time. The output is committed to
``website/dist/`` so a reviewer can read the rendered page in a pull request,
and CI fails when it drifts from a fresh build.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

import extract

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "website"
TEMPLATES = SITE / "templates"
CONTENT = SITE / "content"
ASSETS = SITE / "assets"
OUT_DIR = SITE / "dist"

PAGES_URL = "https://alehar9320.github.io/agentic-odi/"

STUDIO_THEME = ROOT / "apps" / "studio" / "src" / "styles" / "theme.css"
MCP_SERVER_PY = ROOT / "apps" / "mcp-server" / "src" / "agentic_odi_mcp_server" / "mcp_server.py"
CONTRACT_PY = ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "contract.py"
CATALOG_PY = ROOT / "packages" / "connectors" / "src" / "agentic_odi_connectors" / "catalog.py"
CLI_PY = ROOT / "apps" / "cli" / "src" / "agentic_odi_cli" / "cli.py"
CATALOG_TS = ROOT / "apps" / "studio" / "src" / "ui" / "catalog.ts"
ROADMAP_MD = ROOT / "docs" / "roadmap.md"
CORE_MODELS_PY = ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "models.py"

SITE_NAME = "Agentic ODI"


def environment() -> Environment:
    """The Jinja environment. Autoescape is on for every template."""
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _tokens_css() -> str:
    """The site's token file, generated from the Studio's own theme."""
    tokens = extract.read_tokens(STUDIO_THEME)
    easings = extract.read_easings(STUDIO_THEME)
    site_only = {
        "--bg-sunken": "#060709",
        "--accent-ink": "#0a0b0e",
        "--glass": "rgba(255, 255, 255, 0.045)",
        "--glass-blur": "blur(20px) saturate(180%)",
        "--hairline": "inset 0 1px 0 rgba(255, 255, 255, 0.06)",
        "--r-sm": "8px",
        "--r-md": "12px",
        "--r-lg": "16px",
        "--r-xl": "22px",
        "--r-pill": "999px",
        "--w-page": "1200px",
        "--w-wide": "1440px",
        "--w-prose": "68ch",
        "--gutter": "clamp(20px, 5vw, 48px)",
        "--section-y": "clamp(96px, 13vw, 200px)",
    }

    def block(pairs: dict[str, str]) -> str:
        body = "\n".join(f"  {name}: {value};" for name, value in pairs.items())
        return f":root {{\n{body}\n}}"

    return "\n\n".join(
        [
            "/* Generated from apps/studio/src/styles/theme.css. Do not edit by hand. */",
            block(tokens),
            block(easings),
            block(site_only),
        ]
    ) + "\n"


def _formula_parts() -> tuple[str, str]:
    """The opportunity formula, split into its base term and its gap term.

    The formula is read from the core module, never typed here. Splitting it
    lets the page highlight the gap term without maintaining a second copy of
    the expression — and if the core changes shape, the build fails loudly
    instead of quietly publishing a stale equation.
    """
    source = extract.read_odi_formula(CORE_MODELS_PY)
    match = re.fullmatch(
        r"\s*importance\s*\+\s*(max\(\s*importance\s*-\s*satisfaction\s*,\s*0\s*\))\s*",
        source,
    )
    if not match:
        raise ValueError(f"the opportunity formula has an unexpected shape: {source!r}")
    return "importance", match.group(1)


def _signature(tool: dict[str, Any]) -> str:
    """A tool's signature, the way the MCP server declares it."""
    parts = []
    for param in tool["params"]:
        text = param["name"]
        if param["annotation"]:
            text += f": {param['annotation']}"
        if param["default"] is not None:
            text += f" = {param['default']}"
        parts.append(text)
    return f"{tool['name']}({', '.join(parts)})"


def _works_today(
    tools: list[dict[str, Any]],
    cards: list[dict[str, str]],
    connectors: list[dict[str, Any]],
) -> list[str]:
    """What the product actually does today.

    The counts are read from the source; the sentences are editorial.
    """
    return [
        f"{len(tools)} MCP tools over jobs, steps, desired outcomes, customer outcomes, and evidence.",
        f"{len(cards)} agent-composed surfaces, from a closed catalog the studio owns.",
        f"{len(connectors)} connector presets — Notion, Gong, PostHog, Linear, GitHub, and more.",
        "A local-first CLI: full entity CRUD, interactive chat, `schema`, and `score`.",
        "A SQLite store, so the data outlives the session.",
        "The Living Studio, as a web app and as a Tauri desktop app.",
        "A hosted MCP server, for testing and verifying MCP over the wire.",
        "A hosted Studio on Cloudflare Workers.",
    ]


def _load_json(name: str) -> Any:
    import json

    path = CONTENT / name
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _page_context(**extra: Any) -> dict[str, Any]:
    """The context every page receives."""
    context: dict[str, Any] = {
        "site_name": SITE_NAME,
        "pages_url": PAGES_URL,
        "depth": 0,
        "prefix": "",
        "year": "2026",
    }
    context.update(extra)
    return context


def _pages(env: Environment) -> list[tuple[str, str]]:
    """Every page as ``(output path relative to dist, template name)``.

    The pages that need the docs machinery are added once the docs pipeline
    exists; the landing page and the 404 page are always present.
    """
    pages: list[tuple[str, str]] = [("index.html", "landing.html"), ("404.html", "404.html")]
    for name in sorted(p.name for p in TEMPLATES.glob("*.html")):
        # A leading underscore marks a partial, not a page.
        if name.startswith("_"):
            continue
        if name in {"base.html", "landing.html", "404.html"}:
            continue
        pages.append((name, name))
    return pages


def _render_pages(env: Environment) -> dict[str, str]:
    """Render every page, returning output path -> HTML."""
    landing = _load_json("landing.json")
    demo = _load_json("demo.json")
    connectors = extract.read_connectors(CATALOG_PY)
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)
    cards = extract.read_catalog_cards(CATALOG_TS)
    roadmap_pending = extract.read_roadmap_pending(ROADMAP_MD)
    formula_base, formula_gap = _formula_parts()
    rendered: dict[str, str] = {}

    for output, template in _pages(env):
        context = _page_context(
            page={
                "title": SITE_NAME,
                "description": "",
                "path": output,
                "depth": 0,
            },
            landing=landing,
            content=landing,
            demo=demo,
            connectors=connectors,
            connector_areas=extract.group_connectors_by_area(connectors),
            tools={tool["name"]: tool for tool in tools},
            tool_signatures={tool["name"]: _signature(tool) for tool in tools},
            catalog_cards=cards,
            works_today=_works_today(tools, cards, connectors),
            roadmap_pending=roadmap_pending,
            formula_base=formula_base,
            formula_gap=formula_gap,
        )
        if template == "landing.html":
            context["page"] = {
                "title": f"{SITE_NAME} — Ground agents in verified customer outcomes",
                "description": (
                    "An MCP server that hands your agents verified customer outcomes, "
                    "and the evidence behind them."
                ),
                "path": output,
                "depth": 0,
            }
        rendered[output] = env.get_template(template).render(**context)
    return rendered


def _sitemap(urls: list[str]) -> str:
    entries = "\n".join(f"  <url><loc>{PAGES_URL.rstrip('/')}{url}</loc></url>" for url in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )


def _robots() -> str:
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {PAGES_URL}sitemap.xml\n"
    )


def _tree(root: Path) -> dict[str, bytes]:
    """Every file under a directory, keyed by its relative path."""
    if not root.is_dir():
        return {}
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def build(out_dir: Path, *, check: bool = False) -> int:
    """Render the site into ``out_dir``.

    With ``check=True`` nothing is written: the committed output is compared
    against a fresh render and the process exits non-zero when they differ.
    """
    out_dir = Path(out_dir)
    env = environment()
    rendered = _render_pages(env)

    files: dict[str, bytes] = {name: html.encode("utf-8") for name, html in rendered.items()}
    files["sitemap.xml"] = _sitemap(["/"] + [f"/{name}" for name in sorted(rendered) if name.endswith(".html") and name not in {"index.html", "404.html"}]).encode("utf-8")
    files["robots.txt"] = _robots().encode("utf-8")
    files["assets/tokens.css"] = _tokens_css().encode("utf-8")

    for asset in sorted(ASSETS.rglob("*")):
        if asset.is_file():
            files[f"assets/{asset.relative_to(ASSETS).as_posix()}"] = asset.read_bytes()

    if check:
        committed = _tree(out_dir)
        stale = sorted(
            name
            for name in set(committed) | set(files)
            if committed.get(name) != files.get(name)
        )
        if stale:
            print("The committed site is out of date. Run: build_site.py", file=sys.stderr)
            for name in stale:
                print(f"  {name}", file=sys.stderr)
            raise SystemExit(1)
        return len(files)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    for name, data in files.items():
        path = out_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return len(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="where to write the site")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed site differs from a fresh build; write nothing",
    )
    args = parser.parse_args(argv)

    if args.check:
        count = build(args.out, check=True)
        print(f"The committed site is up to date ({count} files).")
        return 0

    count = build(args.out)
    print(f"Built {count} files into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
