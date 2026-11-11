"""Generate the tool section of ``docs/integration.md`` from the contract.

The integration guide's tool reference is not written by hand. It is read from
the same two sources the product runs on — the tool contract in
``packages/core/src/agentic_odi_core/contract.py`` and the server source — by
the site's existing extractor (``website/tools/extract.py``). A tool added to
the contract without a documented row, or a row for a tool that no longer
exists, fails the sync test rather than drifting quietly.

The effect column is the write contract: whether a call reads, writes, or
destroys. It is read from ``TOOL_SPECS`` so it can never disagree with what the
server does.

Usage::

    uv run python scripts/integration_guide.py            # rewrite the block
    uv run python scripts/integration_guide.py --check    # fail if it is stale
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUIDE = REPO_ROOT / "docs" / "integration.md"
CONTRACT_PY = REPO_ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "contract.py"
MCP_SERVER_PY = (
    REPO_ROOT / "apps" / "mcp-server" / "src" / "agentic_odi_mcp_server" / "mcp_server.py"
)
EXTRACT_DIR = REPO_ROOT / "website" / "tools"

BEGIN = "<!-- BEGIN GENERATED TOOLS (scripts/integration_guide.py) -->"
END = "<!-- END GENERATED TOOLS -->"


def _extract_module():
    """Import the site's extractor so the guide and the site cannot disagree."""
    if str(EXTRACT_DIR) not in sys.path:
        sys.path.insert(0, str(EXTRACT_DIR))
    import extract  # type: ignore[import-not-found]

    return extract


def tool_rows() -> list[dict[str, object]]:
    """One row per tool: its name, purpose, effect, required args, and stage.

    The names, purposes and parameters come from the site's extractor (which
    itself fails if the contract and the server disagree). The effect, the
    required subset and the stage come from ``TOOL_SPECS`` so the write contract
    is the server's, not a transcription of it.
    """
    from agentic_odi_core.contract import TOOL_SPECS

    extract = _extract_module()
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)

    rows: list[dict[str, object]] = []
    for tool in tools:
        spec = TOOL_SPECS[tool["name"]]
        rows.append(
            {
                "name": tool["name"],
                "purpose": tool["purpose"],
                "effect": spec.effect.value,
                "required": list(spec.required),
                "stage": spec.stage,
            }
        )
    return rows


def render() -> str:
    """The generated tool block, markers included."""
    rows = tool_rows()
    lines = [
        BEGIN,
        "",
        f"{len(rows)} tools. Generated from the tool contract in "
        "`packages/core/src/agentic_odi_core/contract.py` and the server source; "
        "the effect column is the write contract, read from `TOOL_SPECS`.",
        "",
        "| Tool | Effect | Stage | Required arguments | Purpose |",
        "| ---- | ------ | ----- | ------------------ | ------- |",
    ]
    for row in rows:
        required = ", ".join(f"`{name}`" for name in row["required"]) or "—"
        stage = row["stage"] or "—"
        lines.append(
            f"| `{row['name']}` | `{row['effect']}` | {stage} | {required} | {row['purpose']} |"
        )
    lines.append("")
    lines.append(END)
    return "\n".join(lines) + "\n"


def _replace_block(document: str, block: str) -> str:
    start = document.find(BEGIN)
    end = document.find(END)
    if start == -1 or end == -1:
        raise SystemExit(
            f"{GUIDE} is missing the generated-tools markers; expected {BEGIN} … {END}"
        )
    return document[:start] + block + document[end + len(END) + 1 :]


def main(argv: list[str]) -> int:
    check = "--check" in argv
    block = render()
    current = GUIDE.read_text(encoding="utf-8")
    updated = _replace_block(current, block)
    if check:
        if updated != current:
            print(
                "docs/integration.md tool section is stale; "
                "run `uv run python scripts/integration_guide.py`",
                file=sys.stderr,
            )
            return 1
        print("docs/integration.md tool section is current")
        return 0
    GUIDE.write_text(updated, encoding="utf-8")
    print(f"wrote the generated tool section in {GUIDE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
