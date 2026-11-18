"""Index gitlinks must be registered submodules with a url.

``actions/checkout`` runs ``git submodule foreach --recursive`` while it strips
its auth header from submodule remotes. Git rejects an index entry of mode
160000 that has no matching ``[submodule "<name>"]`` block with a url in
``.gitmodules``::

    fatal: No url found for submodule path '<path>' in .gitmodules

The command exits 128, so the checkout step fails before the job runs any of
its own commands. Nine agent worktrees under ``.qoder/worktrees/`` were
committed that way and turned unrelated jobs red; #1101 deleted them and the
next agent worktree brought them back, so this test keeps the index clean.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GITLINK_MODE = "160000"


def _index_gitlinks() -> list[str]:
    """Paths of index entries that are gitlinks (mode 160000)."""
    output = subprocess.check_output(
        ["git", "ls-files", "--stage"], text=True, cwd=ROOT
    )
    paths: list[str] = []
    for line in output.splitlines():
        meta, _, path = line.partition("\t")
        mode = meta.split(maxsplit=1)[0] if meta else ""
        if mode == GITLINK_MODE:
            paths.append(path)
    return paths


def _declared_submodules() -> dict[str, str]:
    """Submodule path -> url from .gitmodules; empty when there is no file."""
    gitmodules = ROOT / ".gitmodules"
    if not gitmodules.is_file():
        return {}
    result = subprocess.run(
        [
            "git",
            "config",
            "--file",
            str(gitmodules),
            "--get-regexp",
            r"^submodule\..*\.(path|url)$",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:  # no matching keys
        return {}
    paths: dict[str, str] = {}
    urls: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition(" ")
        name, _, setting = key.rpartition(".")
        if setting == "path":
            paths[name] = value.strip()
        elif setting == "url":
            urls[name] = value.strip()
    return {path: urls.get(name, "") for name, path in paths.items()}


def test_gitlinks_are_registered_submodules() -> None:
    gitlinks = _index_gitlinks()
    declared = _declared_submodules()

    unregistered = sorted(path for path in gitlinks if path not in declared)
    assert not unregistered, (
        "Index gitlinks with no submodule block in .gitmodules: "
        + ", ".join(unregistered)
        + "\n`git submodule foreach --recursive`, which actions/checkout runs, "
        "fails with 'No url found for submodule path ...' and exits 128. "
        "Drop them with `git rm -r --cached <path>`: agent worktrees live under "
        "the gitignored .qoder/ directory and never belong in the index."
    )

    missing_url = sorted(
        path for path, url in declared.items() if path in gitlinks and not url
    )
    assert not missing_url, (
        "Submodules declared in .gitmodules without a url: "
        + ", ".join(missing_url)
        + "\n`git submodule foreach` fails with 'No url found for submodule "
        "path ...' and exits 128."
    )
