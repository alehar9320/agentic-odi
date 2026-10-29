"""The release workflows must be triggered by the release itself.

release-please publishes through the GitHub API, which does not emit a
`push` event for the tag. A workflow that only listens for `push: tags`
never runs for an automated release — the failure that left every release
from 0.7.0 to 0.12.0 without desktop bundles. These locks keep the trigger,
the manifest verification, and the App-credentials guard from silently
disappearing.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_release_workflow_triggers_on_published_release() -> None:
    text = _workflow("release.yml")
    assert "release:" in text
    assert "types: [published]" in text


def test_tauri_release_workflow_triggers_on_published_release() -> None:
    text = _workflow("tauri-release.yml")
    assert "release:" in text
    assert "types: [published]" in text


def test_tauri_release_verify_job_checks_every_platform_signed() -> None:
    verify = _workflow("tauri-release.yml").split("\n  verify:\n", 1)[1]
    for key in ("linux-x86_64", "windows-x86_64", "darwin-aarch64", "darwin-x86_64"):
        assert key in verify, f"verify job does not mention {key}"
    assert "signature" in verify
    assert "exit 1" in verify, "the verify job must fail the release, not warn"


def test_release_please_workflow_guards_on_app_credentials() -> None:
    text = _workflow("release-please.yml")
    assert "Check for GitHub App credentials" in text
    assert "RELEASE_PLEASE_APP_CLIENT_ID" in text
    assert "RELEASE_PLEASE_APP_PRIVATE_KEY" in text
