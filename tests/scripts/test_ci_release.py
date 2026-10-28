from __future__ import annotations

from ci_release import environment_for, release_for


def test_a_tag_build_names_the_tag():
    assert release_for("refs/tags/v1.2.3", "0123456789abcdef") == "v1.2.3"


def test_a_branch_build_names_the_short_sha():
    assert release_for("refs/heads/main", "0123456789abcdef") == "0123456789ab"


def test_a_run_without_git_context_is_local():
    assert release_for("", "") == "local"


def test_a_pull_request_is_a_preview():
    assert environment_for("pull_request") == "preview"


def test_a_push_is_production():
    assert environment_for("push") == "production"


def test_any_other_trigger_is_ci():
    assert environment_for("workflow_dispatch") == "ci"
