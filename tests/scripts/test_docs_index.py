"""Tests for scripts/docs_index.py.

Covers both generated blocks owned by the script:

- the docs/front-matter navigation (``website/content/nav.json`` plus the
  README Documentation table), and
- the README Code Overview packages table derived from each workspace
  member's ``pyproject.toml``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.docs_index as docs_index

ROOT = Path(__file__).resolve().parents[2]


def _member(tmp_path: Path, path: str, name: str, description: str) -> None:
    member = tmp_path / path
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\ndescription = "{description}"\n', encoding="utf-8"
    )


# --- docs / navigation block (main's feature) ---


def test_collect_guides_finds_all_front_matter(tmp_path: Path) -> None:
    """A new page with front matter registers itself."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide1.md").write_text(
        "---\ntitle: Guide One\nblurb: First guide\nnav_group: Get started\nnav_order: 0\nslug: guide-one\n---\n\n# Guide One\n\nContent.",
        encoding="utf-8",
    )
    (docs_dir / "guide2.md").write_text(
        "---\ntitle: Guide Two\nblurb: Second guide\nnav_group: Build\nnav_order: 1\nslug: guide-two\n---\n\n# Guide Two\n\nContent.",
        encoding="utf-8",
    )

    original_docs_dir = docs_index.DOCS_DIR
    docs_index.DOCS_DIR = docs_dir
    try:
        guides = docs_index.collect_guides()
    finally:
        docs_index.DOCS_DIR = original_docs_dir

    assert len(guides) == 4
    slugs = {g["slug"] for g in guides}
    assert slugs == {"guide-one", "guide-two", "quick-start", "mcp"}
    for guide in guides:
        assert "title" in guide
        assert "blurb" in guide
        assert "nav_group" in guide
        assert "nav_order" in guide
        assert "slug" in guide
        assert "source" in guide


