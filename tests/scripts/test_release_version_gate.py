"""A release tag must match the version the CLI reports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / ".github" / "workflows" / "release.yml"


def _workflow() -> str:
    return RELEASE.read_text(encoding="utf-8")


def test_the_version_job_runs_before_the_builds() -> None:
    workflow = _workflow()

    assert "\n  version:\n" in workflow
    assert "needs: [version]" in workflow


def test_the_gate_compares_the_tag_with_the_cli_version() -> None:
    workflow = _workflow()
    job = workflow.split("\n  version:\n", 1)[1].split("\n  build:\n", 1)[0]

    assert 'tag_version="${GITHUB_REF_NAME#v}"' in job
    assert "uv run python -m agentic_odi_cli --version" in job
    assert 'cli_version="${reported%% *}"' in job, (
        "the build date must be stripped before comparing"
    )
    assert '"$cli_version" != "$tag_version"' in job
    assert "exit 1" in job
