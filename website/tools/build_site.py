"""Render the Agentic ODI site.

The site is static: this script turns the repository's own sources — the
Studio theme, the MCP tool contract, the connector catalog, the CLI registry,
the ODI schema, and the guides under ``docs/`` — into HTML, CSS, and JS.

Nothing here runs at request time. The output is committed to
   Generated on demand and by CI at build time; never committed.
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import extract
import make_og
import markdown_render
from jinja2 import Environment, FileSystemLoader, select_autoescape

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
SCHEMA_PY = ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "schema.py"

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
        "--shadow-deep": "0 40px 120px -20px rgba(0, 0, 0, 0.85)",
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

    # The light theme is a token swap, nothing else: style.css never names a
    # colour, so overriding the palette here is all a new theme needs. It is
    # the Studio palette rotated onto a paper background, with accents darkened
    # enough to keep their contrast against white.
    light = {
        "--bg": "#f7f8fb",
        "--bg-raised": "#ffffff",
        "--bg-sunken": "#eef0f6",
        "--text": "#12131a",
        "--muted": "#555b68",
        "--faint": "#6b7280",
        "--accent": "#4f46e5",
        "--accent-strong": "#4338ca",
        "--accent-ink": "#ffffff",
        "--green": "#15803d",
        "--amber": "#b45309",
        "--line": "rgba(18, 19, 26, 0.1)",
        "--line-strong": "rgba(18, 19, 26, 0.18)",
        "--surface": "rgba(18, 19, 26, 0.035)",
        "--surface-hover": "rgba(18, 19, 26, 0.07)",
        "--glass": "rgba(255, 255, 255, 0.72)",
        "--hairline": "inset 0 1px 0 rgba(255, 255, 255, 0.9)",
        "--shadow-deep": "0 40px 120px -20px rgba(18, 19, 26, 0.18)",
    }

    def themed_block(selector: str, pairs: dict[str, str]) -> str:
        body = "\n".join(f"  {name}: {value};" for name, value in pairs.items())
        return f"{selector} {{\n{body}\n}}"

    return (
        "\n\n".join(
            [
                "/* Generated from apps/studio/src/styles/theme.css. Do not edit by hand. */",
                block(tokens),
                block(easings),
                block(site_only),
                themed_block(':root[data-theme="light"]', light),
            ]
        )
        + "\n"
    )


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


def _og_image(path: str) -> str:
    """The absolute URL of a page's own social card."""
    return f"{PAGES_URL}assets/og/{make_og.og_name(path)}"


def _page_context(**extra: Any) -> dict[str, Any]:
    """The context every page receives."""
    context: dict[str, Any] = {
        "site_name": SITE_NAME,
        "pages_url": PAGES_URL,
        "depth": 0,
        "prefix": "",
        "year": "2026",
        # The generic card is the fallback; every real page overrides it with
        # its own card, which the build generates from the page's content.
        "og_image": f"{PAGES_URL}assets/og.png",
    }
    context.update(extra)
    return context


