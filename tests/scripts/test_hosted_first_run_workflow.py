"""The hosted probe has a schedule, a commit to compare against, and no vote.

`ci-green` must not go red because production is broken — a visitor-facing failure
belongs to the deploy, not to the pull request that happened to be sharing the
branch. So the job runs on `schedule` and `workflow_dispatch` only, and sits
outside `ci-green`'s `needs:` beside `pr-body` and `updater-e2e`. Its own failure is
the alarm, and the alarm has to carry the output it printed.

These locks also keep the wiring honest in the two ways the issue was born from: a
run against a preview URL (never a pass) and a run that does not say which commit it
believes is deployed (the state that let two merged PRs strand on a feature branch).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"


def _text() -> str:
    return CI.read_text(encoding="utf-8")


def _job(name: str) -> str:
    text = _text()
    start = text.index(f"\n  {name}:\n")
    end = re.search(r"\n  [a-z][a-z0-9-]*:\n", text[start + 1 :])
    assert end is not None
    return text[start : start + 1 + end.start()]


def test_the_probe_runs_on_a_schedule_and_by_hand() -> None:
    job = _job("hosted-first-run")
    assert "github.event_name == 'schedule'" in job
    assert "github.event_name == 'workflow_dispatch'" in job


def test_the_job_asks_the_deployed_host_about_this_commit() -> None:
    job = _job("hosted-first-run")
    assert "bash scripts/verify-hosted-first-run.sh" in job
    # A run that cannot say which commit it expects cannot detect a stranded merge.
    assert '--commit "$(git rev-parse HEAD)"' in job
    # The production URL is the script's default, so the job must not override it
    # with anything a preview could be.
    assert "--base-url" not in job


def test_the_job_is_outside_the_ci_green_vote() -> None:
    needs = re.search(r"  ci-green:\n(?:.*\n)*?    needs: \[(.*?)\]", _text())
    assert needs is not None
    required = {name.strip() for name in needs.group(1).split(",")}
    assert "hosted-first-run" not in required
    # The two other jobs that judge the world outside a pull request stay out too.
    assert {"pr-body", "updater-e2e"}.isdisjoint(required)


def test_the_failure_is_loud_and_keeps_its_output() -> None:
    job = _job("hosted-first-run")
    assert "::error::" in job, "a failure must announce itself, not just exit"
    assert "if: failure()" in job
    assert "hosted-first-run-log" in job


def test_the_schedule_comment_no_longer_claims_a_single_job() -> None:
    header = _text().split("jobs:", 1)[0]
    assert "only the updater-e2e job" not in header
    assert "hosted-first-run" in header, "the schedule comment must name both reactors"