def test_collect_guides_missing_nav_group_fails(tmp_path: Path) -> None:
    """A page missing nav_group fails with the filename."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "bad_guide.md").write_text(
        "---\ntitle: Bad Guide\nblurb: Missing nav_group\nnav_order: 0\nslug: bad-guide\n---\n\n# Bad Guide\n\nContent.",
        encoding="utf-8",
    )

    original_docs_dir = docs_index.DOCS_DIR
    docs_index.DOCS_DIR = docs_dir
    try:
        with pytest.raises(
            ValueError, match=r"bad_guide\.md: missing front matter fields:.*nav_group"
        ):
            docs_index.collect_guides()
    finally:
        docs_index.DOCS_DIR = original_docs_dir


def test_collect_guides_excludes_superpowers(tmp_path: Path) -> None:
    """docs/superpowers/** is excluded from the index."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text(
        "---\ntitle: Guide\nblurb: A guide\nnav_group: Get started\nnav_order: 0\nslug: guide\n---\n\n# Guide\n\nContent.",
        encoding="utf-8",
    )
    superpowers_dir = docs_dir / "superpowers"
    superpowers_dir.mkdir()
    (superpowers_dir / "plan.md").write_text(
        "---\ntitle: Plan\nblurb: A plan\nnav_group: Get started\nnav_order: 0\nslug: plan\n---\n\n# Plan\n\nContent.",
        encoding="utf-8",
    )

    original_docs_dir = docs_index.DOCS_DIR
    docs_index.DOCS_DIR = docs_dir
    try:
        guides = docs_index.collect_guides()
    finally:
        docs_index.DOCS_DIR = original_docs_dir

    assert len(guides) == 3
    slugs = {g["slug"] for g in guides}
    assert slugs == {"guide", "quick-start", "mcp"}
    assert guides[0]["slug"] == "guide"


def test_build_nav_groups_and_sorts(tmp_path: Path) -> None:
    """build_nav groups guides by nav_group and sorts by nav_order."""
    guides = [
        {
            "slug": "c",
            "title": "C",
            "source": "docs/c.md",
            "blurb": "C",
            "nav_group": "Build",
            "nav_order": 0,
        },
        {
            "slug": "a",
            "title": "A",
            "source": "docs/a.md",
            "blurb": "A",
            "nav_group": "Get started",
            "nav_order": 1,
        },
        {
            "slug": "b",
            "title": "B",
            "source": "docs/b.md",
            "blurb": "B",
            "nav_group": "Get started",
            "nav_order": 0,
        },
    ]
    nav = docs_index.build_nav(guides)
    group_titles = [g["title"] for g in nav["groups"]]
    assert group_titles == ["Get started", "Build"]
    get_started_guides = nav["groups"][0]["guides"]
    assert [g["slug"] for g in get_started_guides] == ["b", "a"]
    build_guides = nav["groups"][1]["guides"]
    assert [g["slug"] for g in build_guides] == ["c"]


def test_build_readme_table_sorted(tmp_path: Path) -> None:
    """build_readme_table sorts by group order then nav_order."""
    guides = [
        {
            "slug": "c",
            "title": "C",
            "source": "docs/c.md",
            "blurb": "C",
            "nav_group": "Build",
            "nav_order": 0,
        },
        {
            "slug": "a",
            "title": "A",
            "source": "docs/a.md",
            "blurb": "A",
            "nav_group": "Get started",
            "nav_order": 1,
        },
        {
            "slug": "b",
            "title": "B",
            "source": "docs/b.md",
            "blurb": "B",
            "nav_group": "Get started",
            "nav_order": 0,
        },
    ]
    table = docs_index.build_readme_table(guides)
    lines = table.strip().split("\n")
    assert lines[0] == "| Guide | Contents |"
    assert lines[1] == "|---|---|"
    assert "| [B](docs/b.md) | B |" in lines[2]
    assert "| [A](docs/a.md) | A |" in lines[3]
    assert "| [C](docs/c.md) | C |" in lines[4]


def test_write_and_check_roundtrip(tmp_path: Path) -> None:
    """The generated output is byte-stable across two runs."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text(
        "---\ntitle: Guide\nblurb: A guide\nnav_group: Get started\nnav_order: 0\nslug: guide\n---\n\n# Guide\n\nContent.",
        encoding="utf-8",
    )

    nav_json = tmp_path / "nav.json"
    readme = tmp_path / "README.md"
    readme.write_text(
        "## Documentation\n\n<!-- BEGIN GENERATED: docs -->\n\n<!-- END GENERATED: docs -->\n",
        encoding="utf-8",
    )

    original_docs_dir = docs_index.DOCS_DIR
    original_nav_json = docs_index.NAV_JSON
    original_readme = docs_index.README
    docs_index.DOCS_DIR = docs_dir
    docs_index.NAV_JSON = nav_json
    docs_index.README = readme
    try:
        guides = docs_index.collect_guides()
        nav = docs_index.build_nav(guides)
        table = docs_index.build_readme_table(guides)
        docs_index.write_nav_json(nav)
        docs_index.write_readme_table(table)

        nav_content_1 = nav_json.read_text(encoding="utf-8")
        readme_content_1 = readme.read_text(encoding="utf-8")

        guides = docs_index.collect_guides()
        nav = docs_index.build_nav(guides)
        table = docs_index.build_readme_table(guides)
        docs_index.write_nav_json(nav)
        docs_index.write_readme_table(table)

        nav_content_2 = nav_json.read_text(encoding="utf-8")
        readme_content_2 = readme.read_text(encoding="utf-8")

        assert nav_content_1 == nav_content_2
        assert readme_content_1 == readme_content_2
    finally:
        docs_index.DOCS_DIR = original_docs_dir
        docs_index.NAV_JSON = original_nav_json
        docs_index.README = original_readme


def test_check_detects_stale_nav_json(tmp_path: Path) -> None:
    """--check fails when nav.json is stale."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text(
        "---\ntitle: Guide\nblurb: A guide\nnav_group: Get started\nnav_order: 0\nslug: guide\n---\n\n# Guide\n\nContent.",
        encoding="utf-8",
    )

    nav_json = tmp_path / "nav.json"
    readme = tmp_path / "README.md"
    readme.write_text(
        "## Documentation\n\n<!-- BEGIN GENERATED: docs -->\n| Guide | Contents |\n|---|---|\n| [Guide](docs/guide.md) | A guide |\n<!-- END GENERATED: docs -->\n",
        encoding="utf-8",
    )
    nav_json.write_text(json.dumps({"groups": []}), encoding="utf-8")

    original_docs_dir = docs_index.DOCS_DIR
    original_nav_json = docs_index.NAV_JSON
    original_readme = docs_index.README
    docs_index.DOCS_DIR = docs_dir
    docs_index.NAV_JSON = nav_json
    docs_index.README = readme
    try:
        guides = docs_index.collect_guides()
        nav = docs_index.build_nav(guides)
        assert docs_index.check_nav_json(nav) is False
    finally:
        docs_index.DOCS_DIR = original_docs_dir
        docs_index.NAV_JSON = original_nav_json
        docs_index.README = original_readme


def test_check_detects_stale_readme_table(tmp_path: Path) -> None:
    """--check fails when README table is stale."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text(
        "---\ntitle: Guide\nblurb: A guide\nnav_group: Get started\nnav_order: 0\nslug: guide\n---\n\n# Guide\n\nContent.",
        encoding="utf-8",
    )

    nav_json = tmp_path / "nav.json"
    readme = tmp_path / "README.md"
    nav_json.write_text(
        json.dumps(
            {
                "groups": [
                    {
                        "title": "Get started",
                        "guides": [
                            {
                                "slug": "guide",
                                "title": "Guide",
                                "source": "docs/guide.md",
                                "blurb": "A guide",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    readme.write_text(
        "## Documentation\n\n<!-- BEGIN GENERATED: docs -->\n| Guide | Contents |\n|---|---|\n| [Guide](docs/guide.md) | Different blurb |\n<!-- END GENERATED: docs -->\n",
        encoding="utf-8",
    )

    original_docs_dir = docs_index.DOCS_DIR
    original_nav_json = docs_index.NAV_JSON
    original_readme = docs_index.README
    docs_index.DOCS_DIR = docs_dir
    docs_index.NAV_JSON = nav_json
    docs_index.README = readme
    try:
        guides = docs_index.collect_guides()
        table = docs_index.build_readme_table(guides)
        assert docs_index.check_readme_table(table) is False
    finally:
        docs_index.DOCS_DIR = original_docs_dir
        docs_index.NAV_JSON = original_nav_json
        docs_index.README = original_readme


def test_check_passes_when_up_to_date(tmp_path: Path) -> None:
    """--check passes when both artefacts are up to date."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text(
        "---\ntitle: Guide\nblurb: A guide\nnav_group: Get started\nnav_order: 0\nslug: guide\n---\n\n# Guide\n\nContent.",
        encoding="utf-8",
    )

    nav_json = tmp_path / "nav.json"
    readme = tmp_path / "README.md"
    readme.write_text(
        "## Documentation\n\n<!-- BEGIN GENERATED: docs -->\n\n<!-- END GENERATED: docs -->\n",
        encoding="utf-8",
    )

    original_docs_dir = docs_index.DOCS_DIR
    original_nav_json = docs_index.NAV_JSON
    original_readme = docs_index.README
    docs_index.DOCS_DIR = docs_dir
    docs_index.NAV_JSON = nav_json
    docs_index.README = readme
    try:
        guides = docs_index.collect_guides()
        nav = docs_index.build_nav(guides)
        table = docs_index.build_readme_table(guides)
        docs_index.write_nav_json(nav)
        docs_index.write_readme_table(table)

        nav_content_1 = nav_json.read_text(encoding="utf-8")
        readme_content_1 = readme.read_text(encoding="utf-8")

        guides = docs_index.collect_guides()
        nav = docs_index.build_nav(guides)
        table = docs_index.build_readme_table(guides)
        docs_index.write_nav_json(nav)
        docs_index.write_readme_table(table)

        nav_content_2 = nav_json.read_text(encoding="utf-8")
        readme_content_2 = readme.read_text(encoding="utf-8")

        assert nav_content_1 == nav_content_2
        assert readme_content_1 == readme_content_2
    finally:
        docs_index.DOCS_DIR = original_docs_dir
        docs_index.NAV_JSON = original_nav_json
        docs_index.README = original_readme


def test_slug_defaults_to_filename(tmp_path: Path) -> None:
    """When slug is not in front matter, it defaults to the filename stem."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "my-guide.md").write_text(
        "---\ntitle: My Guide\nblurb: A guide\nnav_group: Get started\nnav_order: 0\n---\n\n# My Guide\n\nContent.",
        encoding="utf-8",
    )

    original_docs_dir = docs_index.DOCS_DIR
    docs_index.DOCS_DIR = docs_dir
    try:
        guides = docs_index.collect_guides()
    finally:
        docs_index.DOCS_DIR = original_docs_dir

    assert len(guides) == 3
    slugs = {g["slug"] for g in guides}
    assert slugs == {"my-guide", "quick-start", "mcp"}
    assert guides[0]["slug"] == "my-guide"


def test_strip_front_matter() -> None:
    """strip_front_matter removes YAML front matter."""
    text = "---\ntitle: Test\nnav_group: Get started\n---\n\n# Content\n\nBody."
    assert docs_index.strip_front_matter(text) == "\n# Content\n\nBody."

    text = "# Content\n\nBody."
    assert docs_index.strip_front_matter(text) == "# Content\n\nBody."

    text = "---\ntitle: Test\n---\n\n# Content\n\nBody."
    assert docs_index.strip_front_matter(text) == "\n# Content\n\nBody."


# --- packages / Code Overview block (#1044's feature) ---


def test_a_new_member_becomes_a_row_from_its_pyproject(tmp_path: Path) -> None:
    _member(tmp_path, "packages/new-thing", "agentic-odi-new", "A new distribution.")

    assert ("packages/new-thing/", "agentic-odi-new", "A new distribution.") in (
        docs_index.distribution_rows(tmp_path)
    )


def test_a_member_without_a_project_table_is_not_a_row(tmp_path: Path) -> None:
    (tmp_path / "apps" / "studio").mkdir(parents=True)
    (tmp_path / "apps" / "studio" / "pyproject.toml").write_text("[tool.x]\n", encoding="utf-8")

    assert docs_index.distribution_rows(tmp_path) == []


def test_the_table_keeps_the_shape_the_path_check_reads(tmp_path: Path) -> None:
    _member(tmp_path, "packages/core", "agentic-odi-core", "Core.")

    table = docs_index.render_packages(tmp_path)

    assert table.splitlines()[:2] == ["| Path | Distribution | Description |", "|---|---|---|"]
    assert table.splitlines()[2] == "| **`packages/core/`** | `agentic-odi-core` | Core. |"


def test_a_stale_description_fails_check(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    _member(tmp_path, "packages/core", "agentic-odi-core", "Renamed since the last render.")
    readme.write_text(
        f"{docs_index.BEGIN.format(name='packages')}\n"
        "| **`packages/core/`** | `agentic-odi-core` | The old description. |\n"
        f"{docs_index.END.format(name='packages')}\n",
        encoding="utf-8",
    )

    assert docs_index.check(tmp_path) == ["README.md is stale; run scripts/docs_index.py --write"]


def test_a_block_missing_its_markers_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("## Code Overview\n\nNo markers here.\n", encoding="utf-8")

    try:
        docs_index.expected(tmp_path)
    except ValueError as error:
        assert "packages" in str(error)
    else:  # pragma: no cover - the assert above is the point
        raise AssertionError("a missing marker pair must be reported")


def test_write_is_byte_stable_across_two_runs(tmp_path: Path) -> None:
    _member(tmp_path, "packages/core", "agentic-odi-core", "Core.")
    readme = tmp_path / "README.md"
    readme.write_text(
        f"{docs_index.BEGIN.format(name='packages')}\nplaceholder\n"
        f"{docs_index.END.format(name='packages')}\n",
        encoding="utf-8",
    )

    assert docs_index.write(tmp_path) == ["README.md"]
    first = readme.read_text(encoding="utf-8")

    assert docs_index.write(tmp_path) == []
    assert readme.read_text(encoding="utf-8") == first


def test_the_committed_readme_matches_a_fresh_render() -> None:
    assert docs_index.check(ROOT) == []
