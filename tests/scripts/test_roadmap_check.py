"""Unit tests for the roadmap gate in scripts/doc_check.py (issue #97)."""

from __future__ import annotations

from doc_check import detect_capabilities, roadmap_errors

CONTRACT = "packages/core/src/agentic_odi_core/contract.py"
ROUTER = "apps/studio-api/src/agentic_odi_studio_api/studio/router.py"
CLI = "apps/cli/src/agentic_odi_cli/jobs.py"
ROADMAP = "docs/roadmap.md"


def _reader(files: dict[str, str]):
    return files.get


def test_a_new_mcp_tool_without_a_roadmap_entry_fails_and_names_it() -> None:
    before = 'class ToolName(str, Enum):\n    GET_JOBS = "get_jobs"\n'
    after = before + '    ADD_WIDGET = "add_widget"\n'

    capabilities = detect_capabilities(
        [CONTRACT], _reader({CONTRACT: before}), _reader({CONTRACT: after})
    )
    errors = roadmap_errors(capabilities, roadmap_changed=False)

    assert capabilities == ["MCP tool `add_widget`"]
    assert len(errors) == 1
    assert "add_widget" in errors[0]


def test_a_new_route_without_a_roadmap_entry_fails_and_names_it() -> None:
    before = '@router.get("/signals")\n'
    after = before + '@router.post("/signals/{signal_id}/archive")\n'

    capabilities = detect_capabilities(
        [ROUTER], _reader({ROUTER: before}), _reader({ROUTER: after})
    )
    errors = roadmap_errors(capabilities, roadmap_changed=False)

    assert capabilities == ["Studio API route `POST /api/signals/{signal_id}/archive`"]
    assert "archive" in errors[0]


def test_a_new_cli_command_without_a_roadmap_entry_fails_and_names_it() -> None:
    before = '@jobs_app.command("list")\n'
    after = before + '@jobs_app.command("archive")\n'

    capabilities = detect_capabilities([CLI], _reader({CLI: before}), _reader({CLI: after}))
    errors = roadmap_errors(capabilities, roadmap_changed=False)

    assert capabilities == ["CLI command `archive`"]
    assert "archive" in errors[0]


def test_a_documentation_only_change_passes() -> None:
    capabilities = detect_capabilities(["docs/cli.md"], _reader({}), _reader({}))

    assert capabilities == []
    assert roadmap_errors(capabilities, roadmap_changed=False) == []


def test_a_capability_with_a_roadmap_update_passes() -> None:
    before = 'class ToolName(str, Enum):\n    GET_JOBS = "get_jobs"\n'
    after = before + '    ADD_WIDGET = "add_widget"\n'

    capabilities = detect_capabilities(
        [CONTRACT, ROADMAP], _reader({CONTRACT: before}), _reader({CONTRACT: after})
    )

    assert capabilities == ["MCP tool `add_widget`"]
    assert roadmap_errors(capabilities, roadmap_changed=True) == []


def test_an_unchanged_file_adds_no_capability() -> None:
    text = 'class ToolName(str, Enum):\n    GET_JOBS = "get_jobs"\n'

    assert (
        detect_capabilities([CONTRACT], _reader({CONTRACT: text}), _reader({CONTRACT: text})) == []
    )
