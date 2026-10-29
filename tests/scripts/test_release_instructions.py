"""Unit tests for scripts/release_instructions.py.

Pure-function coverage: the section generator and the body application
helper. `main()` is exercised with monkeypatched subprocess so no network
or `gh` binary is required.
"""

import shlex
import subprocess

from release_instructions import (
    _studio_install_command,
    apply_instructions,
    build_instructions_section,
    main,
)


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


def _fenced_block_after(section: str, heading: str, language: str = "bash") -> list[str]:
    """Return the lines of the first fenced block of ``language`` after ``heading``."""
    rest = section.split(heading, 1)[1]
    body = rest.split(f"```{language}", 1)[1].split("```", 1)[0]
    return [line for line in body.strip().splitlines() if line.strip()]


def test_verify_block_is_one_copy_pasteable_curl_command():
    import shlex

    section = build_instructions_section("v0.7.0", "alehar9320/agentic-odi", [], "")

    block = _fenced_block_after(section, "### 2. Verify the download")
    urls = [line for line in block if line.startswith("http")]
    curl_lines = [line for line in block if line.startswith("curl")]

    assert urls == []
    assert len(curl_lines) == 1
    # A URL on its own line would make the previous line a broken command.
    assert shlex.split(curl_lines[0]) == [
        "curl",
        "-fsSL",
        "-O",
        "https://github.com/alehar9320/agentic-odi/releases/download/v0.7.0/checksums.txt",
    ]


def test_verify_block_checks_only_the_downloaded_archive():
    """`checksums.txt` lists every platform, so `-c` on the whole file would fail."""
    section = build_instructions_section("v0.12.0", "alehar9320/agentic-odi", CLI_ARTIFACTS, "")

    linux = _fenced_block_after(section, "**Linux (x86_64)**")
    # The check must name the one archive this platform downloaded.
    assert any("odi_0.12.0_linux_x86_64.tar.gz" in line for line in linux)
    assert any(line.startswith("grep ") for line in linux)
    assert not any("sha256sum -c checksums.txt" in line for line in linux)

    mac = _fenced_block_after(section, "**macOS (Intel)**")
    assert any("shasum -a 256 -c -" in line for line in mac)

    windows = _fenced_block_after(section, "**Windows (x86_64)**", language="powershell")
    assert any("Get-FileHash" in line for line in windows)


def test_instructions_are_numbered_steps_with_a_quick_start():
    section = build_instructions_section("v0.12.0", "alehar9320/agentic-odi", [], "")

    for heading in (
        "### 1. Download the archive for your platform",
        "### 2. Verify the download",
        "### 3. Install",
        "### 4. Quick start",
    ):
        assert heading in section
    assert "odi --version" in section
    assert "odi jobs list" in section


def test_instructions_surface_the_release_date_when_known():
    section = build_instructions_section("v0.12.0", "alehar9320/agentic-odi", [], "", "2026-10-21")
    assert "released 2026-10-21" in section


def test_manual_install_uses_real_archive_names_when_available():
    section = build_instructions_section("v0.12.0", "alehar9320/agentic-odi", CLI_ARTIFACTS, "")
    assert "tar -xzf odi_0.12.0_linux_x86_64.tar.gz" in section
    assert "Expand-Archive odi_0.12.0_windows_x86_64.zip" in section


STUDIO_ARTIFACTS = [
    {
        "name": "Agentic ODI Living Studio_0.12.0_amd64.deb",
        "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.12.0/Agentic%20ODI%20Living%20Studio_0.12.0_amd64.deb",
        "size": 1,
    },
    {
        "name": "Agentic ODI Living Studio_0.12.0_x86_64.AppImage",
        "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.12.0/Agentic%20ODI%20Living%20Studio_0.12.0_x86_64.AppImage",
        "size": 1,
    },
    {
        "name": "Agentic ODI Living Studio_0.12.0_x86_64.dmg",
        "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.12.0/Agentic%20ODI%20Living%20Studio_0.12.0_x86_64.dmg",
        "size": 1,
    },
    {
        "name": "Agentic ODI Living Studio_0.12.0_x64-setup.exe",
        "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.12.0/Agentic%20ODI%20Living%20Studio_0.12.0_x64-setup.exe",
        "size": 1,
    },
]

CLI_ARTIFACTS = [
    {
        "name": "odi_0.12.0_linux_x86_64.tar.gz",
        "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.12.0/odi_0.12.0_linux_x86_64.tar.gz",
        "size": 12345,
    },
    {
        "name": "odi_0.12.0_macos_x86_64.tar.gz",
        "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.12.0/odi_0.12.0_macos_x86_64.tar.gz",
        "size": 12345,
    },
    {
        "name": "odi_0.12.0_windows_x86_64.zip",
        "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.12.0/odi_0.12.0_windows_x86_64.zip",
        "size": 6789,
    },
]


def test_studio_section_lists_bundles_with_install_commands():
    section = build_instructions_section("v0.12.0", "alehar9320/agentic-odi", STUDIO_ARTIFACTS, "")

    assert "### Living Studio (desktop)" in section
    assert "## 📦 Download & Run" in section
    for a in STUDIO_ARTIFACTS:
        assert a["browser_download_url"] in section
    assert "Linux (.deb)" in section
    assert "Linux (AppImage)" in section
    assert "macOS (dmg)" in section
    assert "Windows (exe)" in section
    assert "sudo apt install" in section
    assert "double-click" in section
    assert "/S" in section


def test_studio_and_cli_coexist_without_duplication():
    section = build_instructions_section(
        "v0.12.0", "alehar9320/agentic-odi", CLI_ARTIFACTS + STUDIO_ARTIFACTS, ""
    )

    assert "### Living Studio (desktop)" in section
    # Every asset gets exactly one download link.
    for a in CLI_ARTIFACTS + STUDIO_ARTIFACTS:
        assert section.count(a["browser_download_url"]) == 1


def test_studio_install_command_shell_escapes_spaced_names():
    name = "Agentic ODI Living Studio_0.12.0_amd64.deb"
    cmd = _studio_install_command(name)

    assert shlex.quote(name) in cmd
    assert name in shlex.split(cmd)
