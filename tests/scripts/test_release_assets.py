"""Unit tests for scripts/release_assets.py.

The gate decides whether a release is missing assets. It is pure (given the
release's asset names) except for ``_fetch_release``, so these tests cover the
pure helpers plus the CLI's output contract with ``gh`` monkeypatched.
"""

from __future__ import annotations

import json
import subprocess

from release_assets import (
    CLI_TARGETS,
    expected_cli_assets,
    main,
    missing_assets,
    should_build,
    should_publish_instructions,
    version_of,
)


def test_version_of_strips_a_leading_v_only():
    assert version_of("v0.12.0") == "0.12.0"
    assert version_of("0.12.0") == "0.12.0"
    # `lstrip("v")` would eat the whole string here; `removeprefix` must not.
    assert version_of("vv1.2.3") == "v1.2.3"


def test_expected_cli_assets_cover_every_target_plus_support_files():
    names = expected_cli_assets("0.12.0")
    for target in CLI_TARGETS:
        ext = ".zip" if target.startswith("windows") else ".tar.gz"
        assert f"odi_0.12.0_{target}{ext}" in names
    assert "checksums.txt" in names
    assert "install.sh" in names
    assert "install.ps1" in names


def test_missing_cli_assets_reports_every_absent_name():
    present = ["odi_0.12.0_linux_x86_64.tar.gz", "checksums.txt"]
    missing = missing_assets("cli", "0.12.0", present)
    assert "odi_0.12.0_linux_x86_64.tar.gz" not in missing
    assert "checksums.txt" not in missing
    assert "odi_0.12.0_windows_x86_64.zip" in missing
    assert "install.sh" in missing
    assert "install.ps1" in missing


def test_missing_cli_assets_is_empty_for_a_complete_release():
    assert missing_assets("cli", "0.12.0", expected_cli_assets("0.12.0")) == []


def test_missing_studio_assets_keys_on_installer_type():
    # Desktop bundle names embed the product name and version, so the gate only
    # requires one asset per installer type.
    present = [
        "Agentic ODI Living Studio_0.12.0_amd64.deb",
        "Agentic ODI Living Studio_0.12.0_x86_64.AppImage",
    ]
    missing = missing_assets("studio", "0.12.0", present)
    assert "*.dmg" in missing
    assert "*.exe" in missing
    assert "*.deb" not in missing
    assert "*.AppImage" not in missing


def test_should_build_only_when_something_is_missing_or_forced():
    assert should_build(["install.sh"], force=False) is True
    assert should_build([], force=False) is False
    assert should_build([], force=True) is True


def test_should_publish_instructions_when_built_or_still_missing():
    assert should_publish_instructions(build=True, instructions_present=True) is True
    assert should_publish_instructions(build=True, instructions_present=False) is True
    # The self-heal case: assets are fine but the page has no instructions yet.
    assert should_publish_instructions(build=False, instructions_present=False) is True
    assert should_publish_instructions(build=False, instructions_present=True) is False


def _release_payload(assets: list[str], body: str = "") -> str:
    return json.dumps({"assets": [{"name": n} for n in assets], "body": body})


def test_main_gates_a_complete_release_to_a_no_op(monkeypatch, capsys):
    def fake_run(cmd, **kwargs):
        class R:
            stdout = _release_payload(expected_cli_assets("0.12.0"))

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    rc = main(["--stream", "cli", "--tag", "v0.12.0", "--repo", "alehar9320/agentic-odi"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "tag=v0.12.0" in out
    assert "version=0.12.0" in out
    assert "should_build=false" in out


def test_main_builds_a_release_with_no_assets(monkeypatch, capsys):
    def fake_run(cmd, **kwargs):
        class R:
            stdout = _release_payload([])

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    rc = main(["--stream", "cli", "--tag", "v0.12.0", "--repo", "alehar9320/agentic-odi"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "should_build=true" in out
    assert "should_publish=true" in out
    assert (
        "download_base=https://github.com/alehar9320/agentic-odi/releases/download/v0.12.0" in out
    )


def test_main_builds_when_the_tag_has_no_release_yet(monkeypatch, capsys):
    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)
    rc = main(["--stream", "cli", "--tag", "v0.13.0", "--repo", "alehar9320/agentic-odi"])
    assert rc == 0
    assert "should_build=true" in capsys.readouterr().out


def test_main_force_rebuilds_a_complete_release(monkeypatch, capsys):
    def fake_run(cmd, **kwargs):
        class R:
            stdout = _release_payload(expected_cli_assets("0.12.0"))

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    rc = main(
        [
            "--stream",
            "cli",
            "--tag",
            "v0.12.0",
            "--repo",
            "alehar9320/agentic-odi",
            "--force",
        ]
    )
    assert rc == 0
    assert "should_build=true" in capsys.readouterr().out


def test_main_publishes_instructions_when_assets_are_complete_but_body_is_bare(monkeypatch, capsys):
    def fake_run(cmd, **kwargs):
        class R:
            stdout = _release_payload(expected_cli_assets("0.12.0"), body="# Changelog\n")

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    rc = main(["--stream", "cli", "--tag", "v0.12.0", "--repo", "alehar9320/agentic-odi"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "should_build=false" in out
    assert "should_publish=true" in out


def test_main_requires_a_repo(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    rc = main(["--stream", "cli", "--tag", "v0.12.0"])
    assert rc == 2
    assert "required" in capsys.readouterr().err
