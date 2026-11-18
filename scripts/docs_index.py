"""Generate the living docs' generated blocks from their sources (#1044).

Owns every generated region in the docs:

- README Code Overview table (packages): one row per workspace distribution,
  derived from each member's ``pyproject.toml`` so adding a member is one new
  file and nothing else.
- README Documentation table (docs) + ``website/content/nav.json``: derived
  from the front matter on each page in ``docs/`` so a new guide registers
  itself in the navigation without touching a shared file.
- ``docs/reference/test-map.md`` (test-map): one row per test file, derived
  from the file's own docstring or leading comment (#1047), so writing a test
  means writing a docstring instead of editing a shared table.

Run locally with::

    uv run python scripts/docs_index.py --write   # refresh the generated blocks
    uv run python scripts/docs_index.py --check   # fail if a block is stale
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
NAV_JSON = ROOT / "website" / "content" / "nav.json"
README = ROOT / "README.md"
TEST_MAP = "docs/reference/test-map.md"

# --- README Documentation table + website/content/nav.json (docs block) ---

BEGIN_MARKER = "<!-- BEGIN GENERATED: docs -->"
END_MARKER = "<!-- END GENERATED: docs -->"

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_FRONT_MATTER_STRIP_RE = re.compile(r"^---\n.*?\n---\n?", re.DOTALL)

# Virtual pages have no markdown source file: they are rendered from templates
# in website/tools/build_site.py, so the front-matter scan over docs/ cannot
# discover them. They must remain in the generated navigation so those pages
# keep being built; without them the MCP reference page is never emitted and the
# site's content-sync tests fail.
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
        required = {"title", "blurb", "nav_group", "nav_order"}
        missing = required - fm.keys()
        if missing:
            raise ValueError(f"{relative}: missing front matter fields: {missing}")
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
    # Virtual pages have no markdown source (they are rendered from templates in
    # website/tools/build_site.py), so the front-matter scan over docs/ cannot
    # discover them. They must remain in the generated navigation so those pages
    # keep being built; without them the MCP reference page is never emitted and
    # the site's content-sync tests fail.
    guides.extend(VIRTUAL_PAGES)
    return guides


def build_nav(guides: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the nav.json structure from guides."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for guide in guides:
        group_title = guide["nav_group"]
        if group_title not in groups:
            groups[group_title] = []
        groups[group_title].append(guide)

    for group_guides in groups.values():
        group_guides.sort(key=lambda g: g["nav_order"])

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
        json.dumps(nav, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_readme_table(table: str) -> None:
    """Write the generated table into README.md between the docs markers."""
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
    """Check if the README docs table matches the generated version."""
    readme = README.read_text(encoding="utf-8")
    if BEGIN_MARKER not in readme or END_MARKER not in readme:
        return False
    _, rest = readme.split(BEGIN_MARKER, 1)
    current_table, _ = rest.split(END_MARKER, 1)
    return current_table.strip() == table.strip()


# --- README Code Overview table (packages block) ---

BEGIN = "<!-- BEGIN GENERATED: {name} -->"
END = "<!-- END GENERATED: {name} -->"

# The directories whose ``*/pyproject.toml`` files define a distribution row.
# A member without a ``[project]`` table (a JS app, for instance) is not a row.
MEMBER_GLOBS = ("packages/*/pyproject.toml", "apps/*/pyproject.toml")
_PROJECT_SECTION = re.compile(r"^\[project\]\s*$")
_NAME = re.compile(r'^name\s*=\s*"([^"]*)"\s*$')
_DESCRIPTION = re.compile(r'^description\s*=\s*"([^"]*)"\s*$')
_EMPTY_CELL = "—"


def project_metadata(pyproject: Path) -> tuple[str, str] | None:
    """``(name, description)`` from a ``pyproject.toml``'s ``[project]`` table.

    Parsed by hand rather than with ``tomllib`` because the test matrix's floor
    is Python 3.10, where that module does not exist. Returns ``None`` when the
    file declares no distribution, so a non-Python member is skipped rather than
    guessed at.
    """
    name: str | None = None
    description = ""
    in_project = False
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.startswith("["):
            in_project = bool(_PROJECT_SECTION.match(line))
            continue
        if not in_project:
            continue
        if name is None and (match := _NAME.match(line)):
            name = match.group(1)
        elif match := _DESCRIPTION.match(line):
            description = match.group(1)
    if name is None:
        return None
    return name, description


def distribution_rows(root: Path = ROOT) -> list[tuple[str, str, str]]:
    """``(path, distribution, description)`` for every workspace member."""
    rows: list[tuple[str, str, str]] = []
    for pattern in MEMBER_GLOBS:
        for pyproject in sorted(root.glob(pattern)):
            metadata = project_metadata(pyproject)
            if metadata is None:
                continue
            name, description = metadata
            path = pyproject.parent.relative_to(root).as_posix() + "/"
            rows.append((path, name, description))
    return rows


def _cell(value: str) -> str:
    """A Markdown table cell that cannot break the row it sits in."""
    return " ".join(value.split()).replace("|", "\\|") or _EMPTY_CELL


def render_packages(root: Path = ROOT) -> str:
    """The Code Overview table, one row per workspace distribution.

    The shape is load-bearing: ``doc_check.readme_code_overview_paths`` reads the
    first cell of every row as a repository path and fails when it does not
    exist, so a bolded, backticked path in column one is the contract.
    """
    lines = ["| Path | Distribution | Description |", "|---|---|---|"]
    for path, name, description in distribution_rows(root):
        lines.append(f"| **`{path}`** | `{name}` | {_cell(description)} |")
    return "\n".join(lines)


# The generated blocks, in the order they appear in their file. A block is one
# name, one renderer. ``#1041`` adds the docs/nav block here.
BLOCKS: tuple[tuple[str, str, Callable[[Path], str]], ...] = (
    ("packages", "README.md", render_packages),
)


def replace_block(text: str, name: str, body: str) -> str:
    """Replace the body between ``name``'s markers, keeping the markers."""
    begin, end = BEGIN.format(name=name), END.format(name=name)
    start = text.find(begin)
    stop = text.find(end)
    if start == -1 or stop == -1 or stop < start:
        raise ValueError(f"the file is missing the {name!r} generated markers")
    start += len(begin)
    return f"{text[:start]}\n{body}\n{text[stop:]}"


