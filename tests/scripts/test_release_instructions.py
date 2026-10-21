"""Unit tests for scripts/release_instructions.py.

Pure-function coverage: the section generator and the body application
helper. `main()` is exercised with monkeypatched subprocess so no network
or `gh` binary is required.
"""

import subprocess

from release_instructions import apply_instructions, build_instructions_section, main


def test_build_instructions_section_contains_artifacts_and_installers():
    artifacts = [
        {
            "name": "odi_0.7.0_linux_x86_64.tar.gz",
            "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.7.0/odi_0.7.0_linux_x86_64.tar.gz",
            "size": 12345,
        },
        {
            "name": "odi_0.7.0_windows_x86_64.zip",
            "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.7.0/odi_0.7.0_windows_x86_64.zip",
            "size": 67890,
        },
        {
            "name": "checksums.txt",
            "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.7.0/checksums.txt",
            "size": 100,
        },
        {
            "name": "install.sh",
            "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.7.0/install.sh",
            "size": 200,
        },
        {
            "name": "install.ps1",
            "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.7.0/install.ps1",
            "size": 210,
        },
    ]
    section = build_instructions_section(
        "v0.7.0", "alehar9320/agentic-odi", artifacts, "abc123  odi_0.7.0_linux_x86_64.tar.gz\n"
    )
    assert "## 📦 Download & Run" in section
    assert "<!-- AGENTIC_ODI_DOWNLOAD_START -->" in section
    assert "<!-- AGENTIC_ODI_DOWNLOAD_END -->" in section
    assert artifacts[0]["browser_download_url"] in section
    assert artifacts[1]["browser_download_url"] in section
    assert "checksums.txt" in section
    assert "install.sh | sh" in section
    assert "install.ps1 | iex" in section
    assert "odi --version" in section


def test_apply_instructions_appends_when_no_markers():
    body = "# Changelog\n\n- fix: something\n"
    section = "<!-- AGENTIC_ODI_DOWNLOAD_START -->\nX\n<!-- AGENTIC_ODI_DOWNLOAD_END -->\n"
    out = apply_instructions(body, section)
    assert body in out
    assert "X" in out
    assert out.count("<!-- AGENTIC_ODI_DOWNLOAD_START -->") == 1
    assert out.count("<!-- AGENTIC_ODI_DOWNLOAD_END -->") == 1


def test_apply_instructions_replaces_existing_section_without_duplicating():
    old_section = "<!-- AGENTIC_ODI_DOWNLOAD_START -->\nold\n<!-- AGENTIC_ODI_DOWNLOAD_END -->\n"
    body = "# Changelog\n\n" + old_section + "\n"
    new_section = "<!-- AGENTIC_ODI_DOWNLOAD_START -->\nnew\n<!-- AGENTIC_ODI_DOWNLOAD_END -->\n"
    out = apply_instructions(body, new_section)
    assert out.count("<!-- AGENTIC_ODI_DOWNLOAD_START -->") == 1
    assert out.count("<!-- AGENTIC_ODI_DOWNLOAD_END -->") == 1
    assert "old" not in out
    assert "new" in out
    assert "# Changelog" in out


def test_apply_instructions_handles_none_body():
    section = "<!-- AGENTIC_ODI_DOWNLOAD_START -->\nX\n<!-- AGENTIC_ODI_DOWNLOAD_END -->\n"
    out = apply_instructions(None, section)
    assert "X" in out


def test_build_instructions_section_without_checksums_degrades_to_links_only():
    artifacts = [
        {
            "name": "odi_0.7.0_linux_x86_64.tar.gz",
            "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.7.0/odi_0.7.0_linux_x86_64.tar.gz",
            "size": 1,
        },
    ]
    section = build_instructions_section("v0.7.0", "alehar9320/agentic-odi", artifacts, "")
    assert artifacts[0]["browser_download_url"] in section
    assert "checksums.txt" in section
    assert "odi --version" in section


def _is_release_view(cmd, tag):
    return (
        len(cmd) >= 4
        and cmd[0] == "gh"
        and cmd[1] == "release"
        and cmd[2] == "view"
        and cmd[3] == tag
    )


def _is_release_edit(cmd, tag):
    return (
        len(cmd) >= 4
        and cmd[0] == "gh"
        and cmd[1] == "release"
        and cmd[2] == "edit"
        and cmd[3] == tag
    )


def test_main_publishes_instructions(monkeypatch, capsys):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        if _is_release_view(cmd, "v0.7.0"):

            class R:
                stdout = '{"body": "# Changelog\\n"}'

            return R()
        if len(cmd) >= 2 and cmd[0] == "gh" and cmd[1] == "api":

            class R:
                stdout = (
                    '{"assets": [{"name": "odi_0.7.0_linux_x86_64.tar.gz", '
                    '"browser_download_url": "https://x/dl/odi_0.7.0_linux_x86_64.tar.gz", '
                    '"size": 1}]}'
                )

            return R()

        class R:
            stdout = ""

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    rc = main(["--tag", "v0.7.0", "--repo", "alehar9320/agentic-odi", "--dry-run"])
    assert rc == 0
    # dry-run: prints the new body and does NOT call gh release edit
    assert not any(_is_release_edit(c, "v0.7.0") for c in calls)
    out = capsys.readouterr().out
    assert "https://x/dl/odi_0.7.0_linux_x86_64.tar.gz" in out
    assert "install.sh | sh" in out
    assert "## 📦 Download & Run" in out
