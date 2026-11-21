"""Test the AI merge authorization and the check-suite gate it reads.

``pr_ai_authorize.py`` owns two things: the ``ai-merge-authorized`` label and
the CI verdict both merge workflows share. The gate is pinned against the
failure that merged #1100 -- a green legacy commit status standing in for a
check suite that had not reported yet (ADR 0009).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from pr_ai_authorize import (  # noqa: E402
    BLOCKING_CONCLUSIONS,
    CONTROL_CHECKS,
    LABEL,
    MANAGED_LABELS,
    compute_ai_merge_authorized,
    compute_ci_state,
)

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def check(name, conclusion="success", status="completed", app="github-actions"):
    """One check run as the check-runs API reports it."""
    run = {"name": name, "status": status, "conclusion": conclusion}
    if app is not None:
        run["app"] = {"slug": app}
    return run


def green_checks():
    return [
        check("CI green"),
        check("PR guardrails"),
        check("lint"),
        check("test (3.10)"),
        check("test (3.11)"),
        check("test (3.12)"),
        check("End-to-end"),
    ]


def base_facts(**overrides):
    facts = {
        "author": {"login": "alehar9320", "type": "User"},
        "branch": "fix/a-small-typo",
        "commits": [],
        "body": "",
        "files": [],
        "labels": ["ai-merge-safe", "ready-for-merge"],
        "state": "open",
        "draft": False,
        "base": {"ref": "main"},
        "checks": green_checks(),
    }
    facts.update(overrides)
    return facts


# ---------------------------------------------------------------------------
# Gate 1 — trust label ("ai-merge-safe")
# ---------------------------------------------------------------------------


def test_requires_ai_merge_safe():
    facts = base_facts(labels=["ready-for-merge"])
    assert compute_ai_merge_authorized(facts) == set()


def test_ai_merge_safe_satisfies_gate_one():
    assert compute_ai_merge_authorized(base_facts()) == {LABEL}


# ---------------------------------------------------------------------------
# Gate 2 — CI green (the head commit's check suite)
# ---------------------------------------------------------------------------


def test_requires_a_green_check_suite():
    checks = green_checks()
    checks[0] = check("CI green", conclusion="failure")
    assert compute_ai_merge_authorized(base_facts(checks=checks)) == set()


def test_a_green_check_suite_satisfies_gate_two():
    assert compute_ai_merge_authorized(base_facts()) == {LABEL}


@pytest.mark.parametrize("conclusion", sorted(BLOCKING_CONCLUSIONS))
def test_a_blocking_conclusion_on_a_required_check_removes_the_label(conclusion):
    checks = green_checks()
    checks[0] = check("CI green", conclusion=conclusion)
    assert compute_ai_merge_authorized(base_facts(checks=checks)) == set()


def test_a_failing_non_advisory_job_removes_the_label():
    checks = green_checks() + [check("CodeQL", conclusion="failure")]
    assert compute_ai_merge_authorized(base_facts(checks=checks)) == set()


def test_a_failing_advisory_job_does_not_block():
    checks = [
        check("CI green"),
        check("PR guardrails"),
        check("End-to-end", conclusion="failure"),
    ]
    facts = base_facts(checks=checks)
    assert compute_ci_state(facts)["state"] == "green"
    assert compute_ai_merge_authorized(facts) == {LABEL}


def test_the_advisory_failure_is_reported():
    checks = [
        check("CI green"),
        check("PR guardrails"),
        check("End-to-end", conclusion="failure"),
    ]
    assert compute_ci_state(base_facts(checks=checks))["advisory"] == ["End-to-end"]


def test_the_e2e_switch_turns_the_advisory_lane_into_a_gate(monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_E2E_BLOCKING", "true")
    checks = [
        check("CI green"),
        check("PR guardrails"),
        check("End-to-end", conclusion="failure"),
    ]
    state = compute_ci_state(base_facts(checks=checks))
    assert state["state"] == "red"
    assert "End-to-end" in state["blocking"]
    assert compute_ai_merge_authorized(base_facts(checks=checks)) == set()


def test_a_pending_check_is_not_green():
    checks = green_checks() + [check("studio", status="in_progress", conclusion="")]
    facts = base_facts(checks=checks)
    assert compute_ci_state(facts)["state"] == "pending"
    assert compute_ai_merge_authorized(facts) == set()


def test_a_missing_required_check_is_not_green():
    facts = base_facts(checks=[check("lint"), check("End-to-end")])
    state = compute_ci_state(facts)
    assert state["state"] == "pending"
    assert state["missing"] == ["CI green", "PR guardrails"]
    assert compute_ai_merge_authorized(facts) == set()


def test_the_legacy_combined_status_cannot_make_a_red_suite_green():
    """#1100: `.status` read success while every Actions check was still queued."""
    facts = base_facts(
        status="success",
        checks=[check("CI green", conclusion="failure")],
    )
    assert compute_ai_merge_authorized(facts) == set()


