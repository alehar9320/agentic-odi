"""One canonical way to run the stack locally, everywhere it is documented.

`python scripts/dev.py` starts the MCP server and the Studio sidecar together.
Guides that walk a reader through running locally must use it, and no guide may
quietly offer a second way (a bare uvicorn, the sidecar module, an old client).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = "python scripts/dev.py"

# Guides that tell a reader how to run the project on their machine.
LOCAL_GUIDES = (
    ROOT / "README.md",
    ROOT / "docs" / "living-studio.md",
    ROOT / "docs" / "local-llm.md",
    ROOT / "docs" / "deployment.md",
)

# Commands that would start the stack a different way. The MCP server alone is
# a supported entry point (`python -m agentic_odi_mcp_server`) and is not listed.
COMPETING_COMMANDS = (
    "streamlit run",
    "make dev",
    "uvicorn ",
    "python -m agentic_odi_studio_api",
)


def _docs() -> list[Path]:
    return [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]


def test_every_local_guide_uses_the_canonical_command() -> None:
    missing = [
        str(guide.relative_to(ROOT))
        for guide in LOCAL_GUIDES
        if CANONICAL not in guide.read_text(encoding="utf-8")
    ]

    assert not missing, f"These guides do not mention {CANONICAL!r}: {', '.join(missing)}"


def test_no_guide_offers_a_competing_launch_command() -> None:
    offenders: list[str] = []
    for path in _docs():
        text = path.read_text(encoding="utf-8")
        for command in COMPETING_COMMANDS:
            if command in text:
                offenders.append(f"{path.relative_to(ROOT)}: {command.strip()}")

    assert not offenders, "Competing launch commands: " + "; ".join(offenders)
