"""Decide whether a GitHub release still needs its build assets attached.

Why this exists
---------------
The ``release`` and ``Tauri Release`` workflows used to run only on
``push: tags: [v*]``. The tag is created by ``release-please`` with the
repository ``GITHUB_TOKEN``, and GitHub does not create workflow runs for events
that token produces, so those workflows never fired and every release shipped
with no binaries, no ``checksums.txt``, and no install scripts.

Both workflows now also run on ``workflow_run: release-please``. That trigger
fires on every push to the default branch (release-please runs each time it
updates its release PR), so this module is the gate that keeps the extra runs
cheap and self-healing: it reports the tag to build and whether that release is
actually missing assets. A run that finds the release complete does nothing.

Pure functions:
    version_of(tag)
    expected_cli_assets(version)
    missing_assets(stream, version, present)
    should_build(missing, force)
    should_publish_instructions(build, instructions_present)

CLI:
    gate --stream {cli,studio} --tag TAG [--repo R] [--force]
        Print ``tag``/``version``/``missing``/``should_build``/``should_publish``
        as ``KEY=value`` lines ready for ``$GITHUB_OUTPUT``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

GITHUB_RELEASES = "https://github.com"

# Targets the CLI build matrix produces (see .github/workflows/release.yml).
CLI_TARGETS = (
    "linux_x86_64",
    "linux_arm64",
    "macos_arm64",
    "macos_x86_64",
    "windows_x86_64",
)

# Every CLI release also ships the checksum manifest and both installers.
CLI_SUPPORT_FILES = ("checksums.txt", "install.sh", "install.ps1")

# Desktop bundles embed the product name and version, so the studio gate keys on
# the installer types the Tauri build produces rather than exact file names.
STUDIO_SUFFIXES = (".deb", ".AppImage", ".dmg", ".exe")

# Kept in sync with scripts/release_instructions.py so the gate can tell whether
# a release page already carries the end-user instructions.
DOWNLOAD_START = "<!-- AGENTIC_ODI_DOWNLOAD_START -->"


def version_of(tag: str) -> str:
    """``v0.12.0`` -> ``0.12.0``; a bare version is returned unchanged."""
    tag = tag.strip()
    return tag[1:] if tag.startswith("v") else tag


def expected_cli_assets(version: str) -> list[str]:
    """The archive/checksum/installer names a complete CLI release must have."""
    names = [
        f"odi_{version}_{target}{'.zip' if target.startswith('windows') else '.tar.gz'}"
        for target in CLI_TARGETS
    ]
    return names + list(CLI_SUPPORT_FILES)


def missing_assets(stream: str, version: str, present: list[str]) -> list[str]:
    """Names (or ``*<suffix>`` patterns) a release is missing for ``stream``."""
    have = set(present)
    if stream == "cli":
        return [name for name in expected_cli_assets(version) if name not in have]
    if stream == "studio":
        return [
            f"*{suffix}" for suffix in STUDIO_SUFFIXES if not any(p.endswith(suffix) for p in have)
        ]
    raise ValueError(f"unknown stream: {stream!r} (expected 'cli' or 'studio')")


def should_build(missing: list[str], force: bool) -> bool:
    """Build when something is missing, or when a maintainer asked to rebuild."""
    return force or bool(missing)


def should_publish_instructions(build: bool, instructions_present: bool) -> bool:
    """Publish the release page text after a build, or when it is still missing."""
    return build or not instructions_present


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def _fetch_release(repo: str, tag: str) -> dict | None:
    """The release JSON for ``tag``, or ``None`` when the tag has no release yet."""
    try:
        out = _run(["gh", "api", f"repos/{repo}/releases/tags/{tag}"]).stdout
    except subprocess.CalledProcessError:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", choices=("cli", "studio"), required=True)
    parser.add_argument("--tag", required=True, help="Release tag, e.g. v0.12.0")
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
        help="GitHub repository as owner/name",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even when the release already has every asset",
    )
    args = parser.parse_args(argv)

    if not args.repo:
        print("error: --repo or GITHUB_REPOSITORY is required", file=sys.stderr)
        return 2

    tag = args.tag.strip()
    if not tag:
        print("error: --tag is required", file=sys.stderr)
        return 2
    version = version_of(tag)

    release = _fetch_release(args.repo, tag)
    if release is None:
        # No release for this tag yet (e.g. release-please has not cut it): treat
        # every asset as missing so the build still runs.
        present: list[str] = []
        body = ""
    else:
        present = [a.get("name", "") for a in release.get("assets", [])]
        body = release.get("body") or ""

    missing = missing_assets(args.stream, version, present)
    build = should_build(missing, args.force)
    instructions_present = DOWNLOAD_START in body
    publish = should_publish_instructions(build, instructions_present)

    print(f"tag={tag}")
    print(f"version={version}")
    print(f"missing={','.join(missing)}")
    print(f"should_build={'true' if build else 'false'}")
    print(f"should_publish={'true' if publish else 'false'}")
    print(f"download_base={GITHUB_RELEASES}/{args.repo}/releases/download/{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