# --- docs/reference/test-map.md (test-map block, #1047) ---

# Every Python file under these directories is a row: helpers and conftest
# included, so a file cannot hide by having no description.
TEST_DIR_GLOBS = (
    "packages/*/tests",
    "apps/*/tests",
    "tests",
    "website/tests",
    "brand/tests",
)
# The frontend tests live beside the code they cover.
TS_TEST_GLOBS = ("apps/studio/src/**/*.test.ts", "apps/studio/src/**/*.test.tsx")

_REFERENCE_DIRECTIVE = re.compile(r"^\s*///\s*<reference")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"^[ \t]*//(.*)$", re.MULTILINE)


def _first_prose_line(text: str) -> str | None:
    for raw in text.splitlines():
        line = raw.strip().lstrip("*/").strip()
        if line:
            return line
    return None


def _python_description(path: Path) -> str | None:
    """The first line of a Python module's docstring, or ``None``."""
    try:
        module = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return None
    docstring = ast.get_docstring(module)
    return _first_prose_line(docstring) if docstring else None


def _typescript_description(path: Path) -> str | None:
    """The first line of a TypeScript file's leading comment, or ``None``.

    A ``/// <reference ...>`` directive is a compiler instruction, not a
    description, so the first comment that is not one is the one that counts.
    """
    text = path.read_text(encoding="utf-8")
    block = _BLOCK_COMMENT.search(text)
    line = next(
        (
            match
            for match in _LINE_COMMENT.finditer(text)
            if not _REFERENCE_DIRECTIVE.match(match.group(0))
        ),
        None,
    )
    if line is not None and (block is None or line.start() < block.start()):
        return line.group(1).strip() or None
    if block is not None:
        return _first_prose_line(block.group(0))
    return None


def test_files(root: Path = ROOT) -> list[tuple[str, str | None]]:
    """``(path, description)`` for every test file, sorted by path."""
    rows: list[tuple[str, str | None]] = []
    seen: set[str] = set()

    def add(relative: str, description: str | None) -> None:
        if relative not in seen:
            seen.add(relative)
            rows.append((relative, description))

    for pattern in TEST_DIR_GLOBS:
        for base in sorted(root.glob(pattern)):
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*.py")):
                if "__pycache__" in path.parts:
                    continue
                add(path.relative_to(root).as_posix(), _python_description(path))
    for pattern in TS_TEST_GLOBS:
        for path in sorted(root.glob(pattern)):
            add(path.relative_to(root).as_posix(), _typescript_description(path))

    rows.sort(key=lambda row: row[0])
    return rows


def render_test_map(root: Path = ROOT) -> str:
    """The test map, one row per test file, described by the file itself."""
    lines = ["| Path | Covers |", "|---|---|"]
    for path, description in test_files(root):
        lines.append(f"| `{path}` | {_cell(description or '')} |")
    return "\n".join(lines)


