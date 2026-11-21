"""The CI Label workflow: `ci-pending` while CI runs, and only that label."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ci_label import LABEL, MANAGED_LABELS, compute_ci_labels
from pr_labels import MANAGED_LABELS as STATIC_MANAGED_LABELS

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ci_label.py"


def labels(**overrides):
    """Build a minimal facts dict, overriding any key."""
    facts = {
        "is_draft": False,
        "mergeable": "MERGEABLE",
        "base_ref_name": "main",
        "review_decision": "",
        "reviews": [],
        "check_runs": [],
    }
    facts.update(overrides)
    return facts


def check(name="lint", status="COMPLETED", conclusion="SUCCESS"):
    return {"name": name, "status": status, "conclusion": conclusion}


def status_context(state):
    """A legacy commit status: it reports ``state`` and no ``status``."""
    return {"context": "ci/legacy", "state": state}


def run_script(*args, stdin=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_green_ci_applies_no_label():
    """A green PR belongs to ready-for-merge, which this workflow does not own."""
    assert compute_ci_labels(labels(check_runs=[check()])) == set()


def test_multiple_green_checks_apply_no_label():
    assert (
        compute_ci_labels(labels(check_runs=[check("lint"), check("test"), check("build")]))
        == set()
    )


def test_pending_ci_is_ci_pending():
    assert compute_ci_labels(labels(check_runs=[check("lint", status="IN_PROGRESS")])) == {LABEL}


def test_queued_ci_is_ci_pending():
    assert compute_ci_labels(labels(check_runs=[check("lint", status="QUEUED")])) == {LABEL}


def test_mixed_green_and_pending_is_ci_pending():
    assert compute_ci_labels(
        labels(check_runs=[check("lint"), check("test", status="IN_PROGRESS")])
    ) == {LABEL}


def test_no_checks_yet_has_nothing_to_report():
    assert compute_ci_labels(labels()) == set()


def test_completed_non_green_checks_are_not_pending():
    """Skipped or neutral checks will not change on their own, so nothing is in flight."""
    assert compute_ci_labels(labels(check_runs=[check("lint", conclusion="SKIPPED")])) == set()
    assert compute_ci_labels(labels(check_runs=[check("lint", conclusion="NEUTRAL")])) == set()


def test_a_failing_check_is_blocked():
    assert compute_ci_labels(labels(check_runs=[check("lint", conclusion="FAILURE")])) == set()


def test_a_cancelled_check_is_blocked():
    assert compute_ci_labels(labels(check_runs=[check("lint", conclusion="CANCELLED")])) == set()


def test_a_timed_out_check_is_blocked():
    assert compute_ci_labels(labels(check_runs=[check("lint", conclusion="TIMED_OUT")])) == set()


def test_a_failure_blocks_even_with_a_check_still_running():
    assert (
        compute_ci_labels(
            labels(
                check_runs=[
                    check("lint", conclusion="FAILURE"),
                    check("test", status="IN_PROGRESS"),
                ]
            )
        )
        == set()
    )


def test_a_draft_is_blocked_even_with_ci_running():
    assert (
        compute_ci_labels(labels(is_draft=True, check_runs=[check(status="IN_PROGRESS")])) == set()
    )


def test_conflicting_merge_is_blocked_even_with_ci_running():
    assert (
        compute_ci_labels(labels(mergeable="CONFLICTING", check_runs=[check(status="IN_PROGRESS")]))
        == set()
    )


def test_changes_requested_is_blocked_even_with_ci_running():
    assert (
        compute_ci_labels(
            labels(
                check_runs=[check(status="IN_PROGRESS")],
                reviews=[{"state": "CHANGES_REQUESTED"}],
            )
        )
        == set()
    )


def test_approved_review_does_not_block():
    assert compute_ci_labels(
        labels(check_runs=[check(status="IN_PROGRESS")], reviews=[{"state": "APPROVED"}])
    ) == {LABEL}


def test_commented_review_does_not_block():
    assert compute_ci_labels(
        labels(check_runs=[check(status="IN_PROGRESS")], reviews=[{"state": "COMMENTED"}])
    ) == {LABEL}


def test_unknown_mergeable_state_is_not_conflicting():
    assert compute_ci_labels(
        labels(mergeable="UNKNOWN", check_runs=[check(status="IN_PROGRESS")])
    ) == {LABEL}


def test_a_status_context_that_succeeded_is_not_pending():
    """A legacy status reports `state`; it must not read as an unfinished check."""
    assert compute_ci_labels(labels(check_runs=[status_context("SUCCESS")])) == set()


def test_a_pending_status_context_is_ci_pending():
    assert compute_ci_labels(labels(check_runs=[status_context("PENDING")])) == {LABEL}
    assert compute_ci_labels(labels(check_runs=[status_context("EXPECTED")])) == {LABEL}


def test_a_failed_status_context_is_blocked():
    assert compute_ci_labels(labels(check_runs=[status_context("FAILURE")])) == set()
    assert compute_ci_labels(labels(check_runs=[status_context("ERROR")])) == set()


def test_a_green_check_run_and_a_successful_status_context_apply_no_label():
    assert compute_ci_labels(labels(check_runs=[check(), status_context("SUCCESS")])) == set()


def test_a_non_main_base_is_left_alone():
    assert (
        compute_ci_labels(
            labels(base_ref_name="release/1.0", check_runs=[check(status="IN_PROGRESS")])
        )
        == set()
    )


def test_missing_keys_never_raise():
    assert compute_ci_labels({}) == set()
    assert compute_ci_labels({"is_draft": False}) == set()


def test_managed_labels_do_not_overlap_the_static_axes():
    """ci_label owns ci-pending; pr_labels owns the provenance/size/area axes."""
    assert not MANAGED_LABELS & STATIC_MANAGED_LABELS


def test_managed_labels_are_exactly_ci_pending():
    """ready-for-merge has one owner, the merge-conflict workflow, not this one."""
    assert MANAGED_LABELS == {LABEL}


def test_the_cli_runs_as_a_script():
    """The workflow invokes this file directly, so __main__ must call main()."""
    managed = run_script("--managed")
    assert managed.returncode == 0, managed.stderr
    assert set(managed.stdout.splitlines()) == MANAGED_LABELS

    computed = run_script(stdin=json.dumps(labels(check_runs=[check(status="IN_PROGRESS")])))
    assert computed.returncode == 0, computed.stderr
    assert set(computed.stdout.splitlines()) == {LABEL}

    quiet = run_script(stdin=json.dumps(labels(check_runs=[check()])))
    assert quiet.returncode == 0, quiet.stderr
    assert quiet.stdout.strip() == ""


def test_the_cli_fails_loudly_on_unreadable_input():
    result = run_script(stdin="not json")
    assert result.returncode == 1
    assert "could not read" in result.stderr


def test_the_cli_rejects_facts_that_are_not_an_object():
    result = run_script(stdin=json.dumps([1, 2, 3]))
    assert result.returncode == 1
    assert "must be a JSON object" in result.stderr


def test_the_cli_accepts_a_facts_file(tmp_path):
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(
        json.dumps(labels(check_runs=[check("test", status="IN_PROGRESS")])), encoding="utf-8"
    )

    result = run_script("--facts", str(facts_file))
    assert result.returncode == 0, result.stderr
    assert set(result.stdout.splitlines()) == {LABEL}