def _flat_guides(nav: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Every guide, in navigation order, with its group."""
    return [(group, guide) for group in nav.get("groups", []) for guide in group.get("guides", [])]


def _guide_body(
    env: Environment,
    guide: dict[str, Any],
    context: dict[str, Any],
    link_map: dict[str, str],
) -> tuple[str, list[dict[str, str]], str | None]:
    """A guide's rendered body, its table of contents, and its own title.

    A guide with a ``source`` is rendered from the repository's markdown. The
    two without one — the quick start and the MCP reference — are generated,
    because they are joins the repository cannot express.
    """
    slug = guide["slug"]

    if slug == "quick-start":
        body = env.get_template("_quick_start.html").render(**context)
        return body, [], None

    if slug == "mcp":
        body = env.get_template("_mcp_reference.html").render(**context)
        return body, [], None

    source = guide.get("source")
    if not source:
        return "", [], None

    path = ROOT / source
    if not path.is_file():
        raise FileNotFoundError(f"the guide {source} does not exist")
    raw, title = markdown_render.take_title(path.read_text(encoding="utf-8"))
    body = markdown_render.render(
        raw,
        source_path=source,
        link_map=link_map,
        page_path=f"docs/{slug}/index.html",
    )
    if slug == "connectors":
        # The guide explains how presets work; the catalog decides which ones
        # exist. Append the generated reference so a new preset is documented
        # by the build rather than by someone remembering to edit the guide.
        body += env.get_template("_connector_reference.html").render(**context)
    return body, markdown_render.headings(body), title


def _render_docs(env: Environment, nav: dict[str, Any], context: dict[str, Any]) -> dict[str, str]:
    """Every docs page, keyed by its path relative to the site root."""
    guides = _flat_guides(nav)
    rendered: dict[str, str] = {}
    link_map = {
        guide["source"]: f"docs/{guide['slug']}/index.html"
        for _, guide in guides
        if guide.get("source")
    }

    for index, (group, guide) in enumerate(guides):
        slug = guide["slug"]
        output = f"docs/{slug}/index.html"
        page_context = dict(context)
        page_context["nav"] = nav
        page_context["page"] = {
            "title": guide["title"],
            "description": guide.get("blurb", ""),
            "path": output,
            "depth": 2,
            "slug": slug,
            "group_title": group["title"],
            "blurb": guide.get("blurb", ""),
            "previous": guides[index - 1][1] if index else None,
            "next": guides[index + 1][1] if index + 1 < len(guides) else None,
        }
        body, toc, own_title = _guide_body(env, guide, page_context, link_map)
        if own_title:
            # The guide's own top-level heading is its title.
            page_context["page"]["title"] = own_title
        page_context["page"]["body"] = body
        page_context["page"]["toc"] = toc
        page_context["prefix"] = "../../"
        page_context["og_image"] = _og_image(output)
        rendered[output] = env.get_template("doc.html").render(**page_context)

    return rendered


def _render_docs_index(env: Environment, nav: dict[str, Any], context: dict[str, Any]) -> str:
    """The hub index: every guide, grouped by the job it does."""
    page_context = dict(context)
    page_context["nav"] = nav
    page_context["page"] = {
        "title": "Documentation",
        "description": (
            "Every guide, the CLI reference, the connector catalog, and the full "
            "MCP tool reference."
        ),
        "path": "docs/index.html",
        "depth": 1,
        "slug": "",
        "group_title": "Documentation",
        "blurb": "",
        "previous": None,
        "next": None,
        "body": "",
        "toc": [],
    }
    page_context["prefix"] = "../"
    page_context["og_image"] = _og_image("docs/index.html")
    return env.get_template("docs_index.html").render(**page_context)


def _render_pages(env: Environment) -> dict[str, str]:
    """Render every page, returning output path -> HTML."""
    landing = _load_json("landing.json")
    demo = _load_json("demo.json")
    nav = _load_json("nav.json")
    connectors = extract.read_connectors(CATALOG_PY)
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)
    cards = extract.read_catalog_cards(CATALOG_TS)
    roadmap_pending = extract.read_roadmap_pending(ROADMAP_MD)
    odi_schema = extract.read_odi_schema(SCHEMA_PY)
    formula_base, formula_gap = _formula_parts()

    context = _page_context(
        page={
            "title": SITE_NAME,
            "description": "",
            "path": "index.html",
            "depth": 0,
        },
        landing=landing,
        content=landing,
        demo=demo,
        nav=nav,
        connectors=connectors,
        connector_areas=extract.group_connectors_by_area(connectors),
        tools=tools,
        tool_by_name={tool["name"]: tool for tool in tools},
        tool_signatures={tool["name"]: _signature(tool) for tool in tools},
        catalog_cards=cards,
        odi_schema=odi_schema,
        odi_schema_json=json.dumps(odi_schema, indent=1, sort_keys=True),
        works_today=_works_today(tools, cards, connectors),
        roadmap_pending=roadmap_pending,
        formula_base=formula_base,
        formula_gap=formula_gap,
    )

    rendered: dict[str, str] = {}

    landing_context = dict(context)
    landing_context["page"] = {
        "title": f"{SITE_NAME} — Ground agents in verified customer outcomes",
        "description": (
            "An MCP server that hands your agents verified customer outcomes, "
            "and the evidence behind them."
        ),
        "path": "index.html",
        "depth": 0,
    }
    landing_context["og_image"] = _og_image("index.html")
    rendered["index.html"] = env.get_template("landing.html").render(**landing_context)

    rendered["docs/index.html"] = _render_docs_index(env, nav, context)
    rendered.update(_render_docs(env, nav, context))

    not_found = env.get_template("404.html").render(**context)
    rendered["404.html"] = not_found

    return rendered


def _page_url(name: str) -> str:
    """A page's path relative to the site root, without a leading slash."""
    if name == "index.html":
        return ""
    return name[: -len("index.html")]


def _page_sections() -> dict[str, str]:
    """Each page's section label, from the nav groups.

    A card's chip names the section the page belongs to. The nav is the one
    place that already groups the guides, so the label comes from there rather
    than from a second list that would drift.
    """
    nav = _load_json("nav.json")
    sections: dict[str, str] = {}
    for group in nav.get("groups", []):
        for guide in group.get("guides", []):
            sections[f"docs/{guide['slug']}/index.html"] = group["title"]
    sections["index.html"] = "Overview"
    sections["docs/index.html"] = "Documentation"
    return sections


def _search_entry(name: str, page: str) -> dict[str, str]:
    """One search-index entry: a page's title, path, and description."""
    heading = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.DOTALL)
    title = _plain_text(heading.group(1)) if heading else SITE_NAME
    description = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', page)
    excerpt = html_module.unescape(description.group(1)) if description else ""
    return {"title": title, "url": _page_url(name), "excerpt": excerpt}


