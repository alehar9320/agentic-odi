"""The build must be deterministic, and generated output must never be tracked."""

from __future__ import annotations

import json
import subprocess

import build_site
import extract
import jinja2
import pytest
from site_support import ROOT


def _tree(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
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


def test_broken_reference_fails_the_build():
    # A page that points at an asset the build never wrote is broken even
    # though it renders; the build must name the page and the reference.
    files = build_site._render_site()
    files["index.html"] = files["index.html"].replace(
        b"</head>",
        b'<link rel="stylesheet" href="assets/missing.css"></head>',
        1,
    )
    violations = build_site._reference_violations(files)
    assert violations == [
        "index.html references 'assets/missing.css', which is not in the build output"
    ]


def test_an_unrendered_template_slot_fails_the_build():
    # A blank section is a page that shipped with a slot the build never
    # filled; the environment must refuse to render it silently.
    env = build_site.environment()
    with pytest.raises(jinja2.UndefinedError):
        env.from_string("<h1>{{ missing_slot }}</h1>").render()


def test_every_local_reference_resolves():
    # The current tree must pass the same check the build enforces.
    files = build_site._render_site()
    assert build_site._broken_references(files) == []


def test_a_committed_page_that_drifts_fails_the_check(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    page = site / build_site.SAMPLE_OUTPUT
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("stale", encoding="utf-8")
    with pytest.raises(SystemExit):
        build_site.check_committed(site)


def test_committed_outputs_are_current():
    # The committed sample page must match a fresh build of the fixture.
    build_site.check_committed()


def test_generated_output_is_not_tracked():
    # ``website/dist/`` is generated; it must never reappear in source control.
    result = subprocess.run(
        ["git", "ls-files", "--", "website/dist"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", (
        "website/dist is generated; build it instead of committing it"
    )


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
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*.html")
        if path.name != "404.html"
    }
    expected = {"" if page == "index.html" else page[: -len("index.html")] for page in pages}
    assert {entry["url"] for entry in entries} == expected