# Blocks whose home is not README.md. They are rendered on their own so a test
# fixture that writes only a README does not have to create them.
STANDALONE_BLOCKS: tuple[tuple[str, str, Callable[[Path], str]], ...] = (
    ("test-map", TEST_MAP, render_test_map),
)


def _standalone_content(
    path: Path, name: str, render: Callable[[Path], str], root: Path
) -> str | None:
    """The file with its generated block refreshed, or ``None`` when absent."""
    if not path.is_file():
        return None
    return replace_block(path.read_text(encoding="utf-8"), name, render(root))


def expected(root: Path = ROOT) -> dict[str, str]:
    """``relative path -> generated content`` for every README-based block."""
    rendered: dict[str, str] = {}
    for name, relative, render in BLOCKS:
        path = root / relative
        text = rendered.get(relative) or path.read_text(encoding="utf-8")
        rendered[relative] = replace_block(text, name, render(root))
    return rendered


def write(root: Path = ROOT) -> list[str]:
    """Refresh every generated block. Returns the paths that changed."""
    changed: list[str] = []

    # Packages block: README Code Overview table.
    for relative, content in expected(root).items():
        path = root / relative
        if path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
            changed.append(relative)

    # Standalone blocks: their own file, not the README.
    for name, relative, render in STANDALONE_BLOCKS:
        path = root / relative
        refreshed = _standalone_content(path, name, render, root)
        if refreshed is not None and path.read_text(encoding="utf-8") != refreshed:
            path.write_text(refreshed, encoding="utf-8")
            changed.append(relative)

    # Docs / nav block: README docs table + website/content/nav.json.
    # Only active when the README carries the docs GENERATED markers.
    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    if BEGIN_MARKER in readme and END_MARKER in readme:
        guides = collect_guides()
        # Virtual pages (source is None) render from templates, not from a
        # docs/ file, so they belong in the site navigation but not in the
        # README's linked table.
        real_guides = [g for g in guides if g.get("source")]
        table = build_readme_table(real_guides)

        before, rest = readme.split(BEGIN_MARKER, 1)
        _, after = rest.split(END_MARKER, 1)
        new_readme = f"{before}{BEGIN_MARKER}\n{table}{END_MARKER}{after}"
        if readme != new_readme:
            readme_path.write_text(new_readme, encoding="utf-8")
            changed.append("README.md")

        new_nav = json.dumps(build_nav(guides), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        nav_json_path = root / "website" / "content" / "nav.json"
        if nav_json_path.is_file():
            current_nav = nav_json_path.read_text(encoding="utf-8")
            if current_nav != new_nav:
                nav_json_path.write_text(new_nav, encoding="utf-8")
                changed.append(nav_json_path.relative_to(root).as_posix())

    return changed


def check(root: Path = ROOT) -> list[str]:
    """Issues for every stale generated block. Writes nothing."""
    issues: list[str] = []

    # Packages block.
    for relative, content in expected(root).items():
        if (root / relative).read_text(encoding="utf-8") != content:
            issues.append(f"{relative} is stale; run scripts/docs_index.py --write")

    # Standalone blocks, each in its own file.
    for name, relative, render in STANDALONE_BLOCKS:
        path = root / relative
        refreshed = _standalone_content(path, name, render, root)
        if refreshed is not None and path.read_text(encoding="utf-8") != refreshed:
            issues.append(f"{relative} is stale; run scripts/docs_index.py --write")

    # Docs / nav block (only when the README carries the docs markers).
    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    if BEGIN_MARKER in readme and END_MARKER in readme:
        guides = collect_guides()
        # Virtual pages (source is None) render from templates, not from a
        # docs/ file, so they belong in the site navigation but not in the
        # README's linked table.
        real_guides = [g for g in guides if g.get("source")]
        table = build_readme_table(real_guides)

        _, rest = readme.split(BEGIN_MARKER, 1)
        current_table, _ = rest.split(END_MARKER, 1)
        if current_table.strip() != table.strip():
            issues.append("README.md docs table is stale")

        nav_json_path = root / "website" / "content" / "nav.json"
        if nav_json_path.is_file():
            current = json.loads(nav_json_path.read_text(encoding="utf-8"))
            if current != build_nav(guides):
                issues.append(f"{nav_json_path.relative_to(root)} is stale")

    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="refresh the generated blocks (default)")
    mode.add_argument(
        "--check", action="store_true", help="fail if a block is stale; write nothing"
    )
    args = parser.parse_args(argv)

    if args.check:
        issues = check()
        for issue in issues:
            print(f"generated block: {issue}", file=sys.stderr)
        if issues:
            return 1
        print("Generated blocks are up to date.")
        return 0

    changed = write()
    for relative in changed:
        print(f"Updated {relative}")
    if not changed:
        print("Generated blocks are up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
