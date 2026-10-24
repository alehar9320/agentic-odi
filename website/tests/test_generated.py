"""The build must be deterministic, and the committed output must be current."""

from __future__ import annotations

import json

import build_site
import extract
import pytest
from site_support import DIST, ROOT


def _tree(root):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_build_is_deterministic(tmp_path):
    first = tmp_path / "a"
    second = tmp_path / "b"
    build_site.build(first)
    build_site.build(second)
    assert _tree(first) == _tree(second)


def test_build_emits_expected_pages(tmp_path):
    build_site.build(tmp_path)
    for rel in ("index.html", "404.html", "sitemap.xml", "robots.txt"):
        assert (tmp_path / rel).is_file()


def test_check_fails_when_output_is_stale(tmp_path):
    build_site.build(tmp_path)
    (tmp_path / "index.html").write_text("stale", encoding="utf-8")
    with pytest.raises(SystemExit):
        build_site.build(tmp_path, check=True)


def test_check_passes_when_output_is_current(tmp_path):
    build_site.build(tmp_path)
    build_site.build(tmp_path, check=True)


def test_the_committed_site_matches_a_fresh_build():
    # The committed output is committed so a reviewer can read the rendered
    # HTML in a pull request. That only works if it is never stale.
    assert DIST.is_dir(), "the site has not been built; run build_site.py"
    build_site.build(DIST, check=True)


def test_the_cli_reference_mentions_every_registered_command():
    # The CLI reference is hand-written, so this is the only thing keeping it
    # from falling behind the commands the CLI actually registers.
    commands = extract.read_cli(ROOT / "apps" / "cli" / "src" / "agentic_odi_cli" / "cli.py")
    reference = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")

    assert commands
    missing = [command["name"] for command in commands if command["name"] not in reference]
    assert missing == []


def test_build_emits_a_search_index(tmp_path):
    # The docs are static, so the only way to search them without a network
    # call is an index the build writes next to the pages.
    build_site.build(tmp_path)
    entries = json.loads((tmp_path / "search-index.json").read_text(encoding="utf-8"))
    assert entries
    for entry in entries:
        assert entry["title"]
        assert isinstance(entry["url"], str)
        assert not entry["url"].startswith("http")
        assert "excerpt" in entry


def test_the_search_index_covers_every_page(tmp_path):
    build_site.build(tmp_path)
    entries = json.loads((tmp_path / "search-index.json").read_text(encoding="utf-8"))
    pages = {
        str(path.relative_to(tmp_path))
        for path in tmp_path.rglob("*.html")
        if path.name != "404.html"
    }
    expected = {"" if page == "index.html" else page[: -len("index.html")] for page in pages}
    assert {entry["url"] for entry in entries} == expected