def _plain_text(fragment: str) -> str:
    """A fragment's visible text, with tags and entities resolved."""
    text = html_module.unescape(re.sub(r"<[^>]+>", "", fragment))
    return re.sub(r"\s+", " ", text).strip()


def _search_index(rendered: dict[str, str]) -> str:
    """The client-side search index, built from the pages themselves.

    Paths are relative to the site root so the same index works under the
    project site's subpath and under a pull-request preview.
    """
    entries = [
        _search_entry(name, page) for name, page in sorted(rendered.items()) if name != "404.html"
    ]
    return json.dumps(entries, indent=2, ensure_ascii=False) + "\n"


def _sitemap(urls: list[str]) -> str:
    entries = "\n".join(f"  <url><loc>{PAGES_URL.rstrip('/')}{url}</loc></url>" for url in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )


def _robots() -> str:
    return f"User-agent: *\nAllow: /\n\nSitemap: {PAGES_URL}sitemap.xml\n"


def _tree(root: Path) -> dict[str, bytes]:
    """Every file under a directory, keyed by its relative path."""
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def build(out_dir: Path, *, check: bool = False) -> int:
    """Render the site into ``out_dir``.

    With ``check=True`` nothing is written: ``out_dir`` is compared against a
    fresh render and the process exits non-zero when they differ.
    """
    out_dir = Path(out_dir)
    env = environment()
    rendered = _render_pages(env)

    files: dict[str, bytes] = {name: html.encode("utf-8") for name, html in rendered.items()}
    # One card per published page. A page the build emits without a card is a
    # page whose shared link would show someone else's image, so this is a hard
    # failure rather than a warning. (404 is not published, so it has no card.)
    pages_for_cards = {name: html for name, html in rendered.items() if name != "404.html"}
    cards = make_og.render_site(pages_for_cards, PAGES_URL, _page_sections())
    missing = sorted(
        name for name in pages_for_cards if f"assets/og/{make_og.og_name(name)}" not in cards
    )
    if missing:
        raise SystemExit(f"no social card was generated for: {', '.join(missing)}")
    files.update(cards)

    urls = ["/"]
    for name in sorted(rendered):
        if name in {"index.html", "404.html"}:
            continue
        urls.append("/" + name[: -len("index.html")])
    files["sitemap.xml"] = _sitemap(urls).encode("utf-8")
    files["robots.txt"] = _robots().encode("utf-8")
    files["search-index.json"] = _search_index(rendered).encode("utf-8")
    files["assets/tokens.css"] = _tokens_css().encode("utf-8")

    for asset in sorted(ASSETS.rglob("*")):
        if asset.is_file():
            files[f"assets/{asset.relative_to(ASSETS).as_posix()}"] = asset.read_bytes()

    if check:
        committed = _tree(out_dir)
        stale = sorted(
            name for name in set(committed) | set(files) if committed.get(name) != files.get(name)
        )
        if stale:
            print("The built site is out of date. Run: build_site.py", file=sys.stderr)
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
        help="fail if out_dir differs from a fresh build; write nothing",
    )
    args = parser.parse_args(argv)

    if args.check:
        count = build(args.out, check=True)
        print(f"The built site is up to date ({count} files).")
        return 0

    count = build(args.out)
    print(f"Built {count} files into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