def test_a_cancelled_superseded_check_is_not_a_failure():
    """Label workflows cancel each other; a cancelled run is not a red test."""
    checks = green_checks() + [check("Label pull request", conclusion="cancelled")]
    assert compute_ci_state(base_facts(checks=checks))["state"] == "green"


def test_a_cancelled_required_check_is_not_green():
    """`CI green` must report success, not merely avoid reporting failure."""
    checks = green_checks()
    checks[0] = check("CI green", conclusion="cancelled")
    facts = base_facts(checks=checks)
    state = compute_ci_state(facts)
    assert state["state"] == "pending"
    assert state["unconfirmed"] == ["CI green"]
    assert compute_ai_merge_authorized(facts) == set()


def test_a_third_party_check_run_does_not_gate():
    """A vendor outage is not a failing test and is not a required check."""
    checks = [
        check("CI green"),
        check("PR guardrails"),
        check(
            "Workers Builds: agentic-odi",
            conclusion="failure",
            app="cloudflare-workers-and-pages",
        ),
    ]
    assert compute_ci_state(base_facts(checks=checks))["state"] == "green"


def test_the_control_jobs_do_not_judge_themselves():
    """The workflow that asks is a check run on the same head it is judging."""
    checks = green_checks() + [
        check("Label pull request", status="in_progress", conclusion=""),
        check("Auto-merge authorized PR", status="in_progress", conclusion=""),
    ]
    state = compute_ci_state(base_facts(checks=checks))
    assert state["state"] == "green"
    assert state["pending"] == []
    assert state["control"] == ["Auto-merge authorized PR", "Label pull request"]
    assert compute_ai_merge_authorized(base_facts(checks=checks)) == {LABEL}


def test_a_failed_control_run_does_not_block_a_merge():
    """A control run's failure is its own bug, not evidence about the change."""
    checks = green_checks() + [
        check("Auto-merge authorized PR", conclusion="failure"),
        check("Label pull request", conclusion="cancelled"),
    ]
    assert compute_ci_state(base_facts(checks=checks))["state"] == "green"


def _job_names(path: Path) -> set[str]:
    """The ``name:`` of every job in a workflow file."""
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("    name: "):
            names.add(line.split("name: ", 1)[1].strip())
    return names


def test_the_control_check_names_are_the_workflow_job_names():
    """A renamed job would count its own run and never turn green again."""
    names = _job_names(WORKFLOWS / "pr-ai-authorize.yml") | _job_names(
        WORKFLOWS / "pr-ai-merge-act.yml"
    )
    assert CONTROL_CHECKS <= names, (
        f"the verdict ignores {sorted(CONTROL_CHECKS)}, but the workflows name "
        f"{sorted(names)}; the gate would count its own running job"
    )


def test_an_unrecognised_conclusion_is_not_green():
    checks = [check("CI green"), check("PR guardrails"), check("lint", conclusion="")]
    assert compute_ci_state(base_facts(checks=checks))["state"] == "pending"


def test_uppercase_conclusions_are_accepted():
    checks = [
        check("CI green", conclusion="SUCCESS"),
        check("PR guardrails", conclusion="SUCCESS"),
    ]
    assert compute_ai_merge_authorized(base_facts(checks=checks)) == {LABEL}


# ---------------------------------------------------------------------------
# Gate 3 — no merge conflicts ("ready-for-merge")
# ---------------------------------------------------------------------------


def test_requires_ready_for_merge():
    assert compute_ai_merge_authorized(base_facts(labels=["ai-merge-safe"])) == set()


# ---------------------------------------------------------------------------
# Gate 4 — hygiene
# ---------------------------------------------------------------------------


