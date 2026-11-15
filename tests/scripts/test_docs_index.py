"""Tests for scripts/docs_index.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.docs_index as docs_index


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

    # Patch the DOCS_DIR constant
    original_docs_dir = docs_index.DOCS_DIR
    docs_index.DOCS_DIR = docs_dir
    try:
        guides = docs_index.collect_guides()
    finally:
        docs_index.DOCS_DIR = original_docs_dir

    assert len(guides) == 2
    slugs = {g["slug"] for g in guides}
    assert slugs == {"guide-one", "guide-two"}
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

    assert len(guides) == 1
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
    # Header rows
    assert lines[0] == "| Guide | Contents |"
    assert lines[1] == "|---|---|"
    # Data rows in correct order
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
        # First write
        guides = docs_index.collect_guides()
        nav = docs_index.build_nav(guides)
        table = docs_index.build_readme_table(guides)
        docs_index.write_nav_json(nav)
        docs_index.write_readme_table(table)

        nav_content_1 = nav_json.read_text(encoding="utf-8")
        readme_content_1 = readme.read_text(encoding="utf-8")

        # Second write
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
    # Write stale nav.json
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
    # Write correct nav.json
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
    # Write stale README table (different blurb)
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
    # Create initial README with markers
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

        # Second write
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

    assert len(guides) == 1
    assert guides[0]["slug"] == "my-guide"


def test_strip_front_matter() -> None:
    """strip_front_matter removes YAML front matter."""
    text = "---\ntitle: Test\nnav_group: Get started\n---\n\n# Content\n\nBody."
    assert docs_index.strip_front_matter(text) == "\n# Content\n\nBody."

    # No front matter
    text = "# Content\n\nBody."
    assert docs_index.strip_front_matter(text) == "# Content\n\nBody."

    # Front matter with extra content
    text = "---\ntitle: Test\n---\n\n# Content\n\nBody."
    assert docs_index.strip_front_matter(text) == "\n# Content\n\nBody."
