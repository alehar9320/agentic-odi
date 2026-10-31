"""Unit tests for scripts/doc_check.py (issue #97)."""

from __future__ import annotations

from pathlib import Path

from doc_check import (
    collect_issues,
    documented_cli_commands,
    documented_env_vars,
    documented_file_paths,
    missing_cli_commands,
    missing_env_vars,
    missing_file_paths,
    missing_routes,
    readme_code_overview_paths,
)


def test_extracts_documented_cli_commands_without_their_arguments() -> None:
    text = (
        "```bash\n"
        "odi jobs list --limit 5\n"
        "odi score 8 2\n"
        "agentic-odi connectors health\n"
        "uv run python -m agentic_odi_cli signals unread\n"
        "```\n"
    )

    assert documented_cli_commands(text) == [
        ("jobs", "list"),
        ("score",),
        ("connectors", "health"),
        ("signals", "unread"),
    ]


def test_ignores_commands_that_do_not_start_with_a_known_entry_point() -> None:
    text = (
        "```bash\n"
        "npm --prefix apps/studio run dev\n"
        "curl -fsSL https://example.com/install.sh | sh\n"
        "uv run python scripts/dev.py\n"
        "```\n"
    )

    assert documented_cli_commands(text) == []


def test_reports_a_documented_command_that_does_not_exist() -> None:
    tree = {("jobs", "list"), ("score",)}

    assert missing_cli_commands("```bash\nodi jobs inspect\n```", tree) == ["odi jobs inspect"]


def test_accepts_a_leaf_command_followed_by_positional_arguments() -> None:
    tree = {("score",)}

    assert missing_cli_commands("```bash\nodi score 8 2\n```", tree) == []


def test_reports_a_documented_path_that_does_not_exist(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "real.md").write_text("x", encoding="utf-8")

    missing = missing_file_paths({"guide": "See `docs/real.md` and `docs/gone.md`."}, root=tmp_path)

    assert missing == ["docs/gone.md"]


def test_accepts_a_line_range_suffix_on_a_real_path(tmp_path: Path) -> None:
    target = tmp_path / "packages" / "core"
    target.mkdir(parents=True)
    (target / "models.py").write_text("x", encoding="utf-8")

    missing = missing_file_paths({"guide": "See `packages/core/models.py:116-121`."}, root=tmp_path)

    assert missing == []


def test_ignores_code_spans_that_do_not_look_like_repo_paths() -> None:
    text = "`packages/**/*.py`, `https://example.com/apps/x`, `the/answer`, `GET /api/jobs`"

    assert documented_file_paths(text) == []


def test_accepts_a_directory_path(tmp_path: Path) -> None:
    (tmp_path / "apps" / "cli").mkdir(parents=True)

    assert missing_file_paths({"guide": "`apps/cli/`"}, root=tmp_path) == []


def test_matches_routes_through_their_path_parameters() -> None:
    routes = {("POST", "/api/signals/{signal_id}/read")}
    text = "`POST /api/signals/{id}/read`"

    assert missing_routes({"notifications": text}, routes) == []


def test_reports_a_documented_route_the_router_does_not_serve() -> None:
    routes = {("GET", "/api/signals")}

    missing = missing_routes({"guide": "`GET /api/imagination`"}, routes)

    assert missing == ["GET /api/imagination"]


def test_reports_an_environment_variable_nothing_reads() -> None:
    sources = "DB = os.environ.get('AGENTIC_ODI_DB')"

    missing = missing_env_vars(
        {"guide": "Set `AGENTIC_ODI_DB` and `AGENTIC_ODI_IMAGINARY`."}, sources
    )

    assert missing == ["AGENTIC_ODI_IMAGINARY"]


def test_readme_code_overview_paths_come_from_the_table(tmp_path: Path) -> None:
    readme = (
        "## Code Overview\n\n"
        "| Path | Distribution | Description |\n"
        "|---|---|---|\n"
        "| **`packages/core/`** | `agentic-odi-core` | Domain models. |\n"
        "| `scripts/` | — | Tooling. |\n"
        "\n## Next\n"
    )

    assert readme_code_overview_paths(readme) == ["packages/core/", "scripts/"]


def test_the_repository_documentation_matches_the_code() -> None:
    assert collect_issues() == []


def test_env_vars_are_not_invented_by_the_checker() -> None:
    assert documented_env_vars("`AGENTIC_ODI_DB` then `AGENTIC_ODI_DB`") == {"AGENTIC_ODI_DB"}
