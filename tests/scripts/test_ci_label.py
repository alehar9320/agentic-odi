from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ci_label import MANAGED_LABELS, compute_ci_labels
from pr_labels import MANAGED_LABELS as STATIC_MANAGED_LABELS


def labels(**overrides):
    """Build a minimal facts dict, overriding any key."""
    facts = {
        "is_draft": False,
        "mergeable": "MERGEABLE",
        "review_decision": "",
        "reviews": [],
        "check_runs": [],
    }
    facts.update(overrides)
    return facts


def check(name="lint", status="COMPLETED", conclusion="SUCCESS"):
    return {"name": name, "status": status, "conclusion": conclusion}


def test_all_green_ci_means_ready_for_merge():
    assert compute_ci_labels(labels(check_runs=[check()])) == {"ready-for-merge"}


def test_multiple_green_checks_are_ready_for_merge():
    assert compute_ci_labels(labels(check_runs=[check("lint"), check("test"), check("build")])) == {
        "ready-for-merge"
    }


def test_pending_ci_means_ci_pending():
    assert compute_ci_labels(labels(check_runs=[check("lint", status="IN_PROGRESS")])) == {
        "ci-pending"
    }


def test_queued_ci_means_ci_pending():
    assert compute_ci_labels(labels(check_runs=[check("lint", status="QUEUED")])) == {"ci-pending"}


def test_mixed_green_and_pending_means_ci_pending():
    assert compute_ci_labels(
        labels(check_runs=[check("lint"), check("test", status="IN_PROGRESS")])
    ) == {"ci-pending"}


def test_no_checks_yet_is_blocked():
    assert compute_ci_labels(labels()) == set()


def test_all_skipped_checks_is_ci_pending():
    """Checks exist but none is green, and nothing blocks: ci-pending."""
    assert compute_ci_labels(labels(check_runs=[check("lint", conclusion="SKIPPED")])) == {
        "ci-pending"
    }


def test_a_failing_check_is_blocked():
    assert compute_ci_labels(labels(check_runs=[check("lint", conclusion="FAILURE")])) == set()


def test_a_cancelled_check_is_blocked():
    assert compute_ci_labels(labels(check_runs=[check("lint", conclusion="CANCELLED")])) == set()


def test_a_draft_is_blocked_even_with_green_ci():
    assert compute_ci_labels(labels(is_draft=True, check_runs=[check()])) == set()


def test_conflicting_merge_is_blocked_even_with_green_ci():
    assert compute_ci_labels(labels(mergeable="CONFLICTING", check_runs=[check()])) == set()


def test_changes_requested_is_blocked_even_with_green_ci():
    assert (
        compute_ci_labels(
            labels(
                check_runs=[check()],
                reviews=[{"state": "CHANGES_REQUESTED"}],
            )
        )
        == set()
    )


def test_approved_review_does_not_block():
    assert compute_ci_labels(labels(check_runs=[check()], reviews=[{"state": "APPROVED"}])) == {
        "ready-for-merge"
    }


def test_commented_review_does_not_block():
    assert compute_ci_labels(labels(check_runs=[check()], reviews=[{"state": "COMMENTED"}])) == {
        "ready-for-merge"
    }


def test_review_decision_approved_does_not_override_check_state():
    """review_decision is advisory; the check runs decide readiness."""
    assert compute_ci_labels(
        labels(review_decision="APPROVED", check_runs=[check(status="IN_PROGRESS")])
    ) == {"ci-pending"}


def test_unknown_mergeable_state_is_not_conflicting():
    assert compute_ci_labels(labels(mergeable="UNKNOWN", check_runs=[check()])) == {
        "ready-for-merge"
    }


def test_missing_keys_never_raise():
    assert compute_ci_labels({}) == set()
    assert compute_ci_labels({"is_draft": False}) == set()


def test_managed_labels_do_not_overlap_the_static_axes():
    """ci_label owns ci-pending/ready-for-merge; pr_labels owns everything else."""
    assert not MANAGED_LABELS & STATIC_MANAGED_LABELS


def test_managed_labels_are_exactly_the_two_merge_state_labels():
    assert MANAGED_LABELS == {"ci-pending", "ready-for-merge"}


def test_the_cli_runs_as_a_script():
    """The workflow invokes this file directly, so __main__ must call main()."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "ci_label.py"
    managed = subprocess.run(
        [sys.executable, str(script), "--managed"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert managed.returncode == 0, managed.stderr
    assert set(managed.stdout.splitlines()) == MANAGED_LABELS

    computed = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(labels(check_runs=[check()])),
        capture_output=True,
        text=True,
        check=False,
    )
    assert computed.returncode == 0, computed.stderr
    assert set(computed.stdout.splitlines()) == {"ready-for-merge"}


def test_the_cli_fails_loudly_on_unreadable_input():
    script = Path(__file__).resolve().parents[2] / "scripts" / "ci_label.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "could not read" in result.stderr


def test_the_cli_accepts_a_facts_file(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts" / "ci_label.py"
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(
        json.dumps(labels(check_runs=[check("test", status="IN_PROGRESS")])), encoding="utf-8"
    )

    result = subprocess.run(
        [sys.executable, str(script), "--facts", str(facts_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert set(result.stdout.splitlines()) == {"ci-pending"}
