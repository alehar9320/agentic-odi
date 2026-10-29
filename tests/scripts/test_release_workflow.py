"""The release workflows must be wired so assets actually get attached.

Regression guard. The workflows used to trigger only on `push: tags: [v*]`, but
release-please creates the tag with the repository `GITHUB_TOKEN`, and GitHub
does not start workflow runs for events that token produces. The workflows never
fired, every release shipped with zero assets, and `install.sh` /
`checksums.txt` returned 404. These checks assert the trigger and wiring that
make asset attachment independent of who created the tag.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
TAURI = ROOT / ".github" / "workflows" / "tauri-release.yml"

RELEASE_PLEASE_WORKFLOW = '"release-please"'
RESOLVED_TAG = "${{ needs.resolve.outputs.tag }}"


def _normalized(path: Path) -> str:
    """File text with comments dropped and whitespace collapsed to one line."""
    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]
    return re.sub(r"\s+", " ", " ".join(lines))


@pytest.mark.parametrize("path", [RELEASE, TAURI], ids=["release", "tauri-release"])
def test_assets_are_not_only_attached_on_a_tag_push(path: Path) -> None:
    """A `push: tags` trigger never fires for a release-please tag."""
    text = _normalized(path)
    assert "workflow_run:" in text, "must also run after release-please completes"
    assert RELEASE_PLEASE_WORKFLOW in text, "must chain off the release-please workflow"
    assert "workflow_dispatch:" in text, "must offer a manual self-heal path"


@pytest.mark.parametrize("path", [RELEASE, TAURI], ids=["release", "tauri-release"])
def test_the_tag_is_resolved_before_building(path: Path) -> None:
    text = _normalized(path)
    assert "scripts/release_assets.py" in text, "must gate on missing assets"
    assert "needs: resolve" in text or "needs: [resolve" in text


@pytest.mark.parametrize("path", [RELEASE, TAURI], ids=["release", "tauri-release"])
def test_builds_check_out_the_resolved_tag(path: Path) -> None:
    """On workflow_run/workflow_dispatch the default ref is main, not the tag."""
    text = _normalized(path)
    assert f"ref: {RESOLVED_TAG}" in text


def test_cli_assets_are_attached_to_the_resolved_tag() -> None:
    text = _normalized(RELEASE)
    # Every upload step must name the tag; without it an upload would land on
    # the default branch's release instead of the one being repaired.
    uploads = text.count("softprops/action-gh-release")
    assert uploads >= 3
    assert text.count(f"tag_name: {RESOLVED_TAG}") == uploads


def test_desktop_bundles_are_attached_to_the_resolved_tag() -> None:
    text = _normalized(TAURI)
    assert f"tagName: {RESOLVED_TAG}" in text


def test_release_page_instructions_are_published() -> None:
    text = _normalized(RELEASE)
    assert "release_instructions.py" in text
    assert "release-instructions:" in text
