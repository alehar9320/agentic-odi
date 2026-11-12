"""Unit tests for scripts/release_manifest.py.

The module is pure apart from the file reads in ``write`` and the HTTP HEAD in
``verify``, so these tests cover the pure helpers, the ``write`` CLI against
real ``.sig`` files on disk, and the ``verify`` failure path with the version
cross-check.
"""

from __future__ import annotations

import json

import pytest
from release_manifest import (
    PLATFORM_KEYS,
    PLATFORM_SUFFIXES,
    asset_url,
    build_manifest,
    main,
    select_artifact,
    signature_of,
    version_conflict,
    version_of,
)


def test_version_of_strips_a_leading_v_only():
    assert version_of("v0.12.0") == "0.12.0"
    assert version_of("0.12.0") == "0.12.0"
    # `lstrip("v")` would eat the whole string here; `removeprefix` must not.
    assert version_of("vv1.2.3") == "v1.2.3"


def test_signature_of_keeps_the_minisign_block_verbatim():
    block = "untrusted comment: signature from minisign secret key\nRWTYsDP8OfRuHp1s\n"
    # The file's own contents, minus the trailing newline a shell redirect adds.
    assert signature_of(block) == block.rstrip("\n")
    # Interior line breaks are part of the signature, not noise.
    assert "\n" in signature_of(block)


def test_asset_url_percent_encodes_spaces():
    url = asset_url("alehar9320/agentic-odi", "v0.12.0", "Living Studio_0.12.0_x64.dmg")
    assert url == (
        "https://github.com/alehar9320/agentic-odi/releases/download/v0.12.0/"
        "Living%20Studio_0.12.0_x64.dmg"
    )
    # A name with no space is returned unchanged.
    assert asset_url("o/r", "v1.0.0", "plain.AppImage").endswith("/v1.0.0/plain.AppImage")


def test_select_artifact_skips_sig_companions_and_prefers_the_updater_bundle():
    names = [
        "Living Studio_0.12.0_x64.AppImage",
        "Living Studio_0.12.0_x64.AppImage.sig",
        "Living Studio_0.12.0_x64.dmg",
    ]
    chosen = select_artifact("linux-x86_64", names, PLATFORM_SUFFIXES["linux-x86_64"])
    assert chosen == "Living Studio_0.12.0_x64.AppImage"

    macos = ["studio_0.12.0_aarch64.dmg", "studio_0.12.0_aarch64.app.tar.gz"]
    chosen_mac = select_artifact("darwin-aarch64", macos, PLATFORM_SUFFIXES["darwin-aarch64"])
    # The .app.tar.gz is the bundle the updater prefers over the .dmg.
    assert chosen_mac == "studio_0.12.0_aarch64.app.tar.gz"


def test_select_artifact_returns_none_when_the_platform_has_no_bundle():
    # A missing platform must surface, not silently produce a manifest entry.
    assert (
        select_artifact("windows-x86_64", ["studio.AppImage"], PLATFORM_SUFFIXES["windows-x86_64"])
        is None
    )


def test_select_artifact_rejects_an_unknown_key():
    with pytest.raises(ValueError, match="unknown platform key"):
        select_artifact("linux-riscv", [], (".AppImage",))


def test_build_manifest_carries_the_four_required_fields():
    manifest = build_manifest(
        version="0.12.0",
        notes="What changed.",
        pub_date="2026-11-12T00:00:00Z",
        entries=[
            {"key": "linux-x86_64", "url": "https://example.test/a", "signature": "sig-a"},
        ],
    )
    assert manifest["version"] == "0.12.0"
    assert manifest["notes"] == "What changed."
    assert manifest["pub_date"] == "2026-11-12T00:00:00Z"
    assert manifest["platforms"]["linux-x86_64"] == {
        "signature": "sig-a",
        "url": "https://example.test/a",
    }


def test_build_manifest_refuses_an_unsigned_platform():
    with pytest.raises(ValueError, match="no signature"):
        build_manifest(
            version="0.12.0",
            notes="",
            pub_date="2026-11-12T00:00:00Z",
            entries=[{"key": "linux-x86_64", "url": "https://example.test/a", "signature": ""}],
        )


def test_build_manifest_refuses_an_unknown_platform_key():
    with pytest.raises(ValueError, match="unknown platform key"):
        build_manifest(
            version="0.12.0",
            notes="",
            pub_date="2026-11-12T00:00:00Z",
            entries=[{"key": "linux-riscv", "url": "u", "signature": "s"}],
        )


def test_version_conflict_is_silent_when_all_three_agree():
    assert version_conflict("v0.12.0", "0.12.0", "0.12.0") is None
    # An absent release-please manifest is not a conflict; the tag is the source.
    assert version_conflict("v0.12.0", "0.12.0", None) is None


def test_version_conflict_names_all_three_versions():
    message = version_conflict("v0.12.0", "0.11.0", "0.10.0")
    assert message is not None
    assert "v0.12.0" in message
    assert "0.11.0" in message
    assert "0.10.0" in message


