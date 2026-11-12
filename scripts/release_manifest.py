"""Write and verify the desktop updater manifest (``latest.json``).

Why this exists
---------------
``release-please`` publishes through the GitHub API, which never emits the
``push: tags`` event the desktop workflow once listened for, so for many
releases no bundle and no ``latest.json`` were ever attached — and the updater
could only ever report "up to date". The triggers are fixed now, but nothing in
the repository *writes* the manifest: the Tauri build emits one ``.sig`` per
installer and stops there. This module is the missing writer, plus the verifier
that fails a release whose manifest disagrees with the tag.

The manifest is the contract that makes "updates itself" true. Tauri's updater
reads it from ``/releases/latest/download/latest.json``, matches the running
platform, downloads the named artifact, and verifies it against the embedded
minisign signature. Every field therefore has to be real: the version has to be
the tagged version, and the signature has to be the ``.sig`` the build emitted,
byte for byte.

Pure functions:
    version_of(tag)
    signature_of(sig_text)
    asset_url(repo, tag, name)
    select_artifact(key, names)
    build_manifest(version, notes, pub_date, entries)
    version_conflict(tag, manifest_version, release_please_version)

CLI:
    write --version V --notes-file F --pub-date ISO --repo R --tag T
          --asset-dir D (--asset KEY=NAME | --discover) [--out latest.json]
    verify --repo R --tag T --manifest latest.json
           [--release-please-manifest .release-please-manifest.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

GITHUB_RELEASES = "https://github.com"

MANIFEST_NAME = "latest.json"

# The updater platform keys Tauri matches against, in the order the manifest
# should carry them. Each desktop build matrix entry names exactly one of these
# (see `.github/workflows/tauri-release.yml`), so the workflow passes the key
# explicitly rather than having this module guess it from a file name.
PLATFORM_KEYS = (
    "linux-x86_64",
    "windows-x86_64",
    "darwin-aarch64",
    "darwin-x86_64",
)


def version_of(tag: str) -> str:
    """``v0.12.0`` -> ``0.12.0``; a bare version is returned unchanged."""
    tag = tag.strip()
    return tag[1:] if tag.startswith("v") else tag


def signature_of(sig_text: str) -> str:
    """The signature a ``.sig`` file carries, verbatim but for trailing newlines.

    Tauri compares the manifest's ``signature`` against the minisign block it
    computes over the downloaded bytes, so the value must be the file's own
    contents. Only the trailing newline a shell redirect adds is removed; every
    interior character, including the line breaks minisign emits, is kept.
    """
    return sig_text.rstrip("\n")


def asset_url(repo: str, tag: str, name: str) -> str:
    """The public release-asset URL for ``name`` on ``repo`` at ``tag``.

    GitHub percent-encodes spaces in asset names (``%20``); a name with none is
    returned unchanged. This is the URL the app fetches, not a placeholder.
    """
    encoded = urllib.parse.quote(name, safe="")
    return f"{GITHUB_RELEASES}/{repo}/releases/download/{tag}/{encoded}"


# The installer each updater platform key consumes, most specific first. The
# Tauri build emits one bundle per target and a ``.sig`` beside each; discovery
# skips the ``.sig`` names and picks the bundle the updater would install.
PLATFORM_SUFFIXES: dict[str, tuple[str, ...]] = {
    "linux-x86_64": (".AppImage",),
    "windows-x86_64": (".exe", ".msi"),
    "darwin-aarch64": (".app.tar.gz", ".dmg"),
    "darwin-x86_64": (".app.tar.gz", ".dmg"),
}


def select_artifact(key: str, names: list[str], suffixes: tuple[str, ...]) -> str | None:
    """The first of ``names`` the updater for ``key`` would install, or ``None``.

    ``names`` is what the build produced. ``.sig`` companions are skipped, and
    ``suffixes`` is tried in order so a platform that can consume more than one
    bundle (macOS takes the ``.app.tar.gz`` the updater prefers over the
    ``.dmg``) picks the right one. Returning ``None`` rather than a guess is the
    point: a platform with no artifact must fail the release, not ship a
    manifest entry pointing at nothing.
    """
    if key not in PLATFORM_SUFFIXES:
        raise ValueError(f"unknown platform key: {key!r}")
    candidates = [name for name in names if not name.endswith(".sig")]
    for suffix in suffixes:
        for name in candidates:
            if name.endswith(suffix):
                return name
    return None


def build_manifest(
    version: str,
    notes: str,
    pub_date: str,
    entries: list[dict[str, str]],
) -> dict:
    """Assemble the updater manifest.

    ``entries`` is one ``{"key", "name", "signature"}`` per platform, in
    ``PLATFORM_KEYS`` order. Every entry must carry a non-empty ``signature`` —
    a manifest with an unsigned platform is a release that silently installs
    nothing, so this raises rather than writing one.
    """
    platforms: dict[str, dict[str, str]] = {}
    for entry in entries:
        key = entry["key"]
        if key not in PLATFORM_KEYS:
            raise ValueError(f"unknown platform key: {key!r}")
        signature = entry.get("signature", "")
        if not signature:
            raise ValueError(f"platform {key!r} has no signature; refusing to write a manifest")
        platforms[key] = {"signature": signature, "url": entry["url"]}
    return {
        "version": version,
        "notes": notes,
        "pub_date": pub_date,
        "platforms": platforms,
    }


def version_conflict(
    tag: str,
    manifest_version: str,
    release_please_version: str | None,
) -> str | None:
    """The message naming every disagreeing version, or ``None`` when they agree.

    Three values have to line up: the release tag, the version the manifest
    advertises, and the version ``release-please`` recorded in
    ``.release-please-manifest.json``. A mismatch is a trust failure — the app
    would advertise an update it cannot install — so the caller fails loudly and
    names all three rather than guessing which is right.
    """
    tag_version = version_of(tag)
    if manifest_version == tag_version and (
        release_please_version is None or release_please_version == tag_version
    ):
        return None
    recorded = release_please_version if release_please_version is not None else "(not read)"
    return (
        f"version mismatch: tag v{tag_version}, latest.json {manifest_version!r}, "
        f".release-please-manifest.json {recorded!r}"
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_asset(spec: str) -> tuple[str, str]:
    key, sep, name = spec.partition("=")
    if not sep or not key or not name:
        raise argparse.ArgumentTypeError(f"--asset must be KEY=NAME, got {spec!r}")
    return key, name


def _entries_from_assets(
    asset_dir: Path, assets: list[tuple[str, str]], repo: str, tag: str
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for key, name in assets:
        sig_path = asset_dir / f"{name}.sig"
        if not sig_path.is_file():
            raise SystemExit(f"error: no signature file for {key}: expected {sig_path}")
        entries.append(
            {
                "key": key,
                "url": asset_url(repo, tag, name),
                "signature": signature_of(_read_text(sig_path)),
            }
        )
    return entries


def _entries_from_discovery(asset_dir: Path, repo: str, tag: str) -> list[dict[str, str]]:
    """Build one entry per platform key from whatever the build produced.

    This is what the release workflow calls: the Tauri build names its bundles
    after the product, so the workflow cannot spell them out. Each platform's
    bundle is discovered by suffix, its ``.sig`` twin read verbatim, and a
    platform with no bundle aborts the run — a manifest missing a platform is a
    release that cannot update that platform.
    """
    names = sorted(p.name for p in asset_dir.iterdir() if p.is_file())
    entries: list[dict[str, str]] = []
    for key in PLATFORM_KEYS:
        name = select_artifact(key, names, PLATFORM_SUFFIXES[key])
        if name is None:
            raise SystemExit(
                f"error: no installer found for {key} in {asset_dir} "
                f"(looked for {', '.join(PLATFORM_SUFFIXES[key])})"
            )
        sig_path = asset_dir / f"{name}.sig"
        if not sig_path.is_file():
            raise SystemExit(f"error: no signature file for {key}: expected {sig_path}")
        entries.append(
            {
                "key": key,
                "url": asset_url(repo, tag, name),
                "signature": signature_of(_read_text(sig_path)),
            }
        )
    return entries


def _cmd_write(args: argparse.Namespace) -> int:
    notes = _read_text(Path(args.notes_file)) if args.notes_file else ""
    asset_dir = Path(args.asset_dir)
    if args.discover:
        entries = _entries_from_discovery(asset_dir, args.repo, args.tag)
    else:
        assets = [_parse_asset(spec) for spec in args.asset]
        if not assets:
            raise SystemExit("error: at least one --asset KEY=NAME (or --discover) is required")
        entries = _entries_from_assets(asset_dir, assets, args.repo, args.tag)
    manifest = build_manifest(
        version=version_of(args.version) if args.version else version_of(args.tag),
        notes=notes,
        pub_date=args.pub_date,
        entries=entries,
    )
    out = Path(args.out)
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} with {len(manifest['platforms'])} signed platform(s)")
    return 0


def _fetch_manifest(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as response:  # noqa: S310 - release URL
        return json.loads(response.read().decode("utf-8"))


def _cmd_verify(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if manifest_path.is_file():
        manifest = json.loads(_read_text(manifest_path))
    else:
        manifest = _fetch_manifest(manifest_path.as_posix())

    release_please_version: str | None = None
    if args.release_please_manifest:
        data = json.loads(_read_text(Path(args.release_please_manifest)))
        release_please_version = data.get(".")

    conflict = version_conflict(args.tag, manifest.get("version", ""), release_please_version)
    if conflict is not None:
        print(f"::error::{conflict}", file=sys.stderr)
        return 1
    if args.version_only:
        print(f"OK: {args.tag} agrees with latest.json and release-please")
        return 0

    platforms = manifest.get("platforms") or {}
    for key in PLATFORM_KEYS:
        entry = platforms.get(key)
        if not entry or not entry.get("url") or not entry.get("signature"):
            print(f"::error::latest.json is missing a signed {key} artifact.", file=sys.stderr)
            return 1
        url = entry["url"]
        try:
            request = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(request, timeout=20):  # noqa: S310 - release URL
                pass
        except OSError as exc:
            print(f"::error::{key} updater download does not resolve: {url} ({exc})")
            return 1
        print(f"OK: {key} -> {url} is signed and downloadable")
    print(f"OK: {args.tag} publishes a signed updater manifest for every platform")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    write = sub.add_parser("write", help="write latest.json from the build's .sig files")
    write.add_argument("--version", default="", help="defaults to the tag's version")
    write.add_argument("--notes-file", default="", help="release notes to embed")
    write.add_argument("--pub-date", required=True, help="ISO-8601 publish timestamp")
    write.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    write.add_argument("--tag", required=True)
    write.add_argument(
        "--asset-dir", required=True, help="directory holding the bundles and .sig files"
    )
    write.add_argument(
        "--discover",
        action="store_true",
        help="pick each platform's bundle from --asset-dir by suffix (what the workflow uses)",
    )
    write.add_argument(
        "--asset",
        action="append",
        default=[],
        metavar="KEY=NAME",
        help="updater platform key and the installer's asset name; repeat per platform",
    )
    write.add_argument("--out", default=MANIFEST_NAME)
    write.set_defaults(func=_cmd_write)

    verify = sub.add_parser("verify", help="fail when the manifest disagrees with the tag")
    verify.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    verify.add_argument("--tag", required=True)
    verify.add_argument("--manifest", default=MANIFEST_NAME, help="path or URL")
    verify.add_argument(
        "--version-only",
        action="store_true",
        help="check the three version sources and stop; skip the per-platform URL probe",
    )
    verify.add_argument(
        "--release-please-manifest",
        default="",
        help="path to .release-please-manifest.json to cross-check the version",
    )
    verify.set_defaults(func=_cmd_verify)

    args = parser.parse_args(argv)
    if not getattr(args, "repo", ""):
        print("error: --repo or GITHUB_REPOSITORY is required", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
