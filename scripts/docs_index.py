#!/usr/bin/env python3
"""Generate the documentation index: nav.json and README Documentation table.

The index is derived from front matter on each living guide in ``docs/``.
``docs/superpowers/**`` is excluded: it is a frozen record, not navigation.

    uv run python scripts/docs_index.py --write    # write the generated artefacts
    uv run python scripts/docs_index.py --check     # fail if stale
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
NAV_JSON = ROOT / "website" / "content" / "nav.json"
README = ROOT / "README.md"

# The markers that wrap the generated table in README.md
BEGIN_MARKER = "<!-- BEGIN GENERATED: docs -->"
END_MARKER = "<!-- END GENERATED: docs -->"

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_FRONT_MATTER_STRIP_RE = re.compile(r"^---\n.*?\n---\n?", re.DOTALL)

# Virtual pages have no markdown source file: they are rendered from templates
# in website/tools/build_site.py (_quick_start.html and _mcp_reference.html),
# so the front-matter scan over docs/ cannot discover them. They must remain in
# the generated navigation so those pages keep being built; without them the
# MCP reference page is never emitted and the site's content-sync tests fail.
VIRTUAL_PAGES: list[dict[str, Any]] = [
    {
        "source": None,
        "slug": "quick-start",
        "title": "Quick start",
        "blurb": "From nothing to a running studio.",
        "nav_group": "Get started",
        "nav_order": 0,
    },
    {
        "source": None,
        "slug": "mcp",
        "title": "MCP tool reference",
        "blurb": "Every tool the server exposes.",
        "nav_group": "Build",
        "nav_order": 3,
    },
]


def strip_front_matter(text: str) -> str:
    """Remove YAML front matter from markdown if present."""
    return _FRONT_MATTER_STRIP_RE.sub("", text, count=1)


def parse_front_matter(text: str) -> dict[str, Any] | None:
    """Parse YAML front matter from a markdown file."""
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return None
    # Simple YAML parsing for our known keys
    fm: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value.isdigit():
            value = int(value)
        fm[key] = value
    return fm


def collect_guides() -> list[dict[str, Any]]:
    """Collect all guides with valid front matter from docs/."""
    guides: list[dict[str, Any]] = []
    for path in sorted(DOCS_DIR.rglob("*.md")):
        relative = path.relative_to(DOCS_DIR).as_posix()
        if relative.startswith("superpowers/"):
            continue
        text = path.read_text(encoding="utf-8")
        fm = parse_front_matter(text)
        if not fm:
            continue
        # Validate required fields
        required = {"title", "blurb", "nav_group", "nav_order"}
        missing = required - fm.keys()
        if missing:
            raise ValueError(f"{relative}: missing front matter fields: {missing}")
        # Use slug from front matter or derive from filename
        slug = fm.get("slug", path.stem)
        guides.append(
            {
                "source": f"docs/{relative}",
                "slug": slug,
                "title": fm["title"],
                "blurb": fm["blurb"],
                "nav_group": fm["nav_group"],
                "nav_order": fm["nav_order"],
            }
        )
    return guides


def build_nav(guides: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the nav.json structure from guides."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for guide in guides:
        group_title = guide["nav_group"]
        if group_title not in groups:
            groups[group_title] = []
        groups[group_title].append(guide)

    # Sort guides within each group by nav_order
    for group_guides in groups.values():
        group_guides.sort(key=lambda g: g["nav_order"])

    # Fixed group order
    group_order = ["Get started", "Build", "Operate"]
    nav_groups = []
    for group_title in group_order:
        if group_title in groups:
            nav_groups.append(
                {
                    "title": group_title,
                    "guides": [
                        {
                            "slug": g["slug"],
                            "title": g["title"],
                            "source": g["source"],
                            "blurb": g["blurb"],
                        }
                        for g in groups[group_title]
                    ],
                }
            )
    return {"groups": nav_groups}


def build_readme_table(guides: list[dict[str, Any]]) -> str:
    """Build the README Documentation table from guides."""
    # Sort by group order and then nav_order
    group_order = {"Get started": 0, "Build": 1, "Operate": 2}
    guides_sorted = sorted(
        guides, key=lambda g: (group_order.get(g["nav_group"], 99), g["nav_order"])
    )

    lines = ["| Guide | Contents |", "|---|---|"]
    for guide in guides_sorted:
        link = f"[{guide['title']}]({guide['source']})"
        lines.append(f"| {link} | {guide['blurb']} |")
    return "\n".join(lines) + "\n"


def write_nav_json(nav: dict[str, Any]) -> None:
    """Write nav.json with deterministic formatting."""
    NAV_JSON.parent.mkdir(parents=True, exist_ok=True)
    NAV_JSON.write_text(
        json.dumps(nav, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_readme_table(table: str) -> None:
    """Write the generated table into README.md between markers."""
    readme = README.read_text(encoding="utf-8")
    if BEGIN_MARKER not in readme or END_MARKER not in readme:
        raise RuntimeError("README.md missing GENERATED markers for docs table")
    before, rest = readme.split(BEGIN_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)
    new_readme = f"{before}{BEGIN_MARKER}\n{table}{END_MARKER}{after}"
    README.write_text(new_readme, encoding="utf-8")


def check_nav_json(nav: dict[str, Any]) -> bool:
    """Check if nav.json matches the generated version."""
    if not NAV_JSON.is_file():
        return False
    current = json.loads(NAV_JSON.read_text(encoding="utf-8"))
    return current == nav


def check_readme_table(table: str) -> bool:
    """Check if README.md table matches the generated version."""
    readme = README.read_text(encoding="utf-8")
    if BEGIN_MARKER not in readme or END_MARKER not in readme:
        return False
    _, rest = readme.split(BEGIN_MARKER, 1)
    current_table, _ = rest.split(END_MARKER, 1)
    return current_table.strip() == table.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the generated artefacts",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if generated artefacts are stale; write nothing",
    )
    args = parser.parse_args(argv)

    if not args.write and not args.check:
        parser.error("one of --write or --check is required")
    if args.write and args.check:
        parser.error("--write and --check are mutually exclusive")

    guides = collect_guides()
    nav = build_nav(guides + VIRTUAL_PAGES)
    table = build_readme_table(guides)

    if args.write:
        write_nav_json(nav)
        write_readme_table(table)
        print("Generated nav.json and README Documentation table")
        return 0

    # --check
    nav_ok = check_nav_json(nav)
    readme_ok = check_readme_table(table)

    if not nav_ok:
        print(f"Stale: {NAV_JSON.relative_to(ROOT)}", file=sys.stderr)
    if not readme_ok:
        print(f"Stale: {README.relative_to(ROOT)}", file=sys.stderr)

    return 0 if (nav_ok and readme_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
