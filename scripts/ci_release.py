"""Derive the release identity a CI run belongs to.

A failing run is only useful if it points at something a person can name, so
error reports are tagged with the tag being built or, for ordinary branch
builds, the short commit SHA. The output is ``KEY=value`` lines ready for
``$GITHUB_ENV``.
"""

from __future__ import annotations

import argparse
import os

TAG_PREFIX = "refs/tags/"
SHORT_SHA_LENGTH = 12


def release_for(ref: str, sha: str) -> str:
    """Return the tag being built, or the short SHA of a branch build."""
    if ref.startswith(TAG_PREFIX):
        tag = ref[len(TAG_PREFIX) :]
        if tag:
            return tag
    if sha:
        return sha[:SHORT_SHA_LENGTH]
    return "local"


def environment_for(event: str) -> str:
    """Name the environment a run belongs to for error attribution."""
    if event == "pull_request":
        return "preview"
    if event == "push":
        return "production"
    return "ci"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default=os.environ.get("GITHUB_REF", ""))
    parser.add_argument("--sha", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--event", default=os.environ.get("GITHUB_EVENT_NAME", ""))
    args = parser.parse_args(argv)

    print(f"SENTRY_RELEASE={release_for(args.ref, args.sha)}")
    print(f"SENTRY_ENVIRONMENT={environment_for(args.event)}")


if __name__ == "__main__":
    main()