def test_write_produces_a_manifest_whose_signature_is_the_file_verbatim(tmp_path):
    sig_a = "untrusted comment: signature from minisign secret key\nAAAAlinux\n"
    sig_b = "untrusted comment: signature from minisign secret key\nBBBBwindows\n"
    (tmp_path / "studio.AppImage.sig").write_text(sig_a, encoding="utf-8")
    (tmp_path / "studio-setup.exe.sig").write_text(sig_b, encoding="utf-8")
    notes = tmp_path / "notes.md"
    notes.write_text("Notes for the release.\n", encoding="utf-8")
    out = tmp_path / "latest.json"

    rc = main(
        [
            "write",
            "--tag",
            "v0.12.0",
            "--pub-date",
            "2026-11-12T00:00:00Z",
            "--repo",
            "alehar9320/agentic-odi",
            "--asset-dir",
            str(tmp_path),
            "--notes-file",
            str(notes),
            "--asset",
            "linux-x86_64=studio.AppImage",
            "--asset",
            "windows-x86_64=studio-setup.exe",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert manifest["version"] == "0.12.0"
    assert manifest["notes"] == "Notes for the release.\n"
    # The signature is the file's contents verbatim, trailing newline aside.
    assert manifest["platforms"]["linux-x86_64"]["signature"] == sig_a.rstrip("\n")
    assert manifest["platforms"]["windows-x86_64"]["signature"] == sig_b.rstrip("\n")
    assert manifest["platforms"]["linux-x86_64"]["url"].endswith("/v0.12.0/studio.AppImage")


def test_write_discovers_each_platforms_bundle_and_signature(tmp_path):
    bundles = {
        "studio_0.12.0_amd64.AppImage": "sig-linux\n",
        "studio_0.12.0_x64-setup.exe": "sig-windows\n",
        "studio_0.12.0_aarch64.app.tar.gz": "sig-mac-arm\n",
        "studio_0.12.0_x64.app.tar.gz": "sig-mac-x64\n",
    }
    for name, sig in bundles.items():
        (tmp_path / name).write_text("bundle bytes", encoding="utf-8")
        (tmp_path / f"{name}.sig").write_text(sig, encoding="utf-8")
    out = tmp_path / "latest.json"

    rc = main(
        [
            "write",
            "--tag",
            "v0.12.0",
            "--pub-date",
            "2026-11-12T00:00:00Z",
            "--repo",
            "alehar9320/agentic-odi",
            "--asset-dir",
            str(tmp_path),
            "--discover",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert set(manifest["platforms"]) == set(PLATFORM_KEYS)
    assert manifest["platforms"]["linux-x86_64"]["signature"] == "sig-linux"
    assert manifest["platforms"]["windows-x86_64"]["signature"] == "sig-windows"
    assert manifest["platforms"]["linux-x86_64"]["url"].endswith("/studio_0.12.0_amd64.AppImage")
    # Shared macOS suffixes must not hand the ARM bundle to Intel or vice versa.
    assert manifest["platforms"]["darwin-aarch64"]["signature"] == "sig-mac-arm"
    assert manifest["platforms"]["darwin-aarch64"]["url"].endswith(
        "/studio_0.12.0_aarch64.app.tar.gz"
    )
    assert manifest["platforms"]["darwin-x86_64"]["signature"] == "sig-mac-x64"
    assert manifest["platforms"]["darwin-x86_64"]["url"].endswith(
        "/studio_0.12.0_x64.app.tar.gz"
    )


def test_write_discovery_fails_when_a_platform_has_no_bundle(tmp_path):
    (tmp_path / "studio_0.12.0_amd64.AppImage").write_text("b", encoding="utf-8")
    (tmp_path / "studio_0.12.0_amd64.AppImage.sig").write_text("s", encoding="utf-8")
    with pytest.raises(SystemExit, match="no installer found"):
        main(
            [
                "write",
                "--tag",
                "v0.12.0",
                "--pub-date",
                "2026-11-12T00:00:00Z",
                "--repo",
                "alehar9320/agentic-odi",
                "--asset-dir",
                str(tmp_path),
                "--discover",
                "--out",
                str(tmp_path / "latest.json"),
            ]
        )


def test_write_fails_when_a_signature_file_is_missing(tmp_path, capsys):
    out = tmp_path / "latest.json"
    with pytest.raises(SystemExit, match="no signature file"):
        main(
            [
                "write",
                "--tag",
                "v0.12.0",
                "--pub-date",
                "2026-11-12T00:00:00Z",
                "--repo",
                "alehar9320/agentic-odi",
                "--asset-dir",
                str(tmp_path),
                "--asset",
                "linux-x86_64=studio.AppImage",
                "--out",
                str(out),
            ]
        )


def test_verify_goes_red_on_a_wrong_manifest_version(tmp_path, capsys):
    manifest = tmp_path / "latest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "0.11.0",
                "notes": "",
                "pub_date": "2026-11-12T00:00:00Z",
                "platforms": {
                    key: {"url": "https://example.test/a", "signature": "s"}
                    for key in PLATFORM_KEYS
                },
            }
        ),
        encoding="utf-8",
    )
    rp = tmp_path / ".release-please-manifest.json"
    rp.write_text(json.dumps({".": "0.12.0"}), encoding="utf-8")

    rc = main(
        [
            "verify",
            "--tag",
            "v0.12.0",
            "--repo",
            "alehar9320/agentic-odi",
            "--manifest",
            str(manifest),
            "--release-please-manifest",
            str(rp),
        ]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "version mismatch" in err
    # All three values are named, so a maintainer can see which one is wrong.
    assert "v0.12.0" in err
    assert "0.11.0" in err
    assert "0.12.0" in err


def test_verify_requires_a_repo(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    rc = main(["verify", "--tag", "v0.12.0"])
    assert rc == 2
    assert "required" in capsys.readouterr().err
