"""Unit tests for scripts/pr_guards.py (issue #86)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pr_guards import (
    GuardConfig,
    build_diff_args,
    changed_files_from_status,
    check_deletions,
    check_diff_budget,
    check_freshness,
    guard_diff_shape,
    is_generated,
    parse_name_status,
    parse_numstat,
)


def _release(path: str) -> str:
    return "v1.2.3"


# --- Gate 1: deletion budget -------------------------------------------------


def test_deleting_a_shipped_file_fails_and_names_the_release() -> None:
    errors = check_deletions(
        ["apps/old/thing.tsx"],
        allowlist=[],
        release_lookup=_release,
    )

    assert len(errors) == 1
    assert "apps/old/thing.tsx" in errors[0]
    assert "v1.2.3" in errors[0]


def test_an_empty_allowlist_denies_every_deletion() -> None:
    errors = check_deletions(
        ["a.py", "b.py"],
        allowlist=[],
        release_lookup=_release,
    )

    assert len(errors) == 2


def test_an_allowlisted_deletion_passes() -> None:
    allowlist = [{"path": "apps/old/thing.tsx", "issue": "123", "reason": "moved"}]

    errors = check_deletions(["apps/old/thing.tsx"], allowlist=allowlist, release_lookup=_release)

    assert errors == []


def test_the_allowlist_supports_globs() -> None:
    allowlist = [{"path": "apps/old/*.tsx", "issue": "123", "reason": "moved"}]

    errors = check_deletions(["apps/old/a.tsx", "apps/old/b.tsx"], allowlist, _release)

    assert errors == []


def test_missing_release_is_reported_as_unreleased() -> None:
    errors = check_deletions(["new.py"], allowlist=[], release_lookup=lambda _p: None)

    assert len(errors) == 1
    assert "unreleased" in errors[0]


# --- Gate 2: diff size -------------------------------------------------------


def test_exceeding_the_deletion_budget_fails() -> None:
    numstat = {"a.py": (0, 400), "b.py": (0, 200)}

    errors = check_diff_budget(numstat, GuardConfig(max_deletions=500))

    assert len(errors) == 1
    assert "600" in errors[0]


def test_staying_under_the_deletion_budget_passes() -> None:
    numstat = {"a.py": (10, 20)}

    assert check_diff_budget(numstat, GuardConfig(max_deletions=500)) == []


def test_generated_files_are_excluded_from_the_budget() -> None:
    numstat = {"uv.lock": (0, 5000), "package-lock.json": (0, 5000), "a.py": (1, 1)}

    assert check_diff_budget(numstat, GuardConfig(max_deletions=500)) == []


def test_generated_detection_covers_the_documented_paths() -> None:
    config = GuardConfig()

    for path in ("uv.lock", "apps/studio/src/api/schema.d.ts", "openapi.json", "coverage.xml"):
        assert is_generated(path, config), path
    assert not is_generated("apps/cli/src/agentic_odi_cli/cli.py", config)


def test_exceeding_the_changed_file_budget_fails() -> None:
    numstat = {f"f{i}.py": (1, 0) for i in range(11)}

    errors = check_diff_budget(numstat, GuardConfig(max_changed_files=10))

    assert len(errors) == 1
    assert "11" in errors[0]


# --- Gate 3: branch freshness ------------------------------------------------


def test_a_stale_branch_is_a_warning_not_an_error() -> None:
    result = guard_diff_shape(
        deleted=[],
        numstat={},
        allowlist=[],
        config=GuardConfig(max_behind=50),
        release_lookup=_release,
        behind=51,
    )

    assert result.errors == []
    assert any("51" in warning for warning in result.warnings)


def test_a_fresh_branch_has_no_freshness_warning() -> None:
    result = guard_diff_shape(
        deleted=[],
        numstat={},
        allowlist=[],
        config=GuardConfig(max_behind=50),
        release_lookup=_release,
        behind=3,
    )

    assert result.warnings == []


def test_check_freshness_returns_the_warning() -> None:
    warnings = check_freshness(10, GuardConfig(max_behind=5))

    assert len(warnings) == 1


# --- Diff parsing and cumulative (three-dot) semantics ----------------------


def test_parse_name_status_handles_adds_modifies_and_deletes() -> None:
    status = "A\tnew.py\nM\told.py\nD\tgone.py\n"

    parsed = parse_name_status(status)

    assert parsed == [("A", "new.py", None), ("M", "old.py", None), ("D", "gone.py", None)]


def test_parse_name_status_handles_renames() -> None:
    parsed = parse_name_status("R100\told.py\tnew.py\n")

    assert parsed == [("R100", "new.py", "old.py")]


def test_parse_numstat_handles_binary_files() -> None:
    parsed = parse_numstat("10\t2\ta.py\n-\t-\tb.png\n")

    assert parsed == {"a.py": (10, 2), "b.png": (0, 0)}


def test_changed_files_from_status_counts_every_entry() -> None:
    parsed = parse_name_status("A\ta.py\nM\tb.py\nD\tc.py\n")

    assert changed_files_from_status(parsed) == 3


def test_diff_args_use_the_cumulative_three_dot_merge_base_diff() -> None:
    args = build_diff_args("origin/main", "HEAD")

    assert args == ["git", "diff", "--name-status", "origin/main...HEAD"]


def test_cumulative_diff_catches_a_mid_branch_tree_replacement(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

    git("init", "-q", "-b", "main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (repo / "shipped.py").write_text("shipped = True\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "base")

    git("checkout", "-q", "-b", "feature")
    (repo / "feature.py").write_text("feature = True\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "real work")

    (repo / "shipped.py").unlink()
    (repo / "feature.py").write_text("feature = False\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "tree replacement")

    output = subprocess.run(
        build_diff_args("main", "HEAD"),
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    deleted = [new for status, new, _old in parse_name_status(output) if status == "D"]

    assert deleted == ["shipped.py"]


# --- Body truth: natural-language rules (warnings) ---------------------------


from pr_guards import check_body_truth, check_json_block, parse_json_block  # noqa: E402


def _truth(body: str, title: str = "", **overrides: object):
    kwargs = {
        "changed_files": 4,
        "tests_added": 5,
        "net_lines": 100,
        "changed_paths": ["apps/cli/cli.py"],
        "base_paths": ["apps/cli/backend.py"],
        "config": GuardConfig(),
    }
    kwargs.update(overrides)
    return check_body_truth(body, title, **kwargs)


def test_a_file_count_claim_that_disagrees_warns() -> None:
    result = _truth("This changes 20 files.")

    assert result.errors == []
    assert any("20" in warning and "file" in warning for warning in result.warnings)


def test_a_file_count_claim_within_tolerance_does_not_warn() -> None:
    result = _truth("This changes 4 files.")

    assert result.warnings == []


def test_a_numbered_micro_improvement_table_is_treated_as_a_file_count() -> None:
    rows = "\n".join(f"{i}. improvement {i}" for i in range(20))

    result = _truth(f"## 20 micro-improvements\n\n{rows}\n")

    assert any("20" in warning for warning in result.warnings)


def test_a_test_count_claim_that_disagrees_warns() -> None:
    result = _truth("29 total tests passing.")

    assert result.errors == []
    assert any("29" in warning and "test" in warning for warning in result.warnings)


def test_a_named_file_that_is_not_in_the_diff_or_base_warns() -> None:
    result = _truth("We built a slide-over drawer in ChatCopilot.tsx and StudioHeader.tsx.")

    assert any("ChatCopilot.tsx" in warning for warning in result.warnings)


def test_a_named_file_in_the_diff_does_not_warn() -> None:
    result = _truth("Touched apps/cli/cli.py here.", changed_paths=["apps/cli/cli.py"])

    assert result.warnings == []


def test_a_named_file_on_the_base_branch_does_not_warn() -> None:
    result = _truth("Touched apps/cli/backend.py here.")

    assert result.warnings == []


def test_a_number_in_the_title_is_checked_against_the_file_count() -> None:
    result = _truth("", title="20 touch-first micro-improvements")

    assert any("20" in warning for warning in result.warnings)


def test_a_title_number_within_tolerance_does_not_warn() -> None:
    result = _truth("", title="4 improvements", changed_files=4)

    assert result.warnings == []


def test_natural_language_rules_never_fail_the_build() -> None:
    result = _truth("This changes 200 files and ChatCopilot.tsx has 9000 tests passing.")

    assert result.errors == []


def test_a_new_source_file_with_no_reuse_report_warns() -> None:
    result = _truth("Adds a retry helper.", added_paths=["packages/core/retry.py"])

    assert result.errors == []
    assert any("Reuses" in warning for warning in result.warnings)


def test_a_reuse_report_silences_the_new_source_warning() -> None:
    body = "Adds a retry helper.\n\nReuses: apps/cli/cli.py\n"

    result = _truth(body, added_paths=["packages/core/retry.py"])

    assert result.warnings == []


def test_a_bolded_reuse_label_counts_as_a_report() -> None:
    result = _truth(
        "**Reuses:** nothing available", added_paths=["apps/studio/lib/relativeTime.ts"]
    )

    assert result.warnings == []


def test_a_new_test_or_document_owes_no_reuse_report() -> None:
    added = ["tests/test_retry.py", "docs/architecture/reuse.md"]

    result = _truth("Adds coverage.", added_paths=added)

    assert result.warnings == []


def test_several_new_source_files_are_named_once_in_the_warning() -> None:
    result = _truth("", added_paths=["a.py", "b.py", "c.py", "d.py", "e.py", "f.py"])

    warnings = [warning for warning in result.warnings if "Reuses" in warning]

    assert len(warnings) == 1
    assert "6 new source file(s)" in warnings[0]
    assert "f.py" not in warnings[0]


# --- Body truth: machine-readable JSON block (failure) -----------------------


def test_parse_json_block_reads_the_fenced_block() -> None:
    body = 'Intro\n\n```json\n{"changed_files": 7, "tests_added": 5, "net_lines": 156}\n```\n'

    block = parse_json_block(body)

    assert block == {"changed_files": 7, "tests_added": 5, "net_lines": 156}


def test_parse_json_block_returns_none_without_a_block() -> None:
    assert parse_json_block("no block here") is None


def test_a_json_block_that_matches_the_diff_passes() -> None:
    block = {"changed_files": 4, "tests_added": 5, "net_lines": 100}

    assert check_json_block(block, 4, 5, 100, tolerance=0.20) == []


def test_a_json_block_that_disagrees_fails() -> None:
    block = {"changed_files": 7, "tests_added": 5, "net_lines": 156}

    errors = check_json_block(block, 20, 5, 156, tolerance=0.20)

    assert len(errors) == 1
    assert "changed_files" in errors[0]


def test_a_json_block_that_disagrees_within_tolerance_passes() -> None:
    block = {"changed_files": 10, "tests_added": 5, "net_lines": 100}

    assert check_json_block(block, 11, 5, 100, tolerance=0.20) == []


def test_a_json_block_mismatch_is_an_error_in_the_full_gate() -> None:
    body = '```json\n{"changed_files": 7, "tests_added": 5, "net_lines": 156}\n```\n'

    result = _truth(body)

    assert result.failed
    assert any("changed_files" in error for error in result.errors)


# --- Fabrication guard (warnings) -------------------------------------------


from pr_guards import check_fabrication  # noqa: E402


def test_a_fabricated_mock_result_warns() -> None:
    lines = [
        (
            "packages/core/src/agentic_odi_core/services.py",
            391,
            '    return "Executed mock cloud agent task successfully"',
        )
    ]

    warnings = check_fabrication(lines)

    assert len(warnings) == 1
    assert "services.py:391" in warnings[0]


def test_an_unconditional_is_available_warns() -> None:
    lines = [
        ("apps/core/router.py", 39, "    def is_available(self) -> bool:"),
        ("apps/core/router.py", 40, "        return True"),
    ]

    warnings = check_fabrication(lines)

    assert len(warnings) == 1
    assert "is_available" in warnings[0]


def test_a_conditional_is_available_does_not_warn() -> None:
    lines = [
        ("apps/core/router.py", 39, "    def is_available(self) -> bool:"),
        ("apps/core/router.py", 40, "        return self._probe() is not None"),
    ]

    assert check_fabrication(lines) == []


def test_a_hardcoded_measurement_string_warns() -> None:
    lines = [("apps/core/report.py", 10, '    return "3,000 hours of developer agony"')]

    warnings = check_fabrication(lines)

    assert len(warnings) == 1
    assert "measurement" in warnings[0].lower()


def test_a_new_todo_warns() -> None:
    warnings = check_fabrication([("apps/core/x.py", 1, "# TODO: wire this up")])

    assert len(warnings) == 1
    assert "TODO" in warnings[0]


def test_a_new_not_implemented_error_warns() -> None:
    warnings = check_fabrication([("apps/core/x.py", 1, "    raise NotImplementedError")])

    assert len(warnings) == 1


def test_a_stub_pass_warns() -> None:
    warnings = check_fabrication([("apps/core/x.py", 1, "    pass  # stub")])

    assert len(warnings) == 1


def test_a_legitimate_mock_in_a_test_file_is_excluded() -> None:
    lines = [
        ("apps/core/tests/test_x.py", 1, "# TODO: mock this later"),
        ("apps/core/tests/test_x.py", 2, '    return "mock value"'),
    ]

    assert check_fabrication(lines) == []


def test_a_word_mock_without_a_fabricated_return_does_not_warn() -> None:
    lines = [("apps/core/docs.py", 1, "    # the word mock is fine in prose")]

    assert check_fabrication(lines) == []


def test_fabrication_findings_are_warnings_not_errors() -> None:
    warnings = check_fabrication([("apps/core/x.py", 1, "# TODO: later")])

    assert isinstance(warnings, list)
    assert all(isinstance(warning, str) for warning in warnings)


# --- Diff scanning helpers ---------------------------------------------------


from pr_guards import count_tests_added, parse_added_lines  # noqa: E402


def test_parse_added_lines_tracks_paths_and_line_numbers() -> None:
    diff = (
        "diff --git a/apps/core/x.py b/apps/core/x.py\n"
        "--- a/apps/core/x.py\n"
        "+++ b/apps/core/x.py\n"
        "@@ -1,2 +1,3 @@\n"
        " existing\n"
        "+# TODO: later\n"
        "+return True\n"
        " tail\n"
    )

    assert parse_added_lines(diff) == [
        ("apps/core/x.py", 2, "# TODO: later"),
        ("apps/core/x.py", 3, "return True"),
    ]


def test_count_tests_added_counts_python_and_javascript_definitions() -> None:
    lines = [
        ("a.py", 1, "def test_one():"),
        ("b.test.ts", 2, "it('works', () => {"),
        ("c.ts", 3, "test('works', () => {"),
        ("d.py", 4, "def helper():"),
    ]

    assert count_tests_added(lines) == 3


def test_count_tests_added_ignores_removed_context() -> None:
    assert count_tests_added([]) == 0


# --- Wiring: workflow, config, allowlist, template --------------------------

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "pr-guardrails.yml"
CONFIG = ROOT / ".github" / "pr-guardrails" / "config.yml"
ALLOWLIST = ROOT / ".github" / "pr-guardrails" / "deletion-allowlist.yml"
TEMPLATE = ROOT / ".github" / "pull_request_template.md"


def test_the_guardrails_workflow_runs_on_pull_requests() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "pr-guardrails:" in workflow
    assert "scripts/pr_guards.py diff-shape" in workflow
    assert "scripts/pr_guards.py body-truth" in workflow
    assert "scripts/pr_guards.py fabrication" in workflow


def test_the_guardrails_workflow_checks_out_full_history_and_fetches_the_base() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "fetch-depth: 0" in workflow
    assert "git fetch" in workflow
    assert "github.base_ref" in workflow


def test_the_guardrails_workflow_needs_no_repository_secrets() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "secrets." not in workflow


def test_the_default_config_documents_the_thresholds() -> None:
    import yaml

    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))

    assert config["max_deletions"] == 500
    assert config["max_changed_files"] >= 1
    assert config["max_behind"] == 50
    assert config["tolerance"] == 0.20
    assert "uv.lock" in config["generated_exclusions"]


def test_the_allowlist_only_approves_banner_component_replacements() -> None:
    import yaml

    allowlist = yaml.safe_load(ALLOWLIST.read_text(encoding="utf-8"))

    assert {entry["path"] for entry in allowlist} == {
        "apps/studio/src/components/Toasts.test.tsx",
        "apps/studio/src/components/Toasts.tsx",
        "apps/studio/src/components/chat/OfflineNotice.tsx",
        "apps/studio/src/components/notices/SidecarNotice.test.tsx",
        "apps/studio/src/components/notices/SidecarNotice.tsx",
    }
    assert all(entry["issue"] == 264 and entry["reason"] for entry in allowlist)


def test_the_template_asks_for_experience_verification_and_scope() -> None:
    template = TEMPLATE.read_text(encoding="utf-8")

    for section in (
        "## What a person experiences",
        "## How this was verified",
        "## What this does NOT do",
        "## Mock/stub disclosure",
    ):
        assert section in template, f"{section} is missing from the PR template"


def test_the_template_carries_the_machine_readable_diff_summary() -> None:
    template = TEMPLATE.read_text(encoding="utf-8")

    assert "```json" in template
    for key in ("changed_files", "tests_added", "net_lines", "simulated", "breaking"):
        assert f'"{key}"' in template


# --- False-positive control --------------------------------------------------


def test_claims_inside_fenced_code_blocks_are_ignored() -> None:
    body = (
        "## How this was verified\n\n"
        "```\n"
        "293 files already formatted\n"
        "162 source files\n"
        "touched /tmp/nonexistent.json and shipped.py\n"
        "```\n"
    )

    result = _truth(body)

    assert result.warnings == []


def test_fabrication_ignores_markdown_prose() -> None:
    lines = [
        ("docs/architecture/README.md", 82, "new TODO/FIXME/NotImplementedError/stub"),
        ("docs/architecture/README.md", 83, "and 'mock' returns are flagged"),
    ]

    assert check_fabrication(lines) == []


def test_fabrication_ignores_its_own_pattern_definitions() -> None:
    lines = [
        ("scripts/pr_guards.py", 387, 'r"\\b(?:TODO|FIXME)\\b|NotImplementedError"'),
        ("scripts/pr_guards.py", 425, 'and ("return" in text or "mock" in text)'),
    ]

    assert check_fabrication(lines) == []


def test_the_warning_comment_never_edits_an_unrelated_comment() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "--edit-last" not in workflow
    assert 'startswith("## PR guardrails")' in workflow


def test_the_warning_comment_is_removed_when_warnings_are_fixed() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "--method DELETE" in workflow
