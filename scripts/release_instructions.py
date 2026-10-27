"""Generate and publish end-user "Download & Run" instructions for a GitHub release.

Pure functions:
    build_instructions_section(tag, repo, artifacts, checksums_text) -> str
    apply_instructions(body, section) -> str

CLI (``main``): fetches the release body/assets via ``gh``, grabs
``checksums.txt`` via ``curl``, builds the instructions section, applies it
idempotently to the release body, and publishes with ``gh release edit``
(unless ``--dry-run``).
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

DOWNLOAD_START = "<!-- AGENTIC_ODI_DOWNLOAD_START -->"
DOWNLOAD_END = "<!-- AGENTIC_ODI_DOWNLOAD_END -->"

GITHUB_RELEASES = "https://github.com"


def _archive_target(name: str) -> str:
    """Strip the ``odi_<version>_`` prefix and archive suffix to expose ``<os>_<arch>``."""
    stem = name
    for suffix in (".tar.gz", ".zip"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if stem.startswith("odi_"):
        stem = stem[len("odi_") :]
    parts = stem.split("_")
    if len(parts) >= 3:
        return "_".join(parts[1:])
    return stem


def _platform(target: str) -> str:
    mapping = {
        "linux_x86_64": "Linux (x86_64)",
        "linux_arm64": "Linux (ARM64)",
        "macos_x86_64": "macOS (Intel)",
        "macos_arm64": "macOS (Apple Silicon)",
        "windows_x86_64": "Windows (x86_64)",
    }
    return mapping.get(target, target.replace("_", " ").title())


def _hash_for(checksums_text: str, name: str) -> str | None:
    for line in checksums_text.splitlines():
        line = line.strip()
        if not line:
            continue
        hash_, sep, fname = line.partition("  ")
        if not sep:
            hash_, sep, fname = line.partition(" ")
        fname = fname.lstrip("*").strip()
        if fname == name:
            return hash_.strip()
    return None


_STUDIO_INSTALLERS = {
    ".deb": "sudo apt install {file}  # or: sudo dpkg -i {file}",
    ".AppImage": "chmod +x {file} && ./{file}",
    ".dmg": "open {file}  # then drag to Applications",
    ".exe": "{file}  # double-click to run (or append /S for silent install)",
}
_STUDIO_PLATFORM = {
    ".deb": "Linux (.deb)",
    ".AppImage": "Linux (AppImage)",
    ".dmg": "macOS (dmg)",
    ".exe": "Windows (exe)",
}


def _is_cli_archive(name: str) -> bool:
    """A CLI PyInstaller bundle: ``odi_<version>_<platform>.(tar.gz|zip)``."""
    return name.startswith("odi_") and name.endswith((".tar.gz", ".zip"))


def _is_studio_bundle(name: str) -> bool:
    """A Living Studio desktop bundle produced by the Tauri release."""
    return any(name.endswith(ext) for ext in _STUDIO_INSTALLERS) or "Living Studio" in name


def _studio_platform(name: str) -> str:
    for ext, plat in _STUDIO_PLATFORM.items():
        if name.endswith(ext):
            return plat
    return "Desktop bundle"


def _studio_install_command(name: str) -> str:
    template = next(
        (t for ext, t in _STUDIO_INSTALLERS.items() if name.endswith(ext)),
        "Open to install.",
    )
    return template.format(file=shlex.quote(name)) if "{file}" in template else template


def _build_studio_section(tag: str, repo: str, studio_artifacts: list[dict]) -> list[str]:
    dl_base = f"{GITHUB_RELEASES}/{repo}/releases/download/{tag}"
    lines: list[str] = []
    lines.append("### Living Studio (desktop)")
    lines.append("")
    lines.append(
        "The **Living Studio** desktop app is attached for Linux, macOS, and "
        "Windows. Download the bundle for your platform and install it:"
    )
    lines.append("")
    lines.append("| Platform | Bundle | Install |")
    lines.append("| --- | --- | --- |")
    for a in sorted(studio_artifacts, key=lambda x: x["name"]):
        name = a["name"]
        url = a["browser_download_url"]
        command = _studio_install_command(name)
        lines.append(f"| {_studio_platform(name)} | [{name}]({url}) | `{command}` |")
    lines.append("")
    lines.append(
        "> The desktop app self-updates in place via the Tauri updater configured in "
        "`tauri.conf.json`. macOS may quarantine the app bundle "
        "(`xattr -d -r com.apple.quarantine '/Applications/Agentic ODI Living Studio.app'` "
        "if needed); Windows SmartScreen may warn for unsigned builds — choose "
        '"More info → Run anyway" if you trust the release.'
    )
    lines.append("")
    lines.append(f"<!-- studio updater stream: {dl_base} -->")
    lines.append("")
    return lines


def build_instructions_section(
    tag: str, repo: str, artifacts: list[dict], checksums_text: str
) -> str:
    version = tag.lstrip("v")
    dl_base = f"{GITHUB_RELEASES}/{repo}/releases/download/{tag}"

    cli_artifacts = [a for a in artifacts if _is_cli_archive(a["name"])]
    studio_artifacts = [a for a in artifacts if _is_studio_bundle(a["name"])]

    lines: list[str] = []
    lines.append("## 📦 Download & Run")
    lines.append("")
    lines.append(
        f"Prebuilt binaries for **Agentic ODI {version}** are attached to this release. "
        "Pick the archive for your platform, verify its SHA-256 against ``checksums.txt``, "
        "then install with the one-liner below."
    )
    lines.append("")

    if cli_artifacts:
        lines.append("| Platform | Archive | Download | SHA-256 |")
        lines.append("| --- | --- | --- | --- |")
        for a in sorted(cli_artifacts, key=lambda x: x["name"]):
            name = a["name"]
            target = _archive_target(name)
            url = a["browser_download_url"]
            digest = _hash_for(checksums_text, name) or "—"
            lines.append(f"| {_platform(target)} | {name} | [download]({url}) | `{digest}` |")
        lines.append("")

    lines.append("### Verify")
    lines.append("Download ``checksums.txt`` from this release and verify the archive you picked:")
    lines.append("")
    lines.append("```bash")
    lines.append(f"curl -fsSL -O {dl_base}/checksums.txt")
    lines.append("sha256sum -c checksums.txt   # or: shasum -a 256 -c checksums.txt")
    lines.append("```")
    lines.append("")

    lines.append("### Install (one liner)")
    lines.append("**Linux / macOS**")
    lines.append("```bash")
    lines.append(f"curl -fsSL {dl_base}/install.sh | sh")
    lines.append("```")
    lines.append("**Windows (PowerShell)**")
    lines.append("```powershell")
    lines.append(f"iex (Invoke-WebRequest -Uri {dl_base}/install.ps1 -UseBasicParsing)")
    lines.append("# shorthand: install.ps1 | iex")
    lines.append("```")
    lines.append("")

    lines.append("### Install manually")
    lines.append(
        "Extract the archive, then add the folder containing the ``odi`` executable to your ``PATH``."
    )
    lines.append("")
    lines.append("```bash")
    lines.append(f"tar -xzf odi_{version}_<platform>.tar.gz   # or unzip the .zip on Windows")
    lines.append('export PATH="$PWD:$PATH"')
    lines.append("```")
    lines.append("")

    lines.append("### Quick start")
    lines.append("```bash")
    lines.append("odi --version")
    lines.append("odi --help")
    lines.append("odi jobs list")
    lines.append("```")
    lines.append("")

    if studio_artifacts:
        lines.extend(_build_studio_section(tag, repo, studio_artifacts))

    lines.append("### Related artifacts")
    for kind in ("checksums.txt", "install.sh", "install.ps1"):
        match = next((a for a in artifacts if a["name"] == kind), None)
        if match:
            lines.append(f"- [{kind}]({match['browser_download_url']})")
    lines.append("")

    lines.append(
        "> macOS may quarantine the downloaded binary "
        "(``xattr -d com.apple.quarantine odi`` if needed). "
        'Windows SmartScreen may warn for unsigned binaries; choose "More info → Run anyway" '
        "if you trust the release."
    )
    lines.append("")

    return f"{DOWNLOAD_START}\n" + "\n".join(lines) + "\n" + DOWNLOAD_END + "\n"


def apply_instructions(body: str | None, section: str) -> str:
    current = body if body is not None else ""
    start = current.find(DOWNLOAD_START)
    end = current.find(DOWNLOAD_END)
    if start != -1 and end != -1 and end > start:
        head = current[:start].rstrip()
        tail = current[end + len(DOWNLOAD_END) :].lstrip("\n")
        if head and tail:
            return head + "\n\n" + section + "\n" + tail
        if head:
            return head + "\n\n" + section + "\n" + tail
        return section + "\n" + tail
    current = current.rstrip()
    if not current:
        return section
    return current + "\n\n" + section


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish end-user download & run instructions to a GitHub release."
    )
    parser.add_argument("--tag", required=True, help="Release tag, e.g. v0.7.0")
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
        help="GitHub repository as owner/name",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the new body instead of publishing",
    )
    args = parser.parse_args(argv)

    tag = args.tag
    repo = args.repo
    if not repo:
        print("error: --repo or GITHUB_REPOSITORY is required", file=sys.stderr)
        return 2

    view = _run(["gh", "release", "view", tag, "--repo", repo, "--json", "body"])
    body = json.loads(view.stdout).get("body", "") or ""

    assets: list[dict] = []
    try:
        api = _run(["gh", "api", f"repos/{repo}/releases/tags/{tag}", "--json", "assets"])
        assets = json.loads(api.stdout).get("assets", [])
    except subprocess.CalledProcessError:
        assets = []

    checksums_text = ""
    try:
        ck = _run(
            [
                "curl",
                "-fsSL",
                f"{GITHUB_RELEASES}/{repo}/releases/download/{tag}/checksums.txt",
            ]
        )
        checksums_text = ck.stdout
    except subprocess.CalledProcessError:
        checksums_text = ""

    section = build_instructions_section(tag, repo, assets, checksums_text)
    new_body = apply_instructions(body, section)

    if args.dry_run:
        print(new_body)
        return 0

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
        fh.write(new_body)
        notes_path = fh.name
    try:
        _run(["gh", "release", "edit", tag, "--repo", repo, "--notes-file", notes_path])
    finally:
        Path(notes_path).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
