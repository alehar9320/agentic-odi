"""Changelog parser and provider for The Living Studio."""

from __future__ import annotations

import re
from pathlib import Path

VERSION_HEADER_RE = re.compile(
    r"^##\s+\[?v?([0-9]+\.[0-9]+\.[0-9]+(?:\-[a-zA-Z0-9\.]+)?)\]?.*?\(([0-9]{4}-[0-9]{2}-[0-9]{2})\)"
)
ITEM_RE = re.compile(r"^\*\s+(?:(?:\*\*(.*?)\:\*\*\s+)?(.*))")


def find_changelog_path() -> Path | None:
    """Find CHANGELOG.md by searching parent directories from studio-api location."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        candidate = current / "CHANGELOG.md"
        if candidate.is_file():
            return candidate
        current = current.parent
    return None


def parse_changelog_markdown(content: str) -> list[dict]:
    releases: list[dict] = []
    current_release: dict | None = None
    current_category: str = "General"

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        header_match = VERSION_HEADER_RE.match(line)
        if header_match:
            version, date = header_match.groups()
            current_release = {
                "version": version,
                "date": date,
                "categories": {},
            }
            releases.append(current_release)
            current_category = "General"
            continue

        if current_release is not None:
            if line.startswith("### "):
                current_category = line[4:].strip()
                continue

            if line.startswith("* "):
                # Remove commit links like ([8af114f](...))
                clean_line = re.sub(r"\s*\(\[[a-f0-9]+\]\([^\)]+\)\)", "", line)
                item_match = ITEM_RE.match(clean_line)
                if item_match:
                    scope, desc = item_match.groups()
                    desc_text = desc.strip() if desc else clean_line[2:].strip()
                    if scope:
                        entry = f"[{scope}] {desc_text}"
                    else:
                        entry = desc_text
                else:
                    entry = clean_line[2:].strip()

                if current_category not in current_release["categories"]:
                    current_release["categories"][current_category] = []
                current_release["categories"][current_category].append(entry)

    # Convert categories dict to list format for easy frontend iteration
    formatted_releases = []
    for rel in releases:
        cats = [
            {"name": name, "items": items} for name, items in rel["categories"].items() if items
        ]
        formatted_releases.append(
            {
                "version": rel["version"],
                "date": rel["date"],
                "categories": cats,
            }
        )

    return formatted_releases


def get_changelog() -> dict:
    path = find_changelog_path()
    if path and path.is_file():
        try:
            content = path.read_text(encoding="utf-8")
            releases = parse_changelog_markdown(content)
            if releases:
                return {"releases": releases}
        except Exception:  # noqa: BLE001
            releases = []

    # Fallback if CHANGELOG.md is missing or unparseable
    return {
        "releases": [
            {
                "version": "0.8.0",
                "date": "2026-10-20",
                "categories": [
                    {
                        "name": "Features",
                        "items": [
                            "Kiro CLI superpowers integration",
                            "[cli] Entity parity commands for jobs, steps, outcomes, and evidence",
                            "[studio] Discrete Steve Jobs quality Changelog drawer with causal updates",
                        ],
                    }
                ],
            }
        ]
    }