def test_closed_pr_removes_label():
    assert compute_ai_merge_authorized(base_facts(state="closed")) == set()


def test_draft_pr_removes_label():
    assert compute_ai_merge_authorized(base_facts(draft=True)) == set()


def test_pr_not_targeting_main_removes_label():
    assert compute_ai_merge_authorized(base_facts(base={"ref": "feature/x"})) == set()


def test_pr_not_targeting_main_removes_label_string_base():
    """The workflow passes ``base`` as a plain string (``baseRefName``)."""
    assert compute_ai_merge_authorized(base_facts(base="feature/x")) == set()


def test_missing_checks_are_fail_closed():
    """A missing CI signal must never allow the label."""
    facts = base_facts()
    del facts["checks"]
    assert compute_ai_merge_authorized(facts) == set()


def test_missing_state_is_fail_closed():
    facts = base_facts()
    del facts["state"]
    assert compute_ai_merge_authorized(facts) == set()


def test_missing_base_is_fail_closed():
    facts = base_facts()
    del facts["base"]
    assert compute_ai_merge_authorized(facts) == set()


# ---------------------------------------------------------------------------
# All gates pass
# ---------------------------------------------------------------------------


def test_all_gates_pass_applies_label():
    assert compute_ai_merge_authorized(base_facts()) == {LABEL}


# ---------------------------------------------------------------------------
# Tolerances
# ---------------------------------------------------------------------------


def test_missing_keys_are_fail_closed_not_errors():
    assert compute_ai_merge_authorized({}) == set()


def test_managed_label_owns_only_ai_merge_authorized():
    assert MANAGED_LABELS == frozenset({LABEL})


# ---------------------------------------------------------------------------
# The CLI both workflows call
# ---------------------------------------------------------------------------


def _run(*arguments, **kwargs):
    script = Path(__file__).resolve().parents[2] / "scripts" / "pr_ai_authorize.py"
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        capture_output=True,
        text=True,
        check=False,
        **kwargs,
    )


def test_the_cli_prints_nothing_when_no_gate_passes():
    facts = base_facts(labels=["ready-for-merge"])
    result = _run(input=json.dumps(facts))
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_the_cli_prints_the_label_when_all_gates_pass():
    result = _run(input=json.dumps(base_facts()))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == LABEL


def test_the_cli_prints_the_ci_state_for_the_merge_workflow():
    result = _run("--ci-state", input=json.dumps(base_facts()))
    assert result.returncode == 0, result.stderr
    verdict = json.loads(result.stdout)
    assert verdict["state"] == "green"
    assert verdict["blocking"] == []
    assert verdict["missing"] == []


def test_the_ci_state_cli_reports_a_red_suite():
    checks = [check("CI green", conclusion="failure"), check("PR guardrails")]
    result = _run("--ci-state", input=json.dumps(base_facts(checks=checks)))
    assert result.returncode == 0, result.stderr
    verdict = json.loads(result.stdout)
    assert verdict["state"] == "red"
    assert verdict["blocking"] == ["CI green"]


def test_the_cli_fails_loudly_on_unreadable_input():
    result = _run(input="not json")
    assert result.returncode == 1
    assert "could not read" in result.stderr


def test_managed_cli_prints_only_ai_merge_authorized():
    result = _run("--managed")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == LABEL


def test_the_checkout_pins_the_base_ref_not_the_pull_request_head():
    """The gate reads only repo scripts, so it must not check out the head.

    The default ref for a ``pull_request`` event is the merge commit. When a
    branch carries a stray gitlink (mode 160000, no ``.gitmodules`` url),
    ``actions/checkout`` runs ``git submodule foreach`` while it strips its auth
    header and git exits 128, failing the step before any command runs.
    """
    workflow = yaml.safe_load((WORKFLOWS / "pr-ai-authorize.yml").read_text(encoding="utf-8"))
    checkouts = [
        step
        for step in workflow["jobs"]["labels"]["steps"]
        if (step.get("uses") or "").startswith("actions/checkout")
    ]
    assert checkouts, "the labeler runs scripts/pr_ai_authorize.py and needs a tree"
    for step in checkouts:
        assert step["with"]["ref"] == "${{ github.event.pull_request.base.ref || github.ref }}"
