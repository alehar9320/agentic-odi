"""The build must be deterministic, and the committed output must be current."""

from __future__ import annotations

import build_site
import pytest
from site_support import DIST


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
