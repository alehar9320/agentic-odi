"""The renderer inventory and the gate that keeps it true.

The epic's stated failure is a new renderer that nobody audited. A list of
renderers in a document cannot catch that, because the person who adds the
renderer is the person who would have to update the list. So the inventory is
data and the test is the enforcement: a scan of the directories an artifact can
come from must find nothing the inventory does not name.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from artifact_renderers import (
    ARTIFACT_ROOTS,
    MARKUP_SIGNALS,
    RENDERERS,
    REPO_ROOT,
    STATUSES,
    discover_html_emitters,
)


def test_every_registered_renderer_exists_or_is_marked_absent() -> None:
    for renderer in RENDERERS:
        if renderer.status == "absent":
            assert renderer.path == "", f"{renderer.name} is absent, so it names no file"
        else:
            assert (REPO_ROOT / renderer.path).is_file(), (
                f"{renderer.name} points at {renderer.path}, which is not a file"
            )


def test_an_emitter_under_an_artifact_root_must_be_registered() -> None:
    registered = {renderer.path for renderer in RENDERERS if renderer.path}
    unregistered = discover_html_emitters() - registered
    assert unregistered == set(), f"unregistered artifact renderers: {sorted(unregistered)}"


def test_the_inventory_has_no_stale_paths() -> None:
    """A row that points outside the scanned roots would pass the gate forever."""
    paths = [renderer.path for renderer in RENDERERS if renderer.path]
    assert len(paths) == len(set(paths)), "two inventory rows name the same file"
    for renderer in RENDERERS:
        if not renderer.path:
            continue
        assert any(renderer.path.startswith(f"{root}/") for root in ARTIFACT_ROOTS), (
            f"{renderer.name} lives outside every scanned root, so the gate cannot see it"
        )


def test_every_row_claims_a_status_the_inventory_can_say() -> None:
    """A status outside the vocabulary is a row no reader can interpret."""
    for renderer in RENDERERS:
        assert renderer.status in STATUSES, f"{renderer.name} claims {renderer.status!r}"


def test_absent_artifacts_are_recorded_not_claimed() -> None:
    """The issue asks for a memo, a one-pager and a shared page. None exists.

    Recording them as absent is the difference between an inventory and an
    aspirational list: the audit cannot run over an artifact nobody renders, and
    the work to give them a renderer is ALH-252's, not a checkmark here.
    """
    absent = {renderer.name for renderer in RENDERERS if renderer.status == "absent"}
    assert absent == {"memo", "one-pager", "shared page"}
    for renderer in RENDERERS:
        if renderer.status == "absent":
            assert renderer.fixes_owned_by == "ALH-252"


def test_discovery_skips_tests_and_compiled_output(tmp_path: Path) -> None:
    """The scan is a net over sources, not over everything on disk."""
    root = tmp_path / "website" / "tools"
    root.mkdir(parents=True)
    (root / "build_site.py").write_text("page = '<!DOCTYPE html><h1>Title</h1>'", encoding="utf-8")
    (root / "build_site.test.py").write_text("assert '<h1>' in page", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "build_site.cpython-314.pyc").write_text("<table>", encoding="utf-8")
    assert discover_html_emitters(tmp_path) == {"website/tools/build_site.py"}


def test_discovery_reports_relative_paths_for_a_page_template(tmp_path: Path) -> None:
    root = tmp_path / "website" / "templates"
    root.mkdir(parents=True)
    (root / "probe.html").write_text("<h1>x</h1>", encoding="utf-8")
    assert discover_html_emitters(tmp_path) == {"website/templates/probe.html"}


@pytest.mark.parametrize("signal", MARKUP_SIGNALS)
def test_each_markup_signal_can_betray_a_renderer(tmp_path: Path, signal: str) -> None:
    root = tmp_path / "apps" / "studio" / "src" / "lib"
    root.mkdir(parents=True)
    (root / "emit.ts").write_text(f'const markup = "{signal} <";', encoding="utf-8")
    assert discover_html_emitters(tmp_path) == {"apps/studio/src/lib/emit.ts"}
